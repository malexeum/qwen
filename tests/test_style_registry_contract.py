"""
tests/test_style_registry_contract.py

T1–T5: Контракт canonical style registry.

Проверяет:
  T1. Все восемь canonical genre slugs присутствуют в registry.
  T2. Каждый slug имеет правильный canonical palette.
  T3. Top-level schema: все обязательные поля не None, palette != default_dark.
  T4. Resolver smoke: resolve_render_params успешно для всех canonical slugs.
  T5. Идентичность jazz / blues_jazz — палитры разные.

Запуск:
  pytest tests/test_style_registry_contract.py -v
"""
from __future__ import annotations

import pytest
from lib.style_engine.config_loader import load_style_profiles
from lib.style_engine.engine import resolve_render_params

# ---------------------------------------------------------------------------
# Canonical contracts
# ---------------------------------------------------------------------------

EXPECTED_CANONICAL = {
    "ambient",
    "blues_jazz",
    "jazz",
    "classical",
    "electronic",
    "rock",
    "pop",
    "default",
}

EXPECTED_PALETTES = {
    "ambient":    "lunar_mist",
    "blues_jazz": "warm_midnight",
    "jazz":       "nocturne_amber",
    "classical":  "ivory_cobalt",
    "electronic": "neon_dark",
    "rock":       "dark_saturated",
    "pop":        "vivid_light",
    "default":    "neutral_noir",
}

REQUIRED_FIELDS = [
    "palette",
    "contrast",
    "density",
    "motion_intensity",
    "noise_level",
    "symmetry_bias",
    "complexity_bias",
]


def _neutral_perceptual():
    return {
        "energy":             0.5,
        "tension":            0.5,
        "density":            0.5,
        "brightness":         0.5,
        "stability":          0.5,
        "smoothness":         0.5,
        "repetition":         0.5,
        "section_complexity": 0.5,
        "noise_proxy":        0.5,
        "macro_shape_hint":   "unknown",
        "harmony_theta_0":    0.5,
        "harmony_theta_1":    0.5,
        "harmony_theta_2":    0.5,
        "harmony_theta_3":    0.5,
        "harmony_theta_4":    0.5,
        "harmony_theta_5":    0.5,
        "harmony_theta_6":    0.5,
        "harmony_theta_7":    0.5,
    }


def _neutral_preset():
    return {
        "id": "preset_contract_test",
        "complexity": 0.5,
        "symmetry": 0.5,
        "density": 0.5,
        "noise": 0.5,
        "motion": 0.5,
    }


# ---------------------------------------------------------------------------
# T1: Полный canonical registry
# ---------------------------------------------------------------------------

class TestT1FullRegistry:

    def test_all_canonical_slugs_present(self):
        """Все восемь canonical genre slugs присутствуют в registry."""
        registry = load_style_profiles()
        missing = EXPECTED_CANONICAL - set(registry.keys())
        assert not missing, (
            f"Отсутствуют в canonical registry: {sorted(missing)}. "
            f"Присутствуют: {sorted(registry.keys())}"
        )


# ---------------------------------------------------------------------------
# T2: Palette identity
# ---------------------------------------------------------------------------

class TestT2PaletteIdentity:

    @pytest.mark.parametrize("slug,expected_palette", list(EXPECTED_PALETTES.items()))
    def test_palette_matches_contract(self, slug, expected_palette):
        """Каждый canonical slug имеет правильную canonical palette."""
        registry = load_style_profiles()
        assert slug in registry, f"Slug '{slug}' отсутствует в registry"
        actual = registry[slug].palette
        assert actual == expected_palette, (
            f"{slug}.palette = '{actual}', ожидался '{expected_palette}'"
        )


# ---------------------------------------------------------------------------
# T3: Top-level schema
# ---------------------------------------------------------------------------

class TestT3TopLevelSchema:

    @pytest.mark.parametrize("slug", sorted(EXPECTED_CANONICAL))
    def test_required_fields_not_none(self, slug):
        """Все обязательные поля присутствуют и не None."""
        registry = load_style_profiles()
        assert slug in registry, f"Slug '{slug}' отсутствует в registry"
        profile = registry[slug]
        for field in REQUIRED_FIELDS:
            val = getattr(profile, field, None)
            assert val is not None, (
                f"{slug}.{field} is None — возможно legacy base_params schema."
            )

    @pytest.mark.parametrize("slug", sorted(EXPECTED_CANONICAL))
    def test_palette_is_not_fallback(self, slug):
        """Ни один canonical profile не должен иметь fallback palette 'default_dark'."""
        registry = load_style_profiles()
        assert slug in registry
        palette = registry[slug].palette
        assert palette != "default_dark", (
            f"{slug}.palette = 'default_dark' — признак legacy base_params schema или "
            f"отсутствия явного palette в YAML."
        )


# ---------------------------------------------------------------------------
# T4: Resolver smoke
# ---------------------------------------------------------------------------

class TestT4ResolverSmoke:

    @pytest.mark.parametrize("slug", sorted(EXPECTED_CANONICAL))
    def test_resolve_succeeds_for_all_canonical(self, slug):
        """resolve_render_params не падает для каждого canonical slug."""
        params, profile, _ = resolve_render_params(
            project_id="contract_test",
            analysis_id=f"smoke_{slug}",
            perceptual=_neutral_perceptual(),
            style_profile_slug=slug,
            interpretation_profile_slug="default",
            user_preset=_neutral_preset(),
            strict_theta=True,
        )
        assert profile.slug == slug, (
            f"profile.slug = '{profile.slug}', ожидался '{slug}'"
        )
        expected = EXPECTED_PALETTES[slug]
        assert params.palette_id.startswith(expected), (
            f"{slug}: palette_id = '{params.palette_id}', "
            f"ожидалось начало с '{expected}'"
        )


# ---------------------------------------------------------------------------
# T5: Jazz / blues_jazz identity
# ---------------------------------------------------------------------------

class TestT5JazzIdentity:

    def test_jazz_palette_is_nocturne_amber(self):
        registry = load_style_profiles()
        assert registry["jazz"].palette == "nocturne_amber"

    def test_blues_jazz_palette_is_warm_midnight(self):
        registry = load_style_profiles()
        assert registry["blues_jazz"].palette == "warm_midnight"

    def test_jazz_and_blues_jazz_palettes_differ(self):
        registry = load_style_profiles()
        assert registry["jazz"].palette != registry["blues_jazz"].palette, (
            "jazz и blues_jazz имеют одинаковую palette — художественные идентичности не разграничены."
        )
