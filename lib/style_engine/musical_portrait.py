from __future__ import annotations

import hashlib
import json
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
                "steadiness": aggregate_feature_values([
                    get_feature_value(pulse, "beat_confidence"),
                    get_feature_value(pulse, "pulse_regularity"),
                    get_feature_value(recurrence, "repetition_ratio"),
                ]),
                "drive": aggregate_feature_values([
                    get_feature_value(pulse, "onset_density"),
                    get_feature_value(envelope, "attack_sharpness"),
                    get_feature_value(envelope, "macro_energy_arc"),
                ]),
                "syncopation": get_feature_value(pulse, "syncopation_index"),
                "sparsity": aggregate_feature_values([
                    invert(get_feature_value(pulse, "onset_density")),
                    get_feature_value(envelope, "silence_ratio"),
                ]),
            },
            "gesture_profile": {
                "weight": aggregate_feature_values([
                    get_feature_value(envelope, "dynamic_range"),
                    get_feature_value(timbre, "roughness"),
                    get_feature_value(harmony, "dissonance_proxy"),
                ]),
                "attack": aggregate_feature_values([
                    get_feature_value(envelope, "attack_sharpness"),
                    get_feature_value(pulse, "onset_density"),
                ]),
                "flow": aggregate_feature_values([
                    get_feature_value(envelope, "sustain_ratio"),
                    get_feature_value(harmony, "chroma_stability"),
                    invert(get_feature_value(timbre, "spectral_flux")),
                ]),
                "directionality": aggregate_feature_values([
                    get_feature_value(pulse, "pulse_regularity"),
                    get_feature_value(form, "climax_position"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                ]),
            },
            "form_profile": {
                "structural_clarity": aggregate_feature_values([
                    get_feature_value(form, "section_count"),
                    get_feature_value(form, "section_contrast"),
                    get_feature_value(recurrence, "self_similarity"),
                ]),
                "contrast": aggregate_feature_values([
                    get_feature_value(form, "section_contrast"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                    get_feature_value(envelope, "dynamic_range"),
                ]),
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
                "grain": aggregate_feature_values([
                    get_feature_value(timbre, "roughness"),
                    get_feature_value(timbre, "spectral_flux"),
                    get_feature_value(timbre, "brightness"),
                ]),
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
                "tension": aggregate_feature_values([
                    get_feature_value(harmony, "dissonance_proxy"),
                    get_feature_value(harmony, "harmonic_change_rate"),
                    get_feature_value(form, "section_contrast"),
                ]),
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

    scores = {
        "structure": aggregate_feature_values([
            form.get("structural_clarity", DEFAULT_FALLBACK),
            form.get("return_strength", DEFAULT_FALLBACK),
        ]),
        "gesture": aggregate_feature_values([
            gesture.get("attack", DEFAULT_FALLBACK),
            gesture.get("directionality", DEFAULT_FALLBACK),
        ]),
        "light": aggregate_feature_values([
            spatial.get("resonance", DEFAULT_FALLBACK),
            material.get("atmosphere", DEFAULT_FALLBACK),
            affect.get("luminosity", DEFAULT_FALLBACK),
        ]),
        "material": aggregate_feature_values([
            material.get("grain", DEFAULT_FALLBACK),
            material.get("erosion", DEFAULT_FALLBACK),
            affect.get("tension", DEFAULT_FALLBACK),
        ]),
    }

    ranked = sorted(scores.items(), key=lambda item: (item[1], -MODE_PRIORITY.index(item[0])), reverse=True)
    dominant = ranked[0][0]
    secondary = next((name for name, _ in ranked[1:] if name != dominant), "none")
    return dominant, secondary, clamp01(ranked[0][1])


def compute_portrait_hash(portrait: dict) -> str:
    payload_items = []
    for profile_name, profile in sorted(portrait.get("profiles", {}).items()):
        for field_name, value in sorted(profile.items()):
            payload_items.append(f"{profile_name}.{field_name}:{clamp01(value)}")
    payload = json.dumps(payload_items, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
