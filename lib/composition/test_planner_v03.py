"""Unit tests для VisualCompositionPlanner v0.3.

Запуск: python -m pytest lib/composition/test_planner_v03.py -v

Требования (TZ Definition of Done):
  1. Determinism — два запуска с одним входом дают идентичный JSON
  2. Alias canonicalization — aliases приводятся к canonical IDs
  3. Coverage — нет непокрытых обязательных осей
  4. Layer count — 3–5 включённых слоёв
  5. Layer independence — уникальные layer_id и разные seeds
  6. No PIL/matplotlib imports в пакете composition
  7. Layer seeds различаются между слоями
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Make sure repo root is on path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from lib.composition.config_loader import load_composition_config
from lib.composition.planner import (
    PerceptualLatent,
    RenderParams,
    TrackMetadata,
    build_visual_composition_plan,
)
from lib.composition.coverage import validate_coverage


def _make_blues_inputs():
    perceptual = PerceptualLatent(
        energy=0.55, tension=0.35, repetition=0.62,
        tempo=0.42, section_complexity=0.58, silence_rate=0.28,
        harmonic_stability=0.70, harmonic_change_rate=0.30,
        spectral_flatness=0.45, high_frequency_energy=0.30,
    )
    render_params = RenderParams(
        style_profile_slug="blues_jazz",
        symmetry_bias=0.62, density_level=0.48,
        noise_level=0.12, recursion_depth=0.55,
        motion_intensity=0.40, texture_complexity=0.52,
        layout_macro_shape="center", palette_id="nocturne_amber",
        visual_style_slug="grainfilm", variation_seed=0,
    )
    track = TrackMetadata(
        audio_content_hash="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        title="Autumn Leaves",
        artist="Bill Evans",
        duration_ms=225000,
    )
    return perceptual, render_params, track


def _make_electronic_inputs():
    perceptual = PerceptualLatent(
        energy=0.78, tension=0.72, repetition=0.38,
        tempo=0.75, section_complexity=0.65, silence_rate=0.10,
        harmonic_stability=0.30, harmonic_change_rate=0.80,
        spectral_flatness=0.70, high_frequency_energy=0.75,
    )
    render_params = RenderParams(
        style_profile_slug="electronic",
        symmetry_bias=0.40, density_level=0.72,
        noise_level=0.20, recursion_depth=0.65,
        motion_intensity=0.78, texture_complexity=0.68,
        layout_macro_shape="center", palette_id="spectral_neon",
        visual_style_slug="grainfilm", variation_seed=0,
    )
    track = TrackMetadata(
        audio_content_hash="sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        title="Acid Rain",
        artist="Orbital",
        duration_ms=380000,
    )
    return perceptual, render_params, track


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cfg():
    return load_composition_config()


@pytest.fixture(scope="module")
def blues_plan(tmp_path_factory, cfg):
    tmp = tmp_path_factory.mktemp("plans")
    p, r, t = _make_blues_inputs()
    return build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp, save_artifacts=True,
    )


@pytest.fixture(scope="module")
def electronic_plan(tmp_path_factory, cfg):
    tmp = tmp_path_factory.mktemp("plans")
    p, r, t = _make_electronic_inputs()
    return build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp, save_artifacts=True,
    )


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_plan_determinism(tmp_path, cfg):
    """Два запуска с одним входом → идентичный JSON (кроме plan_id)."""
    p, r, t = _make_blues_inputs()
    plan1 = build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp_path / "r1", save_artifacts=True,
    )
    plan2 = build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp_path / "r2", save_artifacts=True,
    )
    assert plan1.plan_id == plan2.plan_id, "plan_id must be deterministic"
    d1 = plan1.to_dict()
    d2 = plan2.to_dict()
    assert d1 == d2, "Plans must be bit-identical"


def test_alias_canonicalization(cfg):
    """smooth_geometric_baseline → julia_orbit_trap, не попадает в план как alias."""
    from lib.composition.canonicalize import build_alias_index, canonicalize_generator_id
    idx = build_alias_index(cfg.catalog)
    assert canonicalize_generator_id("smooth_geometric_baseline", cfg.catalog, idx) == "julia_orbit_trap"
    assert canonicalize_generator_id("random_baseline", cfg.catalog, idx) == "chaotic_scattering_basins"
    assert canonicalize_generator_id("single_parameter_map_baseline", cfg.catalog, idx) == "orbit_ifs_multi_trap"


def test_blues_layer_count(blues_plan):
    enabled = [l for l in blues_plan.layers if l.enabled]
    assert 3 <= len(enabled) <= 5, f"Got {len(enabled)} enabled layers"


def test_electronic_layer_count(electronic_plan):
    enabled = [l for l in electronic_plan.layers if l.enabled]
    assert 3 <= len(enabled) <= 5, f"Got {len(enabled)} enabled layers"


def test_layer_independence(blues_plan):
    """Включённые слои имеют уникальные layer_id и уникальные seeds."""
    enabled = [l for l in blues_plan.layers if l.enabled]
    ids = [l.layer_id for l in enabled]
    seeds = [l.seed for l in enabled]
    assert len(ids) == len(set(ids)), "layer_id must be unique"
    assert len(seeds) == len(set(seeds)), "layer seeds must be unique"


def test_parameter_coverage_blues(blues_plan):
    uncovered = validate_coverage(blues_plan.parameter_coverage)
    assert not uncovered, f"Uncovered axes: {uncovered}"


def test_parameter_coverage_electronic(electronic_plan):
    uncovered = validate_coverage(electronic_plan.parameter_coverage)
    assert not uncovered, f"Uncovered axes: {uncovered}"


def test_no_aliases_in_plan(blues_plan):
    """В план не должны попасть aliases — только canonical IDs."""
    aliases = {"smooth_geometric_baseline", "random_baseline", "single_parameter_map_baseline"}
    for layer in blues_plan.layers:
        assert layer.generator_id not in aliases, (
            f"Alias '{layer.generator_id}' found in plan layer '{layer.layer_id}'"
        )


def test_no_pil_imports():
    """Пакет composition не должен импортировать PIL или matplotlib."""
    import lib.composition.schema
    import lib.composition.planner
    import lib.composition.mappings.julia
    import lib.composition.mappings.ifs
    import lib.composition.mappings.duffing
    import lib.composition.mappings.scattering
    import lib.composition.mappings.procedural

    forbidden = {"PIL", "Pillow", "matplotlib"}
    for mod_name, mod in sys.modules.items():
        top = mod_name.split(".")[0]
        if top in forbidden:
            pass  # проверяем ниже

    composition_mods = [
        "lib.composition.schema",
        "lib.composition.planner",
        "lib.composition.config_loader",
        "lib.composition.seed_policy",
        "lib.composition.canonicalize",
        "lib.composition.validation",
        "lib.composition.coverage",
        "lib.composition.storage",
        "lib.composition.mappings.julia",
        "lib.composition.mappings.ifs",
        "lib.composition.mappings.duffing",
        "lib.composition.mappings.scattering",
        "lib.composition.mappings.procedural",
    ]
    for mod_name in composition_mods:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for bad in ["import PIL", "from PIL", "import matplotlib", "from matplotlib"]:
            assert bad not in src, (
                f"Forbidden import '{bad}' found in {mod.__file__}"
            )


def test_storage_artifacts(tmp_path, cfg):
    """Три обязательных JSON-файла создаются в storage папке."""
    p, r, t = _make_blues_inputs()
    plan = build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp_path, save_artifacts=True,
    )
    plan_dir = tmp_path / plan.plan_id
    assert (plan_dir / "visual_composition_plan.json").exists()
    assert (plan_dir / "parameter_coverage.json").exists()
    assert (plan_dir / "planner_diagnostics.json").exists()


def test_canvas_spec(blues_plan):
    assert blues_plan.canvas.width_px == 1024
    assert blues_plan.canvas.height_px == 1024
    assert blues_plan.canvas.mode == "preview"
