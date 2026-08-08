"""Tests для reference executor v0.3.

Запуск: python -m pytest lib/reference_renderer/test_execute_plan.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from lib.composition.config_loader import load_composition_config
from lib.composition.planner import (
    PerceptualLatent, RenderParams, TrackMetadata,
    build_visual_composition_plan,
)
from lib.reference_renderer.execute_plan import execute_plan
from lib.reference_renderer.canvas import Canvas
from lib.reference_renderer.blend import composite
from lib.reference_renderer.palette import resolve_palette
from lib.reference_renderer.postprocess import postprocess


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cfg():
    return load_composition_config()


@pytest.fixture(scope="module")
def blues_plan(tmp_path_factory, cfg):
    tmp = tmp_path_factory.mktemp("render_plans")
    p = PerceptualLatent(
        energy=0.55, tension=0.35, repetition=0.62,
        tempo=0.42, section_complexity=0.58, silence_rate=0.28,
        harmonic_stability=0.70, harmonic_change_rate=0.30,
        spectral_flatness=0.45, high_frequency_energy=0.30,
    )
    r = RenderParams(
        style_profile_slug="blues_jazz",
        symmetry_bias=0.62, density_level=0.48,
        noise_level=0.12, recursion_depth=0.55,
        motion_intensity=0.40, texture_complexity=0.52,
        layout_macro_shape="center", palette_id="nocturne_amber",
        visual_style_slug="grainfilm", variation_seed=0,
    )
    t = TrackMetadata(
        audio_content_hash="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        title="Autumn Leaves", artist="Bill Evans", duration_ms=225000,
    )
    return build_visual_composition_plan(
        perceptual=p, render_params=r, track_metadata=t,
        config=cfg, storage_root=tmp, save_artifacts=True,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_canvas_black():
    c = Canvas.black(64, 64)
    assert c.data.shape == (64, 64, 4)
    assert c.data.dtype == np.float32
    assert c.data.sum() == 0.0


def test_canvas_fill_background():
    c = Canvas.black(64, 64)
    c.fill_background((10, 20, 30, 255))
    assert abs(c.data[0, 0, 0] - 10 / 255.0) < 1e-5
    assert abs(c.data[0, 0, 2] - 30 / 255.0) < 1e-5


def test_canvas_to_uint8():
    c = Canvas.black(8, 8)
    c.data[..., 0] = 1.0
    arr = c.to_uint8()
    assert arr.dtype == np.uint8
    assert arr[0, 0, 0] == 255


def test_blend_screen():
    dst = np.zeros((4, 4, 4), dtype=np.float32)
    dst[..., 3] = 1.0
    src = np.ones((4, 4, 4), dtype=np.float32) * 0.5
    out = composite(dst, src, "screen")
    assert out.shape == (4, 4, 4)
    assert out[..., :3].max() <= 1.0 + 1e-6


def test_blend_add_clamps():
    dst = np.ones((4, 4, 4), dtype=np.float32)
    src = np.ones((4, 4, 4), dtype=np.float32)
    out = composite(dst, src, "add")
    assert out[..., :3].max() <= 1.0 + 1e-6


def test_palette_resolve(cfg):
    pal = resolve_palette("nocturne_amber", cfg.palettes)
    assert len(pal.stops) >= 2
    assert pal.background_rgba[3] == 255


def test_palette_unknown_raises(cfg):
    with pytest.raises(KeyError):
        resolve_palette("nonexistent_palette_xyz", cfg.palettes)


def test_postprocess_grainfilm_shape():
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    out = postprocess(img, "grainfilm", seed=42)
    assert out.shape == (64, 64, 3)
    assert out.dtype == np.uint8


def test_execute_plan_no_save(blues_plan):
    """Рендер без сохранения PNG — проверяем RenderResult."""
    result = execute_plan(blues_plan, save_png=False)
    assert result.plan_id == blues_plan.plan_id
    assert result.width == 1024
    assert result.height == 1024
    assert result.layers_rendered >= 3
    assert result.output_path is None


def test_execute_plan_saves_png(tmp_path, blues_plan):
    """Рендер с сохранением — файл poster.png существует и > 10 KB."""
    result = execute_plan(blues_plan, output_dir=tmp_path, save_png=True)
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.suffix == ".png"
    assert result.output_path.stat().st_size > 10_000


def test_execute_plan_determinism(blues_plan):
    """Два рендера → одинаковое layers_rendered и plan_id."""
    r1 = execute_plan(blues_plan, save_png=False)
    r2 = execute_plan(blues_plan, save_png=False)
    assert r1.layers_rendered == r2.layers_rendered
    assert r1.plan_id == r2.plan_id


def test_no_pil_in_composition():
    """lib.composition не должен импортировать PIL ни прямо, ни косвенно."""
    import lib.composition.planner
    import lib.composition.schema
    composition_mods = [
        "lib.composition.schema",
        "lib.composition.planner",
        "lib.composition.config_loader",
        "lib.composition.seed_policy",
        "lib.composition.canonicalize",
        "lib.composition.validation",
        "lib.composition.coverage",
        "lib.composition.storage",
    ]
    for mod_name in composition_mods:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for bad in ["import PIL", "from PIL"]:
            assert bad not in src, f"PIL import found in {mod.__file__}"
