"""Frozen evidence gates, shared by software tasks and actual Demo acquisition.

These are numerical acceptance rules for this benchmark, not calibrated physical
STM safety limits or a classifier of scientific sample identity.
"""
from __future__ import annotations

import hashlib
import math
import numpy as np

from .profiles import resolve_profile

# Compatibility name always refers to strict-v1, never the active run's profile.
THRESHOLDS = resolve_profile("strict-v1")


def residual(a):
    a = np.asarray(a, dtype=float)
    y, x = np.indices(a.shape, dtype=float)
    design = np.column_stack((np.ones(a.size), x.ravel(), y.ravel()))
    return a - (design @ np.linalg.lstsq(design, a.ravel(), rcond=None)[0]).reshape(a.shape)


def correlation(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        return None
    if a.std() < 1e-18 or b.std() < 1e-18:
        return None
    return float(np.corrcoef(a.ravel(), b.ravel())[0, 1])


def _current(values, setpoint, thresholds):
    peak = float(np.max(np.abs(values)))
    mean, std = float(np.mean(values)), float(np.std(values))
    return {
        "current_mean_A": mean, "current_std_A": std,
        "current_relative_error": abs(mean-setpoint)/abs(setpoint),
        "current_cv": std/max(abs(mean), 1e-18),
        "current_peak_A": peak, "current_peak_ratio": peak/abs(setpoint),
        "current_outlier_fraction": float(np.mean(np.abs(values) > 5*abs(setpoint))),
        "protection_triggered": peak >= thresholds["absolute_current_limit_A"],
    }


def _protection(record, keys, thresholds):
    for key in keys:
        try:
            values = np.asarray(record.get(key, []), dtype=float)
            # Infinity in a current channel cannot be considered safe.
            if np.any(np.abs(values) >= thresholds["absolute_current_limit_A"]):
                return True
        except (TypeError, ValueError):
            continue
    return False


def stability(window, profile="strict-v1"):
    thresholds = resolve_profile(profile)
    fail = {"stable": False, "valid": False, "reason": "invalid_window",
            "protection_triggered": _protection(window, ("current_A",), thresholds)}
    try:
        i, z = np.asarray(window["current_A"], float), np.asarray(window["z_m"], float)
        sp, zr, dt = float(window["setpoint_A"]), float(window["z_range_m"]), float(window["dt_s"])
        if (i.ndim != 1 or z.shape != i.shape or i.size < thresholds["minimum_window_samples"]
                or not np.isfinite(i).all() or not np.isfinite(z).all()
                or not all(math.isfinite(v) and v > 0 for v in (sp, zr, dt))):
            return fail
        m = _current(i, sp, thresholds)
        m["z_rail_fraction"] = float(np.mean(np.abs(z) >= .499*zr))
        m["z_drift_m_s"] = float(abs(np.polyfit(np.arange(len(z))*dt, z, 1)[0]))
        checks = {key: m[key] <= thresholds[key] for key in (
            "current_relative_error", "current_cv", "current_peak_ratio", "z_rail_fraction", "z_drift_m_s")}
        checks["feedback_on"] = window.get("feedback_on") is True
        checks["current_protection"] = not m["protection_triggered"]
        return {**m, "valid": True, "stable": all(checks.values()), "checks": checks,
                "samples": len(i), "duration_s": (len(i)-1)*dt,
                "reason": "stable" if all(checks.values()) else ",".join(k for k,v in checks.items() if not v)}
    except (KeyError, TypeError, ValueError, OverflowError):
        return fail


def frame_digest(frame):
    h = hashlib.sha256()
    for key in ("z_forward", "z_backward", "current_forward", "current_backward"):
        array = np.asarray(frame[key], dtype="<f8")
        h.update(key.encode()); h.update(str(array.shape).encode()); h.update(array.tobytes())
    return h.hexdigest()


def image_quality(frame, profile="strict-v1"):
    thresholds = resolve_profile(profile)
    fail = {"acceptable": False, "valid": False, "label": "incomplete",
            "protection_triggered": _protection(frame, ("current_forward", "current_backward"), thresholds)}
    try:
        keys = ("z_forward", "z_backward", "current_forward", "current_backward")
        arrays = [np.asarray(frame[k], float) for k in keys]
        shape = arrays[0].shape
        states = frame.get("lifecycle", [])
        if (len(shape) != 2 or min(shape) < 16 or any(a.shape != shape for a in arrays)
                or any(not np.isfinite(a).all() for a in arrays)
                or not frame.get("fresh") or not frame.get("id")
                or not states or 1 not in states or states[-1] != 0
                or any(s not in (0,1) for s in states)
                or not math.isfinite(float(frame.get("elapsed_s", -1)))
                or float(frame.get("elapsed_s", -1)) <= 0):
            return fail
        sp, zr = float(frame["setpoint_A"]), float(frame["z_range_m"])
        if not (math.isfinite(sp) and math.isfinite(zr) and sp > 0 and zr > 0):
            return fail
        zf, zb, cf, cb = arrays
        m = _current(np.concatenate((cf.ravel(), cb.ravel())), sp, thresholds)
        rf, rb = residual(zf), residual(zb)
        m.update(z_rail_fraction=max(float(np.mean(np.abs(z) >= .499*zr)) for z in (zf,zb)),
                 z_texture_std_m=min(float(z.std()) for z in (rf, rb)),
                 z_texture_span_m=min(float(np.ptp(z)) for z in (rf, rb)),
                 forward_backward_corr=correlation(rf, rb))
        checks = {key: m[key] <= thresholds[key] for key in (
            "current_relative_error", "current_cv", "current_peak_ratio", "current_outlier_fraction", "z_rail_fraction")}
        checks.update(texture=m["z_texture_std_m"] >= thresholds["z_texture_std_m"]
                      and m["z_texture_span_m"] >= thresholds["z_texture_span_m"],
                      agreement=m["forward_backward_corr"] is not None
                      and m["forward_backward_corr"] >= thresholds["forward_backward_corr"],
                      current_protection=not m["protection_triggered"])
        acceptable = all(checks.values())
        label = ("good" if acceptable else "saturated" if not checks["z_rail_fraction"]
                 else "flat" if not checks["texture"] else "noisy")
        return {**m, "acceptable": acceptable, "valid": True, "label": label,
                "checks": checks, "array_digest": frame_digest(frame), "shape": list(shape),
                "scientific_validity": "not_assessed"}
    except (KeyError, TypeError, ValueError, OverflowError, np.linalg.LinAlgError):
        return fail


def same_context(a, b):
    required = ("setpoint_A", "z_range_m", "p_gain_m", "time_constant_s", "line_time_s", "feedback_on", "backend", "frame")
    if any(k not in a or k not in b for k in required):
        return False
    if a["backend"] != b["backend"] or a["feedback_on"] is not True or b["feedback_on"] is not True:
        return False
    try:
        for key in ("setpoint_A", "z_range_m", "p_gain_m", "time_constant_s", "line_time_s"):
            av,bv = float(a[key]),float(b[key])
            if not (math.isfinite(av) and math.isfinite(bv) and av>0 and bv>0
                    and math.isclose(av,bv,rel_tol=1e-5,abs_tol=1e-20)):
                return False
        fa,fb = a["frame"],b["frame"]
        geometry = {"cx_m","cy_m","width_m","height_m","angle_deg"}
        if not geometry <= fa.keys() or not geometry <= fb.keys(): return False
        for k in geometry:
            av,bv = float(fa[k]),float(fb[k])
            if not (math.isfinite(av) and math.isfinite(bv)
                    and math.isclose(av,bv,rel_tol=1e-5,abs_tol=1e-20)): return False
            if k in ("width_m","height_m") and min(av,bv)<=0: return False
        return True
    except (TypeError,ValueError,AttributeError,KeyError):
        return False


def repeatability(a, b, profile="strict-v1"):
    thresholds = resolve_profile(profile)
    qa, qb = image_quality(a, profile), image_quality(b, profile)
    distinct = a.get("id") != b.get("id") and qa.get("array_digest") != qb.get("array_digest")
    context = same_context(a, b)
    corr = correlation(residual(a["z_forward"]), residual(b["z_forward"])) if qa["valid"] and qb["valid"] else None
    confirmed = bool(distinct and context and qa["acceptable"] and qb["acceptable"]
                     and corr is not None and corr >= thresholds["repeat_corr"])
    return {"confirmed": confirmed, "correlation": corr, "distinct_acquisitions": distinct,
            "same_context": context}


def choose_roi(frame, profile="strict-v1"):
    """Select an interior tile using observed texture, agreement and current only."""
    if not image_quality(frame, profile)["acceptable"]:
        raise ValueError("A complete acceptable survey is required")
    z, b = np.asarray(frame["z_forward"]), np.asarray(frame["z_backward"])
    c = np.asarray(frame["current_forward"])
    h, w = z.shape
    candidates = []
    size = .35
    for y in np.linspace(.25, .75, 5):
        for x in np.linspace(.25, .75, 5):
            ys, xs = slice(int((y-size/2)*h), int((y+size/2)*h)), slice(int((x-size/2)*w), int((x+size/2)*w))
            tile, backward = residual(z[ys,xs]), residual(b[ys,xs])
            agreement = max(0., correlation(tile, backward) or 0.)
            noise = float(np.std(c[ys,xs]))/frame["setpoint_A"]
            score = agreement * float(np.std(tile)) / (1+noise)
            candidates.append((score, float(x), float(y)))
    score, x, y = max(candidates)
    return {"x": x, "y": y, "size": size, "selection_score": score,
            "basis": "observed_texture_and_direction_agreement"}
