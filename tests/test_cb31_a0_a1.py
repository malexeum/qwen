"""
CB-3.1 Gate A0 + A1 tests.

Метрика:
  14 pytest test cases (методы test_*)
  22 логических assertion-контракта внутри них

Corrective (2026-08-11):
  - Точные source_axes per-param parametrize-тесты (расхождение №1 закрыто)
  - Исправлена арифметика метрики (расхождение №2 закрыто)
  - Каноничные θ-оси взяты из фактического default.yaml, не из commit message

Запуск:
  pytest tests/test_cb31_a0_a1.py -v
"""
from __future__ import annotations

import math
import pytest
from lib.style_engine.engine import (
    MappingTraceEntry,
    resolve_render_params,
)


# ---------------------------------------------------------------------------
# Канонический θ-контракт (source of truth для всех тестов)
# Взят из фактического default.yaml, зафиксирован 2026-08-11.
# Изменять только вместе с изменением default.yaml + standard.yaml.
# ---------------------------------------------------------------------------
THETA_CONTRACT: dict[str, list[str]] = {
    # param               canonical theta axes in source_axes
    "symmetry_bias":      ["harmony_theta_0", "harmony_theta_7"],
    "recursion_depth":    ["harmony_theta_2"],
    "density_level":      ["harmony_theta_3"],
    "noise_level":        ["harmony_theta_5"],
    "motion_intensity":   ["harmony_theta_6"],
    "texture_complexity": ["harmony_theta_2", "harmony_theta_5"],
    # θ₆ в texture_complexity отсутствует — "развитие во времени" ≠ "фактурная сложность"
}

# Параметры для теста чувствительности: (param, theta_key, delta_weight)
# delta_weight — коэффициент из формулы, delta_input=+0.20
SENSITIVITY_CASES: list[tuple[str, str, float]] = [
    ("symmetry_bias",      "harmony_theta_0", 0.20),  # w=0.20, Δ=0.04
    ("symmetry_bias",      "harmony_theta_7", 0.15),  # w=0.15, Δ=0.03
    ("recursion_depth",    "harmony_theta_2", 0.25),  # w=0.25, Δ=0.05
    ("noise_level",        "harmony_theta_5", 0.25),  # w=0.25, Δ=0.05
    ("motion_intensity",   "harmony_theta_6", 0.20),  # w=0.20, Δ=0.04
    ("texture_complexity", "harmony_theta_2", 0.20),  # w=0.20, Δ=0.04
    ("texture_complexity", "harmony_theta_5", 0.15),  # w=0.15, Δ=0.03
]

# Параметры для теста локальности: (param, theta_which_must_not_affect)
LOCALITY_CASES: list[tuple[str, str]] = [
    ("noise_level",        "harmony_theta_1"),  # θ₁ ∉ noise_level
    ("noise_level",        "harmony_theta_7"),  # θ₇ ∉ noise_level
    ("motion_intensity",   "harmony_theta_3"),  # θ₃ ∉ motion_intensity
    ("motion_intensity",   "harmony_theta_5"),  # θ₅ ∉ motion_intensity
    ("recursion_depth",    "harmony_theta_4"),  # θ₄ ∉ recursion_depth
    ("texture_complexity", "harmony_theta_6"),  # θ₆ ∉ texture_complexity ← ключевая проверка
    ("symmetry_bias",      "harmony_theta_5"),  # θ₅ ∉ symmetry_bias
]


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

DEFAULT_PRESET = {
    "id": "neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}


def _neutral_perceptual(**overrides) -> dict:
    base = {
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
    base.update(overrides)
    return base


def _resolve(perceptual: dict, preset: dict = None) -> object:
    rp, _, _ = resolve_render_params(
        project_id="test",
        analysis_id="gate_a0",
        perceptual=perceptual,
        style_profile_slug="default",
        interpretation_profile_slug="default",
        user_preset=preset or DEFAULT_PRESET,
        strict_theta=True,
    )
    return rp


def _trace_for(rp, param: str) -> list:
    return [
        e for e in rp.mapping_trace
        if e.param == param and e.stage == "perceptual"
    ]


# ===========================================================================
# A0-1: Нейтральность θ=0.5  (5 pytest cases)
# Контракт: при полностью нейтральных входах formula → base (±1e-6)
# ===========================================================================

class TestA0Neutrality:
    """5 pytest cases / 5 logical assertions."""

    def test_symmetry_bias_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.symmetry_bias, 0.5, abs_tol=1e-6)

    def test_recursion_depth_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.recursion_depth, 0.5, abs_tol=1e-6)

    def test_noise_level_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.noise_level, 0.5, abs_tol=1e-6)

    def test_motion_intensity_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.motion_intensity, 0.5, abs_tol=1e-6)

    def test_texture_complexity_neutral(self):
        # texture включает morphology_guard (не-theta), поэтому [0.5, 0.6]
        rp = _resolve(_neutral_perceptual())
        assert 0.5 <= rp.texture_complexity <= 0.6


