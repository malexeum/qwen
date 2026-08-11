"""
test14_e4_gate0.py — Gate 0 перед E4

Три блока по рекомендациям архитектора (11.08.2026):

  T1  PaletteJazzIdentity       — nocturne_amber в jazz-профиле; blues_jazz отличается
  T2  ThetaHashPermutation      — hash инвариантен к порядку ключей в dict
  T3  MorphologyGuardPipeline   — guard виден в mapping_trace и влияет на visual params

Архитектурные замечания (зафиксированы в этом файле):
  - palette_registry не является отдельным модулем: палитра хранится как
    StyleProfile.palette (строка); _derive_palette_id добавляет суффикс _bright/_dark
  - RenderParams не имеет поля morphology_guard напрямую; guard — derived axis
    в axes-словаре resolver; в mapping_trace попадает через InterpretationProfile
    mapping_rules, если profile содержит formula, ссылающуюся на morphology_guard
  - _compute_theta_hash уже итерирует по THETA_AXES (0..7), а не по dict —
    порядок ключей не влияет на хэш по конструкции

Запуск:
  python -m pytest test14_e4_gate0.py -v
"""

import random
from typing import Any, Dict

import pytest

from lib.style_engine.engine import (
    THETA_AXES,
    _compute_morphology_guard,
    _compute_theta_hash,
    _normalize_style_slug,
    load_interpretation_profiles,
    load_style_profiles,
    resolve_render_params,
)

# ---------------------------------------------------------------------------
# Общие фикстуры
# ---------------------------------------------------------------------------

BASE_PERCEPTUAL: Dict[str, Any] = {
    "energy":             0.6,
    "tension":            0.4,
    "density":            0.5,
    "brightness":         0.5,
    "stability":          0.5,
    "smoothness":         0.5,
    "repetition":         0.5,
    "section_complexity": 0.5,
    "macro_shape_hint":   "neutral",
    "spectral_flatness":  0.03,
}

BASE_PRESET: Dict[str, float] = {
    "id":         "preset_gate0",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}


def _resolve(
    style: str = "ambient",
    interp: str = "default",
    perceptual: Dict[str, Any] = None,
    preset: Dict[str, float] = None,
    theta_override: Dict[str, float] = None,
):
    """Вспомогательный wrapper вокруг resolve_render_params."""
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
# Палитра хранится как StyleProfile.palette (строка).
# ===========================================================================

class TestT1PaletteJazzIdentity:
    """jazz.palette == 'nocturne_amber'; blues_jazz.palette != 'nocturne_amber'."""

    def test_jazz_profile_exists_in_registry(self):
        registry = load_style_profiles()
        assert "jazz" in registry, (
            "jazz не найден в style registry — "
            "создайте configs/style_profiles/jazz.yaml"
        )

    def test_jazz_palette_is_nocturne_amber(self):
        """jazz.palette == 'nocturne_amber' — художественный контракт профиля."""
        registry = load_style_profiles()
        jazz = registry["jazz"]
        assert jazz.palette == "nocturne_amber", (
            f"jazz.palette = '{jazz.palette}', ожидался 'nocturne_amber'. "
            f"Добавьте palette: nocturne_amber в configs/style_profiles/jazz.yaml"
        )

    def test_blues_jazz_exists(self):
        registry = load_style_profiles()
        assert "blues_jazz" in registry, (
            "blues_jazz не найден — создайте configs/style_profiles/blues_jazz.yaml"
        )

    def test_blues_jazz_palette_differs_from_jazz(self):
        """Художественные идентичности jazz и blues_jazz разные — палитры не совпадают."""
        registry = load_style_profiles()
        jazz_palette = registry["jazz"].palette
        bj_palette   = registry["blues_jazz"].palette
        assert jazz_palette != bj_palette, (
            f"jazz.palette == blues_jazz.palette == '{jazz_palette}'. "
            f"Идентичности должны различаться: jazz→nocturne_amber, blues_jazz→warm_midnight"
        )

    def test_blues_jazz_palette_is_warm_midnight(self):
        """blues_jazz использует warm_midnight, а не nocturne_amber."""
        registry = load_style_profiles()
        bj = registry["blues_jazz"]
        assert bj.palette == "warm_midnight", (
            f"blues_jazz.palette = '{bj.palette}', ожидался 'warm_midnight'. "
            f"Обновите configs/style_profiles/blues_jazz.yaml"
        )

    def test_resolve_jazz_sets_palette_id_from_nocturne_amber(self):
        """
        resolve_render_params с jazz-профилем → palette_id начинается с 'nocturne_amber'.
        _derive_palette_id добавляет суффикс _bright/_dark; базовая часть сохраняется.
        """
        rp, sp, _ = _resolve(style="jazz")
        assert rp.palette_id.startswith("nocturne_amber"), (
            f"rp.palette_id = '{rp.palette_id}'. "
            f"Ожидается 'nocturne_amber', 'nocturne_amber_bright' или 'nocturne_amber_dark'. "
            f"jazz.palette = '{sp.palette}'"
        )

    def test_resolve_blues_jazz_palette_id_differs_from_jazz(self):
        """После resolver: palette_id для jazz и blues_jazz не совпадают."""
        rp_jazz, _, _ = _resolve(style="jazz")
        rp_bj,   _, _ = _resolve(style="blues_jazz")
        assert rp_jazz.palette_id != rp_bj.palette_id, (
            f"jazz.palette_id == blues_jazz.palette_id == '{rp_jazz.palette_id}'. "
            f"Художественные идентичности не разграничены."
        )


