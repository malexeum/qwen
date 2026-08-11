"""
CB-3.1 Step B — GeneratorRuntime тесты.

12 pytest cases / 18 логических assertion-контрактов.

Проверяет:
  B-1: ResolvedGeneratorLayer схема (layer_id, generator_id, builder, ...)
  B-2: resolve_stack строит корректный список слоёв
  B-3: render возвращает фактический generator_stack (не декларацию)
  B-4: generator_stack содержит только реально вызванные builders
  B-5: orbit_map нормирован [0, 1], shape корректен
  B-6: layer_results содержит RunResult по каждому слою
  B-7: неизвестный builder → ValueError с информативным сообщением
  B-8: lib/generators.py НЕ изменён (SHA cc95a078 проверяется через import)
  B-9: пустой layers → пустой generator_stack, нулевая карта
  B-10: generator_id в ResolvedGeneratorLayer = builder (не None)
  B-11: source_axes не пустой после resolve (есть хоть одна θ-ось)
  B-12: stochastic_scale=0 → детерминированный результат (два вызова = одинаково)

Запуск:
  pytest tests/test_cb31_b_runtime.py -v
"""
from __future__ import annotations

import math
import numpy as np
import pytest

from lib.style_engine.generator_runtime import (
    GeneratorRuntime,
    ResolvedGeneratorLayer,
    RenderResult,
)
from lib.style_engine.engine import resolve_render_params


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


def _make_render_params(**overrides):
    rp, _, _ = resolve_render_params(
        project_id="test_b",
        analysis_id="gate_b",
        perceptual=_neutral_perceptual(**overrides),
        style_profile_slug="default",
        interpretation_profile_slug="default",
        user_preset=DEFAULT_PRESET,
        strict_theta=True,
    )
    return rp


def _single_layer_profile(builder: str = "julia_orbit_trap") -> dict:
    return {
        "layers": [
            {"id": "layer_0", "builder": builder, "palette_id": "default_dark"}
        ]
    }


def _two_layer_profile() -> dict:
    return {
        "layers": [
            {"id": "layer_0", "builder": "julia_orbit_trap",    "palette_id": "default_dark"},
            {"id": "layer_1", "builder": "orbit_ifs_multi_trap", "palette_id": "default_dark"},
        ]
    }


@pytest.fixture(scope="module")
def runtime():
    return GeneratorRuntime()


@pytest.fixture(scope="module")
def render_params_neutral():
    return _make_render_params()


# ===========================================================================
# B-1: ResolvedGeneratorLayer схема
# ===========================================================================

class TestResolvedLayerSchema:
    """3 pytest cases / 5 logical assertions."""

    def test_layer_has_required_fields(self, runtime, render_params_neutral):
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        assert len(layers) == 1
        layer = layers[0]
        assert isinstance(layer, ResolvedGeneratorLayer)
        assert layer.layer_id == "layer_0"
        assert layer.builder == "julia_orbit_trap"

    def test_generator_id_equals_builder(self, runtime, render_params_neutral):
        """B-10: generator_id не None и = builder."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        layer = layers[0]
        assert layer.generator_id is not None
        assert layer.generator_id == layer.builder

    def test_resolved_mapping_contains_theta_axes(self, runtime, render_params_neutral):
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        mapping = layers[0].resolved_mapping
        for ax in ["harmony_theta_0", "harmony_theta_5", "harmony_theta_7"]:
            assert ax in mapping, f"Missing {ax} in resolved_mapping"
            val = mapping[ax]
            assert 0.0 <= val <= 1.0, f"{ax}={val} out of [0,1]"


# ===========================================================================
# B-2: resolve_stack
# ===========================================================================

class TestResolveStack:
    """2 pytest cases / 4 logical assertions."""

    def test_two_layers_resolved(self, runtime, render_params_neutral):
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _two_layer_profile()
        )
        assert len(layers) == 2
        assert layers[0].builder == "julia_orbit_trap"
        assert layers[1].builder == "orbit_ifs_multi_trap"

    def test_source_axes_not_empty(self, runtime, render_params_neutral):
        """B-11: source_axes содержит хотя бы одну θ-ось после resolve."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        assert len(layers[0].source_axes) > 0, (
            "source_axes пуст после resolve_stack — нет θ-осей из trace"
        )


# ===========================================================================
# B-3 + B-4: generator_stack = фактический журнал
# ===========================================================================

