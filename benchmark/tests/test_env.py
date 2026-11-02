"""Behavioral tests for task progression, provenance and fault containment."""
from copy import deepcopy
import json

import numpy as np
import pytest

from stm_bench.env import STMEnv
from stm_bench.metrics import choose_roi, image_quality
from stm_bench.synthetic import SCENARIOS, SyntheticBackend


GOOD_SETTINGS = {"p_gain_m": 40e-12, "time_constant_s": 0.004, "line_time_s": 0.128}


def act(env, name, **kwargs):
    return env.step({"action": name, **kwargs})


def survey_ready(env):
    act(env, "approach")
    act(env, "observe")
    return act(env, "observe")[0]


def detail_ready(env):
    survey_ready(env)
    obs = act(env, "survey")[0]
    act(env, "select_roi", roi=choose_roi(obs["latest_frame"]))
    act(env, "observe")
    return act(env, "observe")[0]


def complete(env):
    detail_ready(env)
    act(env, "scan")
    act(env, "scan")
    act(env, "judge", label="good")
    return act(env, "accept")


def test_nominal_full_task_requires_all_stages_and_clean_reset():
    env = STMEnv()
    first, _ = env.reset(seed=24)
    obs, reward, terminated, truncated, info = complete(env)
    assert terminated and not truncated and info["success"]
    assert obs["stage"] == "complete" and not obs["action_mask"]
    summary = env.summary()
    assert all(summary["stages"].values())
    assert summary["localization_valid"] and summary["scientific_localization_accuracy"] is None
    assert summary["repeatability"]["confirmed"]
    assert summary["steps"] == 11
    with pytest.raises(RuntimeError, match="finished"):
        act(env, "observe")
    assert env.close()["restored"]
    assert env.close()["restored"]
    again, _ = env.reset(seed=24)
    assert first == again
    assert env.summary()["steps"] == 0
    env.close()


def test_invalid_actions_never_bypass_order_or_consume_backend_measurements():
    backend = SyntheticBackend()
    env = STMEnv(backend)
    env.reset()
    for name in ("scan", "survey", "select_roi", "accept", "judge"):
        obs, reward, terminated, truncated, info = act(env, name)
        assert not info["valid_action"] and reward < 0
        assert not terminated and not truncated
        assert backend._scan_number == backend._sample_number == 0
    act(env, "approach")
    one = act(env, "observe")[0]
    assert one["stable_windows"] == 1 and "survey" not in one["action_mask"]
    two = act(env, "observe")[0]
    assert two["stable_windows"] == 2 and "survey" in two["action_mask"]


def test_nominal_cannot_accept_first_scan_or_unjudged_second():
    env = STMEnv(); env.reset()
    detail_ready(env)
    one = act(env, "scan")[0]
    assert "accept" not in one["action_mask"]
    act(env, "judge", label="good")
    two = act(env, "scan")[0]
    assert two["repeatability"]["confirmed"] and "accept" not in two["action_mask"]
    wrong = act(env, "judge", label="flat")
    assert not wrong[4]["judgment_agreement"]
    assert "accept" not in wrong[0]["action_mask"]
    assert env.summary()["score_parts"]["wrong_judgments"] == -1
    right = act(env, "judge", label="good")[0]
    assert "accept" in right["action_mask"]


def test_configure_and_roi_invalidate_stability_and_image_confirmation():
    env = STMEnv(); env.reset()
    detail_ready(env)
    act(env, "scan"); act(env, "scan"); act(env, "judge", label="good")
    obs = act(env, "configure", params=GOOD_SETTINGS)[0]
    assert obs["stage"] == "stabilize"
    assert obs["stable_windows"] == 0 and obs["detail_scans"] == 0
    assert obs["latest_frame"] is None and obs["latest_image"] is None
    assert "scan" not in obs["action_mask"] and "accept" not in obs["action_mask"]
    act(env, "observe")
    assert "scan" in act(env, "observe")[0]["action_mask"]


def test_agent_observation_does_not_expose_scenario_or_evaluator_labels():
    env = STMEnv(); env.reset(seed=7, options={"scenario": "nominal"})
    survey_ready(env)
    obs = act(env, "survey")[0]
    assert not ({"label", "acceptable", "checks", "scientific_validity"} & obs["latest_image"].keys())
    def inspect(value):
        if isinstance(value, dict):
            assert not {"scenario", "ground_truth", "truth", "seed"} & value.keys()
            for v in value.values(): inspect(v)
        elif isinstance(value, list):
            for v in value: inspect(v)
    inspect(obs)
    original = float(obs["latest_frame"]["z_forward"][0, 0])
    obs["latest_frame"]["z_forward"][0, 0] = 123
    assert env._latest_frame["z_forward"][0, 0] == original


