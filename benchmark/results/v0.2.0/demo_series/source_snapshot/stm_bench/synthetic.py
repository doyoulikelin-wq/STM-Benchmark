"""Seeded software task generator; deliberately not a calibrated STM simulator.

Coordinates are physical metres. Array columns increase along the rotated frame
x axis and rows along its rotated y axis. Both scan directions are returned in
this same orientation. No scenario name or latent surface state is exposed by
the instrument-shaped API.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

import numpy as np


SCENARIOS = (
    "nominal", "noisy", "drift", "double_tip", "no_tunnel",
    "current_spike", "scan_timeout", "flat", "stale_frame",
)


class SyntheticBackend:
    """Independent RNG streams keep observation and image draws reproducible."""

    backend = "synthetic"
    RANGES = {
        "p_gain_m": (10e-12, 160e-12),
        "time_constant_s": (0.0005, 0.02),
        "line_time_s": (0.01, 0.5),
        "setpoint_A": (0.05e-9, 5e-9),
    }

    def __init__(self, pixels: int = 64):
        if not isinstance(pixels, int) or isinstance(pixels, bool) or not 16 <= pixels <= 256:
            raise ValueError("pixels must be an integer from 16 to 256")
        self.pixels = pixels
        self._ready = False
        self._closed = False

    def reset(self, seed: int = 0, scenario: str = "nominal") -> dict:
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown synthetic scenario: {scenario}")
        if not isinstance(seed, (int, np.integer)) or isinstance(seed, bool) or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        self._scenario = scenario
        self._seed = int(seed)
        streams = np.random.SeedSequence(self._seed).spawn(3)
        self._surface_rng, self._signal_rng, self._scan_rng = [np.random.default_rng(s) for s in streams]
        self._phase = self._surface_rng.uniform(0, 2 * np.pi, 3)
        self._defects = self._surface_rng.uniform(-10e-9, 10e-9, (7, 2))
        self._defect_sizes = self._surface_rng.uniform(0.45e-9, 1.1e-9, 7)
        self._state = {
            "backend": self.backend,
            "feedback_on": False,
            "setpoint_A": 1e-9,
            "p_gain_m": 40e-12,
            "time_constant_s": 0.004,
            "line_time_s": 0.128,
            "z_range_m": 1.5e-6,
            "frame": {"cx_m": 0.0, "cy_m": 0.0, "width_m": 24e-9,
                      "height_m": 24e-9, "angle_deg": 0.0},
        }
        if scenario == "noisy":
            self._state.update(p_gain_m=120e-12, time_constant_s=0.001, line_time_s=0.016)
        self._initial = deepcopy(self._state)
        self._approached = False
        self._scan_number = self._sample_number = 0
        self._clock_s = 0.0
        self._last_scan = None
        self._survey_frame = None
        self._ready, self._closed = True, False
        self._cleanup = None
        return self.snapshot()

    def _check_ready(self):
        if not self._ready or self._closed:
            raise RuntimeError("Backend requires reset before use")

    def snapshot(self) -> dict:
        self._check_ready()
        return deepcopy(self._state)

    def approach(self) -> dict:
        self._check_ready()
        if self._scenario == "no_tunnel":
            self._clock_s += 3.0
            return {"backend": self.backend, "completed": False, "method": "bounded_synthetic_approach",
                    "elapsed_s": 3.0, "reason": "tunneling_not_detected", "feedback_on": False,
                    "samples_A": [0.0, 0.0, 0.0, 0.0], "attempts": 4}
        self._approached = True
        self._state["feedback_on"] = True
        self._clock_s += 0.8
        sp = self._state["setpoint_A"]
        return {"backend": self.backend, "completed": True, "method": "bounded_synthetic_approach",
                "elapsed_s": 0.8, "feedback_on": True, "attempts": 4,
                "samples_A": [sp * v for v in (0.001, 0.04, 0.48, 1.0)]}

    def configure(self, params: dict) -> dict:
        self._check_ready()
        if not isinstance(params, dict) or not params or set(params) - self.RANGES.keys():
            raise ValueError("Only nonempty bounded controller settings are accepted")
        checked = {}
        for key, value in params.items():
            if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
                raise ValueError(f"Invalid numerical setting {key}")
            value = float(value)
            low, high = self.RANGES[key]
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"Setting outside synthetic task bounds: {key}")
            checked[key] = value
        self._state.update(checked)
        return self.snapshot()

    def _control_error(self) -> float:
        s = self._state
        # A transparent engineering task landscape, not a physical transfer function.
        return (max(0.0, s["p_gain_m"] / 40e-12 - 1) * 0.14
                + max(0.0, 0.002 / s["time_constant_s"] - 1) * 0.12
                + max(0.0, 0.08 / s["line_time_s"] - 1) * 0.08
                + max(0.0, 20e-12 / s["p_gain_m"] - 1) * 0.08)

    def sample(self, count: int = 32) -> dict:
        self._check_ready()
        if not isinstance(count, int) or isinstance(count, bool) or not 8 <= count <= 4096:
            raise ValueError("sample count must be an integer from 8 to 4096")
        self._sample_number += 1
        dt = 0.02
        times = self._clock_s + dt * np.arange(count)
        self._clock_s += count * dt
        sp = self._state["setpoint_A"]
        error = self._control_error()
        active = self._approached and self._state["feedback_on"]
        noise = self._signal_rng.normal(size=count)
        current = sp * (1 + 0.08 * error + (0.025 + error) * noise) if active else sp * 1e-4 * noise
        z = 25e-9 + (0.8e-12 + error * 1e-9) * self._signal_rng.normal(size=count)
        if self._scenario == "drift":
            z = z + times * 0.15e-9
        if self._scenario == "current_spike" and active:
            current[count // 2] = 2e-6
        return {"backend": self.backend, "window_id": f"window-{self._sample_number:06d}",
                "current_A": current.tolist(), "z_m": z.tolist(), "dt_s": dt,
                "started_s": float(times[0]), "ended_s": float(times[-1]),
                "feedback_on": self._state["feedback_on"], "setpoint_A": sp,
                "z_range_m": self._state["z_range_m"]}

    def _coordinates(self, frame: dict) -> tuple[np.ndarray, np.ndarray]:
        col = (np.arange(self.pixels) + 0.5) / self.pixels - 0.5
        row = (np.arange(self.pixels) + 0.5) / self.pixels - 0.5
        x, y = np.meshgrid(col * frame["width_m"], row * frame["height_m"])
        angle = math.radians(frame["angle_deg"])
        return (frame["cx_m"] + x * math.cos(angle) - y * math.sin(angle),
                frame["cy_m"] + x * math.sin(angle) + y * math.cos(angle))

    def _surface(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ph = self._phase
        z = (13e-12 * np.sin(2 * np.pi * x / 1.1e-9 + ph[0])
             * np.cos(2 * np.pi * y / 1.3e-9 + ph[1])
             + 7e-12 * np.sin(2 * np.pi * (x + y) / 2.4e-9 + ph[2]))
        z += 45e-12 * np.tanh((x + 0.4 * y - 3e-9) / 0.3e-9)
        defects = np.zeros_like(z)
        for (cx, cy), size in zip(self._defects, self._defect_sizes):
            spot = np.exp(-((x - cx)**2 + (y - cy)**2) / (2 * size**2))
            z -= 65e-12 * spot
            defects += spot
        return z, np.clip(defects, 0, 2)

    def scan(self, kind: str) -> dict:
        self._check_ready()
        if kind not in ("survey", "detail"):
            raise ValueError("scan kind must be survey or detail")
        if not self._approached or not self._state["feedback_on"]:
            raise RuntimeError("Tunneling feedback is not established")
        if self._scenario == "scan_timeout":
            self._clock_s += 30.0
            raise TimeoutError("Scan did not complete before the 30 s synthetic deadline")
        self._scan_number += 1
        if self._scenario == "stale_frame" and self._last_scan is not None:
            stale = deepcopy(self._last_scan)
            stale.update(kind=kind, fresh=False, lifecycle=[0], elapsed_s=0.0)
            return stale
        frame = deepcopy(self._state["frame"])
        x, y = self._coordinates(frame)
        if self._scenario == "drift":
            x = x + self._scan_number * 0.45e-9
        texture, defects = self._surface(x, y)
        error = self._control_error()
        noise_scale = 0.45e-12 + error * 80e-12
        zf = texture + self._scan_rng.normal(0, noise_scale, texture.shape)
        zb = texture + self._scan_rng.normal(0, noise_scale, texture.shape)
        if self._scenario == "double_tip":
            left, _ = self._surface(x + 0.65e-9, y + 0.3e-9)
            right, _ = self._surface(x - 1.1e-9, y + 0.6e-9)
            zf += 1.8 * left
            zb += 1.8 * right
            zb += self._scan_rng.normal(0, 20e-12, texture.shape)
        if self._scenario == "flat":
            zf = np.zeros_like(texture)
            zb = np.zeros_like(texture)
        sp = self._state["setpoint_A"]
        # Defects are spatially coupled to tracking error, so ROI selection changes data.
        sigma = 0.025 + error + 0.018 * defects
        cf = sp * (1 + self._scan_rng.normal(size=texture.shape) * sigma)
        cb = sp * (1 + self._scan_rng.normal(size=texture.shape) * sigma)
        if self._scenario == "current_spike":
            cf[self.pixels // 3, self.pixels // 2] = 2e-6
        elapsed = 2 * self.pixels * self._state["line_time_s"]
        self._clock_s += elapsed
        result = {**self.snapshot(), "id": f"scan-{self._scan_number:06d}", "backend": self.backend,
                  "kind": kind, "z_forward": zf, "z_backward": zb,
                  "current_forward": cf, "current_backward": cb, "frame": frame,
                  "setpoint_A": sp, "z_range_m": self._state["z_range_m"],
                  "fresh": True, "lifecycle": [1, 1, 0], "elapsed_s": elapsed,
                  "acquisition": {"source": "synthetic", "frame_orientation": "increasing_row_is_positive_frame_y",
                                  "configuration": self.snapshot()}}
        self._last_scan = deepcopy(result)
        if kind == "survey":
            self._survey_frame = frame
        return result

    def move_roi(self, roi: dict) -> dict:
        self._check_ready()
        if self._survey_frame is None:
            raise RuntimeError("ROI requires a previously acquired survey")
        if not isinstance(roi, dict) or not {"x", "y", "size"} <= set(roi):
            raise ValueError("ROI requires x, y and size")
        values = [roi[k] for k in ("x", "y", "size")]
        if any(isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not math.isfinite(v) for v in values):
            raise ValueError("ROI values must be finite numbers")
        x, y, size = map(float, values)
        if not 0 <= x <= 1 or not 0 <= y <= 1 or not 0.15 <= size <= 0.5:
            raise ValueError("ROI outside task bounds")
        if min(x, y, 1 - x, 1 - y) < size / 2 - 1e-12:
            raise ValueError("Entire ROI must fit inside the survey")
        base = self._survey_frame
        angle = math.radians(base["angle_deg"])
        dx, dy = (x - 0.5) * base["width_m"], (y - 0.5) * base["height_m"]
        self._state["frame"] = {
            "cx_m": base["cx_m"] + dx * math.cos(angle) - dy * math.sin(angle),
            "cy_m": base["cy_m"] + dx * math.sin(angle) + dy * math.cos(angle),
            "width_m": base["width_m"] * size, "height_m": base["height_m"] * size,
            "angle_deg": base["angle_deg"],
        }
        return self.snapshot()

    def retract(self) -> dict:
        self._check_ready()
        self._state["feedback_on"] = False
        self._approached = False
        return {"backend": self.backend, "retracted": True, "feedback_on": False,
                "verified": True, "method": "synthetic_feedback_disable"}

    def close(self) -> dict:
        if self._closed:
            return deepcopy(self._cleanup)
        if not self._ready:
            return {"backend": self.backend, "restored": True, "initialized": False}
        before = self.snapshot()
        self._state = deepcopy(self._initial)
        self._approached = False
        self._cleanup = {"backend": self.backend, "restored": True, "before": before,
                         "after": deepcopy(self._state), "verified": True}
        self._closed = True
        return deepcopy(self._cleanup)


# Short alias useful for applications selecting a backend by name.
SyntheticSTM = SyntheticBackend