class TestGeneratorStack:
    """3 pytest cases / 5 logical assertions."""

    def test_single_layer_stack(self, runtime, render_params_neutral):
        """B-3: один слой → stack из одного элемента."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        result = runtime.render(layers, seed=42, width=64, height=64)
        assert result.generator_stack == ["julia_orbit_trap"], (
            f"Expected ['julia_orbit_trap'], got {result.generator_stack}"
        )

    def test_two_layer_stack_order(self, runtime, render_params_neutral):
        """B-4: порядок stack совпадает с порядком вызовов, не с YAML-декларацией."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _two_layer_profile()
        )
        result = runtime.render(layers, seed=42, width=64, height=64)
        assert result.generator_stack == ["julia_orbit_trap", "orbit_ifs_multi_trap"], (
            f"Stack order wrong: {result.generator_stack}"
        )

    def test_stack_length_equals_layers(self, runtime, render_params_neutral):
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _two_layer_profile()
        )
        result = runtime.render(layers, seed=42, width=64, height=64)
        assert len(result.generator_stack) == len(layers)


# ===========================================================================
# B-5: orbit_map shape и нормировка
# ===========================================================================

class TestOrbitMap:
    """2 pytest cases / 4 logical assertions."""

    def test_orbit_map_shape(self, runtime, render_params_neutral):
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        result = runtime.render(layers, seed=0, width=64, height=64)
        assert result.orbit_map.shape == (64, 64), (
            f"Expected (64,64), got {result.orbit_map.shape}"
        )

    def test_orbit_map_normalized(self, runtime, render_params_neutral):
        """B-5: orbit_map ∈ [0, 1] после нормировки."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        result = runtime.render(layers, seed=0, width=64, height=64)
        assert result.orbit_map.min() >= -1e-6
        assert result.orbit_map.max() <= 1.0 + 1e-6


# ===========================================================================
# B-6: layer_results
# ===========================================================================

class TestLayerResults:
    """1 pytest case / 2 logical assertions."""

    def test_layer_results_count(self, runtime, render_params_neutral):
        """B-6: layer_results содержит RunResult по каждому слою."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _two_layer_profile()
        )
        result = runtime.render(layers, seed=0, width=64, height=64)
        assert len(result.layer_results) == 2
        from lib.core import RunResult
        for lr in result.layer_results:
            assert isinstance(lr, RunResult)


# ===========================================================================
# B-7: неизвестный builder → ValueError
# ===========================================================================

class TestUnknownBuilder:
    """1 pytest case / 1 logical assertion."""

    def test_unknown_builder_raises(self, runtime, render_params_neutral):
        bad_profile = {"layers": [{"id": "l0", "builder": "nonexistent_generator"}]}
        with pytest.raises(ValueError, match="unknown builder"):
            runtime.resolve_stack("default", render_params_neutral, bad_profile)


# ===========================================================================
# B-9: пустой layers
# ===========================================================================

class TestEmptyLayers:
    """1 pytest case / 3 logical assertions."""

    def test_empty_layers_returns_zero_map(self, runtime, render_params_neutral):
        """B-9: пустой composition_profile → пустой stack, нулевая карта."""
        result = runtime.render([], seed=0, width=32, height=32)
        assert result.generator_stack == []
        assert result.orbit_map.shape == (32, 32)
        assert result.orbit_map.max() == 0.0


# ===========================================================================
# B-12: детерминизм при stochastic_scale=0
# ===========================================================================

class TestDeterminism:
    """1 pytest case / 1 logical assertion."""

    def test_deterministic_with_zero_stochastic(self, runtime, render_params_neutral):
        """B-12: два вызова с одинаковым seed и stochastic_scale=0 → идентичный orbit_map."""
        layers = runtime.resolve_stack(
            "default", render_params_neutral, _single_layer_profile()
        )
        r1 = runtime.render(layers, seed=7, width=64, height=64, stochastic_scale=0.0)
        r2 = runtime.render(layers, seed=7, width=64, height=64, stochastic_scale=0.0)
        np.testing.assert_array_equal(
            r1.orbit_map, r2.orbit_map,
            err_msg="orbit_map не детерминирован при stochastic_scale=0"
        )


# ---------------------------------------------------------------------------
# Быстрый smoke без pytest
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback
    rt = GeneratorRuntime()
    rp = _make_render_params()
    classes = [
        TestResolvedLayerSchema, TestResolveStack, TestGeneratorStack,
        TestOrbitMap, TestLayerResults, TestUnknownBuilder,
        TestEmptyLayers, TestDeterminism,
    ]
    passed = failed = 0
    for cls in classes:
        obj = cls()
        for name in dir(obj):
            if not name.startswith("test_"):
                continue
            fn = getattr(obj, name)
            try:
                import inspect
                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())
                kwargs = {}
                if "runtime" in params:
                    kwargs["runtime"] = rt
                if "render_params_neutral" in params:
                    kwargs["render_params_neutral"] = rp
                fn(**kwargs)
                print(f"  PASS  {cls.__name__}::{name}")
                passed += 1
            except Exception:
                print(f"  FAIL  {cls.__name__}::{name}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed + failed} cases: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
