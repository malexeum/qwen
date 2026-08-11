"""
test14_e4_gate0.py — Gate 0 перед E4

Три блока по рекомендациям архитектора (11.08.2026):

  T1  PaletteJazzIdentity       — nocturne_amber в реестре; jazz → nocturne_amber
  T2  ThetaHashPermutation      — hash не зависит от порядка ключей в dict
  T3  MorphologyGuardIntegration — guard влияет на RenderParams и виден в mapping_trace

Запуск:
  python -m pytest test14_e4_gate0.py -v
"""

import pytest
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Импорты из lib
# ---------------------------------------------------------------------------
from lib.style_engine.engine import (
    load_style_profiles,
    load_interpretation_profiles,
    resolve_render_params,
    _normalize_style_slug,
    _compute_theta_hash,
)
from lib.style_engine.palette_registry import load_palette_registry, resolve_palette

# ---------------------------------------------------------------------------
# Общие фикстуры
# ---------------------------------------------------------------------------

BASE_PERCEPTUAL: Dict[str, Any] = {
    "energy": 0.6,
    "tension": 0.4,
    "density": 0.5,
    "brightness": 0.5,
    "stability": 0.5,
    "smoothness": 0.5,
    "repetition": 0.5,
    "section_complexity": 0.5,
    "macro_shape_hint": "neutral",
    "spectral_flatness": 0.3,
}

BASE_PRESET: Dict[str, float] = {
    "id": "preset_gate0",
    "complexity": 0.5,
    "symmetry": 0.5,
    "density": 0.5,
    "noise": 0.5,
    "motion": 0.5,
}

NEUTRAL_THETA: Dict[str, float] = {f"harmony_theta_{i}": 0.5 for i in range(8)}


def _resolve(
    style: str = "ambient",
    interp: str = "default",
    perceptual: Dict[str, Any] = None,
    preset: Dict[str, float] = None,
    theta_override: Dict[str, float] = None,
):
    """Вспомогательный wrapper."""
    p = dict(BASE_PERCEPTUAL if perceptual is None else perceptual)
    if theta_override:
        p.update(theta_override)
    rp, sp, ip = resolve_render_params(
        project_id="gate0",
        analysis_id="gate0_analysis",
        perceptual=p,
        style_profile_slug=style,
        interpretation_profile_slug=interp,
        user_preset=dict(BASE_PRESET if preset is None else preset),
        strict_theta=True,
    )
    return rp, sp, ip


# ===========================================================================
# T1: PaletteJazzIdentity
# ===========================================================================

class TestT1PaletteJazzIdentity:
    """nocturne_amber присутствует в palette registry и jazz профиль ссылается на неё."""

    def test_nocturne_amber_in_registry(self):
        """nocturne_amber должна быть зарегистрирована в palette registry."""
        registry = load_palette_registry()
        assert "nocturne_amber" in registry, (
            "nocturne_amber не найдена в palette registry — "
            "jazz профиль будет использовать fallback palette вместо художественной идентичности"
        )

    def test_resolve_palette_returns_correct_id(self):
        """resolve_palette('nocturne_amber') → объект с .id == 'nocturne_amber'."""
        palette = resolve_palette("nocturne_amber")
        assert palette.id == "nocturne_amber"

    def test_nocturne_amber_family(self):
        """nocturne_amber имеет family == 'blue_amber' (художественный контракт)."""
        palette = resolve_palette("nocturne_amber")
        assert palette.family == "blue_amber", (
            f"Ожидалась family='blue_amber', получена '{palette.family}'"
        )

    def test_jazz_profile_palette_is_nocturne_amber(self):
        """StyleProfile 'jazz' должен ссылаться на palette='nocturne_amber'."""
        registry = load_style_profiles()
        assert "jazz" in registry, "Профиль 'jazz' отсутствует в style registry"
        jazz_profile = registry["jazz"]
        assert jazz_profile.palette == "nocturne_amber", (
            f"jazz.palette = '{jazz_profile.palette}', ожидался 'nocturne_amber'"
        )

    def test_jazz_resolve_uses_nocturne_amber(self):
        """resolve_render_params с jazz профилем → resolved palette = nocturne_amber."""
        rp, sp, _ip = _resolve(style="jazz")
        assert sp.palette == "nocturne_amber", (
            f"После resolve sp.palette = '{sp.palette}', ожидался 'nocturne_amber'"
        )

    def test_blues_jazz_does_not_use_nocturne_amber(self):
        """blues_jazz — отдельная палитра (warm_midnight), не nocturne_amber."""
        registry = load_style_profiles()
        assert "blues_jazz" in registry
        bj = registry["blues_jazz"]
        assert bj.palette != "nocturne_amber", (
            "blues_jazz ошибочно использует nocturne_amber — "
            "художественные идентичности jazz и blues_jazz должны быть различны"
        )


