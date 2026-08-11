"""test12.py — E3: harmony_theta_0..7 integration tests (P1-P8)

P1  theta_defaults        — если perceptual без theta, RenderParams получает 0.5 по всем 8 осям
P2  theta_passthrough      — значения theta из perceptual без искажений проходят в RenderParams
P3  theta_clamp            — значения за пределами [0,1] зажимаются
P4  theta_invalid_type     — некорректный тип → ValueError
P5  seed_theta_sensitive   — seed меняется при любом изменении theta
P6  mapping_trace          — trace не пустой, содержит стадии base/perceptual/user
P7  profile_pop            — профиль pop разрешается, не редиректирует в rock
P8  alias_pop_removed      — старый алиас pop→rock удалён: slug не резолвится в rock
                             E3-C: jazz теперь canonical профиль, алиас jazz→blues_jazz удалён

Запуск:
    python -m pytest test12.py -v
Требует наличия config_loader, engine и запущенного YAML-профиля для pop и rock.
"""

from __future__ import annotations

import pytest

from lib.style_engine.engine import (
    THETA_AXES,
    RenderParams,
    _compute_variation_seed,
    _extract_theta_axes,
    _normalize_style_slug,
    resolve_render_params,
)
from lib.style_engine.config_loader import load_style_profiles


# ---------------------------------------------------------------------------
# Фикстуры — базовый perceptual без theta
# ---------------------------------------------------------------------------

BASE_PERCEPTUAL: dict = {
    "energy": 0.6,
    "tension": 0.4,
    "density": 0.5,
    "brightness": 0.5,
    "stability": 0.5,
    "smoothness": 0.4,
    "repetition": 0.3,
    "section_complexity": 0.5,
    "macro_shape_hint": "ABA_like",
    "silence_rate": 0.1,
    "tempo": 0.5,
    "spectral_flatness": 0.4,
    "high_frequency_energy": 0.3,
    "harmonic_stability": 0.6,
    "harmonic_change_rate": 0.3,
}

BASE_PRESET: dict = {
    "id": "preset_test",
    "complexity": 0.5,
    "symmetry": 0.5,
    "density": 0.5,
    "noise": 0.5,
    "motion": 0.5,
}


def _perceptual_with_theta(**theta_overrides) -> dict:
    """BASE_PERCEPTUAL плюс произвольные theta."""
    p = dict(BASE_PERCEPTUAL)
    for k, v in theta_overrides.items():
        p[k] = v
    return p


def _resolve(style: str = "ambient", perceptual: dict | None = None) -> RenderParams:
    """Shortcut: resolve_render_params с тестовыми данными."""
    p = perceptual if perceptual is not None else BASE_PERCEPTUAL
    rp, _, _ = resolve_render_params(
        project_id="test_project",
        analysis_id="test_analysis",
        perceptual=p,
        style_profile_slug=style,
        interpretation_profile_slug="default",
        user_preset=BASE_PRESET,
    )
    return rp


# ---------------------------------------------------------------------------
# P1: theta_defaults
# ---------------------------------------------------------------------------

class TestP1ThetaDefaults:
    """P1: если perceptual не содержит harmony_theta_*, все получают 0.5."""

    def test_all_theta_are_05_when_absent(self):
        rp = _resolve(perceptual=BASE_PERCEPTUAL)
        for axis in THETA_AXES:
            val = getattr(rp, axis)
            assert val == pytest.approx(0.5), (
                f"{axis} should default to 0.5, got {val}"
            )

    def test_theta_fields_exist_on_render_params(self):
        """RenderParams должен иметь все 8 полей harmony_theta_*."""
        rp = _resolve()
        for axis in THETA_AXES:
            assert hasattr(rp, axis), f"RenderParams missing field: {axis}"


# ---------------------------------------------------------------------------
# P2: theta_passthrough
# ---------------------------------------------------------------------------

