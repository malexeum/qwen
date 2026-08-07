# test_composition.py
# Минимальный smoke-тест для composition pipeline.
# Запуск: python -m pytest lib/composition/test_composition.py -v
# или:    python lib/composition/test_composition.py

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from composition.composition_planner import (
    PlannerInput, build_composition_plan,
    _compute_density, _compute_symmetry, _compute_visual_mass,
)
from composition.composition_adapter import build_planner_input


# ── helpers ─────────────────────────────────────────────────────────────────

SAMPLE_FEATURES = {
    "bpm": 120.0,
    "energy": 0.5,
    "repetition_score": 0.75,
    "band_energy_0_250_hz": 0.30,
    "band_energy_250_2000_hz": 0.50,
    "band_energy_2000_6000_hz": 0.15,
}

SAMPLE_PERCEPTUAL = {
    "stability": 0.8,
    "tension": 0.4,
    "macro_shape_hint": "ABA_like",
}


def _check(condition: bool, msg: str):
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"OK  : {msg}")


# ── тесты ───────────────────────────────────────────────────────────────────

def test_planner_input_ranges():
    inp = build_planner_input(SAMPLE_FEATURES, SAMPLE_PERCEPTUAL)
    _check(40.0 <= inp.bpm <= 240.0, f"bpm in [40, 240]: {inp.bpm}")
    for field_name in ("energy", "repetition_score", "band_low", "band_mid",
                        "band_high", "perceptual_stability", "perceptual_tension"):
        v = getattr(inp, field_name)
        _check(0.0 <= v <= 1.0, f"{field_name} in [0, 1]: {v}")
    _check(inp.band_low + inp.band_mid + inp.band_high <= 1.001,
           "band sum <= 1")


def test_zone_weights_sum_to_one():
    inp = build_planner_input(SAMPLE_FEATURES, SAMPLE_PERCEPTUAL)
    plan = build_composition_plan(inp)
    w_sum = sum(z.weight for z in plan.zones)
    _check(abs(w_sum - 1.0) < 0.001, f"zone weights sum == 1.0 (got {w_sum})")


def test_determinism():
    inp = build_planner_input(SAMPLE_FEATURES, SAMPLE_PERCEPTUAL, seed=7)
    plan_a = build_composition_plan(inp)
    plan_b = build_composition_plan(inp)
    _check(plan_a.to_dict() == plan_b.to_dict(), "determinism: same input → same output")


def test_archetypes_all_reachable():
    """Проверяем, что все 4 архетипа достижимы через hint."""
    for hint, expected in [
        ("ABA_like", "radial_balance"),
        ("arch",     "radial_balance"),
        ("linear",   "diagonal_tension"),
        ("stochastic", "organic_flow"),
    ]:
        f = dict(SAMPLE_FEATURES)
        p = dict(SAMPLE_PERCEPTUAL, macro_shape_hint=hint)
        inp = build_planner_input(f, p)
        plan = build_composition_plan(inp)
        _check(plan.archetype == expected,
               f"hint={hint!r} → archetype={expected!r} (got {plan.archetype!r})")


def test_edge_bpm_low():
    """Очень медленный трек: BPM=45 должен клипироваться к 40."""
    f = dict(SAMPLE_FEATURES, bpm=35.0)
    inp = build_planner_input(f, SAMPLE_PERCEPTUAL)
    _check(inp.bpm == 40.0, f"bpm clipped to 40 (got {inp.bpm})")


def test_band_overflow_normalization():
    """Если полосы дают сумму > 1, адаптер должен нормировать."""
    f = dict(SAMPLE_FEATURES,
             band_energy_0_250_hz=0.60,
             band_energy_250_2000_hz=0.60,
             band_energy_2000_6000_hz=0.60)
    inp = build_planner_input(f, SAMPLE_PERCEPTUAL)
    _check(inp.band_low + inp.band_mid + inp.band_high <= 1.001,
           "band sum normalized when overflow")


def test_canvas_size_passthrough():
    inp = build_planner_input(SAMPLE_FEATURES, SAMPLE_PERCEPTUAL)
    plan = build_composition_plan(inp, canvas_width_px=1024, canvas_height_px=768)
    _check(plan.canvas_width_px == 1024, "canvas width passthrough")
    _check(plan.canvas_height_px == 768, "canvas height passthrough")


def test_to_dict_serializable():
    import json
    inp = build_planner_input(SAMPLE_FEATURES, SAMPLE_PERCEPTUAL)
    plan = build_composition_plan(inp)
    try:
        s = json.dumps(plan.to_dict())
        _check(len(s) > 0, "to_dict() is JSON-serializable")
    except Exception as e:
        _check(False, f"to_dict() JSON error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Composition Pipeline Smoke Tests")
    print("=" * 60)
    test_planner_input_ranges()
    test_zone_weights_sum_to_one()
    test_determinism()
    test_archetypes_all_reachable()
    test_edge_bpm_low()
    test_band_overflow_normalization()
    test_canvas_size_passthrough()
    test_to_dict_serializable()
    print("=" * 60)
    print("All tests passed.")