# ===========================================================================
# T2: ThetaHashPermutation
# ===========================================================================

class TestT2ThetaHashPermutation:
    """
    theta_hash должен быть инвариантен к порядку ключей в dict.

    Правило архитектора: hash строится по THETA_AXES = tuple('harmony_theta_0'...'harmony_theta_7')
    в фиксированном порядке 0..7, а не по порядку обхода входного dict.
    """

    def _ordered(self) -> Dict[str, float]:
        return {f"harmony_theta_{i}": 0.1 * i for i in range(8)}

    def test_reversed_order_same_hash(self):
        """dict в обратном порядке ключей → тот же hash."""
        theta_a = self._ordered()
        theta_b = dict(reversed(list(theta_a.items())))
        assert _compute_theta_hash(theta_a) == _compute_theta_hash(theta_b), (
            "theta_hash зависит от порядка ключей — это нарушает детерминизм seed между "
            "платформами (JSON/YAML/API могут возвращать ключи в разном порядке)"
        )

    def test_shuffled_order_same_hash(self):
        """Произвольная перестановка ключей → тот же hash."""
        import random
        theta_a = self._ordered()
        keys = list(theta_a.keys())
        random.shuffle(keys)
        theta_shuffled = {k: theta_a[k] for k in keys}
        assert _compute_theta_hash(theta_a) == _compute_theta_hash(theta_shuffled)

    def test_different_value_different_hash(self):
        """Изменение значения одной оси → другой hash (чувствительность сохраняется)."""
        theta_a = self._ordered()
        theta_b = dict(theta_a)
        theta_b["harmony_theta_3"] += 0.15
        assert _compute_theta_hash(theta_a) != _compute_theta_hash(theta_b)

    def test_each_axis_independently_changes_hash(self):
        """Изменение любой из 8 осей по одной → hash меняется."""
        base = {f"harmony_theta_{i}": 0.5 for i in range(8)}
        base_hash = _compute_theta_hash(base)
        for i in range(8):
            variant = dict(base)
            variant[f"harmony_theta_{i}"] = 0.7
            assert _compute_theta_hash(variant) != base_hash, (
                f"harmony_theta_{i} не влияет на hash — ось не участвует в хэшировании"
            )

    def test_hash_is_hex_16_chars(self):
        """hash — шестнадцатеричная строка длиной 16."""
        h = _compute_theta_hash(self._ordered())
        assert isinstance(h, str)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_across_calls(self):
        """Один и тот же input → одинаковый hash при повторном вызове."""
        theta = self._ordered()
        assert _compute_theta_hash(theta) == _compute_theta_hash(theta)


# ===========================================================================
# T3: MorphologyGuardIntegration
# ===========================================================================