class TestP2ThetaPassthrough:
    """P2: значения theta из perceptual проходят в RenderParams без искажений."""

    def test_theta_values_propagate(self):
        theta_input = {
            "harmony_theta_0": 0.1,
            "harmony_theta_1": 0.2,
            "harmony_theta_2": 0.3,
            "harmony_theta_3": 0.4,
            "harmony_theta_4": 0.6,
            "harmony_theta_5": 0.7,
            "harmony_theta_6": 0.8,
            "harmony_theta_7": 0.9,
        }
        rp = _resolve(perceptual=_perceptual_with_theta(**theta_input))
        for axis, expected in theta_input.items():
            actual = getattr(rp, axis)
            assert actual == pytest.approx(expected, abs=1e-6), (
                f"{axis}: expected {expected}, got {actual}"
            )

    def test_partial_theta_does_not_affect_others(self):
        """partial override: неуказанные оси остаются 0.5."""
        p = _perceptual_with_theta(harmony_theta_0=0.1, harmony_theta_7=0.9)
        rp = _resolve(perceptual=p)
        assert rp.harmony_theta_0 == pytest.approx(0.1)
        assert rp.harmony_theta_7 == pytest.approx(0.9)
        for axis in THETA_AXES[1:7]:  # theta_1..theta_6
            assert getattr(rp, axis) == pytest.approx(0.5), (
                f"{axis} should be 0.5 (unset), got {getattr(rp, axis)}"
            )


# ---------------------------------------------------------------------------
# P3: theta_clamp
# ---------------------------------------------------------------------------

class TestP3ThetaClamp:
    """P3: значения theta за [0,1] зажимаются при извлечении."""

    def test_clamp_above_1(self):
        result = _extract_theta_axes({"harmony_theta_0": 1.8})
        assert result["harmony_theta_0"] == pytest.approx(1.0)

    def test_clamp_below_0(self):
        result = _extract_theta_axes({"harmony_theta_3": -0.5})
        assert result["harmony_theta_3"] == pytest.approx(0.0)

    def test_boundary_0_and_1_preserved(self):
        result = _extract_theta_axes({
            "harmony_theta_1": 0.0,
            "harmony_theta_2": 1.0,
        })
        assert result["harmony_theta_1"] == pytest.approx(0.0)
        assert result["harmony_theta_2"] == pytest.approx(1.0)

    def test_clamped_values_end_to_end(self):
        """resolve_render_params: переданные 1.5/−0.3 зажаты в 1.0/0.0."""
        p = _perceptual_with_theta(
            harmony_theta_0=1.5,
            harmony_theta_5=-0.3,
        )
        rp = _resolve(perceptual=p)
        assert rp.harmony_theta_0 == pytest.approx(1.0)
        assert rp.harmony_theta_5 == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# P4: theta_invalid_type
# ---------------------------------------------------------------------------

