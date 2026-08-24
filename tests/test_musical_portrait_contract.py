from __future__ import annotations

import inspect

import yaml

from lib.style_engine.musical_portrait import (
    MusicalPortrait,
    resolve_macro_params,
    resolve_mode,
)


ROOT = "configs"


def _load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_portrait_axes_have_explicit_sources_and_fallbacks():
    portrait_cfg = _load_yaml(f"{ROOT}/musical_portrait_v1.yaml")
    axes = portrait_cfg["axes"]
    for group_name, group in axes.items():
        for axis_name, spec in group.items():
            assert "range" in spec
            assert "formula_version" in spec
            assert "required_raw_inputs" in spec
            assert spec["required_raw_inputs"]
            assert "neutral_fallback" in spec
            assert "trace_fields" in spec
            assert spec["trace_fields"]
            assert spec["range"] == [0.0, 1.0]


def test_music_features_v2_contains_only_approved_categories():
    features = _load_yaml(f"{ROOT}/music_features_v2.yaml")
    approved_categories = {
        "pulse",
        "envelope",
        "form",
        "recurrence",
        "timbre",
        "harmony",
        "space",
    }
    assert set(features["categories"]) == approved_categories

    expected = {
        "pulse": [
            "bpm",
            "beat_confidence",
            "beat_regularity",
            "onset_density",
        ],
        "envelope": [
            "dynamic_range",
            "attack_ratio",
            "sustain_ratio",
            "energy_arc",
        ],
        "form": [
            "section_boundaries",
            "section_count",
            "section_duration_entropy",
            "section_contrast",
            "climax_position",
        ],
        "recurrence": [
            "self_similarity",
            "repetition_strength",
            "motif_recurrence",
            "return_ratio",
        ],
        "timbre": [
            "spectral_centroid",
            "spectral_rolloff",
            "spectral_flatness",
            "spectral_flux",
            "roughness",
        ],
        "harmony": [
            "harmonic_ratio",
            "chroma_stability",
            "harmonic_change_rate",
            "tonal_stability",
        ],
        "space": [
            "spectral_bandwidth",
            "stereo_width_if_available",
            "reverb_proxy",
        ],
    }

    assert set(features["fields"]) == approved_categories
    for category, field_names in expected.items():
        assert list(features["fields"][category].keys()) == field_names
        for field_name, field_meta in features["fields"][category].items():
            assert "type" in field_meta
            assert "description" in field_meta
            if field_meta["type"] != "list":
                assert "range" in field_meta


def test_mode_selection_and_macro_resolution_are_deterministic_without_seed():
    assert "seed" not in inspect.signature(resolve_mode).parameters
    assert "seed" not in inspect.signature(resolve_macro_params).parameters

    portrait = MusicalPortrait(
        pulse_regularity=0.74,
        pulse_urgency=0.61,
        pulse_impact=0.68,
        gesture_continuity=0.42,
        gesture_angularity=0.69,
        gesture_propulsion=0.73,
        form_complexity=0.78,
        form_recurrence=0.55,
        form_contrast=0.71,
        form_climax_position=0.43,
        material_roughness=0.58,
        material_brightness=0.75,
        material_density=0.79,
        material_sustain=0.62,
        affect_tension=0.66,
        affect_stability=0.47,
        affect_openness=0.58,
    )

    grammar = _load_yaml(f"{ROOT}/rock_composition_grammar_v8.yaml")
    mode_a = resolve_mode(portrait)
    macro_a = resolve_macro_params(portrait, mode_a)

    assert mode_a in {"monolithic", "kinetic_break", "recursive_grove", "fragmented_signal", "open_horizon"}

    normalized_names = {
        "junction",
        "flow_angle",
        "global_symmetry",
        "line_continuity",
        "density",
        "materiality",
        "palette_usage_ratio",
    }
    integer_ranges = {
        "competing_centers": (1, 6),
        "branch_count": (4, 15),
        "recursion_levels": (1, 6),
    }

    for name in normalized_names:
        value = macro_a[name]
        assert isinstance(value, (int, float))
        assert 0.0 <= float(value) <= 1.0

    for name, (low, high) in integer_ranges.items():
        value = macro_a[name]
        assert isinstance(value, int)
        assert low <= value <= high

    assert "modes" in grammar
    assert mode_a in grammar["modes"]
    portrait_copy = MusicalPortrait(**portrait.as_dict())
    assert resolve_mode(portrait_copy) == mode_a
    assert resolve_macro_params(portrait_copy, mode_a) == macro_a


def test_contrasting_portraits_select_different_modes_and_ignore_seed():
    calm = MusicalPortrait(
        pulse_regularity=0.35,
        pulse_urgency=0.22,
        pulse_impact=0.28,
        gesture_continuity=0.65,
        gesture_angularity=0.25,
        gesture_propulsion=0.22,
        form_complexity=0.30,
        form_recurrence=0.75,
        form_contrast=0.20,
        form_climax_position=0.36,
        material_roughness=0.20,
        material_brightness=0.30,
        material_density=0.28,
        material_sustain=0.70,
        affect_tension=0.20,
        affect_stability=0.80,
        affect_openness=0.68,
    )
    storm = MusicalPortrait(
        pulse_regularity=0.72,
        pulse_urgency=0.88,
        pulse_impact=0.81,
        gesture_continuity=0.38,
        gesture_angularity=0.76,
        gesture_propulsion=0.82,
        form_complexity=0.90,
        form_recurrence=0.22,
        form_contrast=0.87,
        form_climax_position=0.72,
        material_roughness=0.80,
        material_brightness=0.90,
        material_density=0.86,
        material_sustain=0.42,
        affect_tension=0.84,
        affect_stability=0.35,
        affect_openness=0.38,
    )

    calm_mode = resolve_mode(calm)
    storm_mode = resolve_mode(storm)
    assert calm_mode != storm_mode

    calm_macro = resolve_macro_params(calm, calm_mode)
    storm_macro = resolve_macro_params(storm, storm_mode)
    assert calm_macro != storm_macro

    assert resolve_mode(calm) == calm_mode
    assert resolve_mode(storm) == storm_mode


def test_grammar_yaml_has_selection_rules_and_guardrails():
    grammar = _load_yaml(f"{ROOT}/rock_composition_grammar_v8.yaml")
    assert "modes" in grammar
    assert "open_horizon" in grammar["modes"]
    assert set(grammar["modes"]) >= {
        "monolithic",
        "kinetic_break",
        "recursive_grove",
        "fragmented_signal",
        "open_horizon",
    }
    for mode_name, mode_cfg in grammar["modes"].items():
        assert "selection_rule" in mode_cfg
        assert "macro_params" in mode_cfg
        assert "guardrails" in mode_cfg
        assert mode_cfg["guardrails"]
