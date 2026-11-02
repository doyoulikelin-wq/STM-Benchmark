"""Profile differences must not weaken protection or evidence provenance."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import numpy as np
import pytest

from stm_bench.env import STMEnv
from stm_bench.metrics import THRESHOLDS, choose_roi, image_quality, repeatability, residual, stability
from stm_bench.policies import RandomPolicy, RulePolicy
from stm_bench.profiles import PROFILE_NAMES, PROFILES, resolve_profile, thresholds_snapshot
from stm_bench.synthetic import SyntheticBackend


def evidence(seed=1):
    backend = SyntheticBackend()
    backend.reset(seed)
    backend.approach()
    return backend.sample(), backend.scan("detail")


def correlated_structure(frame, rho):
    """Construct two detrended signals with an explicitly chosen correlation."""
    first = residual(frame["z_forward"])
    first /= first.std()
    other = residual(np.random.default_rng(7).normal(size=first.shape))
    other -= np.sum(other * first) / np.sum(first * first) * first
    other /= other.std()
    return 30e-9 + 20e-12 * (rho * first + np.sqrt(1 - rho**2) * other)


def test_profiles_are_immutable_serializable_snapshots_and_have_exact_declared_changes():
    assert PROFILE_NAMES == ("strict-v1", "relaxed-v1")
    strict, relaxed = resolve_profile(), resolve_profile("relaxed-v1")
    assert THRESHOLDS is strict
    changed = {key: value for key, value in relaxed.items() if strict[key] != value}
    assert changed == {"current_relative_error": .40, "current_cv": 1.0,
                       "current_outlier_fraction": .003, "forward_backward_corr": .50,
                       "repeat_corr": .80}
    with pytest.raises(TypeError): strict["repeat_corr"] = 0
    with pytest.raises(TypeError): relaxed["absolute_current_limit_A"] = 1
    with pytest.raises(TypeError): PROFILES["custom"] = strict
    snapshot = thresholds_snapshot("relaxed-v1")
    assert json.loads(json.dumps(snapshot)) == dict(relaxed)
    snapshot["repeat_corr"] = 0
    assert resolve_profile("relaxed-v1")["repeat_corr"] == .80


@pytest.mark.parametrize("invalid", ["relaxed", "STRICT-v1", None, {}, 1])
def test_unknown_profiles_fail_in_all_public_entrypoints(invalid):
    window, frame = evidence()
    calls = [lambda: resolve_profile(invalid), lambda: thresholds_snapshot(invalid),
             lambda: STMEnv(profile=invalid), lambda: RulePolicy(profile=invalid),
             lambda: RandomPolicy(profile=invalid), lambda: stability(window, invalid),
             lambda: image_quality(frame, invalid), lambda: choose_roi(frame, invalid),
             lambda: repeatability(frame, frame, invalid)]
    for call in calls:
        with pytest.raises(ValueError, match="Unknown acceptance profile"):
            call()


def test_default_metrics_preserve_strict_behavior():
    window, frame = evidence()
    _, another = evidence(2)
    assert stability(window) == stability(window, "strict-v1")
    assert image_quality(frame) == image_quality(frame, "strict-v1")
    assert choose_roi(frame) == choose_roi(frame, "strict-v1")
    assert repeatability(frame, another) == repeatability(frame, another, "strict-v1")


@pytest.mark.parametrize("metric", ["current_relative_error", "current_cv"])
def test_relaxed_current_tolerances_change_only_borderline_acceptance(metric):
    window, frame = evidence()
    sp = window["setpoint_A"]
    values = np.full(32, 1.35 * sp) if metric == "current_relative_error" else np.tile([.1*sp, 1.9*sp], 16)
    window["current_A"] = values
    for key in ("current_forward", "current_backward"):
        frame[key] = np.resize(values, frame[key].shape)
    assert not stability(window)["stable"]
    assert stability(window, "relaxed-v1")["stable"]
    assert not image_quality(frame)["acceptable"]
    assert image_quality(frame, "relaxed-v1")["acceptable"]
    with pytest.raises(ValueError): choose_roi(frame)
    assert choose_roi(frame, "relaxed-v1")["basis"] == "observed_texture_and_direction_agreement"


def test_relaxed_outlier_fraction_accepts_sparse_subprotection_outliers():
    _, frame = evidence()
    for key in ("current_forward", "current_backward"):
        frame[key][:] = frame["setpoint_A"]
        frame[key].flat[:8] = 6 * frame["setpoint_A"]
    strict, relaxed = image_quality(frame), image_quality(frame, "relaxed-v1")
    assert strict["current_outlier_fraction"] == pytest.approx(16 / 8192)
    assert not strict["acceptable"] and relaxed["acceptable"]
    assert not relaxed["protection_triggered"]


def test_relaxed_direction_agreement_tolerance():
    _, frame = evidence()
    frame["z_backward"] = correlated_structure(frame, .55)
    assert image_quality(frame)["forward_backward_corr"] == pytest.approx(.55)
    assert not image_quality(frame)["acceptable"]
    assert image_quality(frame, "relaxed-v1")["acceptable"]


def test_relaxed_repeat_tolerance_requires_two_distinct_same_context_frames():
    _, first = evidence()
    second = deepcopy(first)
    second["id"] += "-second"
    second["z_forward"] = correlated_structure(first, .85)
    second["z_backward"] = second["z_forward"].copy()
    assert repeatability(first, second)["correlation"] == pytest.approx(.85)
    assert not repeatability(first, second)["confirmed"]
    assert repeatability(first, second, "relaxed-v1")["confirmed"]
    for damage in ("same_id", "same_arrays", "changed_context"):
        altered = deepcopy(second)
        if damage == "same_id": altered["id"] = first["id"]
        elif damage == "same_arrays":
            altered = deepcopy(first)
            altered["id"] += "-renamed"
        else: altered["frame"]["cx_m"] += 1e-9
        assert not repeatability(first, altered, "relaxed-v1")["confirmed"]


@pytest.mark.parametrize("damage", ["overcurrent", "negative_overcurrent", "peak", "rail", "drift", "short", "feedback"])
def test_relaxed_stability_keeps_protection_and_complete_window_requirements(damage):
    window, _ = evidence()
    if damage in ("overcurrent", "negative_overcurrent"):
        window["current_A"][0] = 1e-6 if damage == "overcurrent" else -1e-6
    elif damage == "peak": window["current_A"][0] = 21 * window["setpoint_A"]
    elif damage == "rail": window["z_m"] = [window["z_range_m"]] * 32
    elif damage == "drift": window["z_m"] = np.arange(32) * window["dt_s"] * 3e-9
    elif damage == "short":
        window["current_A"] = window["current_A"][:15]
        window["z_m"] = window["z_m"][:15]
    else: window["feedback_on"] = False
    assert not stability(window, "relaxed-v1")["stable"]


@pytest.mark.parametrize("damage", ["overcurrent", "peak", "rail", "texture", "stale", "unfinished", "short"])
def test_relaxed_images_keep_protection_texture_and_acquisition_requirements(damage):
    _, frame = evidence()
    if damage == "overcurrent": frame["current_forward"][0, 0] = 1e-6
    elif damage == "peak": frame["current_forward"][0, 0] = 21 * frame["setpoint_A"]
    elif damage == "rail": frame["z_forward"][:] = frame["z_range_m"]
    elif damage == "texture": frame["z_forward"][:] = 30e-9
    elif damage == "stale": frame["fresh"] = False
    elif damage == "unfinished": frame["lifecycle"] = [1, 1]
    else:
        for key in ("z_forward", "z_backward", "current_forward", "current_backward"):
            frame[key] = frame[key][:15, :15]
    assert not image_quality(frame, "relaxed-v1")["acceptable"]


def test_parallel_profiles_do_not_share_active_threshold_state():
    window, _ = evidence()
    window["current_A"] = [1.35 * window["setpoint_A"]] * 32
    profiles = ["strict-v1", "relaxed-v1"] * 40
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda profile: stability(window, profile)["stable"], profiles))
    assert results == [False, True] * 40
    assert THRESHOLDS["current_relative_error"] == .30


def test_environment_instances_retain_profile_and_require_fresh_evidence():
    class MarginalCurrent(SyntheticBackend):
        def sample(self, count=32):
            window = super().sample(count)
            window["current_A"] = [1.35 * window["setpoint_A"]] * count
            return window
    strict, relaxed = STMEnv(MarginalCurrent()), STMEnv(MarginalCurrent(), profile="relaxed-v1")
    for env in (strict, relaxed):
        obs, info = env.reset()
        assert obs["profile"] == info["profile"] == env.summary()["profile"] == env.profile
        with pytest.raises(AttributeError): env.profile = "relaxed-v1"
        env.step({"action": "approach"})
        first = env.step({"action": "observe"})[0]
        assert "survey" not in first["action_mask"]
    strict_obs = strict.step({"action": "observe"})[0]
    relaxed_obs = relaxed.step({"action": "observe"})[0]
    assert strict_obs["stable_windows"] == 0 and relaxed_obs["stable_windows"] == 2
    assert "survey" not in strict_obs["action_mask"] and "survey" in relaxed_obs["action_mask"]
    survey = relaxed.step({"action": "survey"})[0]
    relaxed.step({"action": "select_roi", "roi": choose_roi(survey["latest_frame"], "relaxed-v1")})
    assert "scan" not in relaxed.step({"action": "observe"})[0]["action_mask"]
    relaxed.step({"action": "observe"})
    first_scan = relaxed.step({"action": "scan"})[0]
    assert first_scan["detail_scans"] == 1 and "accept" not in first_scan["action_mask"]
    second_scan = relaxed.step({"action": "scan"})[0]
    assert second_scan["repeatability"]["confirmed"] and "accept" not in second_scan["action_mask"]
    relaxed.step({"action": "judge", "label": "good"})
    assert relaxed.step({"action": "accept"})[4]["success"]
    strict.close(); relaxed.close()


def test_rule_policy_uses_its_profile_for_quality_and_roi():
    _, frame = evidence()
    for key in ("current_forward", "current_backward"):
        frame[key][:] = 1.35 * frame["setpoint_A"]
    obs = {"stage": "locate", "action_mask": ["select_roi", "judge", "retract"],
           "latest_frame": frame, "repeatability": None}
    assert RulePolicy().act(obs) == {"type": "judge", "label": "noisy"}
    assert RulePolicy(profile="relaxed-v1").act(obs)["type"] == "select_roi"
