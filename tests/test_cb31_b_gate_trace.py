"""
tests/test_cb31_b_gate_trace.py

Gate-тест для merge Step B.

Доказывает полную цепочку:

  θ₅ (harmony_theta_5)
    ↓ interpretation formula (noise_level чувствителен к θ₅ согласно A0)
  RenderParams.noise_level
    ↓ GeneratorRuntime.resolve_stack
  ResolvedGeneratorLayer.resolved_mapping["harmony_theta_5"]
    ↓ GeneratorRuntime.render → builder_fn(SimState)
  RenderResult.generator_stack  [фактически вызванный builder]

Печатает JSON-трейс при запуске с -s.

Запуск:
  pytest tests/test_cb31_b_gate_trace.py -v -s
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from lib.style_engine.engine import resolve_render_params
from lib.style_engine.generator_runtime import GeneratorRuntime, ResolvedGeneratorLayer


# ---------------------------------------------------------------------------
# Фабрики
# ---------------------------------------------------------------------------

DEFAULT_PRESET = {
    "id": "neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}

SINGLE_LAYER_PROFILE = {
    "layers": [
        {"id": "layer_0", "builder": "julia_orbit_trap", "palette_id": "neutral_noir"}
    ]
}


def _perceptual(theta_5: float = 0.5) -> dict:
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
        "harmony_theta_5":    theta_5,   # управляемая ось
        "harmony_theta_6":    0.5,
        "harmony_theta_7":    0.5,
    }


def _resolve(theta_5: float):
    rp, _, _ = resolve_render_params(
        project_id="gate_b",
        analysis_id="theta5_sensitivity",
        perceptual=_perceptual(theta_5),
        style_profile_slug="default",
        interpretation_profile_slug="default",
        user_preset=DEFAULT_PRESET,
        strict_theta=True,
    )
    return rp


def _build_trace_record(layer: ResolvedGeneratorLayer, result) -> dict:
    """JSON-трейс уровня B для печати."""
    return {
        "layer_id":        layer.layer_id,
        "generator_id":    layer.generator_id,
        "source_axes":     layer.source_axes,
        "resolved_mapping": {
            k: round(float(v), 6)
            for k, v in layer.resolved_mapping.items()
        },
        "generator_stack": result.generator_stack,
    }


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------

class TestGateTraceB:

    def test_trace_record_has_required_fields(self, capsys):
        """
        Реальный runtime trace уровня B:
        layer_id, generator_id, source_axes содержат непустые значения,
        resolved_mapping содержит harmony_theta_5.
        """
        rt = GeneratorRuntime()
        rp = _resolve(0.5)
        layers = rt.resolve_stack("default", rp, SINGLE_LAYER_PROFILE)
        result = rt.render(layers, seed=42, width=32, height=32)

        layer = layers[0]
        trace = _build_trace_record(layer, result)

        print("\n=== Runtime trace (theta_5=0.50) ===")
        print(json.dumps(trace, indent=2, ensure_ascii=False))

        assert layer.layer_id == "layer_0"
        assert layer.generator_id == "julia_orbit_trap"
        assert "harmony_theta_5" in layer.source_axes, (
            f"harmony_theta_5 отсутствует в source_axes: {layer.source_axes}"
        )
        assert "harmony_theta_5" in layer.resolved_mapping
        assert result.generator_stack == ["julia_orbit_trap"]

    def test_theta5_changes_resolved_mapping(self):
        """
        θ₅: 0.50 → 0.70 → меняется resolved_mapping["harmony_theta_5"].
        """
        rt = GeneratorRuntime()

        rp_50 = _resolve(0.50)
        rp_70 = _resolve(0.70)

        layers_50 = rt.resolve_stack("default", rp_50, SINGLE_LAYER_PROFILE)
        layers_70 = rt.resolve_stack("default", rp_70, SINGLE_LAYER_PROFILE)

        t5_50 = layers_50[0].resolved_mapping["harmony_theta_5"]
        t5_70 = layers_70[0].resolved_mapping["harmony_theta_5"]

        assert not math.isclose(t5_50, t5_70, abs_tol=1e-6), (
            f"θ₅ изменился 0.50→0.70, но resolved_mapping не изменился: "
            f"{t5_50} vs {t5_70}"
        )
        assert t5_70 > t5_50, (
            f"θ₅ вырос, но resolved_mapping уменьшился: {t5_50} → {t5_70}"
        )

    def test_theta5_changes_noise_level(self):
        """
        θ₅ → interpretation formula → noise_level меняется.
        Доказывает: A0 формула не только в YAML, но реально влияет на RenderParams.
        """
        rp_50 = _resolve(0.50)
        rp_70 = _resolve(0.70)

        assert not math.isclose(rp_50.noise_level, rp_70.noise_level, abs_tol=1e-6), (
            f"θ₅ изменился 0.50→0.70, но noise_level не изменился: "
            f"{rp_50.noise_level} vs {rp_70.noise_level}"
        )

    def test_theta5_changes_variation_seed(self):
        """
        θ₅: 0.50 → 0.70 → меняется variation_seed.
        variation_seed зависит от θ-вектора, значит одинаковые фичер невозможны.
        """
        rp_50 = _resolve(0.50)
        rp_70 = _resolve(0.70)

        assert rp_50.variation_seed != rp_70.variation_seed, (
            f"variation_seed не изменился: {rp_50.variation_seed} == {rp_70.variation_seed}. "
            "_compute_variation_seed должен включать theta_values в хэш."
        )

    def test_generator_stack_contains_actual_builder(self, capsys):
        """
        generator_stack содержит фактически вызванный builder,
        не строку из YAML-декларации.
        Печатает два trace для визуального сравнения.
        """
        rt = GeneratorRuntime()

        rp_50 = _resolve(0.50)
        rp_70 = _resolve(0.70)

        layers_50 = rt.resolve_stack("default", rp_50, SINGLE_LAYER_PROFILE)
        layers_70 = rt.resolve_stack("default", rp_70, SINGLE_LAYER_PROFILE)

        r50 = rt.render(layers_50, seed=42, width=32, height=32)
        r70 = rt.render(layers_70, seed=42, width=32, height=32)

        trace_50 = _build_trace_record(layers_50[0], r50)
        trace_70 = _build_trace_record(layers_70[0], r70)

        print("\n=== Runtime trace (theta_5=0.50) ===")
        print(json.dumps(trace_50, indent=2, ensure_ascii=False))
        print("\n=== Runtime trace (theta_5=0.70) ===")
        print(json.dumps(trace_70, indent=2, ensure_ascii=False))
        print(f"\nИзменения при θ₅ 0.50 → 0.70:")
        print(f"  noise_level:       {rp_50.noise_level:.6f} → {rp_70.noise_level:.6f}")
        print(f"  harmony_theta_5:   {layers_50[0].resolved_mapping['harmony_theta_5']:.6f} → {layers_70[0].resolved_mapping['harmony_theta_5']:.6f}")
        print(f"  variation_seed:    {rp_50.variation_seed} → {rp_70.variation_seed}")
        print(f"  generator_stack:   {r50.generator_stack}")

        # Стек содержит фактический builder, не пустой список
        assert len(r50.generator_stack) == 1
        assert r50.generator_stack[0] == "julia_orbit_trap"
        assert r70.generator_stack[0] == "julia_orbit_trap"

        # θ₅ действительно изменился в resolved_mapping
        assert not math.isclose(
            trace_50["resolved_mapping"]["harmony_theta_5"],
            trace_70["resolved_mapping"]["harmony_theta_5"],
            abs_tol=1e-6
        )