class TestP4ThetaInvalidType:
    """P4: неконвертируемый тип → ValueError (не silent-zero)."""

    @pytest.mark.parametrize("bad_value", [
        "loud",
        [0.5],
        {"x": 1},
        object(),
    ])
    def test_raises_on_bad_type(self, bad_value):
        with pytest.raises(ValueError, match="harmony_theta_parse_error"):
            _extract_theta_axes({"harmony_theta_2": bad_value})

    def test_none_is_neutral_not_error(self):
        """None → default 0.5, не ошибка."""
        result = _extract_theta_axes({"harmony_theta_4": None})
        assert result["harmony_theta_4"] == pytest.approx(0.5)

    def test_int_is_accepted(self):
        """int конвертируется в float."""
        result = _extract_theta_axes({"harmony_theta_6": 1})
        assert result["harmony_theta_6"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# P5: seed_theta_sensitive
# ---------------------------------------------------------------------------

class TestP5SeedThetaSensitive:
    """P5: seed меняется при любом изменении theta."""

    def _seed(self, **theta_overrides) -> int:
        theta_base = {ax: 0.5 for ax in THETA_AXES}
        theta_base.update(theta_overrides)
        return _compute_variation_seed(
            "proj", "anal", "preset", "ambient", "default", theta_base
        )

    def test_different_theta_gives_different_seed(self):
        s1 = self._seed(harmony_theta_0=0.1)
        s2 = self._seed(harmony_theta_0=0.9)
        assert s1 != s2

    def test_same_theta_gives_same_seed(self):
        s1 = self._seed(harmony_theta_3=0.42)
        s2 = self._seed(harmony_theta_3=0.42)
        assert s1 == s2

    def test_each_axis_independently_changes_seed(self):
        """Every theta axis contributes to the seed independently."""
        base_seed = self._seed()
        for axis in THETA_AXES:
            changed = self._seed(**{axis: 0.123})
            assert changed != base_seed, (
                f"Seed did not change when {axis} changed from 0.5 to 0.123"
            )

    def test_end_to_end_seed_differs_with_theta(self):
        """resolve_render_params: variation_seed различен при разных theta."""
        rp1 = _resolve(perceptual=_perceptual_with_theta(harmony_theta_0=0.1))
        rp2 = _resolve(perceptual=_perceptual_with_theta(harmony_theta_0=0.9))
        assert rp1.variation_seed != rp2.variation_seed


# ---------------------------------------------------------------------------
# P6: mapping_trace
# ---------------------------------------------------------------------------

class TestP6MappingTrace:
    """P6: mapping_trace не пустой, содержит нужные стадии."""

    def test_trace_is_not_empty(self):
        rp = _resolve()
        assert len(rp.mapping_trace) > 0, "mapping_trace should not be empty"

    def test_trace_contains_base_stage(self):
        rp = _resolve()
        stages = {e.stage for e in rp.mapping_trace}
        assert "base" in stages

    def test_trace_contains_perceptual_stage(self):
        rp = _resolve()
        stages = {e.stage for e in rp.mapping_trace}
        assert "perceptual" in stages

    def test_trace_contains_user_stage(self):
        rp = _resolve()
        stages = {e.stage for e in rp.mapping_trace}
        assert "user" in stages

    def test_trace_entry_fields(self):
        """MappingTraceEntry имеет поля param, source, raw, final, stage."""
        rp = _resolve()
        entry = rp.mapping_trace[0]
        for field in ("param", "source", "raw", "final", "stage"):
            assert hasattr(entry, field), f"MappingTraceEntry missing field: {field}"

    def test_trace_final_values_are_clamped(self):
        """final в каждой записи ∈ [0, 1]."""
        rp = _resolve()
        for entry in rp.mapping_trace:
            if isinstance(entry.final, float):
                assert 0.0 <= entry.final <= 1.0, (
                    f"Trace entry final out of [0,1]: {entry}"
                )


# ---------------------------------------------------------------------------
# P7: profile_pop
# ---------------------------------------------------------------------------

class TestP7ProfilePop:
    """P7: профиль pop разрешается независимо, theta работают."""

    def test_pop_profile_resolves(self):
        rp = _resolve(style="pop")
        assert rp.style_profile_slug == "pop"

    def test_pop_is_not_rock(self):
        rp = _resolve(style="pop")
        assert rp.style_profile_slug != "rock", (
            "pop should not redirect to rock — alias was removed in E3"
        )

    def test_pop_theta_passthrough(self):
        p = _perceptual_with_theta(
            harmony_theta_0=0.2,
            harmony_theta_7=0.8,
        )
        rp = _resolve(style="pop", perceptual=p)
        assert rp.harmony_theta_0 == pytest.approx(0.2)
        assert rp.harmony_theta_7 == pytest.approx(0.8)

    def test_pop_render_params_complete(self):
        rp = _resolve(style="pop")
        for axis in THETA_AXES:
            assert hasattr(rp, axis)
            val = getattr(rp, axis)
            assert 0.0 <= val <= 1.0, f"{axis} out of range in pop profile"


# ---------------------------------------------------------------------------
# P8: alias_pop_removed
# ---------------------------------------------------------------------------

class TestP8AliasPopRemoved:
    """P8: старый алиас pop→rock удалён.
    E3-C: jazz теперь canonical самостоятельный профиль.
           Алиас jazz→blues_jazz удалён из _STYLE_ALIASES.
           _normalize_style_slug("jazz") → "jazz" (прямо в реестре).
    """

    def test_pop_not_aliased_to_rock_in_normalize(self):
        registry = load_style_profiles()
        result = _normalize_style_slug("pop", registry)
        assert result != "rock", (
            f"'pop' should NOT normalize to 'rock' (alias removed). Got: {result!r}"
        )

    def test_pop_slug_returned_as_is_or_resolves_directly(self):
        """pop нормализуется в 'pop' (registry знает этот профиль)."""
        registry = load_style_profiles()
        result = _normalize_style_slug("pop", registry)
        assert result == "pop", (
            f"Expected 'pop', got {result!r}. Check style registry and alias table."
        )

    def test_rock_resolves_independently(self):
        """rock резолвится как rock — независимо от pop."""
        rp = _resolve(style="rock")
        assert rp.style_profile_slug == "rock"

    def test_jazz_alias_still_works(self):
        """E3-C: jazz — canonical профиль, не алиас.
        _normalize_style_slug("jazz") возвращает "jazz" напрямую из реестра.
        Алиас jazz→blues_jazz удалён; jazz и blues_jazz — разные самостоятельные профили.
        """
        registry = load_style_profiles()
        result = _normalize_style_slug("jazz", registry)
        assert result == "jazz", (
            f"Expected 'jazz' (canonical E3-C profile), got {result!r}. "
            "jazz→blues_jazz alias was removed per E3-C contract."
        )
