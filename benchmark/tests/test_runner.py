"""Independent checks of scoring, frozen case splits and saved evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from stm_bench.artifacts import audit, seal, sha, write_json
from stm_bench.runner import EXPECTED, POLICIES, SCENARIOS, make_cases, run_episode, scenario_pass, wilson
from stm_bench.synthetic import SyntheticBackend


FAULTS = tuple(s for s in SCENARIOS if EXPECTED[s] == "reject")


def summary(scenario, **updates):
    result = {
        "scenario": scenario, "success": False, "cleanup_ok": True,
        "error": None, "terminated": True, "truncated": False,
        "termination_reason": "agent_retracted", "judgments": [], "stages": {},
    }
    result.update(updates)
    return result


def supported_fault(scenario):
    row = summary(scenario)
    evidence = {"image_labels": []}
    if scenario == "no_tunnel":
        evidence["failed_approach"] = True
        row["termination_reason"] = "approach_not_established"
    elif scenario == "current_spike":
        evidence["overcurrent"] = True
        row["termination_reason"] = "RuntimeError: Measured current exceeded the protection limit"
    elif scenario == "scan_timeout":
        evidence["scan_timeout"] = evidence["scan_attempt"] = True
        row["stages"]["stability"] = True
        row["termination_reason"] = "TimeoutError: Scan did not complete before the 30 s synthetic deadline"
    elif scenario == "stale_frame":
        evidence["scan_attempt"] = True
        row["termination_reason"] = "RuntimeError: Missing or stale acquisition evidence"
    elif scenario in ("flat", "double_tip"):
        label = "flat" if scenario == "flat" else "noisy"
        evidence["image_labels"] = [label]
        row["judgments"] = [{"label": label, "agrees_with_metrics": True}]
    elif scenario == "drift":
        evidence["excess_z_drift"] = True
    return row, evidence


class ScenarioScoringTests(unittest.TestCase):
    def test_early_abort_never_receives_fault_detection_credit(self):
        for scenario in FAULTS:
            with self.subTest(scenario=scenario):
                self.assertFalse(scenario_pass(summary(scenario), {"image_labels": []}))

    def test_matching_measured_fault_receives_rejection_credit(self):
        for scenario in FAULTS:
            with self.subTest(scenario=scenario):
                row, evidence = supported_fault(scenario)
                self.assertTrue(scenario_pass(row, evidence))

    def test_expected_success_requires_successful_workflow(self):
        for scenario in ("nominal", "noisy"):
            with self.subTest(scenario=scenario):
                self.assertFalse(scenario_pass(summary(scenario), {}))
                self.assertTrue(scenario_pass(summary(scenario, success=True), {}))

    def test_unsupported_or_unexpected_errors_receive_no_credit(self):
        for scenario in FAULTS:
            with self.subTest(scenario=scenario):
                row = summary(scenario, termination_reason="KeyError: implementation_bug")
                self.assertFalse(scenario_pass(row, {"image_labels": []}))
                # An old correct observation must not excuse a later unrelated error.
                row, evidence = supported_fault(scenario)
                row["termination_reason"] = "KeyError: implementation_bug"
                self.assertFalse(scenario_pass(row, evidence))

    def test_cleanup_error_execution_error_truncation_and_false_accept_block_credit(self):
        for scenario in FAULTS:
            for field, value in (("cleanup_ok", False), ("error", "RuntimeError: interrupted"),
                                 ("truncated", True), ("success", True)):
                with self.subTest(scenario=scenario, field=field):
                    row, evidence = supported_fault(scenario)
                    row[field] = value
                    self.assertFalse(scenario_pass(row, evidence))

    def test_fault_flags_without_corresponding_evidence_are_insufficient(self):
        for scenario in FAULTS:
            with self.subTest(scenario=scenario):
                row, _ = supported_fault(scenario)
                self.assertFalse(scenario_pass(row, {"image_labels": []}))

    def test_image_rejection_requires_both_measured_label_and_correct_judgment(self):
        for scenario in ("flat", "double_tip"):
            with self.subTest(scenario=scenario):
                row, evidence = supported_fault(scenario)
                row["judgments"][0]["agrees_with_metrics"] = False
                self.assertFalse(scenario_pass(row, evidence))
                row, evidence = supported_fault(scenario)
                evidence["image_labels"] = ["good"]
                self.assertFalse(scenario_pass(row, evidence))

    def test_timeout_cannot_pass_without_established_stability(self):
        row, evidence = supported_fault("scan_timeout")
        row["stages"] = {}
        self.assertFalse(scenario_pass(row, evidence))

    def test_run_episode_does_not_credit_an_abort_policy(self):
        class AbortPolicy:
            def __init__(self, seed=0): pass
            def act(self, observation): return {"type": "retract"}
        with tempfile.TemporaryDirectory(prefix="stm_runner_abort_") as directory:
            with patch.dict(POLICIES, {"test_abort": AbortPolicy}):
                for scenario in FAULTS:
                    with self.subTest(scenario=scenario):
                        out = Path(directory) / scenario
                        result, _ = run_episode(out, policy="test_abort", scenario=scenario)
                        self.assertFalse(result["success"])
                        self.assertFalse(result["task_pass"])
                        self.assertTrue(result["cleanup_ok"])
                        self.assertEqual(result["frames"], 0)
                        self.assertTrue(audit(out)["valid"])

    def test_run_episode_does_not_credit_an_unexpected_backend_error(self):
        class BrokenBackend(SyntheticBackend):
            def approach(self):
                raise KeyError("test implementation failure")
        with tempfile.TemporaryDirectory(prefix="stm_runner_error_") as directory:
            result, _ = run_episode(Path(directory) / "episode", backend=BrokenBackend(), scenario="no_tunnel")
            self.assertFalse(result["success"])
            self.assertFalse(result["task_pass"])
            self.assertIn("KeyError", result["termination_reason"])
            self.assertTrue(result["cleanup_ok"])


class ArtifactIntegrityTests(unittest.TestCase):
    def make_evidence(self, root):
        root = Path(root)
        write_json(root / "summary.json", {"success": False, "backend": "synthetic"})
        arrays = root / "frames" / "raw.npy"
        arrays.parent.mkdir()
        np.save(arrays, np.arange(16, dtype=float).reshape(4, 4), allow_pickle=False)
        seal(root)
        return root

    def test_sealed_evidence_audits_without_modification(self):
        with tempfile.TemporaryDirectory(prefix="stm_artifact_clean_") as directory:
            root = self.make_evidence(directory)
            before = {p.relative_to(root): sha(p) for p in root.rglob("*") if p.is_file()}
            result = audit(root)
            self.assertTrue(result["valid"])
            self.assertEqual(result["files"], 2)
            after = {p.relative_to(root): sha(p) for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_modified_array_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="stm_artifact_changed_") as directory:
            root = self.make_evidence(directory)
            np.save(root / "frames" / "raw.npy", np.zeros((4, 4)), allow_pickle=False)
            result = audit(root)
            self.assertFalse(result["valid"])
            self.assertEqual(result["changed"], ["frames/raw.npy"])

    def test_extra_file_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="stm_artifact_extra_") as directory:
            root = self.make_evidence(directory)
            (root / "untracked.txt").write_text("new evidence", encoding="utf-8")
            result = audit(root)
            self.assertFalse(result["valid"])
            self.assertEqual(result["extra"], ["untracked.txt"])

    def test_missing_file_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="stm_artifact_missing_") as directory:
            root = self.make_evidence(directory)
            (root / "frames" / "raw.npy").unlink()
            result = audit(root)
            self.assertFalse(result["valid"])
            self.assertEqual(result["missing"], ["frames/raw.npy"])

    def test_aggregate_manifest_protects_nested_episode_manifests(self):
        with tempfile.TemporaryDirectory(prefix="stm_artifact_nested_") as directory:
            root = Path(directory)
            episode = self.make_evidence(root / "episode")
            seal(root)
            self.assertTrue(audit(root)["valid"])
            write_json(episode / "manifest.json", {"algorithm": "sha256", "files": {}})
            result = audit(root)
            self.assertFalse(result["valid"])
            self.assertIn("episode/manifest.json", result["changed"])


class FrozenCaseTests(unittest.TestCase):
    def test_case_generation_is_deterministic_and_preserves_scenario_balance(self):
        for split in ("train", "dev", "test"):
            with self.subTest(split=split):
                cases = make_cases(split, seeds_per_scenario=5)
                self.assertEqual(cases, make_cases(split, seeds_per_scenario=5))
                self.assertEqual(len(cases), len(SCENARIOS) * 5)
                self.assertEqual(len({c["id"] for c in cases}), len(cases))
                self.assertEqual(len({c["seed"] for c in cases}), len(cases))
                for scenario in SCENARIOS:
                    rows = [c for c in cases if c["scenario"] == scenario]
                    self.assertEqual(len(rows), 5)
                    self.assertTrue(all(c["split"] == split and c["expected"] == EXPECTED[scenario] for c in rows))

    def test_all_supported_seed_counts_have_disjoint_splits(self):
        sets = {
            split: {case["seed"] for case in make_cases(split, seeds_per_scenario=50)}
            for split in ("train", "dev", "test")
        }
        self.assertFalse(sets["train"] & sets["dev"])
        self.assertFalse(sets["train"] & sets["test"])
        self.assertFalse(sets["dev"] & sets["test"])

    def test_same_case_reproduces_raw_scan_and_different_split_changes_it(self):
        frames = []
        for split in ("test", "test", "dev"):
            case = next(c for c in make_cases(split, 1) if c["scenario"] == "nominal")
            backend = SyntheticBackend()
            backend.reset(case["seed"], case["scenario"])
            backend.approach()
            frames.append(deepcopy(backend.scan("survey")["z_forward"]))
            backend.close()
        np.testing.assert_array_equal(frames[0], frames[1])
        self.assertFalse(np.array_equal(frames[0], frames[2]))

    def test_wilson_reports_uncertainty_for_small_success_counts(self):
        self.assertIsNone(wilson(0, 0))
        low, high = wilson(1, 1)
        self.assertAlmostEqual(low, .20654931437723745)
        self.assertAlmostEqual(high, 1.)
        low, high = wilson(0, 1)
        self.assertAlmostEqual(low, 0.)
        self.assertAlmostEqual(high, .7934506856227626)
        lower_small = wilson(2, 2)[0]
        lower_large = wilson(20, 20)[0]
        self.assertLess(lower_small, lower_large)


if __name__ == "__main__":
    unittest.main()
