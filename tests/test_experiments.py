"""Offline orchestration checks; Demo transport is replaced before construction."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from stm_bench import experiments, runner
from stm_bench.artifacts import audit
from stm_bench.profiles import thresholds_snapshot


def episode_row(**updates):
    row = {
        "backend": "synthetic", "case_id": "case", "policy": "rule",
        "scenario": "nominal", "seed": 0, "profile": "strict-v1",
        "success": True, "task_pass": True, "expected_outcome": "success",
        "score": 98.9, "steps": 11, "frames": 3, "cleanup_ok": True,
        "error": None, "termination_reason": "verified_task_success",
    }
    row.update(updates)
    return row


def test_comparison_pairs_exact_seeds_scenarios_policies_and_profiles(tmp_path):
    calls = []

    def fake_episode(output, **args):
        calls.append((Path(output), args))
        expected = runner.EXPECTED[args["scenario"]]
        # Different profile outcomes prove the paired columns are not aliases.
        success = expected == "success" and args["profile"] == "relaxed-v1"
        return episode_row(**{k: args[k] for k in ("seed", "scenario", "policy", "case_id", "profile")},
                           expected_outcome=expected, success=success,
                           task_pass=success if expected == "success" else True), []

    output = tmp_path / "comparison"
    with patch.object(runner, "run_episode", side_effect=fake_episode):
        result = experiments.compare_profiles(output, seeds=2, seed_offset=100)

    assert len(calls) == 2 * 2 * 9 * 2
    assert result["aggregate"] == {"episodes": 72, "paired_cases": 36, "profiles": 2}
    cases = runner.make_cases("test", seeds_per_scenario=2, seed_offset=100)
    expected = {(case["id"], policy): (case["seed"], case["scenario"])
                for case in cases for policy in ("rule", "random")}
    for profile in ("strict-v1", "relaxed-v1"):
        observed = {(args["case_id"], args["policy"]): (args["seed"], args["scenario"])
                    for _, args in calls if args["profile"] == profile}
        assert observed == expected
        assert json.loads((output / profile / "cases.json").read_text()) == cases
        protocol = json.loads((output / profile / "protocol.json").read_text())
        assert protocol["profile"] == profile
        assert protocol["thresholds"] == thresholds_snapshot(profile)
    for row in result["paired_outcomes"]:
        assert (row["seed"], row["scenario"]) == expected[(row["case_id"], row["policy"])]
        if runner.EXPECTED[row["scenario"]] == "success":
            assert row["strict_pass"] is False and row["relaxed_pass"] is True
            assert row["strict_success"] is False and row["relaxed_success"] is True
    assert audit(output)["valid"]


@pytest.mark.parametrize("profile", ["strict-v1", "relaxed-v1"])
def test_episode_propagates_profile_to_policy_environment_and_saved_evidence(tmp_path, profile):
    from stm_bench.env import STMEnv
    from stm_bench.policies import RulePolicy

    output = tmp_path / profile
    with patch("stm_bench.env.STMEnv", wraps=STMEnv) as env_factory, \
            patch.dict(runner.POLICIES, {"rule": RulePolicy}), \
            patch.object(RulePolicy, "__init__", autospec=True, side_effect=RulePolicy.__init__) as policy_init:
        result, _ = runner.run_episode(output, seed=1000100, profile=profile)

    assert env_factory.call_args.kwargs["profile"] == profile
    assert policy_init.call_args.kwargs["profile"] == profile
    assert result["profile"] == profile and result["task_pass"] and result["cleanup_ok"]
    protocol = json.loads((output / "protocol.json").read_text())
    assert protocol["profile"] == profile
    assert protocol["thresholds"] == thresholds_snapshot(profile)
    events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
    observations = [event["observation"] for event in events if "observation" in event]
    assert observations and all(obs["profile"] == profile for obs in observations)
    assert audit(output)["valid"]


class OfflineDemo:
    """Only records constructor/reset/configure arguments; has no transport."""
    instances = []

    def __init__(self, directory, *, port, pixels):
        self.directory, self.port, self.pixels = directory, port, pixels
        self.history = []
        self.instances.append(self)

    def reset(self, *, seed, scenario):
        self.history.append(("reset", seed, scenario))
        return {"phase": "reset"}

    def configure(self, params):
        self.history.append(("configure", dict(params)))
        return {"phase": "configured", "params": dict(params)}


@pytest.mark.parametrize("failure", ["cleanup", "execution"])
def test_demo_series_stops_after_uncertain_cleanup_or_execution(tmp_path, failure):
    OfflineDemo.instances = []
    calls = []

    def fake_episode(output, **args):
        calls.append(args)
        backend = args["backend"](Path(output) / "device")
        backend.reset(seed=0, scenario=args["scenario"])
        failed = len(calls) == 2
        return episode_row(backend="nanonis_demo", case_id=args["case_id"], profile=args["profile"],
                           success=not failed, task_pass=not failed,
                           cleanup_ok=not (failed and failure == "cleanup"),
                           error="ConnectionError: uncertain transport" if failed and failure == "execution" else None,
                           termination_reason="cleanup_failed" if failed else "verified_task_success"), []

    output = tmp_path / failure
    with patch("stm_bench.demo.DemoBackend", OfflineDemo), \
            patch.object(experiments, "run_episode", side_effect=fake_episode):
        result = experiments.demo_series(output, repeats=5, port=6502)

    assert len(calls) == len(OfflineDemo.instances) == 2
    assert result["aggregate"]["planned"] == 5 and result["aggregate"]["completed"] == 2
    assert result["aggregate"]["successes"] == 1
    assert result["aggregate"]["cleanup_failures"] == (1 if failure == "cleanup" else 0)
    assert all(args["profile"] == "relaxed-v1" and args["max_steps"] == 32 for args in calls)
    for backend, recipe in zip(OfflineDemo.instances, experiments.DEMO_RECIPES):
        assert backend.port == 6502 and backend.pixels == recipe["pixels"]
        assert backend.history == [("reset", 0, "nominal"), ("configure", recipe["params"])]
    plan = json.loads((output / "plan.json").read_text())
    progress = json.loads((output / "progress.json").read_text())
    assert plan["stop_on_cleanup_failure"] and len(plan["recipes"]) == 5
    assert progress["completed"] == 2 and progress["planned"] == 5
    assert audit(output)["valid"]


def test_demo_series_retains_clean_rejections_and_runs_every_predeclared_recipe(tmp_path):
    OfflineDemo.instances = []
    calls = []

    def fake_episode(output, **args):
        calls.append(args)
        backend = args["backend"](Path(output) / "device")
        backend.reset(seed=0, scenario=args["scenario"])
        success = len(calls) != 2
        return episode_row(backend="nanonis_demo", case_id=args["case_id"], profile=args["profile"],
                           success=success, task_pass=success,
                           termination_reason="verified_task_success" if success else "agent_retracted"), []

    output = tmp_path / "complete"
    with patch("stm_bench.demo.DemoBackend", OfflineDemo), \
            patch.object(experiments, "run_episode", side_effect=fake_episode):
        result = experiments.demo_series(output, repeats=5, profile="strict-v1")

    assert len(calls) == len(OfflineDemo.instances) == 5
    assert result["aggregate"] == {"planned": 5, "completed": 5, "successes": 4,
                                    "cleanup_failures": 0, "fresh_frames": 15}
    assert result["episodes"][1]["success"] is False
    assert all(args["profile"] == "strict-v1" for args in calls)
    assert [instance.pixels for instance in OfflineDemo.instances] == [64, 64, 64, 64, 128]
    assert [episode["trial_recipe"] for episode in result["episodes"]] == list(experiments.DEMO_RECIPES)
    assert audit(output)["valid"]
