"""Inspectable reference policies. No training or hidden scenario access."""
from __future__ import annotations
import numpy as np
from .metrics import image_quality, choose_roi
from .profiles import resolve_profile


class RulePolicy:
    """Numerical-rule baseline; does not claim learned scientific image judgment."""
    def __init__(self, seed=0, profile="strict-v1"):
        resolve_profile(profile)
        self.profile = profile
        self.adjustments = 0
        self.observed_unstable = 0
        self.last_scan_id = None
        self.reject_pending = False
        self.detail_attempts = 0

    def act(self, obs):
        allowed = obs["action_mask"]
        stage = obs["stage"]
        if self.reject_pending:
            return {"type": "retract"}
        if "approach" in allowed:
            return {"type": "approach"}
        if stage == "stabilize" or ("observe" in allowed and not any(x in allowed for x in ("survey", "scan"))):
            m = obs.get("latest_stability") or {}
            if m and not m.get("stable", False):
                self.observed_unstable += 1
                if "configure" in allowed and self.observed_unstable % 2 == 0 and self.adjustments < 3:
                    return self.tune(obs)
                if self.observed_unstable >= 8:
                    return {"type": "retract"}
            return {"type": "observe"}
        frame = obs.get("latest_frame")
        if frame and frame.get("id") != self.last_scan_id:
            self.last_scan_id = frame["id"]
            if frame.get("kind") in ("detail","confirm"):
                self.detail_attempts += 1
            quality = image_quality(frame, profile=self.profile)
            if not quality["acceptable"]:
                if quality["label"] == "noisy" and "configure" in allowed and self.adjustments < 3:
                    return self.tune(obs)
                if "judge" in allowed:
                    self.reject_pending = True
                    return {"type": "judge", "label": quality["label"]}
                return {"type": "retract"}
            repeat = obs.get("repeatability") or {}
            if self.detail_attempts >= 3 and repeat and not repeat.get("confirmed"):
                self.reject_pending = True
                return {"type": "judge", "label": quality["label"]}
        if "select_roi" in allowed:
            roi = choose_roi(frame, profile=self.profile)
            return {"type": "select_roi", "roi": {k: roi[k] for k in ("x", "y", "size")}}
        if "survey" in allowed:
            return {"type": "survey"}
        if "accept" in allowed:
            return {"type": "accept"}
        # Both independent detail acquisitions must precede the final verdict.
        confirmed = (obs.get("repeatability") or {}).get("confirmed", False)
        if confirmed and "judge" in allowed:
            return {"type": "judge", "label": image_quality(frame, profile=self.profile)["label"]}
        if "scan" in allowed:
            return {"type": "scan"}
        if "observe" in allowed:
            return {"type": "observe"}
        return {"type": "retract"}

    def tune(self, obs):
        self.adjustments += 1
        return {"type": "configure", "params": {
            "p_gain_m": (35e-12, 30e-12, 20e-12)[self.adjustments-1],
            "time_constant_s": .001 if self.adjustments == 1 else .002,
            "line_time_s": .256,
        }}


class RandomPolicy:
    def __init__(self, seed=0, profile="strict-v1"):
        resolve_profile(profile)
        self.profile = profile
        self.rng = np.random.default_rng(seed)

    def act(self, obs):
        name = self.rng.choice(obs["action_mask"])
        if name == "configure":
            return {"type": name, "params": {"line_time_s": float(self.rng.choice([.0768,.1536,.256]))}}
        if name == "select_roi":
            return {"type": name, "roi": {"x": float(self.rng.uniform(.25,.75)), "y": float(self.rng.uniform(.25,.75)), "size": .35}}
        if name == "judge":
            return {"type": name, "label": str(self.rng.choice(["good","flat","noisy","saturated","incomplete"]))}
        return {"type": str(name)}


POLICIES = {"rule": RulePolicy, "random": RandomPolicy}
