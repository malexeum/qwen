from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

DEFAULT_FALLBACK = 0.5
MODE_PRIORITY = ("structure", "gesture", "light", "material")


def clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return DEFAULT_FALLBACK
    if numeric != numeric:
        return DEFAULT_FALLBACK
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def get_feature_value(features: dict, dotted_path: str, fallback: float = DEFAULT_FALLBACK) -> float:
    current: Any = features
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return float(fallback)
        current = current[part]
    try:
        return clamp01(current)
    except (TypeError, ValueError):
        return float(fallback)


def aggregate_feature_values(values: Iterable[float | int | None]) -> float:
    cleaned = []
    for value in values:
        if value is None:
            continue
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    if not cleaned:
        return DEFAULT_FALLBACK
    return clamp01(sum(cleaned) / len(cleaned))


def weighted_contrast(
    values: Iterable[float | int | None],
    weights: Iterable[float],
    gain: float = 1.5,
    center: float = 0.5,
) -> float:
    cleaned = []
    for value, weight in zip(values, weights):
        try:
            numeric = float(value)
            numeric_weight = float(weight)
        except (TypeError, ValueError):
            continue
        cleaned.append((numeric, numeric_weight))
    if not cleaned:
        return DEFAULT_FALLBACK
    total_weight = sum(weight for _, weight in cleaned)
    if total_weight <= 0.0:
        return DEFAULT_FALLBACK
    weighted_mean = sum(value * weight for value, weight in cleaned) / total_weight
    return clamp01(center + (weighted_mean - center) * gain)


def get_normalized_bpm(pulse: dict) -> float:
    return clamp01(get_feature_value(pulse, "bpm") / 220.0)


def expand_spectral_flatness(timbre: dict) -> float:
    value = max(get_feature_value(timbre, "spectral_flatness"), 1.0e-4)
    return clamp01((math.log10(value) + 4.0) / 2.0)


def invert(value: Any) -> float:
    return clamp01(1.0 - clamp01(value))