def test_seed_reproduces_measurements_and_repeated_windows_are_fresh():
    a, b = SyntheticBackend(), SyntheticBackend()
    a.reset(58, "nominal"); b.reset(58, "nominal")
    a.approach(); b.approach()
    w1, w2 = a.sample(), a.sample()
    assert w1 == b.sample()
    assert w1["window_id"] != w2["window_id"]
    assert w2["started_s"] > w1["ended_s"]
    f1, f2 = a.scan("survey"), b.scan("survey")
    np.testing.assert_array_equal(f1["z_forward"], f2["z_forward"])
    assert not np.array_equal(w1["current_A"], w2["current_A"])


def test_roi_rotation_and_measurements_depend_on_location():
    backend = SyntheticBackend(); backend.reset(4, "nominal"); backend.approach()
    backend._state["frame"]["angle_deg"] = 90.0
    survey = backend.scan("survey")
    moved = backend.move_roi({"x": 0.75, "y": 0.5, "size": 0.3})
    assert abs(moved["frame"]["cx_m"]) < 1e-20
    assert moved["frame"]["cy_m"] == pytest.approx(6e-9)
    assert moved["frame"]["width_m"] == pytest.approx(7.2e-9)
    first = backend.scan("detail")
    backend.move_roi({"x": 0.25, "y": 0.5, "size": 0.3})
    second = backend.scan("detail")
    assert np.mean(np.abs(first["z_forward"] - second["z_forward"])) > 2e-12
    # All selections remain relative to the survey, not the previous detail crop.
    assert second["frame"]["cy_m"] == pytest.approx(-6e-9)


def test_parameters_have_observable_effects_and_can_recover_noisy_task():
    env = STMEnv(); env.reset(seed=3, options={"scenario": "noisy"})
    act(env, "approach")
    noisy = act(env, "observe")[0]["latest_stability"]
    act(env, "configure", params=GOOD_SETTINGS)
    stable = act(env, "observe")[0]["latest_stability"]
    assert stable["current_cv"] < noisy["current_cv"] / 4
    act(env, "observe")
    survey = act(env, "survey")[0]
    assert image_quality(survey["latest_frame"])["acceptable"]


@pytest.mark.parametrize("scenario,stop_after", [("no_tunnel",1),("current_spike",2),("scan_timeout",4)])
def test_bounded_backend_failures_terminate_and_disable_feedback(scenario, stop_after):
    env = STMEnv(); env.reset(options={"scenario": scenario})
    actions = ["approach", "observe", "observe", "survey"]
    for name in actions[:stop_after]:
        obs, reward, terminated, truncated, info = act(env, name)
    assert terminated and not truncated and not info["success"]
    assert not obs["snapshot"]["feedback_on"] and not obs["action_mask"]
    assert env.summary()["cleanup"]["verified"]


def test_flat_survey_cannot_open_roi_gate():
    env = STMEnv(); env.reset(seed=3, options={"scenario": "flat"})
    survey_ready(env)
    obs = act(env, "survey")[0]
    assert image_quality(obs["latest_frame"])["label"] == "flat"
    assert "select_roi" not in obs["action_mask"]
    assert "accept" not in obs["action_mask"]


def test_direction_dependent_double_image_can_pass_survey_but_fail_detail():
    # This checks a constructed numerical artifact, not universal double-tip detection.
    env = STMEnv(); env.reset(seed=3, options={"scenario": "double_tip"})
    detail_ready(env)
    obs = act(env, "scan")[0]
    assert not image_quality(obs["latest_frame"])["acceptable"]
    assert obs["detail_scans"] == 0 and "accept" not in obs["action_mask"]


def test_drift_cannot_satisfy_repeatability():
    env = STMEnv(); env.reset(seed=3, options={"scenario": "drift"})
    detail_ready(env)
    act(env, "scan")
    obs = act(env, "scan")[0]
    assert not obs["repeatability"]["confirmed"]
    assert "accept" not in obs["action_mask"]


def test_stale_buffer_fault_is_terminal():
    env = STMEnv(); env.reset(options={"scenario": "stale_frame"})
    detail_ready(env)
    obs, _, terminated, truncated, _ = act(env, "scan")
    assert terminated and not truncated and "stale" in obs["last_error"]


@pytest.mark.parametrize("mutation", ["id", "overlap", "missing", "denominator"])
def test_window_replay_overlap_missing_and_denominator_are_rejected(mutation):
    class BadWindow(SyntheticBackend):
        def sample(self, count=32):
            window = super().sample(count)
            if self._sample_number == 1:
                self._saved = deepcopy(window)
            elif mutation == "id": window["window_id"] = self._saved["window_id"]
            elif mutation == "overlap": window["started_s"] = self._saved["ended_s"]
            elif mutation == "missing": window.pop("window_id")
            elif mutation == "denominator": window["setpoint_A"] *= 2
            return window
    env = STMEnv(BadWindow()); env.reset(); act(env, "approach"); act(env, "observe")
    obs, _, terminated, _, _ = act(env, "observe")
    assert terminated and obs["stable_windows"] < 2


