"""
test_cb31_default_profile.py

4 pytest cases по спецификации CB-3.1-A0:

  1. test_default_profile_is_discoverable
     load_style_profiles()["default"].slug == "default"

  2. test_default_resolves_at_neutral_input
     resolve_render_params(..., style_profile_slug="default", perceptual=neutral_0.5)
     → params.palette_id == "neutral_noir"
       (brightness=0.5 → _derive_palette_id не добавляет суффикс)

  3. test_default_is_not_an_alias
     _normalize_style_slug("default", registry) == "default"
     (не проходит через _STYLE_ALIASES как перенаправление)

  4. test_unknown_profile_does_not_fallback_to_default
     resolve_render_params(style_profile_slug="typo_profile", ...)
     → ValueError: unknown_style_profile

Запуск:
  pytest tests/test_cb31_default_profile.py -v
"""
from __future__ import annotations

import pytest

from lib.style_engine.config_loader import load_style_profiles
from lib.style_engine.engine import (
    _normalize_style_slug,
    _STYLE_ALIASES,
    resolve_render_params,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_PRESET = {
    "id": "neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}


def _neutral_perceptual() -> dict:
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDefaultProfile:

    def test_default_profile_is_discoverable(self):
        """
        load_style_profiles() должен обнаружить slug="default".
        """
        registry = load_style_profiles()
        assert "default" in registry, (
            f"slug 'default' не найден в реестре. Доступные: {sorted(registry.keys())}"
        )
        profile = registry["default"]
        assert profile.slug == "default"

    def test_default_resolves_at_neutral_input(self):
        """
        При brightness=0.5 → _derive_palette_id("neutral_noir", 0.5) → "neutral_noir".
        Никакого _dark / _bright суффикса.
        """
        params, _, _ = resolve_render_params(
            project_id="test_default",
            analysis_id="gate_default",
            perceptual=_neutral_perceptual(),
            style_profile_slug="default",
            interpretation_profile_slug="default",
            user_preset=DEFAULT_PRESET,
            strict_theta=True,
        )
        assert params.palette_id == "neutral_noir", (
            f"Ожидался palette_id='neutral_noir', получен: {params.palette_id!r}"
        )

    def test_default_is_not_an_alias(self):
        """
        "default" должен быть явным slug-ом, а не перенаправлением через _STYLE_ALIASES.
        _normalize_style_slug("default") == "default" и
        "default" не является ключом в _STYLE_ALIASES (т.е. не алиас чего-то другого).
        """
        registry = load_style_profiles()
        normalized = _normalize_style_slug("default", registry)
        assert normalized == "default", (
            f"_normalize_style_slug вернул {normalized!r} вместо 'default'"
        )
        # Алиас — это когда ключ в _STYLE_ALIASES ведёт на другой slug.
        # "default" не должен быть псевдонимом чего-то иного.
        if "default" in _STYLE_ALIASES:
            target = _STYLE_ALIASES["default"]
            assert target == "default", (
                f"'default' в _STYLE_ALIASES указывает на '{target}' — это нарушение контракта. "
                "default должен быть самостоятельным профилем."
            )

    def test_unknown_profile_does_not_fallback_to_default(self):
        """
        Опечатка в slug НЕ должна молча давать default.
        Движок обязан бросить ValueError: unknown_style_profile.
        """
        with pytest.raises(ValueError, match="unknown_style_profile"):
            resolve_render_params(
                project_id="test_default",
                analysis_id="gate_default",
                perceptual=_neutral_perceptual(),
                style_profile_slug="typo_profile",
                interpretation_profile_slug="default",
                user_preset=DEFAULT_PRESET,
                strict_theta=True,
            )
