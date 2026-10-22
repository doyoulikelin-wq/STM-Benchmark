"""Adversarial evidence-gate checks; fixtures are synthetic, never STM data."""
from __future__ import annotations

import copy
import unittest

import numpy as np

from stm_bench.metrics import (
    THRESHOLDS,
    choose_roi,
    frame_digest,
    image_quality,
    repeatability,
    same_context,
    stability,
)


def good_frame(seed=1, acquisition_id=None):
    rng = np.random.default_rng(seed)
    y, x = np.indices((64, 64), dtype=float)
    z = 30e-9 + 20e-12 * np.sin(x * .37) + 15e-12 * np.cos(y * .41)
    return {
        "id": acquisition_id or f"synthetic-fixture-{seed}",
        "backend": "synthetic",
        "kind": "detail",
        "fresh": True,
        "lifecycle": [1, 1, 0],
        "elapsed_s": 3.0,
        "feedback_on": True,
        "setpoint_A": 5e-9,
        "z_range_m": 1.5e-6,
        "p_gain_m": 35e-12,
        "time_constant_s": .001,
        "line_time_s": .2,
        "frame": {
            "cx_m": 2e-9, "cy_m": -1e-9,
            "width_m": 5e-9, "height_m": 5e-9, "angle_deg": 30.,
        },
        "z_forward": z + rng.normal(0, .03e-12, z.shape),
        "z_backward": z + rng.normal(0, .03e-12, z.shape),
        "current_forward": 5e-9 + rng.normal(0, .01e-9, z.shape),
        "current_backward": 5e-9 + rng.normal(0, .01e-9, z.shape),
    }


def good_window(seed=1):
    rng = np.random.default_rng(seed)
    return {
        "current_A": (5e-9 + rng.normal(0, .01e-9, 32)).tolist(),
        "z_m": (30e-9 + rng.normal(0, .01e-12, 32)).tolist(),
        "setpoint_A": 5e-9,
        "z_range_m": 1.5e-6,
        "dt_s": .1,
        "feedback_on": True,
    }


class StabilityEvidenceTests(unittest.TestCase):
    def test_complete_window_is_stable(self):
        result = stability(good_window())
        self.assertTrue(result["valid"])
        self.assertTrue(result["stable"])
        self.assertFalse(result["protection_triggered"])

    def test_incomplete_window_cannot_be_stable(self):
        for field, value in (
            ("current_A", []), ("current_A", [5e-9] * 15),
            ("current_A", [[5e-9] * 32]), ("z_m", [30e-9] * 31),
            ("z_m", [float("nan")] * 32),
            ("dt_s", 0), ("dt_s", -1), ("dt_s", float("inf")),
            ("setpoint_A", 0), ("setpoint_A", float("nan")),
            ("z_range_m", -1),
        ):
            with self.subTest(field=field, value=value):
                window = good_window()
                window[field] = value
                result = stability(window)
                self.assertFalse(result["valid"])
                self.assertFalse(result["stable"])

    def test_feedback_off_and_large_drift_are_not_stable(self):
        window = good_window()
        window["feedback_on"] = False
        self.assertFalse(stability(window)["stable"])
        window = good_window()
        window["z_m"] = (30e-9 + np.arange(32) * 1e-9).tolist()
        self.assertFalse(stability(window)["stable"])

    def test_positive_and_negative_current_protection(self):
        for sign in (-1, 1):
            with self.subTest(sign=sign):
                window = good_window()
                window["current_A"][-1] = sign * THRESHOLDS["absolute_current_limit_A"]
                result = stability(window)
                self.assertTrue(result["protection_triggered"])
                self.assertFalse(result["stable"])

    def test_incomplete_evidence_must_not_mask_known_overcurrent(self):
        for damage in ("nan_z", "nan_current", "short_z", "bad_dt", "bad_setpoint"):
            with self.subTest(damage=damage):
                window = good_window()
                window["current_A"][-1] = -2e-6
                if damage == "nan_z":
                    window["z_m"][0] = float("nan")
                elif damage == "nan_current":
                    window["current_A"][0] = float("nan")
                elif damage == "short_z":
                    window["z_m"] = window["z_m"][:-1]
                elif damage == "bad_dt":
                    window["dt_s"] = 0
                else:
                    window["setpoint_A"] = 0
                result = stability(window)
                self.assertFalse(result["stable"])
                self.assertTrue(result["protection_triggered"])


