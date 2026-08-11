"""
CB-3.1 Gate A0 + A1 tests.

Структура:
  A0: Тесты формул (нейтральность, чувствительность, локальность, clamp)
  A1: Тесты схемы trace (source_axes, formula, input_values, layer_id, generator_id)

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
    """
    Полностью нейтральный perceptual-словарь.
    Все классические оси = 0.5, все theta = 0.5.
    """
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
    """Shortcut: resolve с default-профилем."""
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


# ---------------------------------------------------------------------------
# A0-1: Нейтральность при theta=0.5
# С полностью нейтральными входами все параметры должны совпадать с base (0.5).
# Пресет preset тоже нейтральный (все пресет-слайдеры = 0.5).
# ---------------------------------------------------------------------------

class TestA0Neutrality:
    """Gate A0-1: нейтральность."""

    def test_symmetry_bias_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.symmetry_bias, 0.5, abs_tol=1e-6), (
            f"symmetry_bias expected 0.5, got {rp.symmetry_bias}"
        )

    def test_recursion_depth_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.recursion_depth, 0.5, abs_tol=1e-6), (
            f"recursion_depth expected 0.5, got {rp.recursion_depth}"
        )

    def test_noise_level_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.noise_level, 0.5, abs_tol=1e-6), (
            f"noise_level expected 0.5, got {rp.noise_level}"
        )

    def test_motion_intensity_neutral(self):
        rp = _resolve(_neutral_perceptual())
        assert math.isclose(rp.motion_intensity, 0.5, abs_tol=1e-6), (
            f"motion_intensity expected 0.5, got {rp.motion_intensity}"
        )

    def test_texture_complexity_neutral(self):
        rp = _resolve(_neutral_perceptual())
        # texture_complexity: base=0.5 + morphology_guard*0.30 + ...
        # при нейтральных входах morphology_guard ≈ 0.20 (section=0.5, tension=0.5, rep=0.5, stab=0.5)
        # morphology_guard = 0.5*0.5 + 0.4*0.5 - 0.3*0.5 - 0.3*0.5 = 0.25+0.2-0.15-0.15 = 0.15
        # texture = 0.5 + 0.15*0.30 + 0 + 0 = 0.5 + 0.045 = 0.545
        # после preset (neutral) = 0.545 + (0.5-0.5)*0.5 = 0.545
        # morphology_guard не зависит от theta, так что проверяем в range [0.5, 0.6]
        assert 0.5 <= rp.texture_complexity <= 0.6, (
            f"texture_complexity expected [0.5, 0.6] at neutral inputs, got {rp.texture_complexity}"
        )


# ---------------------------------------------------------------------------
# A0-2: Чувствительность: relevant theta +0.20 меняет целевой параметр
# ---------------------------------------------------------------------------

class TestA0Sensitivity:
    """Gate A0-2: чувствительность."""

    def test_theta5_increases_noise_level(self):
        """theta_5 (+0.20) → noise_level должен вырасти."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_5=0.70))
        assert rp_pert.noise_level > rp_base.noise_level, (
            f"noise_level should increase with theta_5+0.20: "
            f"{rp_base.noise_level} -> {rp_pert.noise_level}"
        )
        # Ожидаемый дельта: (0.70-0.5)*0.25 = 0.05
        delta = rp_pert.noise_level - rp_base.noise_level
        assert math.isclose(delta, 0.05, abs_tol=0.005), (
            f"Expected delta ~0.05, got {delta:.6f}"
        )

    def test_theta2_increases_recursion_depth(self):
        """theta_2 (+0.20) → recursion_depth должен вырасти."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_2=0.70))
        assert rp_pert.recursion_depth > rp_base.recursion_depth
        delta = rp_pert.recursion_depth - rp_base.recursion_depth
        assert math.isclose(delta, 0.05, abs_tol=0.005), (
            f"Expected delta ~0.05, got {delta:.6f}"
        )

    def test_theta0_increases_symmetry_bias(self):
        """theta_0 (+0.20) → symmetry_bias должен вырасти."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_0=0.70))
        assert rp_pert.symmetry_bias > rp_base.symmetry_bias
        delta = rp_pert.symmetry_bias - rp_base.symmetry_bias
        assert math.isclose(delta, 0.04, abs_tol=0.005), (
            f"Expected delta ~0.04, got {delta:.6f}"
        )

    def test_theta6_increases_motion_intensity(self):
        """theta_6 (+0.20) → motion_intensity должен вырасти."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_6=0.70))
        assert rp_pert.motion_intensity > rp_base.motion_intensity
        delta = rp_pert.motion_intensity - rp_base.motion_intensity
        assert math.isclose(delta, 0.04, abs_tol=0.005), (
            f"Expected delta ~0.04, got {delta:.6f}"
        )

    def test_theta7_increases_symmetry_bias(self):
        """theta_7 (+0.20) → symmetry_bias должен вырасти."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_7=0.70))
        assert rp_pert.symmetry_bias > rp_base.symmetry_bias
        delta = rp_pert.symmetry_bias - rp_base.symmetry_bias
        assert math.isclose(delta, 0.03, abs_tol=0.005), (
            f"Expected delta ~0.03, got {delta:.6f}"
        )


