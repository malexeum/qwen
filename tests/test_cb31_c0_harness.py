"""
tests/test_cb31_c0_harness.py

C0/C1 gate: verify that e4_render_harness uses GeneratorRuntime as the
authoritative source of generator_stack, loads the canonical
visual_composition_profiles.yaml by default, and that layer_id /
generator_id are correctly propagated into provenance after integration.

All tests are unit-level: no PNG files are written, no disk I/O beyond
what resolve_render_params and GeneratorRuntime itself need.
"""
from __future__ import annotations

import sys
import hashlib
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.style_engine.engine import resolve_render_params
from lib.style_engine.generator_runtime import (
    GeneratorRuntime,
    ResolvedGeneratorLayer,
    RenderResult,
    _BUILDER_REGISTRY,
)
from lib.style_engine.e4_render_harness import (
    CANONICAL_COMPOSITION_YAML,
    ValidationError,
    load_composition_profiles,
    get_composition_for_slug,
    _DEV_COMPOSITION,
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
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
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
        assert CANONICAL_COMPOSITION_YAML.exists(), (
            f"Missing canonical YAML: {CANONICAL_COMPOSITION_YAML}"
        )
        with open(CANONICAL_COMPOSITION_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)

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
        with open(CANONICAL_COMPOSITION_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        CANONICAL = {"ambient", "blues_jazz", "jazz", "classical",
                     "electronic", "rock", "pop", "default"}
        profiles = set(data.get("profiles", {}).keys())
        missing = CANONICAL - profiles
        assert not missing, f"Missing canonical slugs in composition YAML: {missing}"

    def test_palette_identity_in_composition_yaml(self):
        with open(CANONICAL_COMPOSITION_YAML, encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
# TC4 (C1): harness loads canonical composition by default
# ---------------------------------------------------------------------------

class TestC1CanonicalCompositionLoading:

    def test_harness_loads_canonical_composition_by_default(self):
        """CANONICAL_COMPOSITION_YAML must point to the real YAML and be loadable."""
        assert CANONICAL_COMPOSITION_YAML.exists(), (
            f"CANONICAL_COMPOSITION_YAML does not exist: {CANONICAL_COMPOSITION_YAML}"
        )
        profiles, yaml_hash = load_composition_profiles(CANONICAL_COMPOSITION_YAML)
        assert isinstance(profiles, dict)
        assert len(profiles) >= 8
        assert yaml_hash.startswith("sha256:")

    def test_rock_runtime_stack_matches_yaml(self):
        """Rock profile: chaotic_scattering_basins first, duffing_lyapunov_map second."""
        profiles, _ = load_composition_profiles(CANONICAL_COMPOSITION_YAML)
        composition = get_composition_for_slug(profiles, "rock")

        runtime = GeneratorRuntime()
        render_params = make_render_params("rock")
        layers = runtime.resolve_stack("rock", render_params, composition)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert result.generator_stack[0] == "chaotic_scattering_basins", (
            f"rock layer 0 must be chaotic_scattering_basins, got: {result.generator_stack}"
        )
        assert result.generator_stack[1] == "duffing_lyapunov_map", (
            f"rock layer 1 must be duffing_lyapunov_map, got: {result.generator_stack}"
        )

    def test_ambient_runtime_stack_matches_yaml(self):
        """Ambient profile: julia_orbit_trap first, orbit_ifs_multi_trap second."""
        profiles, _ = load_composition_profiles(CANONICAL_COMPOSITION_YAML)
        composition = get_composition_for_slug(profiles, "ambient")

        runtime = GeneratorRuntime()
        render_params = make_render_params("ambient")
        layers = runtime.resolve_stack("ambient", render_params, composition)
        result = runtime.render(layers, seed=render_params.variation_seed, width=64, height=64)

        assert result.generator_stack[0] == "julia_orbit_trap", (
            f"ambient layer 0 must be julia_orbit_trap, got: {result.generator_stack}"
        )
        assert result.generator_stack[1] == "orbit_ifs_multi_trap", (
            f"ambient layer 1 must be orbit_ifs_multi_trap, got: {result.generator_stack}"
        )

    def test_missing_composition_slug_raises(self):
        """Unknown slug must raise ValidationError, no default fallback."""
        profiles, _ = load_composition_profiles(CANONICAL_COMPOSITION_YAML)

        with pytest.raises(ValidationError) as exc_info:
            get_composition_for_slug(profiles, "nonexistent_genre_xyz")

        assert "nonexistent_genre_xyz" in str(exc_info.value)
        # Must NOT fall back silently
        assert "_DEFAULT_COMPOSITION" not in str(exc_info.value)

    def test_provenance_contains_composition_config_hash(self):
        """composition_config_hash must be sha256 of the actual loaded YAML bytes."""
        profiles, yaml_hash = load_composition_profiles(CANONICAL_COMPOSITION_YAML)

        # Verify hash is reproducible
        with open(CANONICAL_COMPOSITION_YAML, "rb") as f:
            raw = f.read()
        expected_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"

        assert yaml_hash == expected_hash, (
            f"yaml_hash mismatch: got {yaml_hash!r}, expected {expected_hash!r}"
        )
        assert len(yaml_hash) == len("sha256:") + 64  # sha256 hex = 64 chars

    def test_rock_and_ambient_stacks_differ(self):
        """End-to-end: rock and ambient stacks differ in builder identity and order."""
        profiles, _ = load_composition_profiles(CANONICAL_COMPOSITION_YAML)
        runtime = GeneratorRuntime()

        rock_composition = get_composition_for_slug(profiles, "rock")
        rock_params = make_render_params("rock")
        rock_layers = runtime.resolve_stack("rock", rock_params, rock_composition)
        rock_result = runtime.render(rock_layers, seed=rock_params.variation_seed, width=64, height=64)

        ambient_composition = get_composition_for_slug(profiles, "ambient")
        ambient_params = make_render_params("ambient")
        ambient_layers = runtime.resolve_stack("ambient", ambient_params, ambient_composition)
        ambient_result = runtime.render(ambient_layers, seed=ambient_params.variation_seed, width=64, height=64)

        assert rock_result.generator_stack != ambient_result.generator_stack, (
            f"rock and ambient must have different generator stacks. "
            f"rock={rock_result.generator_stack}, ambient={ambient_result.generator_stack}"
        )
        # Rock must start with scattering, ambient with julia
        assert rock_result.generator_stack[0] != ambient_result.generator_stack[0]