class ImageEvidenceTests(unittest.TestCase):
    def test_complete_numeric_fixture_and_scientific_scope(self):
        result = image_quality(good_frame())
        self.assertTrue(result["valid"])
        self.assertTrue(result["acceptable"])
        self.assertEqual(result["label"], "good")
        self.assertEqual(result["scientific_validity"], "not_assessed")

    def test_nonfinite_missing_and_mismatched_channel(self):
        for damage in ("nan", "inf", "missing", "short", "one_dimensional", "too_small"):
            with self.subTest(damage=damage):
                frame = good_frame()
                if damage in ("nan", "inf"):
                    frame["z_forward"][0, 0] = float(damage)
                elif damage == "missing":
                    del frame["current_backward"]
                elif damage == "short":
                    frame["current_backward"] = frame["current_backward"][:-1]
                elif damage == "one_dimensional":
                    frame["z_forward"] = frame["z_forward"].ravel()
                else:
                    for key in ("z_forward", "z_backward", "current_forward", "current_backward"):
                        frame[key] = frame[key][:8, :8]
                result = image_quality(frame)
                self.assertFalse(result["valid"])
                self.assertFalse(result["acceptable"])

    def test_freshness_lifecycle_and_normalization_required(self):
        for field, value in (
            ("fresh", False), ("id", ""), ("lifecycle", []),
            ("lifecycle", [0, 0]), ("lifecycle", [1, 1]),
            ("lifecycle", [1, 7, 0]), ("elapsed_s", 0),
            ("elapsed_s", -1), ("elapsed_s", float("inf")),
            ("setpoint_A", 0), ("setpoint_A", -5e-9),
            ("setpoint_A", float("inf")), ("z_range_m", float("nan")),
        ):
            with self.subTest(field=field, value=value):
                frame = good_frame()
                frame[field] = value
                result = image_quality(frame)
                self.assertFalse(result["valid"])
                self.assertFalse(result["acceptable"])

    def test_constant_z_and_common_plane_are_not_structure(self):
        y, x = np.indices((64, 64), dtype=float)
        for z in (np.full((64, 64), 30e-9), 30e-9 + x * 2e-12 + y * 5e-12):
            with self.subTest(plane_span=float(np.ptp(z))):
                frame = good_frame()
                frame["z_forward"] = z.copy()
                frame["z_backward"] = z.copy()
                result = image_quality(frame)
                self.assertFalse(result["acceptable"])
                self.assertEqual(result["label"], "flat")

    def test_opposite_structure_and_z_rail_are_rejected(self):
        frame = good_frame()
        frame["z_backward"] = -frame["z_forward"]
        self.assertFalse(image_quality(frame)["acceptable"])
        frame = good_frame()
        frame["z_forward"] += 1e-6
        self.assertEqual(image_quality(frame)["label"], "saturated")

    def test_incomplete_frame_must_not_mask_known_overcurrent(self):
        for damage in ("nan_z", "nan_current", "missing_z", "short", "stale", "bad_setpoint"):
            with self.subTest(damage=damage):
                frame = good_frame()
                frame["current_forward"][1, 1] = -2e-6
                if damage == "nan_z":
                    frame["z_backward"][0, 0] = float("nan")
                elif damage == "nan_current":
                    frame["current_forward"][0, 0] = float("nan")
                elif damage == "missing_z":
                    del frame["z_backward"]
                elif damage == "short":
                    frame["current_backward"] = frame["current_backward"][:-1]
                elif damage == "stale":
                    frame["fresh"] = False
                else:
                    frame["setpoint_A"] = 0
                result = image_quality(frame)
                self.assertFalse(result["acceptable"])
                self.assertTrue(result["protection_triggered"])