def build_musical_portrait(features: dict) -> dict:
    if not isinstance(features, dict):
        raise TypeError("features must be a dict")

    pulse = features.get("pulse", {})
    envelope = features.get("envelope", {})
    form = features.get("form", {})
    recurrence = features.get("recurrence", {})
    timbre = features.get("timbre", {})
    harmony = features.get("harmony", {})
    space = features.get("space", {})

    portrait = {
        "schema": "MusicalPortraitV1",
        "version": "v1.0.0",
        "artifact": {
            "track_id": str(features.get("artifact", {}).get("track_id", "unknown_track")),
            "source_feature_hash": str(features.get("artifact", {}).get("feature_hash", "unknown_hash")),
            "portrait_hash": "",
            "resolver_name": "musical_portrait_v1",
            "resolver_version": "v1.0.0",
            "created_at": str(features.get("artifact", {}).get("created_at", "1970-01-01T00:00:00Z")),
        },
        "identity_core": {
            "dominant_interpretation_mode": "structure",
            "secondary_interpretation_mode": "none",
            "identity_confidence": 0.5,
        },
        "profiles": {
            "pulse_profile": {
                "steadiness": weighted_contrast([
                    get_feature_value(pulse, "beat_confidence"),
                    get_feature_value(pulse, "pulse_regularity"),
                    get_feature_value(recurrence, "repetition_ratio"),
                ], [0.35, 0.4, 0.25]),
                "drive": weighted_contrast([
                    get_feature_value(pulse, "onset_density"),
                    get_feature_value(envelope, "attack_sharpness"),
                    get_feature_value(envelope, "macro_energy_arc"),
                    get_normalized_bpm(pulse),
                ], [0.35, 0.3, 0.15, 0.2], gain=3.2, center=0.3),
                "syncopation": get_feature_value(pulse, "syncopation_index"),
                "sparsity": aggregate_feature_values([
                    invert(get_feature_value(pulse, "onset_density")),
                    get_feature_value(envelope, "silence_ratio"),
                ]),
            },
            "gesture_profile": {
                "weight": weighted_contrast([
                    get_feature_value(envelope, "dynamic_range"),
                    get_feature_value(timbre, "roughness"),
                    get_feature_value(harmony, "dissonance_proxy"),
                ], [0.4, 0.4, 0.2]),
                "attack": weighted_contrast([
                    get_feature_value(envelope, "attack_sharpness"),
                    get_feature_value(pulse, "onset_density"),
                ], [0.65, 0.35]),
                "flow": aggregate_feature_values([
                    get_feature_value(envelope, "sustain_ratio"),
                    get_feature_value(harmony, "chroma_stability"),
                    invert(get_feature_value(timbre, "spectral_flux")),
                ]),
                "directionality": weighted_contrast([
                    get_feature_value(pulse, "pulse_regularity"),
                    get_feature_value(form, "climax_position"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                ], [0.25, 0.5, 0.25]),
            },
            "form_profile": {
                "structural_clarity": weighted_contrast([
                    clamp01(get_feature_value(form, "section_count") / 12.0),
                    get_feature_value(form, "section_contrast"),
                    get_feature_value(recurrence, "self_similarity"),
                ], [0.25, 0.45, 0.3]),
                "contrast": weighted_contrast([
                    get_feature_value(form, "section_contrast"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                    get_feature_value(envelope, "dynamic_range"),
                ], [0.45, 0.35, 0.2]),
                "climax_strength": aggregate_feature_values([
                    get_feature_value(form, "climax_position"),
                    get_feature_value(envelope, "macro_energy_arc"),
                ]),
                "return_strength": aggregate_feature_values([
                    get_feature_value(recurrence, "motif_return_strength"),
                    get_feature_value(recurrence, "self_similarity"),
                ]),
            },
            "material_profile": {
                "smoothness": aggregate_feature_values([
                    invert(get_feature_value(timbre, "roughness")),
                    get_feature_value(envelope, "sustain_ratio"),
                ]),
                "grain": weighted_contrast([
                    get_feature_value(timbre, "roughness"),
                    get_feature_value(timbre, "spectral_flux"),
                    expand_spectral_flatness(timbre),
                    get_feature_value(timbre, "brightness"),
                ], [0.25, 0.15, 0.5, 0.1]),
                "erosion": aggregate_feature_values([
                    get_feature_value(timbre, "spectral_flatness"),
                    get_feature_value(harmony, "dissonance_proxy"),
                    get_feature_value(envelope, "attack_sharpness"),
                ]),
                "crystallinity": aggregate_feature_values([
                    get_feature_value(harmony, "tonal_stability"),
                    get_feature_value(harmony, "chroma_stability"),
                    get_feature_value(timbre, "brightness"),
                ]),
                "atmosphere": aggregate_feature_values([
                    get_feature_value(space, "reverb_proxy"),
                    get_feature_value(space, "depth_proxy"),
                    get_feature_value(envelope, "sustain_ratio"),
                ]),
            },
            "affect_profile": {
                "tension": weighted_contrast([
                    get_feature_value(harmony, "dissonance_proxy"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                    get_feature_value(form, "section_contrast"),
                ], [0.25, 0.35, 0.4]),
                "stability": aggregate_feature_values([
                    get_feature_value(harmony, "tonal_stability"),
                    get_feature_value(pulse, "pulse_regularity"),
                    get_feature_value(recurrence, "self_similarity"),
                ]),
                "luminosity": aggregate_feature_values([
                    get_feature_value(timbre, "brightness"),
                    get_feature_value(harmony, "harmonic_ratio"),
                ]),
                "dramatic_charge": aggregate_feature_values([
                    get_feature_value(envelope, "macro_energy_arc"),
                    get_feature_value(form, "climax_position"),
                    get_feature_value(form, "section_contrast"),
                ]),
            },
            "spatial_profile": {
                "width": get_feature_value(space, "stereo_width"),
                "depth": aggregate_feature_values([
                    get_feature_value(space, "depth_proxy"),
                    get_feature_value(space, "reverb_proxy"),
                ]),
                "resonance": aggregate_feature_values([
                    get_feature_value(space, "reverb_proxy"),
                    get_feature_value(envelope, "sustain_ratio"),
                ]),
                "openness": aggregate_feature_values([
                    get_feature_value(space, "spectral_bandwidth"),
                    get_feature_value(envelope, "silence_ratio"),
                    get_feature_value(timbre, "brightness"),
                ]),
            },
        },
    }

    dominant, secondary, confidence = resolve_interpretation_modes(portrait)
    portrait["identity_core"]["dominant_interpretation_mode"] = dominant
    portrait["identity_core"]["secondary_interpretation_mode"] = secondary
    portrait["identity_core"]["identity_confidence"] = clamp01(confidence)
    portrait["artifact"]["portrait_hash"] = compute_portrait_hash(portrait)
    return portrait


def resolve_interpretation_modes(portrait: dict) -> tuple[str, str, float]:
    if not isinstance(portrait, dict):
        raise TypeError("portrait must be a dict")

    profiles = portrait.get("profiles", {})
    form = profiles.get("form_profile", {})
    gesture = profiles.get("gesture_profile", {})
    material = profiles.get("material_profile", {})
    affect = profiles.get("affect_profile", {})
    spatial = profiles.get("spatial_profile", {})

    structural_clarity = clamp01(form.get("structural_clarity", DEFAULT_FALLBACK))
    return_strength = clamp01(form.get("return_strength", DEFAULT_FALLBACK))
    material_grain = clamp01(material.get("grain", DEFAULT_FALLBACK))
    scores = {
        "structure": clamp01(
            0.5 * structural_clarity
            + 0.3 * return_strength
            + 0.2 * clamp01(profiles.get("pulse_profile", {}).get("steadiness", DEFAULT_FALLBACK))
            - 0.2 * clamp01(form.get("contrast", DEFAULT_FALLBACK))
            + 0.8 * max(0.0, structural_clarity - 0.3)
        ),
        "gesture": clamp01(
            0.45 * clamp01(gesture.get("attack", DEFAULT_FALLBACK))
            + 0.35 * clamp01(gesture.get("directionality", DEFAULT_FALLBACK))
            + 0.2 * clamp01(profiles.get("pulse_profile", {}).get("drive", DEFAULT_FALLBACK))
        ),
        "light": weighted_contrast([
            spatial.get("resonance", DEFAULT_FALLBACK),
            material.get("atmosphere", DEFAULT_FALLBACK),
            affect.get("luminosity", DEFAULT_FALLBACK),
        ], [0.4, 0.35, 0.25]),
        "material": clamp01(
            0.65 * material_grain
            + 0.2 * clamp01(material.get("erosion", DEFAULT_FALLBACK))
            + 0.15 * clamp01(affect.get("tension", DEFAULT_FALLBACK))
        ),
    }

    ranked = sorted(scores.items(), key=lambda item: (item[1], -MODE_PRIORITY.index(item[0])), reverse=True)
    dominant = ranked[0][0]
    score_gap = ranked[0][1] - ranked[1][1]
    secondary = ranked[1][0] if score_gap <= 0.35 else "none"
    confidence = 0.5 + 0.45 * clamp01(score_gap)
    return dominant, secondary, clamp01(confidence)


def compute_portrait_hash(portrait: dict) -> str:
    payload_items = []
    for profile_name, profile in sorted(portrait.get("profiles", {}).items()):
        for field_name, value in sorted(profile.items()):
            payload_items.append(f"{profile_name}.{field_name}:{clamp01(value)}")
    payload = json.dumps(payload_items, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
