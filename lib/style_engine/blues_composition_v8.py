from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _number(source: Mapping[str, Any], key: str, default: float) -> float:
    raw = source.get(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BluesCompositionTrace:
    gravity: Mapping[str, float]
    inflow: Mapping[str, float]
    blue_note_bend: Mapping[str, float]
    tube_warmth: Mapping[str, float]


def resolve_blues_composition_v8(
    portrait: Mapping[str, Any],
) -> tuple[dict[str, Any], BluesCompositionTrace]:
    perceptual_raw = portrait.get("perceptual", {})
    perceptual = perceptual_raw if isinstance(perceptual_raw, Mapping) else {}

    theta_raw = portrait.get("harmony_theta", portrait.get("theta", {}))
    theta = theta_raw if isinstance(theta_raw, Mapping) else {}

    brightness = _clamp01(_number(perceptual, "brightness", 0.50))
    density = _clamp01(_number(perceptual, "density", 0.50))
    stability = _clamp01(_number(perceptual, "stability", 0.50))
    smoothness = _clamp01(_number(perceptual, "smoothness", 0.50))
    tension = _clamp01(_number(perceptual, "tension", 0.50))
    repetition = _clamp01(_number(perceptual, "repetition", 0.50))
    noise_proxy = _clamp01(_number(perceptual, "noise_proxy", 0.50))
    symmetry = _clamp01(_number(perceptual, "symmetry_bias", 0.40))
    energy = _clamp01(_number(perceptual, "energy", density))
    resonance = _clamp01(_number(portrait, "resonance", smoothness))

    theta_3 = _clamp01(_number(theta, "theta_3", _number(theta, "3", tension)))
    theta_5 = _clamp01(_number(theta, "theta_5", _number(theta, "5", noise_proxy)))
    theta_6 = _clamp01(_number(theta, "theta_6", _number(theta, "6", 0.50)))

    bpm = _number(portrait, "bpm", 92.0)
    spectral_skewness = _clamp01(_number(portrait, "spectral_skewness", 0.50))
    dynamic_range = _clamp01(_number(portrait, "dynamic_range", 0.50))

    gravity_raw = (
        0.45 * (1.0 - brightness)
        + 0.35 * density
        + 0.20 * (1.0 - spectral_skewness)
    )
    gravity = _clamp01(gravity_raw)

    inflow_raw = (
        0.50 * tension
        + 0.30 * resonance
        + 0.20 * (1.0 - stability)
    )
    inflow = _clamp01(inflow_raw)

    bend_raw = (
        0.60 * theta_3
        + 0.25 * smoothness
        + 0.15 * (1.0 - symmetry)
    )
    blue_note_bend = _clamp01(bend_raw)

    warmth_raw = (
        0.45 * brightness
        + 0.30 * energy
        + 0.25 * (1.0 - spectral_skewness)
    )
    tube_warmth = _clamp01(warmth_raw)

    smoke_density = _clamp01(
        0.55 * theta_5
        + 0.25 * noise_proxy
        + 0.20 * smoothness
    )

    slow_factor = _clamp01((126.0 - bpm) / 76.0)
    swing_lag = _clamp01(
        0.45 * repetition
        + 0.35 * smoothness
        + 0.20 * slow_factor
    )

    void_radius = 54.0 + 34.0 * gravity
    spiral_turns = 0.55 + 0.35 * inflow + 0.10 * theta_6
    ring_fragmentation = _clamp01(
        0.50 * theta_3
        + 0.30 * theta_5
        + 0.20 * (1.0 - repetition)
    )

    bridge = {
        "grammar": "BluesGravityWellCompositionV8",
        "dominant_mode": "slow_blues",
        "palette_id": "warm_midnight",
        "junction": {"x": 540.0, "y": 520.0},
        "gravity": round(gravity, 6),
        "inflow": round(inflow, 6),
        "blue_note_bend": round(blue_note_bend, 6),
        "tube_warmth": round(tube_warmth, 6),
        "smoke_density": round(smoke_density, 6),
        "swing_lag": round(swing_lag, 6),
        "void_radius": round(void_radius, 3),
        "spiral_turns": round(spiral_turns, 6),
        "ring_fragmentation": round(ring_fragmentation, 6),
        "bpm": round(bpm, 3),
        "spectral_skewness": round(spectral_skewness, 6),
        "dynamic_range": round(dynamic_range, 6),
    }

    trace = BluesCompositionTrace(
        gravity={
            "brightness": brightness,
            "density": density,
            "spectral_skewness": spectral_skewness,
            "raw": gravity_raw,
            "final": gravity,
        },
        inflow={
            "tension": tension,
            "resonance": resonance,
            "stability": stability,
            "raw": inflow_raw,
            "final": inflow,
        },
        blue_note_bend={
            "theta_3": theta_3,
            "smoothness": smoothness,
            "symmetry": symmetry,
            "raw": bend_raw,
            "final": blue_note_bend,
        },
        tube_warmth={
            "brightness": brightness,
            "energy": energy,
            "spectral_skewness": spectral_skewness,
            "raw": warmth_raw,
            "final": tube_warmth,
        },
    )
    return bridge, trace