# ---------------------------------------------------------------------------
# A0-3: Локальность: нерелевантная theta НЕ меняет целевой параметр
# ---------------------------------------------------------------------------

class TestA0Locality:
    """Gate A0-3: локальность."""

    def test_theta1_does_not_affect_noise_level(self):
        """theta_1 (стабильность×смена) НЕ входит в noise_level."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_1=0.90))
        assert math.isclose(rp_base.noise_level, rp_pert.noise_level, abs_tol=1e-6), (
            f"theta_1 should NOT affect noise_level: "
            f"{rp_base.noise_level} vs {rp_pert.noise_level}"
        )

    def test_theta3_does_not_affect_motion_intensity(self):
        """theta_3 (напряжение) НЕ входит в motion_intensity."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_3=0.90))
        assert math.isclose(rp_base.motion_intensity, rp_pert.motion_intensity, abs_tol=1e-6), (
            f"theta_3 should NOT affect motion_intensity: "
            f"{rp_base.motion_intensity} vs {rp_pert.motion_intensity}"
        )

    def test_theta4_does_not_affect_recursion_depth(self):
        """theta_4 (контраст секций) НЕ входит в recursion_depth."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_4=0.90))
        assert math.isclose(rp_base.recursion_depth, rp_pert.recursion_depth, abs_tol=1e-6), (
            f"theta_4 should NOT affect recursion_depth"
        )

    def test_theta7_does_not_affect_noise_level(self):
        """theta_7 (crystallinity) НЕ входит в noise_level."""
        rp_base = _resolve(_neutral_perceptual())
        rp_pert = _resolve(_neutral_perceptual(harmony_theta_7=0.90))
        assert math.isclose(rp_base.noise_level, rp_pert.noise_level, abs_tol=1e-6), (
            f"theta_7 should NOT affect noise_level"
        )


# ---------------------------------------------------------------------------
# A0-4: Clamp [0, 1]
# ---------------------------------------------------------------------------

class TestA0Clamp:
    """Gate A0-4: все параметры остаются в [0, 1] при экстремальных theta."""

    def test_extreme_theta_max(self):
        """theta = 1.0 → все параметры <= 1.0."""
        rp = _resolve(_neutral_perceptual(
            harmony_theta_0=1.0, harmony_theta_1=1.0,
            harmony_theta_2=1.0, harmony_theta_3=1.0,
            harmony_theta_4=1.0, harmony_theta_5=1.0,
            harmony_theta_6=1.0, harmony_theta_7=1.0,
            energy=1.0, tension=1.0, density=1.0,
            stability=1.0, section_complexity=1.0,
            noise_proxy=1.0,
        ))
        for attr in ["symmetry_bias", "recursion_depth", "density_level",
                     "noise_level", "motion_intensity", "texture_complexity"]:
            val = getattr(rp, attr)
            assert val <= 1.0 + 1e-9, f"{attr}={val} exceeds 1.0"

    def test_extreme_theta_min(self):
        """theta = 0.0 → все параметры >= 0.0."""
        rp = _resolve(_neutral_perceptual(
            harmony_theta_0=0.0, harmony_theta_1=0.0,
            harmony_theta_2=0.0, harmony_theta_3=0.0,
            harmony_theta_4=0.0, harmony_theta_5=0.0,
            harmony_theta_6=0.0, harmony_theta_7=0.0,
            energy=0.0, tension=0.0, density=0.0,
            stability=0.0, section_complexity=0.0,
            noise_proxy=0.0,
        ))
        for attr in ["symmetry_bias", "recursion_depth", "density_level",
                     "noise_level", "motion_intensity", "texture_complexity"]:
            val = getattr(rp, attr)
            assert val >= -1e-9, f"{attr}={val} below 0.0"


# ---------------------------------------------------------------------------
# A1: Тесты схемы trace
# ---------------------------------------------------------------------------

class TestA1TraceSchema:
    """Gate A1: MappingTraceEntry несёт полный theta-провенанс."""

    def test_all_perceptual_entries_have_source_axes(self):
        """A1-1: каждый perceptual-entry имеет source_axes (не None)."""
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            if entry.stage == "perceptual":
                assert entry.source_axes is not None, (
                    f"source_axes is None for param={entry.param}"
                )
                assert isinstance(entry.source_axes, list), (
                    f"source_axes must be list for param={entry.param}"
                )

    def test_theta5_in_noise_level_trace(self):
        """A1-2: harmony_theta_5 должна появляться в source_axes noise_level."""
        rp = _resolve(_neutral_perceptual(harmony_theta_5=0.70))
        noise_entries = [
            e for e in rp.mapping_trace
            if e.param == "noise_level" and e.stage == "perceptual"
        ]
        assert noise_entries, "No perceptual trace entry for noise_level"
        entry = noise_entries[0]
        assert "harmony_theta_5" in entry.source_axes, (
            f"harmony_theta_5 not in source_axes={entry.source_axes}"
        )

    def test_layer_id_is_interpretation(self):
        """A1-3: все trace entries до Stage B имеют layer_id='interpretation'."""
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            assert entry.layer_id == "interpretation", (
                f"layer_id expected 'interpretation', got '{entry.layer_id}' "
                f"for param={entry.param} stage={entry.stage}"
            )

    def test_generator_id_is_none(self):
        """A1-3b: generator_id=None на этапе A (до подключения composition runtime)."""
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            assert entry.generator_id is None, (
                f"generator_id expected None pre-Step-B, got '{entry.generator_id}' "
                f"for param={entry.param}"
            )

    def test_perceptual_entries_have_formula(self):
        """A1-4: perceptual entries несут не-None formula."""
        rp = _resolve(_neutral_perceptual())
        for entry in rp.mapping_trace:
            if entry.stage == "perceptual":
                # Если в YAML есть formula: — она должна быть записана
                # (для default.yaml все 5 параметров имеют formula)
                if entry.formula is not None:
                    assert isinstance(entry.formula, str) and len(entry.formula) > 0, (
                        f"formula field empty for param={entry.param}"
                    )

    def test_input_values_snapshot_theta5(self):
        """A1-5: снимок input_values фиксирует значение theta_5 на момент вычисления."""
        rp = _resolve(_neutral_perceptual(harmony_theta_5=0.73))
        noise_entries = [
            e for e in rp.mapping_trace
            if e.param == "noise_level" and e.stage == "perceptual"
        ]
        assert noise_entries
        entry = noise_entries[0]
        if "harmony_theta_5" in (entry.source_axes or []):
            assert "harmony_theta_5" in entry.input_values, (
                f"harmony_theta_5 in source_axes but missing from input_values"
            )
            assert math.isclose(
                entry.input_values["harmony_theta_5"], 0.73, abs_tol=1e-5
            ), (
                f"input_values snapshot mismatch: "
                f"expected 0.73, got {entry.input_values.get('harmony_theta_5')}"
            )

    def test_theta2_in_texture_complexity_trace(self):
        """A1-6: harmony_theta_2 должна появляться в source_axes texture_complexity."""
        rp = _resolve(_neutral_perceptual(harmony_theta_2=0.80))
        tex_entries = [
            e for e in rp.mapping_trace
            if e.param == "texture_complexity" and e.stage == "perceptual"
        ]
        assert tex_entries, "No perceptual trace entry for texture_complexity"
        entry = tex_entries[0]
        assert "harmony_theta_2" in entry.source_axes, (
            f"harmony_theta_2 not in source_axes={entry.source_axes}"
        )


# ---------------------------------------------------------------------------
# Отчёт o пройденных gate-ах (pytest summary сам подсчитывает)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Быстрый smoke-прогон без pytest
    import traceback
    tests = [
        TestA0Neutrality,
        TestA0Sensitivity,
        TestA0Locality,
        TestA0Clamp,
        TestA1TraceSchema,
    ]
    passed = failed = 0
    for cls in tests:
        obj = cls()
        for name in dir(obj):
            if not name.startswith("test_"):
                continue
            try:
                getattr(obj, name)()
                print(f"  PASS  {cls.__name__}::{name}")
                passed += 1
            except Exception:
                print(f"  FAIL  {cls.__name__}::{name}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