class TestT3MorphologyGuardIntegration:
    """
    _compute_morphology_guard должен влиять на RenderParams через resolver pipeline.

    Контракт архитектора:
      - Тот же feature vector + тот же θ + тот же профиль
      - morphology_guard = low  → RenderParams A
      - morphology_guard = high → RenderParams B
      - Меняется минимум один разрешённый target: angular_break / map_diversity /
        branch_jitter / opacity_chaos_layer или complexity_bias
      - Изменённый target отражён в mapping_trace
      - Palette, seed policy и несвязанные параметры не меняются без причины
    """

    def _low_guard_perceptual(self) -> Dict[str, Any]:
        """Низкая морфологическая активность: высокое repetition, высокое stability, низкое tension."""
        p = dict(BASE_PERCEPTUAL)
        p.update({
            "repetition": 0.85,
            "stability": 0.80,
            "tension": 0.15,
            "section_complexity": 0.10,
        })
        return p

    def _high_guard_perceptual(self) -> Dict[str, Any]:
        """Высокая морфологическая активность: высокое tension, высокая section_complexity."""
        p = dict(BASE_PERCEPTUAL)
        p.update({
            "repetition": 0.10,
            "stability": 0.15,
            "tension": 0.85,
            "section_complexity": 0.90,
        })
        return p

    def test_guard_value_differs_between_low_and_high(self):
        """morphology_guard в RenderParams должен быть существенно выше при high-inputs."""
        rp_low, _, _ = _resolve(style="jazz", perceptual=self._low_guard_perceptual())
        rp_high, _, _ = _resolve(style="jazz", perceptual=self._high_guard_perceptual())
        # guard должен отличаться на >0.30 (formula: complexity*0.40 + tension*0.30 vs repetition*0.25 + stability*0.20)
        assert hasattr(rp_low, "morphology_guard"), (
            "RenderParams не содержит поле 'morphology_guard' — "
            "guard не дошёл до pipeline"
        )
        assert hasattr(rp_high, "morphology_guard")
        delta = rp_high.morphology_guard - rp_low.morphology_guard
        assert delta > 0.30, (
            f"Ожидался delta > 0.30 между high/low guard, получен {delta:.3f}. "
            f"Проверьте что _compute_morphology_guard вызывается в resolver и результат "
            f"записывается в RenderParams.morphology_guard"
        )

    def test_guard_low_value_is_low(self):
        """При low-inputs guard < 0.35."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._low_guard_perceptual())
        assert rp.morphology_guard < 0.35, (
            f"guard = {rp.morphology_guard:.3f} при low-inputs — ожидался < 0.35"
        )

    def test_guard_high_value_is_high(self):
        """При high-inputs guard > 0.65."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_guard_perceptual())
        assert rp.morphology_guard > 0.65, (
            f"guard = {rp.morphology_guard:.3f} при high-inputs — ожидался > 0.65"
        )

    def test_guard_appears_in_mapping_trace(self):
        """morphology_guard должен быть отражён в mapping_trace."""
        rp, _, ip = _resolve(style="jazz", perceptual=self._high_guard_perceptual())
        assert hasattr(rp, "_trace"), (
            "RenderParams не содержит _trace — trace не прикреплён к результату resolver"
        )
        trace_params = {entry.param for entry in rp._trace}
        assert "morphology_guard" in trace_params, (
            f"'morphology_guard' не найден в mapping_trace. "
            f"Параметры в trace: {sorted(trace_params)}"
        )

    def test_guard_does_not_change_palette(self):
        """Изменение guard не должно влиять на palette."""
        rp_low, sp_low, _ = _resolve(style="jazz", perceptual=self._low_guard_perceptual())
        rp_high, sp_high, _ = _resolve(style="jazz", perceptual=self._high_guard_perceptual())
        assert sp_low.palette == sp_high.palette, (
            "Смена morphology_guard изменила palette — нарушена независимость параметров"
        )

    def test_guard_affect_complexity_or_morpho_param(self):
        """
        При high guard минимум один из морфологически связанных параметров должен отличаться:
        complexity_bias, angular_break, map_diversity, branch_jitter, opacity_chaos_layer.
        """
        MORPHO_PARAMS = (
            "complexity_bias",
            "angular_break",
            "map_diversity",
            "branch_jitter",
            "opacity_chaos_layer",
        )
        rp_low, _, _ = _resolve(style="jazz", perceptual=self._low_guard_perceptual())
        rp_high, _, _ = _resolve(style="jazz", perceptual=self._high_guard_perceptual())

        found_diff = False
        for param in MORPHO_PARAMS:
            val_low = getattr(rp_low, param, None)
            val_high = getattr(rp_high, param, None)
            if val_low is not None and val_high is not None:
                if abs(float(val_high) - float(val_low)) > 0.01:
                    found_diff = True
                    break

        assert found_diff, (
            f"Ни один из морфологических параметров {MORPHO_PARAMS} не изменился "
            f"при переходе от low к high morphology_guard. "
            f"Guard вычисляется, но не влияет на RenderParams — не хватает mapping rule "
            f"в interpretation profile, которая связывает morphology_guard с визуальным параметром."
        )