# ===========================================================================
# T2: ThetaHashPermutation
# _compute_theta_hash итерирует по THETA_AXES в порядке 0..7 —
# проверяем что это действительно так, а не по порядку dict.
# ===========================================================================

class TestT2ThetaHashPermutation:
    """
    Если _compute_theta_hash правильно реализован (итерация по THETA_AXES),
    все permutation-тесты пройдут сразу.
    Если упадут — значит где-то в цепочке (bridge/serializer) dict
    переставляет порядок до вызова функции.
    """

    def _ordered_theta(self) -> Dict[str, float]:
        return {f"harmony_theta_{i}": round(0.1 * i, 6) for i in range(8)}

    def test_reversed_order_same_hash(self):
        """dict с обратным порядком ключей → тот же hash."""
        theta_a = self._ordered_theta()
        theta_b = dict(reversed(list(theta_a.items())))
        assert _compute_theta_hash(theta_a) == _compute_theta_hash(theta_b), (
            "theta_hash зависит от порядка ключей в dict. "
            "_compute_theta_hash должен итерировать по THETA_AXES, а не theta_values.items()"
        )

    def test_random_shuffle_same_hash(self):
        """Произвольная перестановка ключей → тот же hash."""
        theta_a = self._ordered_theta()
        keys = list(theta_a.keys())
        random.shuffle(keys)
        theta_shuffled = {k: theta_a[k] for k in keys}
        assert _compute_theta_hash(theta_a) == _compute_theta_hash(theta_shuffled), (
            "theta_hash изменился после shuffle ключей. "
            "Порядок должен определяться THETA_AXES[0..7], а не dict-итерацией."
        )

    def test_four_random_permutations_agree(self):
        """4 случайных перестановки → все дают тот же hash что и canonical."""
        theta_base = self._ordered_theta()
        base_hash  = _compute_theta_hash(theta_base)
        keys = list(theta_base.keys())
        for _ in range(4):
            random.shuffle(keys)
            perm = {k: theta_base[k] for k in keys}
            assert _compute_theta_hash(perm) == base_hash

    def test_value_change_changes_hash(self):
        """Изменение значения оси → другой hash (чувствительность сохраняется)."""
        theta_a = self._ordered_theta()
        theta_b = dict(theta_a)
        theta_b["harmony_theta_3"] = round(theta_b["harmony_theta_3"] + 0.15, 6)
        assert _compute_theta_hash(theta_a) != _compute_theta_hash(theta_b)

    def test_each_axis_independently_affects_hash(self):
        """Изменение любой из 8 осей в отдельности меняет hash."""
        base = {ax: 0.5 for ax in THETA_AXES}
        base_hash = _compute_theta_hash(base)
        for i, axis in enumerate(THETA_AXES):
            variant = dict(base)
            variant[axis] = 0.7
            assert _compute_theta_hash(variant) != base_hash, (
                f"{axis} (index {i}) не влияет на hash — ось пропущена в хэшировании"
            )

    def test_hash_format(self):
        """hash — hex-строка длиной 16."""
        h = _compute_theta_hash(self._ordered_theta())
        assert isinstance(h, str)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h), f"Не hex: '{h}'"

    def test_deterministic(self):
        """Повторный вызов с тем же input → тот же hash."""
        theta = self._ordered_theta()
        assert _compute_theta_hash(theta) == _compute_theta_hash(theta)


