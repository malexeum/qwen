"""
tests/test_cb31_c0_harness.py

C0 gate: verify that e4_render_harness uses GeneratorRuntime as the
authoritative source of generator_stack, and that layer_id / generator_id
are correctly propagated into provenance after runtime integration.

All tests are unit-level: no PNG files are written, no disk I/O beyond
what resolve_render_params and GeneratorRuntime itself need.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.style_engine.engine import resolve_render_params
from lib.style_engine.generator_runtime import (
    GeneratorRuntime,
    ResolvedGeneratorLayer,
    RenderResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NEUTRAL_PERCEPTUAL = {
    "energy": 0.5,
    "tension": 0.5,
    "density": 0.5,
    "brightness": 0.5,
    "stability": 0.5,
    "smoothness": 0.5,
    "repetition": 0.5,
    "section_complexity": 0.5,
    "noise_proxy": 0.5,
    "macro_shape_hint": "balanced",
    **{f"harmony_theta_{i}": 0.5 for i in range(8)},
}

DEFAULT_PRESET = {
    "id": "c0_test",
    "complexity": 0.5,
    "symmetry": 0.5,
    "density": 0.5,
    "noise": 0.5,
    "motion": 0.5,
}

SINGLE_LAYER_COMPOSITION = {
    "layers": [
        {"id": "test_layer_0", "builder": "julia_orbit_trap", "weight": 1.0}
    ]
}

TWO_LAYER_COMPOSITION = {
    "layers": [
        {"id": "test_layer_0", "builder": "julia_orbit_trap", "weight": 0.6},
        {"id": "test_layer_1", "builder": "orbit_ifs_multi_trap", "weight": 0.4},
    ]
}


def make_render_params(profile_slug: str = "jazz"):
    render_params, style_profile, interp_profile = resolve_render_params(
        project_id="c0_test",
        analysis_id="fixture_c0",
        perceptual=NEUTRAL_PERCEPTUAL,
        style_profile_slug=profile_slug,
        interpretation_profile_slug="default",
        user_preset=DEFAULT_PRESET,
        strict_theta=True,
    )
    return render_params


# ---------------------------------------------------------------------------
# TC1: generator_stack is a non-empty list of strings (not a static literal)
# ---------------------------------------------------------------------------

class TestGeneratorStackIsRuntimeJournal:
    def test_stack_is_list_of_strings(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, SINGLE_LAYER_COMPOSITION)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert isinstance(result.generator_stack, list)
        assert len(result.generator_stack) > 0
        assert all(isinstance(s, str) for s in result.generator_stack)

    def test_stack_contains_called_builder(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, SINGLE_LAYER_COMPOSITION)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert "julia_orbit_trap" in result.generator_stack

    def test_stack_is_not_static_harness_string(self):
        """Forbidden pattern from pre-C0: static 'e4_render_harness' literal."""
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, SINGLE_LAYER_COMPOSITION)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        for entry in result.generator_stack:
            assert "e4_render_harness" not in entry, (
                f"generator_stack must not contain static harness literal, got: {entry!r}"
            )

    def test_two_layer_stack_length(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, TWO_LAYER_COMPOSITION)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert len(result.generator_stack) == 2

    def test_two_layer_stack_order(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, TWO_LAYER_COMPOSITION)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert result.generator_stack[0] == "julia_orbit_trap"
        assert result.generator_stack[1] == "orbit_ifs_multi_trap"


# ---------------------------------------------------------------------------
# TC2: layer_id and generator_id are populated in ResolvedGeneratorLayer
# ---------------------------------------------------------------------------

class TestLayerIdGeneratorIdInResolvedLayer:
    def test_layer_id_matches_composition(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, SINGLE_LAYER_COMPOSITION)

        assert layers[0].layer_id == "test_layer_0"

    def test_generator_id_equals_builder(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, SINGLE_LAYER_COMPOSITION)

        assert layers[0].generator_id == layers[0].builder
        assert layers[0].generator_id == "julia_orbit_trap"

    def test_two_layers_have_distinct_layer_ids(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params()
        layers = runtime.resolve_stack("jazz", render_params, TWO_LAYER_COMPOSITION)

        ids = [l.layer_id for l in layers]
        assert len(set(ids)) == len(ids), f"layer_ids must be unique, got: {ids}"

    def test_generator_id_never_none_after_resolve(self):
        runtime = GeneratorRuntime()
        render_params = make_render_params("ambient")
        layers = runtime.resolve_stack("ambient", render_params, TWO_LAYER_COMPOSITION)

        for layer in layers:
            assert layer.generator_id is not None
            assert layer.generator_id != ""


# ---------------------------------------------------------------------------
# TC3: visual_composition_profiles.yaml builders are valid
# ---------------------------------------------------------------------------

class TestCompositionProfileYAML:
    def test_yaml_builders_are_in_registry(self):
        """Every builder in visual_composition_profiles.yaml must exist in
        GeneratorRuntime._BUILDER_REGISTRY."""
        import yaml
        yaml_path = (
            Path(__file__).resolve().parents[1]
            / "lib/style_engine/configs/visual_composition_profiles.yaml"
        )
        assert yaml_path.exists(), f"Missing: {yaml_path}"
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        from lib.style_engine.generator_runtime import _BUILDER_REGISTRY
        profiles = data.get("profiles", {})
        assert profiles, "visual_composition_profiles.yaml has no profiles"

        for slug, profile in profiles.items():
            for layer in profile.get("layers", []):
                builder = layer["builder"]
                assert builder in _BUILDER_REGISTRY, (
                    f"Profile '{slug}': builder '{builder}' not in "
                    f"_BUILDER_REGISTRY. Available: {sorted(_BUILDER_REGISTRY)}"
                )

    def test_all_canonical_slugs_have_composition(self):
        import yaml
        yaml_path = (
            Path(__file__).resolve().parents[1]
            / "lib/style_engine/configs/visual_composition_profiles.yaml"
        )
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        CANONICAL = {"ambient", "blues_jazz", "jazz", "classical",
                     "electronic", "rock", "pop", "default"}
        profiles = set(data.get("profiles", {}).keys())
        missing = CANONICAL - profiles
        assert not missing, f"Missing canonical slugs in composition YAML: {missing}"

    def test_palette_identity_in_composition_yaml(self):
        """palette field in composition YAML must match registry contract."""
        import yaml
        yaml_path = (
            Path(__file__).resolve().parents[1]
            / "lib/style_engine/configs/visual_composition_profiles.yaml"
        )
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        EXPECTED = {
            "ambient":    "lunar_mist",
            "blues_jazz": "warm_midnight",
            "jazz":       "nocturne_amber",
            "classical":  "ivory_cobalt",
            "electronic": "neon_dark",
            "rock":       "dark_saturated",
            "pop":        "vivid_light",
            "default":    "neutral_noir",
        }
        profiles = data.get("profiles", {})
        for slug, expected_palette in EXPECTED.items():
            actual = profiles.get(slug, {}).get("palette")
            assert actual == expected_palette, (
                f"Profile '{slug}': expected palette '{expected_palette}', "
                f"got '{actual}'"
            )