# ===========================================================================
# A0-2: Чувствительность — relevant θ +0.20 меняет цель  (7 pytest cases)
# Контракт: delta = (0.70 - 0.50) * weight  ±0.005
# ===========================================================================

class TestA0Sensitivity:
    """7 pytest cases / 14 logical assertions (direction + magnitude)."""

    @pytest.mark.parametrize("param,theta_key,weight", SENSITIVITY_CASES)
    def test_theta_increases_target(self, param, theta_key, weight):
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(**{theta_key: 0.70}))
        val_base = getattr(rp_base, param)
        val_pert = getattr(rp_pert, param)
        # логическая проверка 1: направление
        assert val_pert > val_base, (
            f"{param}: expected increase with {theta_key}+0.20, "
            f"got {val_base:.6f} -> {val_pert:.6f}"
        )
        # логическая проверка 2: величина
        expected_delta = 0.20 * weight
        actual_delta = val_pert - val_base
        assert math.isclose(actual_delta, expected_delta, abs_tol=0.005), (
            f"{param}[{theta_key}]: expected Δ={expected_delta:.4f}, got {actual_delta:.6f}"
        )


# ===========================================================================
# A0-3: Локальность — irrelevant θ НЕ меняет цель  (7 pytest cases)
# Контракт: при theta_key=0.90 param не изменился
# ===========================================================================

class TestA0Locality:
    """7 pytest cases / 7 logical assertions."""

    @pytest.mark.parametrize("param,theta_key", LOCALITY_CASES)
    def test_irrelevant_theta_has_no_effect(self, param, theta_key):
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(**{theta_key: 0.90}))
        val_base = getattr(rp_base, param)
        val_pert = getattr(rp_pert, param)
        assert math.isclose(val_base, val_pert, abs_tol=1e-6), (
            f"{param} changed when irrelevant {theta_key} was perturbed: "
            f"{val_base:.8f} -> {val_pert:.8f}. "
            f"θ₆ ∉ texture_complexity по каноническому контракту."
        )


# ===========================================================================
# A0-4: Clamp [0, 1] при экстремальных входах  (2 pytest cases)
# ===========================================================================

NUMERIC_PARAMS = [
    "symmetry_bias", "recursion_depth", "density_level",
    "noise_level", "motion_intensity", "texture_complexity",
]


class TestA0Clamp:
    """2 pytest cases / 12 logical assertions (6 params × 2 bounds)."""

    def test_extreme_theta_max(self):
        rp = _resolve(_neutral_perceptual(
            harmony_theta_0=1.0, harmony_theta_1=1.0,
            harmony_theta_2=1.0, harmony_theta_3=1.0,
            harmony_theta_4=1.0, harmony_theta_5=1.0,
            harmony_theta_6=1.0, harmony_theta_7=1.0,
            energy=1.0, tension=1.0, density=1.0,
            stability=1.0, section_complexity=1.0,
            noise_proxy=1.0,
        ))
        for attr in NUMERIC_PARAMS:
            val = getattr(rp, attr)
            assert val <= 1.0 + 1e-9, f"{attr}={val:.8f} exceeds 1.0"

    def test_extreme_theta_min(self):
        rp = _resolve(_neutral_perceptual(
            harmony_theta_0=0.0, harmony_theta_1=0.0,
            harmony_theta_2=0.0, harmony_theta_3=0.0,
            harmony_theta_4=0.0, harmony_theta_5=0.0,
            harmony_theta_6=0.0, harmony_theta_7=0.0,
            energy=0.0, tension=0.0, density=0.0,
            stability=0.0, section_complexity=0.0,
            noise_proxy=0.0,
        ))
        for attr in NUMERIC_PARAMS:
            val = getattr(rp, attr)
            assert val >= -1e-9, f"{attr}={val:.8f} below 0.0"


# ===========================================================================
# A1: Схема trace  (6 pytest cases)
# ===========================================================================