# ===========================================================================
# T3: MorphologyGuardPipeline
#
# Что реально доступно в engine.py:
#   - _compute_morphology_guard(perceptual) -> float [0,1]  (unit-функция)
#   - axes['morphology_guard'] передаётся в InterpretationProfile mapping_rules
#   - mapping_trace в RenderParams содержит записи о каждом параметре
#   - 6 визуальных параметров в RenderParams:
#       symmetry_bias, recursion_depth, density_level,
#       noise_level, motion_intensity, texture_complexity
#
# Gate 0 контракт архитектора:
#   «guard вычисляется, виден в pipeline, и при достаточной дельте
#    меняет хотя бы один visual param через interpretation profile»
# ===========================================================================

class TestT3MorphologyGuardPipeline:

    @staticmethod
    def _low_p() -> Dict[str, Any]:
        """Низкий guard: высокое repetition + stability, низкое tension + complexity."""
        p = dict(BASE_PERCEPTUAL)
        p.update({
            "repetition":         0.85,
            "stability":          0.80,
            "tension":            0.12,
            "section_complexity": 0.10,
        })
        return p

    @staticmethod
    def _high_p() -> Dict[str, Any]:
        """Высокий guard: высокое tension + complexity, низкое repetition + stability."""
        p = dict(BASE_PERCEPTUAL)
        p.update({
            "repetition":         0.10,
            "stability":          0.12,
            "tension":            0.85,
            "section_complexity": 0.90,
        })
        return p

    # --- unit: формула guard ---

    def test_unit_formula_low(self):
        """_compute_morphology_guard возвращает малое значение при low-inputs."""
        # formula: clamp01(0.5*complexity + 0.4*tension - 0.3*repetition - 0.3*stability)
        # clamp01(0.5*0.10 + 0.4*0.12 - 0.3*0.85 - 0.3*0.80)
        # = clamp01(0.05 + 0.048 - 0.255 - 0.24) = clamp01(-0.397) = 0.0
        g = _compute_morphology_guard(self._low_p())
        assert g < 0.25, f"Ожидался guard < 0.25 при low-inputs, получен {g:.4f}"

    def test_unit_formula_high(self):
        """_compute_morphology_guard возвращает высокое значение при high-inputs."""
        # clamp01(0.5*0.90 + 0.4*0.85 - 0.3*0.10 - 0.3*0.12)
        # = clamp01(0.45 + 0.34 - 0.03 - 0.036) = clamp01(0.724) = 0.724
        g = _compute_morphology_guard(self._high_p())
        assert g > 0.60, f"Ожидался guard > 0.60 при high-inputs, получен {g:.4f}"

    def test_unit_formula_delta(self):
        """Разница guard между high и low > 0.50."""
        low  = _compute_morphology_guard(self._low_p())
        high = _compute_morphology_guard(self._high_p())
        delta = high - low
        assert delta > 0.50, (
            f"Ожидалась delta > 0.50, получена {delta:.4f} "
            f"(low={low:.4f}, high={high:.4f})"
        )

    def test_unit_output_in_01(self):
        """Guard всегда в [0, 1]."""
        for p in [self._low_p(), self._high_p(), BASE_PERCEPTUAL]:
            g = _compute_morphology_guard(p)
            assert 0.0 <= g <= 1.0, f"Guard вне [0,1]: {g}"

    # --- pipeline: guard в mapping_trace ---

    def test_mapping_trace_not_empty_after_resolve(self):
        """После resolve_render_params mapping_trace содержит хотя бы одну запись."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        assert len(rp.mapping_trace) > 0, (
            "mapping_trace пуст — _trace() не вызывается в resolver"
        )

    def test_mapping_trace_has_base_stage(self):
        """В mapping_trace есть записи stage='base' (из StyleProfile)."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        stages = {e.stage for e in rp.mapping_trace}
        assert "base" in stages, f"stage='base' не найден. Stages: {stages}"

    def test_mapping_trace_has_perceptual_stage(self):
        """В mapping_trace есть записи stage='perceptual' (из mapping_rules)."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        stages = {e.stage for e in rp.mapping_trace}
        assert "perceptual" in stages, (
            f"stage='perceptual' не найден. Stages: {stages}. "
            f"Проверьте mapping_rules в configs/interpretation_profiles/default.yaml"
        )

    def test_mapping_trace_has_user_stage(self):
        """В mapping_trace есть записи stage='user' (из UserPreset)."""
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        stages = {e.stage for e in rp.mapping_trace}
        assert "user" in stages, f"stage='user' не найден. Stages: {stages}"

    def test_morphology_guard_referenced_in_trace(self):
        """
        morphology_guard должен присутствовать в axes-словаре resolver
        и попасть в формулу хотя бы одного perceptual-маппинга.

        Проверяем косвенно: в mapping_trace должна быть запись,
        где source содержит 'morphology_guard' (т.е. какая-то formula
        использует эту ось).

        Если тест падает — нужно добавить в configs/interpretation_profiles/default.yaml
        mapping rule, например:
          texture_complexity:
            formula: 'base + morphology_guard * 0.30'
        """
        rp, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        sources_using_guard = [
            e for e in rp.mapping_trace
            if "morphology_guard" in str(e.source)
        ]
        assert len(sources_using_guard) > 0, (
            "Ни одна formula в mapping_trace не ссылается на 'morphology_guard'. "
            "Добавьте в configs/interpretation_profiles/default.yaml mapping rule, "
            "например: texture_complexity: {formula: 'base + morphology_guard * 0.30'}"
        )

    # --- pipeline: guard влияет на visual params ---

    def test_high_guard_changes_at_least_one_visual_param(self):
        """
        Integration-тест по контракту архитектора:
          same profile + same theta + low guard  -> RenderParams A
          same profile + same theta + high guard -> RenderParams B
          минимум один visual param отличается.

        Если тест падает — morphology_guard вычисляется но не используется
        ни в одной formula в InterpretationProfile.mapping_rules.
        Добавьте хотя бы одно правило вида:
          texture_complexity:
            formula: 'base + morphology_guard * 0.30'
        """
        VISUAL_PARAMS = (
            "symmetry_bias",
            "recursion_depth",
            "density_level",
            "noise_level",
            "motion_intensity",
            "texture_complexity",
        )
        rp_low,  _, _ = _resolve(style="jazz", perceptual=self._low_p())
        rp_high, _, _ = _resolve(style="jazz", perceptual=self._high_p())

        diffs = []
        for param in VISUAL_PARAMS:
            v_low  = getattr(rp_low,  param)
            v_high = getattr(rp_high, param)
            if abs(v_high - v_low) > 0.01:
                diffs.append((param, round(v_low, 4), round(v_high, 4)))

        assert len(diffs) > 0, (
            "Ни один visual param не изменился при переходе от low к high morphology_guard. "
            "morphology_guard вычисляется, но не используется ни в одной formula "
            "в InterpretationProfile.mapping_rules. "
            "Добавьте в default.yaml хотя бы одно правило:\n"
            "  texture_complexity:\n"
            "    formula: 'base + morphology_guard * 0.30'\n"
            "Или аналогичное для recursion_depth / motion_intensity."
        )

    def test_palette_unchanged_between_low_and_high_guard(self):
        """Изменение morphology_guard не должно менять palette_id при той же brightness."""
        rp_low,  _, _ = _resolve(style="jazz", perceptual=self._low_p())
        rp_high, _, _ = _resolve(style="jazz", perceptual=self._high_p())
        # brightness одинакова в обоих случаях (из BASE_PERCEPTUAL = 0.5)
        assert rp_low.palette_id == rp_high.palette_id, (
            f"palette_id изменился при смене guard: "
            f"low='{rp_low.palette_id}' high='{rp_high.palette_id}'. "
            f"Изменение guard не должно влиять на palette."
        )
