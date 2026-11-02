"""Evidence-gated STM task environment with a Gym-style five-value step API."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any

import numpy as np

from .metrics import stability, image_quality, repeatability, frame_digest, same_context
from .profiles import resolve_profile
from .synthetic import SyntheticBackend


class STMEnv:
    """The policy only sees measurements; evaluator decisions own progression.

    Termination means success, explicit abort, or a backend/evidence fault.
    Truncation means the external action budget expired. A successful last-budget
    action remains a success. Invalid actions consume budget but never call a
    backend method.
    """

    WEIGHTS = {"approach": 10.0, "stability": 15.0, "survey": 15.0,
               "roi": 15.0, "detail": 15.0, "repeatability": 15.0,
               "judgment": 5.0, "accepted": 10.0}
    CURRENT_LIMIT_A = 1e-6
    LABELS = {"good", "noisy", "flat", "saturated", "incomplete"}
    DIAGNOSES = {"unknown", "clean", "double_tip", "drift"}

    def __init__(self, backend=None, max_steps: int = 48, profile="strict-v1"):
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        self.backend = backend if backend is not None else SyntheticBackend()
        self.max_steps = max_steps
        resolve_profile(profile)
        self._profile = profile
        self._initialized = False
        self._closed = False

    @property
    def profile(self):
        """Acceptance profile is fixed for the lifetime of this environment."""
        return self._profile

    def reset(self, seed: int = 0, options=None):
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a dictionary")
        options = options or {}
        if self._initialized and not self._closed:
            result = self.backend.close()
            if result.get("restored") is False:
                raise RuntimeError("Previous episode settings were not restored")
        self._snapshot = self.backend.reset(seed=seed, scenario=options.get("scenario", "nominal"))
        self._stage = "approach"
        self._steps = self._invalid = 0
        self._terminated = self._truncated = self._success = False
        self._reason = None
        self._last_error = None
        self._latest_stability = self._latest_image = self._latest_frame = None
        self._streak = 0
        self._window_ids = set()
        self._frame_ids = set()
        self._frame_digests = set()
        self._window_end = None
        self._detail_frames = []
        self._detail_context = None
        self._repeat = None
        self._judged_id = None
        self._survey = None
        self._roi = None
        self._scan_target = "survey"
        self._stages = {k: False for k in self.WEIGHTS}
        self._judgments = []
        self._wrong_judgments = 0
        self._backend_faults = 0
        self._cleanup = None
        self._initialized = True
        self._closed = False
        return self._observation(), {"backend": self._snapshot.get("backend"), "reset": True,
                                     "profile": self.profile}

    def _mask(self):
        if self._terminated or self._truncated or self._closed:
            return []
        if self._stage == "approach":
            return ["approach", "retract"]
        allowed = ["observe", "configure", "retract"]
        if self._streak >= 2:
            if self._scan_target == "survey":
                allowed.append("survey")
                if self._survey is not None and self._latest_image and self._latest_image.get("acceptable"):
                    allowed.append("select_roi")
            else:
                allowed.append("scan")
        if self._latest_frame is not None and self._latest_image is not None:
            allowed.append("judge")
        if (self._repeat and self._repeat.get("confirmed") and self._latest_image
                and self._latest_image.get("acceptable") and self._judged_id == self._latest_frame["id"]):
            allowed.append("accept")
        return allowed

    def _observation(self):
        image_observation = None if self._latest_image is None else {
            k: v for k, v in self._latest_image.items()
            if k not in {"acceptable", "label", "checks", "scientific_validity"}}
        return deepcopy({"stage": self._stage, "action_mask": self._mask(), "profile": self.profile,
                         "snapshot": self._snapshot, "latest_stability": self._latest_stability,
                         "latest_image": image_observation, "latest_frame": self._latest_frame,
                         "stable_windows": self._streak, "detail_scans": len(self._detail_frames),
                         "repeatability": self._repeat,
                         "budgets": {"steps_used": self._steps, "steps_left": max(0, self.max_steps - self._steps),
                                     "max_steps": self.max_steps}, "last_error": self._last_error})

    def _context(self):
        keys = ("backend", "feedback_on", "setpoint_A", "p_gain_m", "time_constant_s",
                "line_time_s", "z_range_m", "frame")
        settings = {k: self._snapshot[k] for k in keys}
        return hashlib.sha256(json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def _invalidate(self):
        self._streak = 0
        self._latest_stability = self._latest_image = self._latest_frame = None
        self._detail_frames = []
        self._detail_context = None
        self._repeat = None
        self._judged_id = None
        self._stage = "stabilize"

    def _validate_action(self, action):
        if not isinstance(action, dict):
            raise ValueError("Action must be a dictionary")
        # Accept both common spellings without forcing model-specific parsing.
        name = action.get("action", action.get("type"))
        if not isinstance(name, str) or name not in self._mask():
            raise ValueError("Action is not legal in the current stage")
        if "action" in action and "type" in action and action["action"] != action["type"]:
            raise ValueError("Conflicting action names")
        if name == "configure":
            p = action.get("params")
            bounds = getattr(self.backend, "configuration_bounds", SyntheticBackend.RANGES)
            if not isinstance(p, dict) or not p or set(p) - bounds.keys():
                raise ValueError("configure needs bounded controller parameters")
            for k, v in p.items():
                lo, hi = bounds[k]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                    raise ValueError(f"Invalid configuration value: {k}")
        elif name == "select_roi":
            r = action.get("roi")
            if not isinstance(r, dict) or not {"x", "y", "size"} <= r.keys():
                raise ValueError("select_roi needs x, y and size")
            vals = [r[k] for k in ("x", "y", "size")]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vals):
                raise ValueError("ROI must contain finite numbers")
            x, y, size = vals
            if not 0.15 <= size <= 0.5 or min(x, y, 1-x, 1-y) < size/2 - 1e-12:
                raise ValueError("ROI must fit within the survey")
        elif name == "judge":
            if action.get("label") not in self.LABELS or action.get("diagnosis", "unknown") not in self.DIAGNOSES:
                raise ValueError("Unsupported judgment label or diagnosis")
        return name

    def _fresh_window(self, window):
        wid = window.get("window_id")
        if not isinstance(wid, str) or not wid or wid in self._window_ids:
            raise RuntimeError("Missing or repeated stability window ID")
        self._window_ids.add(wid)
        start, end = window.get("started_s"), window.get("ended_s")
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end) or end <= start):
            raise RuntimeError("Invalid stability window times")
        if self._window_end is not None and start <= self._window_end:
            raise RuntimeError("Overlapping stability evidence")
        self._window_end = end
        for key in ("setpoint_A", "z_range_m"):
            value = window.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not math.isclose(
                    value, self._snapshot[key], rel_tol=1e-5, abs_tol=1e-20):
                raise RuntimeError("Stability denominator changed from the configured context")
        if window.get("feedback_on") is not self._snapshot["feedback_on"]:
            raise RuntimeError("Stability feedback state differs from the configured context")
        currents = np.asarray(window.get("current_A", []), dtype=float)
        if currents.size and np.any(np.abs(currents) >= self.CURRENT_LIMIT_A):
            raise RuntimeError("Measured current exceeded the protection limit")

    def _check_frame(self, frame):
        fid = frame.get("id")
        life = frame.get("lifecycle", [])
        if not fid or fid in self._frame_ids or frame.get("fresh") is not True:
            raise RuntimeError("Missing or stale acquisition evidence")
        if (not isinstance(life, list) or not life or life[-1] != 0 or 1 not in life[:-1]
                or any(v not in (0, 1) for v in life)):
            raise RuntimeError("Unverified running-to-stopped scan lifecycle")
        elapsed = frame.get("elapsed_s")
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
            raise RuntimeError("Missing acquisition duration")
        for key in ("current_forward", "current_backward"):
            values = np.asarray(frame.get(key, []), dtype=float)
            if values.size and np.any(np.abs(values) >= self.CURRENT_LIMIT_A):
                raise RuntimeError("Frame current exceeded the protection limit")
        digest = frame_digest(frame)
        if digest in self._frame_digests:
            raise RuntimeError("Repeated raw scan buffers despite an acquisition label change")
        self._frame_digests.add(digest)
        if not same_context(frame, self._snapshot):
            raise RuntimeError("Acquisition settings do not match the current task context")
        self._frame_ids.add(fid)

    def _fail(self, reason):
        self._terminated = True
        self._reason = reason
        self._stage = "failed"
        self._last_error = reason
        try:
            self._cleanup = self.backend.retract()
            if self._cleanup.get("retracted") is False:
                self._last_error += "; retraction was not verified"
            self._snapshot = self.backend.snapshot()
        except Exception as exc:
            self._cleanup = {"verified": False, "error": str(exc)}
            self._last_error += "; cleanup failed: " + str(exc)

    def step(self, action: dict):
        if not self._initialized or self._closed:
            raise RuntimeError("Environment requires reset before step")
        if self._terminated or self._truncated:
            raise RuntimeError("Episode finished; reset before another step")
        before_score = sum(self.WEIGHTS[k] for k, v in self._stages.items() if v)
        self._steps += 1
        self._last_error = None
        info: dict[str, Any] = {"valid_action": True}
        reward = -0.1
        try:
            name = self._validate_action(action)
        except (ValueError, TypeError) as exc:
            self._invalid += 1
            self._last_error = str(exc)
            info.update(valid_action=False, error=str(exc))
            reward -= 2.0
            name = None
        if name is not None:
            try:
                if name == "approach":
                    evidence = self.backend.approach()
                    info["approach"] = evidence
                    self._snapshot = self.backend.snapshot()
                    if evidence.get("completed") is not True or not self._snapshot.get("feedback_on"):
                        self._fail("approach_not_established")
                    else:
                        self._stages["approach"] = True
                        self._stage = "stabilize"
                elif name == "observe":
                    before = self.backend.snapshot()
                    if not same_context(before, self._snapshot):
                        raise RuntimeError("Instrument configuration changed before observation")
                    window = self.backend.sample()
                    if not same_context(before, self.backend.snapshot()):
                        raise RuntimeError("Instrument configuration changed during observation")
                    info["window"] = window
                    self._fresh_window(window)
                    self._latest_stability = stability(window, profile=self.profile)
                    self._streak = self._streak + 1 if self._latest_stability.get("stable") else 0
                    if self._streak >= 2:
                        self._stages["stability"] = True
                        self._stage = "survey" if self._scan_target == "survey" else "scan"
                    else:
                        self._stage = "stabilize"
                        self._detail_frames = []
                        self._repeat = None
                        self._judged_id = None
                elif name == "configure":
                    self._snapshot = self.backend.configure(action["params"])
                    self._invalidate()
                    if self._scan_target == "survey":
                        self._survey = None
                elif name in ("survey", "scan"):
                    before = self.backend.snapshot()
                    if not same_context(before, self._snapshot):
                        raise RuntimeError("Instrument configuration changed outside the environment")
                    frame = self.backend.scan("survey" if name == "survey" else "detail")
                    # Rejected frames are evidence too; the runner persists these raw arrays.
                    info["acquired_frame"] = frame
                    after = self.backend.snapshot()
                    if not same_context(before, after):
                        raise RuntimeError("Instrument configuration changed during acquisition")
                    info["frame_id"] = frame.get("id")
                    self._check_frame(frame)
                    self._latest_frame = deepcopy(frame)
                    self._latest_image = image_quality(frame, profile=self.profile)
                    self._judged_id = None
                    if name == "survey":
                        self._survey = deepcopy(frame)
                        self._stage = "locate" if self._latest_image.get("acceptable") else "survey"
                        if self._latest_image.get("acceptable"):
                            self._stages["survey"] = True
                    else:
                        context = self._context()
                        if self._detail_context != context:
                            self._detail_frames = []
                        self._detail_context = context
                        if self._latest_image.get("acceptable"):
                            self._stages["detail"] = True
                            self._detail_frames.append(deepcopy(frame))
                            self._detail_frames = self._detail_frames[-2:]
                        else:
                            self._detail_frames = []
                        self._repeat = repeatability(*self._detail_frames, profile=self.profile) if len(self._detail_frames) == 2 else None
                        self._stage = "judge" if self._repeat and self._repeat.get("confirmed") else "scan"
                        if self._repeat and self._repeat.get("confirmed"):
                            self._stages["repeatability"] = True
                elif name == "select_roi":
                    self._snapshot = self.backend.move_roi(action["roi"])
                    self._roi = deepcopy(action["roi"])
                    self._stages["roi"] = True
                    self._scan_target = "detail"
                    self._invalidate()
                elif name == "judge":
                    correct = action["label"] == self._latest_image["label"]
                    diagnosis = action.get("diagnosis", "unknown")
                    self._judgments.append({"frame_id": self._latest_frame["id"], "label": action["label"],
                                            "metric_label": self._latest_image["label"], "agrees_with_metrics": correct,
                                            "diagnosis": diagnosis, "diagnosis_status": "unverified_agent_hypothesis"})
                    info["judgment_agreement"] = correct
                    self._judged_id = None
                    if correct:
                        self._stages["judgment"] = True
                        if action["label"] == "good" and self._scan_target == "detail" and diagnosis in ("unknown", "clean"):
                            self._judged_id = self._latest_frame["id"]
                    else:
                        self._wrong_judgments += 1
                        reward -= 1.0
                        self._last_error = "Judgment disagrees with measured image criteria"
                elif name == "accept":
                    fresh = self.backend.snapshot()
                    if not same_context(fresh, self._snapshot):
                        raise RuntimeError("Instrument configuration changed before acceptance")
                    self._snapshot = fresh
                    self._success = self._terminated = True
                    self._stages["accepted"] = True
                    self._stage = "complete"
                    self._reason = "verified_task_success"
                elif name == "retract":
                    self._cleanup = self.backend.retract()
                    if self._cleanup.get("retracted") is False:
                        raise RuntimeError("Agent retraction did not complete")
                    self._snapshot = self.backend.snapshot()
                    self._terminated = True
                    self._stage = "failed"
                    self._reason = "agent_retracted"
            except Exception as exc:
                self._backend_faults += 1
                info["error_type"] = type(exc).__name__
                self._fail(f"{type(exc).__name__}: {exc}")
                reward -= 5.0
        reward += sum(self.WEIGHTS[k] for k, v in self._stages.items() if v) - before_score
        if self._steps >= self.max_steps and not self._terminated:
            self._truncated = True
            self._reason = "step_budget_exhausted"
            # Budget expiry must leave no continuing owned operation.
            try:
                self._cleanup = self.backend.retract()
                self._snapshot = self.backend.snapshot()
            except Exception as exc:
                self._cleanup = {"verified": False, "error": str(exc)}
                self._last_error = "Budget cleanup failed: " + str(exc)
        info.update(termination_reason=self._reason, success=self._success, stages=deepcopy(self._stages))
        return self._observation(), float(reward), self._terminated, self._truncated, info

    def summary(self):
        if not self._initialized:
            return {"success": False, "stages": {}, "score_parts": {}, "score": 0.0, "steps": 0,
                    "profile": self.profile}
        parts = {k: weight if self._stages[k] else 0.0 for k, weight in self.WEIGHTS.items()}
        parts.update(invalid_actions=-2.0 * self._invalid, wrong_judgments=-float(self._wrong_judgments),
                     backend_faults=-5.0 * self._backend_faults,
                     step_cost=-0.1 * self._steps)
        return {"backend": self._snapshot.get("backend"), "success": self._success, "profile": self.profile,
                "stages": deepcopy(self._stages), "score_parts": parts,
                "score": float(sum(parts.values())), "steps": self._steps,
                "invalid_actions": self._invalid, "terminated": self._terminated,
                "localization_valid": self._stages["roi"], "scientific_localization_accuracy": None,
                "truncated": self._truncated, "termination_reason": self._reason,
                "judgments": deepcopy(self._judgments), "repeatability": deepcopy(self._repeat),
                "cleanup": deepcopy(self._cleanup), "last_error": self._last_error}

    def close(self):
        if self._closed:
            return deepcopy(self._cleanup)
        result = self.backend.close()
        self._cleanup = result
        self._closed = True
        if result.get("restored") is False:
            self._success = False
            self._reason = "cleanup_restoration_failed"
            raise RuntimeError("Backend settings restoration failed")
        return deepcopy(result)