def test_mixed_nan_overcurrent_still_triggers_protection():
    class BadCurrent(SyntheticBackend):
        def sample(self, count=32):
            window = super().sample(count)
            window["current_A"][0] = float("nan")
            window["current_A"][1] = 2e-6
            return window
    env = STMEnv(BadCurrent()); env.reset(); act(env, "approach")
    obs, _, terminated, _, _ = act(env, "observe")
    assert terminated and "protection" in obs["last_error"]


def test_renamed_old_scan_is_rejected_even_after_intervening_scan():
    class Replay(SyntheticBackend):
        def scan(self, kind):
            frame = super().scan(kind)
            if self._scan_number == 2: self._saved_detail = deepcopy(frame)
            if self._scan_number == 4:
                duplicate = deepcopy(self._saved_detail)
                duplicate["id"] = "new-label-old-buffer"
                return duplicate
            return frame
    env = STMEnv(Replay()); env.reset(); detail_ready(env)
    act(env, "scan"); act(env, "scan")
    obs, _, terminated, _, info = act(env, "scan")
    assert terminated and "Repeated raw scan" in obs["last_error"]
    assert info["acquired_frame"]["id"] == "new-label-old-buffer"


def test_changed_context_during_scan_is_rejected():
    class Changed(SyntheticBackend):
        def scan(self, kind):
            frame = super().scan(kind)
            self._state["p_gain_m"] *= 1.1
            return frame
    env = STMEnv(Changed()); env.reset(); survey_ready(env)
    obs, _, terminated, _, _ = act(env, "survey")
    assert terminated and "changed during acquisition" in obs["last_error"]


def test_invalid_actions_consume_budget_and_last_step_success_is_not_truncated():
    env = STMEnv(max_steps=2); env.reset()
    act(env, "accept")
    obs, _, terminated, truncated, _ = act(env, "accept")
    assert not terminated and truncated and not obs["action_mask"]
    assert not obs["snapshot"]["feedback_on"]
    env = STMEnv(max_steps=11); env.reset()
    _, _, terminated, truncated, info = complete(env)
    assert terminated and not truncated and info["success"]


def test_invalid_parameter_batch_is_atomic():
    backend = SyntheticBackend(); backend.reset()
    before = backend.snapshot()
    with pytest.raises(ValueError):
        backend.configure({"p_gain_m": 20e-12, "line_time_s": float("nan")})
    assert backend.snapshot() == before
    with pytest.raises(ValueError):
        backend.configure({"feedback_on": True})


def test_all_declared_scenarios_and_argument_validation():
    assert len(SCENARIOS) == 9
    for scenario in SCENARIOS:
        backend = SyntheticBackend(); assert backend.reset(1, scenario)["backend"] == "synthetic"
        backend.close()
    with pytest.raises(ValueError): STMEnv(max_steps=0)
    with pytest.raises(ValueError): SyntheticBackend(pixels=1)
    with pytest.raises(ValueError): SyntheticBackend().reset(1, "typo")
    with pytest.raises(RuntimeError): STMEnv().step({"action": "approach"})


def test_restoration_failure_is_not_silent_pass():
    class BadRestore(SyntheticBackend):
        def close(self):
            super().close()
            return {"restored": False, "verified": False}
    env = STMEnv(BadRestore()); env.reset(); complete(env)
    with pytest.raises(RuntimeError, match="restoration"):
        env.close()
    assert not env.summary()["success"]


def test_accept_refreshes_context_and_rejects_out_of_band_change():
    env = STMEnv(); env.reset(); detail_ready(env)
    act(env, "scan"); act(env, "scan"); act(env, "judge", label="good")
    env.backend._state["frame"]["cx_m"] += 1e-9
    obs, _, terminated, truncated, info = act(env, "accept")
    assert terminated and not truncated and not info["success"]
    assert "changed before acceptance" in obs["last_error"]


def test_context_ignores_live_readings_and_score_equals_accumulated_reward():
    env = STMEnv(); env.reset()
    before = env._context()
    env._snapshot.update(current_A=123, z_m=456)
    assert env._context() == before
    env = STMEnv(); env.reset(options={"scenario": "scan_timeout"})
    reward_sum = 0.0
    for name in ("approach", "observe", "observe", "survey"):
        reward_sum += act(env, name)[1]
    assert env.summary()["score_parts"]["backend_faults"] == -5.0
    assert env.summary()["score"] == pytest.approx(reward_sum)
