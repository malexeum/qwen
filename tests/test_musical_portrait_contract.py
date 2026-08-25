from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from lib.style_engine.musical_portrait import (
    build_musical_portrait,
    compute_portrait_hash,
    resolve_interpretation_modes,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "lib" / "style_engine" / "configs"


def _load_yaml(name: str):
    with (CONFIG_DIR / name).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _fixture_rigid_pulse():
    return {
        "artifact": {"track_id": "rigid_pulse_fixture", "feature_hash": "hash_rigid", "created_at": "2026-01-01T00:00:00Z"},
        "pulse": {
            "beat_confidence": 0.92,
            "pulse_regularity": 0.88,
            "onset_density": 0.86,
            "syncopation_index": 0.22,
        },
        "envelope": {
            "dynamic_range": 0.82,
            "attack_sharpness": 0.78,
            "sustain_ratio": 0.33,
            "macro_energy_arc": 0.76,
            "silence_ratio": 0.12,
        },
        "form": {
            "section_count": 5,
            "section_contrast": 0.8,
            "climax_position": 0.56,
        },
        "recurrence": {
            "self_similarity": 0.75,
            "motif_return_strength": 0.7,
            "repetition_ratio": 0.74,
        },
        "timbre": {
            "roughness": 0.38,
            "spectral_flux": 0.4,
            "brightness": 0.62,
            "spectral_flatness": 0.34,
        },
        "harmony": {
            "dissonance_proxy": 0.29,
            "harmonic_change_rate": 0.34,
            "chroma_stability": 0.7,
            "tonal_stability": 0.76,
            "harmonic_ratio": 0.68,
        },
        "space": {
            "stereo_width": 0.48,
            "reverb_proxy": 0.38,
            "depth_proxy": 0.4,
            "spectral_bandwidth": 0.46,
        },
    }


def _fixture_ambient_light():
    return {
        "artifact": {"track_id": "ambient_light_fixture", "feature_hash": "hash_ambient", "created_at": "2026-01-02T00:00:00Z"},
        "pulse": {
            "beat_confidence": 0.64,
            "pulse_regularity": 0.58,
            "onset_density": 0.42,
            "syncopation_index": 0.18,
        },
        "envelope": {
            "dynamic_range": 0.38,
            "attack_sharpness": 0.24,
            "sustain_ratio": 0.8,
            "macro_energy_arc": 0.46,
            "silence_ratio": 0.28,
        },
        "form": {
            "section_count": 4,
            "section_contrast": 0.34,
            "climax_position": 0.42,
        },
        "recurrence": {
            "self_similarity": 0.72,
            "motif_return_strength": 0.66,
            "repetition_ratio": 0.64,
        },
        "timbre": {
            "roughness": 0.18,
            "spectral_flux": 0.18,
            "brightness": 0.78,
            "spectral_flatness": 0.2,
        },
        "harmony": {
            "dissonance_proxy": 0.14,
            "harmonic_change_rate": 0.2,
            "chroma_stability": 0.82,
            "tonal_stability": 0.88,
            "harmonic_ratio": 0.84,
        },
        "space": {
            "stereo_width": 0.72,
            "reverb_proxy": 0.9,
            "depth_proxy": 0.82,
            "spectral_bandwidth": 0.78,
        },
    }


def _fixture_eroded_material():
    return {
        "artifact": {"track_id": "eroded_material_fixture", "feature_hash": "hash_eroded", "created_at": "2026-01-03T00:00:00Z"},
        "pulse": {
            "beat_confidence": 0.52,
            "pulse_regularity": 0.4,
            "onset_density": 0.88,
            "syncopation_index": 0.81,
        },
        "envelope": {
            "dynamic_range": 0.76,
            "attack_sharpness": 0.9,
            "sustain_ratio": 0.2,
            "macro_energy_arc": 0.82,
            "silence_ratio": 0.14,
        },
        "form": {
            "section_count": 6,
            "section_contrast": 0.88,
            "climax_position": 0.72,
        },
        "recurrence": {
            "self_similarity": 0.3,
            "motif_return_strength": 0.34,
            "repetition_ratio": 0.32,
        },
        "timbre": {
            "roughness": 0.92,
            "spectral_flux": 0.88,
            "brightness": 0.46,
            "spectral_flatness": 0.82,
        },
        "harmony": {
            "dissonance_proxy": 0.88,
            "harmonic_change_rate": 0.91,
            "chroma_stability": 0.25,
            "tonal_stability": 0.18,
            "harmonic_ratio": 0.34,
        },
        "space": {
            "stereo_width": 0.38,
            "reverb_proxy": 0.2,
            "depth_proxy": 0.18,
            "spectral_bandwidth": 0.52,
        },
    }


def test_music_features_v2_schema_contract():
    schema = _load_yaml("music_features_v2.yaml")
    assert schema["schema"] == "MusicFeaturesV2"
    assert schema["version"] == "v2.0.0"
    assert schema["artifact"]["track_id"] == "track_id"
    assert set(schema["feature_groups"]) == {"pulse", "envelope", "form", "recurrence", "timbre", "harmony", "space"}

    for group_name, fields in schema["feature_groups"].items():
        assert fields
        for field_name, meta in fields.items():
            assert "type" in meta
            assert "description" in meta
            assert "normalized" in meta or "range_hint" in meta
            if meta.get("normalized") is True:
                assert meta.get("range_hint") or "range" in meta


def test_musical_portrait_v1_schema_contract():
    schema = _load_yaml("musical_portrait_v1.yaml")
    assert schema["schema"] == "MusicalPortraitV1"
    assert schema["version"] == "v1.0.0"
    assert set(schema["identity_core"]) >= {"dominant_interpretation_mode", "secondary_interpretation_mode", "identity_confidence"}
    for profile_name, profile in schema["profiles"].items():
        assert profile
        for field_name, field_meta in profile.items():
            assert "range" in field_meta
            assert "mapping_rules" in field_meta
            assert field_meta["mapping_rules"]["from"]


def test_build_musical_portrait_is_deterministic_and_bounded():
    fixture = _fixture_rigid_pulse()
    portrait = build_musical_portrait(fixture)
    assert portrait["schema"] == "MusicalPortraitV1"
    assert portrait["artifact"]["track_id"] == "rigid_pulse_fixture"
    for profile_name, profile in portrait["profiles"].items():
        for field_name, value in profile.items():
            assert 0.0 <= float(value) <= 1.0, (profile_name, field_name, value)
    assert portrait["artifact"]["portrait_hash"]
    assert compute_portrait_hash(portrait) == portrait["artifact"]["portrait_hash"]

    portrait_again = build_musical_portrait(fixture)
    assert portrait_again == portrait
    assert portrait["identity_core"]["dominant_interpretation_mode"] == "structure"


def test_mode_selection_is_deterministic_and_seed_free():
    signature = inspect.signature(resolve_interpretation_modes)
    assert "seed" not in signature.parameters

    fixture_a = _fixture_ambient_light()
    fixture_b = _fixture_eroded_material()

    portrait_a = build_musical_portrait(fixture_a)
    portrait_b = build_musical_portrait(fixture_b)

    mode_a_1, secondary_a_1, confidence_a_1 = resolve_interpretation_modes(portrait_a)
    mode_a_2, secondary_a_2, confidence_a_2 = resolve_interpretation_modes(portrait_a)
    assert (mode_a_1, secondary_a_1, confidence_a_1) == (mode_a_2, secondary_a_2, confidence_a_2)

    mode_b_1, secondary_b_1, confidence_b_1 = resolve_interpretation_modes(portrait_b)
    assert mode_b_1 in {"structure", "gesture", "light", "material"}
    assert 0.0 <= confidence_b_1 <= 1.0
    assert (mode_a_1, secondary_a_1) != (mode_b_1, secondary_b_1)


def test_synthetic_fixtures_have_distinct_modes_and_profile_values():
    fixtures = {
        "rigid": _fixture_rigid_pulse(),
        "ambient": _fixture_ambient_light(),
        "eroded": _fixture_eroded_material(),
    }

    portraits = {name: build_musical_portrait(data) for name, data in fixtures.items()}
    modes = {name: resolve_interpretation_modes(data)[0] for name, data in portraits.items()}

    assert len(set(modes.values())) >= 2
    assert portraits["rigid"]["profiles"]["form_profile"]["structural_clarity"] > portraits["ambient"]["profiles"]["form_profile"]["structural_clarity"]
    assert portraits["ambient"]["profiles"]["spatial_profile"]["resonance"] > portraits["eroded"]["profiles"]["spatial_profile"]["resonance"]
    assert portraits["eroded"]["profiles"]["material_profile"]["grain"] > portraits["ambient"]["profiles"]["material_profile"]["grain"]
