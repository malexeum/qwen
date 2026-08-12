from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Any

from lib.canonicalization import THETA_AXES
from lib.composition.harmony_encoder import HARMONY_AXES, HarmonyEncoder


BRIDGE_NAME = "perceptual_projection"
BRIDGE_VERSION = "v1"
ENCODER_NAME = "crossproduct"


@dataclass(frozen=True)
class D1HarmonyBridgeResult:
    encoder_features: Mapping[str, float]
    named_theta: Mapping[str, float]
    bridge_name: str
    bridge_version: str
    encoder_name: str
    encoder_version: str


def _validate_perceptual(perceptual: Mapping[str, Any]) -> dict[str, float]:
    expected = set(HARMONY_AXES)
    actual = set(perceptual)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        raise ValueError("D1 perceptual bridge schema violation: " + ", ".join(details))

    validated: dict[str, float] = {}
    for axis in HARMONY_AXES:
        value = perceptual[axis]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"D1 perceptual bridge axis '{axis}' must be a finite real number")
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or not 0.0 <= numeric_value <= 1.0:
            raise ValueError(f"D1 perceptual bridge axis '{axis}' must be within [0, 1]")
        validated[axis] = numeric_value
    return validated


def project_perceptual_to_harmony(perceptual: Mapping[str, Any]) -> D1HarmonyBridgeResult:
    """Validate canonical D1 perceptual inputs and project them through E2 HarmonyEncoder."""
    if not isinstance(perceptual, Mapping):
        raise ValueError("D1 perceptual bridge input must be a mapping")

    encoder_features = MappingProxyType(_validate_perceptual(perceptual))
    harmony_theta = HarmonyEncoder().encode(encoder_features)
    named_theta = MappingProxyType(dict(harmony_theta.as_mapping_axes()))

    if tuple(named_theta) != THETA_AXES:
        raise RuntimeError("HarmonyEncoder output does not match the shared D1 theta-axis contract")

    return D1HarmonyBridgeResult(
        encoder_features=encoder_features,
        named_theta=named_theta,
        bridge_name=BRIDGE_NAME,
        bridge_version=BRIDGE_VERSION,
        encoder_name=ENCODER_NAME,
        encoder_version=harmony_theta.version,
    )


__all__ = [
    "BRIDGE_NAME",
    "BRIDGE_VERSION",
    "ENCODER_NAME",
    "D1HarmonyBridgeResult",
    "project_perceptual_to_harmony",
]