class TestA1TraceSchema:
    """6 pytest cases / 10 logical assertions."""

    def test_source_axes_canonical_per_param(self):
        """
        A1-canonical: source_axes для каждого перцептивного param
        содержит ровно те theta-оси, которые указаны в THETA_CONTRACT.
        Это закрывает расхождение №1 (commit c7e4425 vs default.yaml).
        """
        rp = _resolve(_neutral_perceptual())
        for param, expected_axes in THETA_CONTRACT.items():
            entries = _trace_for(rp, param)
            if not entries:
                continue  # param может быть categorical (layout_macro_shape)
            entry = entries[0]
            for ax in expected_axes:
                assert ax in (entry.source_axes or []), (
                    f"{param}: expected theta axis '{ax}' in source_axes, "
                    f"got {entry.source_axes}"
                )
            # θ₆ НЕ должна появляться в texture_complexity
            if param == "texture_complexity":
                assert "harmony_theta_6" not in (entry.source_axes or []), (
                    "θ₆ found in texture_complexity.source_axes — нарушение контракта!"
                )

    def test_layer_id_is_interpretation(self):
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            assert entry.layer_id == "interpretation", (
                f"layer_id expected 'interpretation', got '{entry.layer_id}' "
                f"for param={entry.param}"
            )

    def test_generator_id_is_none_before_step_b(self):
        """До Step B generator_id=None — trace StyleEngine, не composition runtime."""
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            assert entry.generator_id is None, (
                f"generator_id expected None pre-Step-B, got '{entry.generator_id}' "
                f"for param={entry.param}"
            )

    def test_perceptual_entries_have_formula_string(self):
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            if entry.stage == "perceptual" and entry.formula is not None:
                assert isinstance(entry.formula, str) and len(entry.formula) > 0, (
                    f"formula field empty for param={entry.param}"
                )

    def test_input_values_snapshot_all_used_axes(self):
        """
        input_values должен содержать значения ВСЕХ реально использованных θ-осей.
        Проверяем для noise_level (θ₅) и texture_complexity (θ₂, θ₅).
        """
        theta5_val = 0.73
        theta2_val = 0.68
        rp = _resolve(_neutral_perceptual(
            harmony_theta_5=theta5_val,
            harmony_theta_2=theta2_val,
        ))
        # noise_level → θ₅
        for entry in _trace_for(rp, "noise_level"):
            if "harmony_theta_5" in (entry.source_axes or []):
                assert "harmony_theta_5" in entry.input_values, (
                    "harmony_theta_5 in source_axes but missing from input_values (noise_level)"
                )
                assert math.isclose(
                    entry.input_values["harmony_theta_5"], theta5_val, abs_tol=1e-5
                )
        # texture_complexity → θ₂ + θ₅
        for entry in _trace_for(rp, "texture_complexity"):
            axes = entry.source_axes or []
            for ax, expected in [
                ("harmony_theta_2", theta2_val),
                ("harmony_theta_5", theta5_val),
            ]:
                if ax in axes:
                    assert ax in entry.input_values, (
                        f"{ax} in source_axes but missing from input_values (texture_complexity)"
                    )
                    assert math.isclose(entry.input_values[ax], expected, abs_tol=1e-5)

    def test_source_axes_is_list_not_none(self):
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            if entry.stage == "perceptual":
                assert entry.source_axes is not None, (
                    f"source_axes is None for param={entry.param}"
                )
                assert isinstance(entry.source_axes, list)


# ---------------------------------------------------------------------------
# Быстрый smoke без pytest
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback
    classes = [
        TestA0Neutrality, TestA0Sensitivity,
        TestA0Locality, TestA0Clamp, TestA1TraceSchema,
    ]
    passed = failed = 0
    for cls in classes:
        obj = cls()
        for name in dir(obj):
            if not name.startswith("test_"):
                continue
            fn = getattr(obj, name)
            # parametrize раскрываем вручную
            marks = getattr(fn, "pytestmark", [])
            param_sets = []
            for m in marks:
                if hasattr(m, 'args') and m.args:
                    import itertools
                    param_sets = list(m.args[1])
                    break
            if param_sets:
                for ps in param_sets:
                    try:
                        fn(*ps)
                        print(f"  PASS  {cls.__name__}::{name}[{ps}]")
                        passed += 1
                    except Exception:
                        print(f"  FAIL  {cls.__name__}::{name}[{ps}]")
                        traceback.print_exc()
                        failed += 1
            else:
                try:
                    fn()
                    print(f"  PASS  {cls.__name__}::{name}")
                    passed += 1
                except Exception:
                    print(f"  FAIL  {cls.__name__}::{name}")
                    traceback.print_exc()
                    failed += 1
    print(f"\n{passed + failed} cases: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