class ConfirmationAndROITests(unittest.TestCase):
    def test_two_distinct_same_context_scans_confirm(self):
        result = repeatability(good_frame(1), good_frame(2))
        self.assertTrue(result["confirmed"])
        self.assertGreater(result["correlation"], .99)

    def test_renamed_cached_arrays_do_not_confirm(self):
        first = good_frame()
        second = copy.deepcopy(first)
        second["id"] = "renamed-cache"
        self.assertEqual(frame_digest(first), frame_digest(second))
        self.assertFalse(repeatability(first, second)["confirmed"])

    def test_reused_acquisition_id_does_not_confirm(self):
        self.assertFalse(repeatability(good_frame(1, "same-id"), good_frame(2, "same-id"))["confirmed"])

    def test_missing_required_context_cannot_confirm(self):
        for key in ("frame", "setpoint_A", "z_range_m", "p_gain_m", "time_constant_s",
                    "line_time_s", "feedback_on", "backend"):
            with self.subTest(key=key):
                first, second = good_frame(1), good_frame(2)
                del first[key]
                del second[key]
                self.assertFalse(same_context(first, second))
                self.assertFalse(repeatability(first, second)["confirmed"])

    def test_changed_context_cannot_confirm(self):
        changes = {
            "setpoint_A": 6e-9, "z_range_m": 2e-6,
            "p_gain_m": 40e-12, "time_constant_s": .002, "line_time_s": .25,
            "feedback_on": False, "backend": "nanonis_demo",
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                first, second = good_frame(1), good_frame(2)
                second[key] = value
                self.assertFalse(same_context(first, second))
                self.assertFalse(repeatability(first, second)["confirmed"])
        for key in ("cx_m", "cy_m", "width_m", "height_m", "angle_deg"):
            with self.subTest(frame_field=key):
                first, second = good_frame(1), good_frame(2)
                second["frame"][key] += 1. if key == "angle_deg" else 1e-9
                self.assertFalse(repeatability(first, second)["confirmed"])

    def test_matching_but_invalid_controller_context_is_rejected(self):
        for key in ("setpoint_A", "z_range_m", "p_gain_m", "time_constant_s", "line_time_s"):
            for value in (float("nan"), float("inf"), -1, 0, None, "invalid"):
                with self.subTest(key=key, value=value):
                    first, second = good_frame(1), good_frame(2)
                    first[key] = second[key] = value
                    self.assertFalse(same_context(first, second))
                    self.assertFalse(repeatability(first, second)["confirmed"])

    def test_matching_but_incomplete_or_invalid_geometry_is_rejected(self):
        for frame_value in (
            {}, None, {"cx_m": 0},
            {"cx_m": 0, "cy_m": 0, "width_m": -1e-9, "height_m": 1e-9, "angle_deg": 0},
            {"cx_m": 0, "cy_m": 0, "width_m": 1e-9, "height_m": 0, "angle_deg": 0},
            {"cx_m": 0, "cy_m": 0, "width_m": 1e-9, "height_m": 1e-9, "angle_deg": float("inf")},
        ):
            with self.subTest(frame=frame_value):
                first, second = good_frame(1), good_frame(2)
                first["frame"] = copy.deepcopy(frame_value)
                second["frame"] = copy.deepcopy(frame_value)
                self.assertFalse(same_context(first, second))
                self.assertFalse(repeatability(first, second)["confirmed"])

    def test_selected_roi_is_interior_and_reproducible(self):
        frame = good_frame()
        roi = choose_roi(frame)
        self.assertEqual(roi, choose_roi(frame))
        self.assertGreaterEqual(roi["size"], .15)
        self.assertLessEqual(roi["size"], .5)
        for axis in ("x", "y"):
            self.assertGreaterEqual(roi[axis] - roi["size"] / 2, 0)
            self.assertLessEqual(roi[axis] + roi["size"] / 2, 1)

    def test_invalid_survey_cannot_supply_roi(self):
        frame = good_frame()
        frame["fresh"] = False
        with self.assertRaises(ValueError):
            choose_roi(frame)


if __name__ == "__main__":
    unittest.main()
