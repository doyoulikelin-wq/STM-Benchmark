"""Versioned numerical acceptance profiles, separate from instrument protection.

Profiles are immutable and chosen per environment or metric call. Relaxed-v1
changes only the five declared quality tolerances; provenance, freshness, sample
counts, geometry, texture and protection requirements remain unchanged.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


_STRICT = MappingProxyType({
    "minimum_window_samples": 16,
    "current_relative_error": 0.30,
    "current_cv": 0.80,
    "current_peak_ratio": 20.0,
    "current_outlier_fraction": 0.001,
    "z_rail_fraction": 0.01,
    "z_drift_m_s": 2e-9,
    "z_texture_std_m": 1e-12,
    "z_texture_span_m": 5e-12,
    "forward_backward_corr": 0.60,
    "repeat_corr": 0.90,
    "absolute_current_limit_A": 1e-6,
})
_RELAXED = MappingProxyType({
    **_STRICT,
    "current_relative_error": 0.40,
    "current_cv": 1.00,
    "current_outlier_fraction": 0.003,
    "forward_backward_corr": 0.50,
    "repeat_corr": 0.80,
})
PROFILES = MappingProxyType({"strict-v1": _STRICT, "relaxed-v1": _RELAXED})
PROFILE_NAMES = tuple(PROFILES)


def resolve_profile(profile: str = "strict-v1") -> Mapping[str, float | int]:
    """Return immutable registered thresholds; unknown or custom inputs fail."""
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError(f"Unknown acceptance profile {profile!r}; choose one of {PROFILE_NAMES}")
    return PROFILES[profile]


def thresholds_snapshot(profile: str = "strict-v1") -> dict[str, float | int]:
    """Return an independent serializable copy for manifests and reports."""
    return dict(resolve_profile(profile))
