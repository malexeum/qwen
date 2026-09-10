from __future__ import annotations

from typing import Any

import numpy as np


FALLBACK_VALUE = 0.5


def clip01(value: Any, fallback: float = FALLBACK_VALUE) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(numeric):
        return fallback
    return float(np.clip(numeric, 0.0, 1.0))


def normalize(value: Any, low: float, high: float, fallback: float = FALLBACK_VALUE) -> float:
    if high <= low:
        raise ValueError("normalization high bound must exceed low bound")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(numeric):
        return fallback
    return clip01((numeric - low) / (high - low), fallback)


def normalize_features(features: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for group, values in features.items():
        normalized[group] = {}
        for name, value in values.items():
            if group == "pulse" and name == "bpm":
                normalized[group][name] = round(max(0.0, min(220.0, float(value))), 6)
            elif group == "form" and name == "section_count":
                normalized[group][name] = max(1, int(round(float(value))))
            else:
                normalized[group][name] = round(clip01(value), 6)
    return normalized


NORMALIZATION_METADATA = {
    "range": [0.0, 1.0],
    "bpm_range": [0.0, 220.0],
    "section_count": "integer count, range 1..12",
    "fallback_value": FALLBACK_VALUE,
    "fallback_policy": "missing or unsupported measurement is explicitly listed in artifact metadata",
}