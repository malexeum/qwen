"""Unit-тесты Reference Renderer C1."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

# Убедимся что корень проекта в sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_PLAN = {
    "schema_version": "composition-plan/v0.3",
    "plan_id": "test_plan_0000000000000001",
    "seed": 42,
    "canvas": {"width_px": 128, "height_px": 128},
    "visual_identity": {"profile_id": "blues_jazz", "palette_id": "deep_blue_amber"},
    "silence_mask": {"enabled": False, "coverage": 0.0, "direction": 0.5, "edge_softness": 0.3},
    "layers": [
        {
            "layer_id": "l0",
            "generator_id": "colored_noise_field",
            "enabled": True,
            "z_index": 0,
            "blend_mode": "normal",
            "opacity": 1.0,
            "palette_id": "deep_blue_amber",
            "computation_resolution_fraction": 1.0,
            "seed": 42,
            "params": {
                "amplitude": 0.8,
                "frequency_scale": 0.5,
                "grain_size": 2.0,
                "anisotropy": 0.0,
            },
        }
    ],
}

_SCATTERING_PARAMS = {
    "scatterer_radius": 0.20,
    "center_phase_offset": 0.1,
    "center_radius": 0.75,
    "initial_velocity_x": 0.025,
    "initial_velocity_y": 0.018,
    "max_steps": 300,
    "stochastic_scale": 0.0,
}

_JULIA_PARAMS = {
    "c_real": -0.4,
    "c_imag": 0.6,
    "exponent_p": 2.0,
    "trap_radius": 0.5,
    "max_iter": 64,
    "stochastic_scale": 0.0,
}


@pytest.fixture(scope="module")
def plan_json_path(tmp_path_factory) -> Path:
    """Сохраняет минимальный plan.json во временную папку."""
    tmp = tmp_path_factory.mktemp("plans")
    path = tmp / "visual_composition_plan.json"
    path.write_text(json.dumps(_MINIMAL_PLAN), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def full_plan_path(tmp_path_factory) -> Path:
    """Plan с colored_noise слоем для render()."""
    tmp = tmp_path_factory.mktemp("full_plans")
    path = tmp / "visual_composition_plan.json"
    path.write_text(json.dumps(_MINIMAL_PLAN), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# test_plan_loader
# ---------------------------------------------------------------------------

def test_plan_loader_valid(plan_json_path):
    from lib.renderer.plan_loader import load_plan
    plan = load_plan(plan_json_path)
    assert plan["plan_id"] == "test_plan_0000000000000001"


def test_plan_loader_missing_file(tmp_path):
    from lib.renderer.plan_loader import load_plan, PlanLoadError
    with pytest.raises(PlanLoadError, match="not found"):
        load_plan(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# test_theta_builder
# ---------------------------------------------------------------------------

def test_theta_builder_julia():
    from lib.renderer.theta_builder import build_theta_julia
    theta = build_theta_julia(_JULIA_PARAMS)
    assert len(theta) == 6
    assert theta[0] == pytest.approx(-0.4)
    assert theta[1] == pytest.approx(0.6)
    assert theta[2] == pytest.approx(2.0)
    assert theta[3] == pytest.approx(0.5)


def test_theta_builder_scattering():
    from lib.renderer.theta_builder import build_theta_scattering
    theta = build_theta_scattering(_SCATTERING_PARAMS)
    assert len(theta) == 5
    # theta[0] = (0.20 - 0.15) / 0.05 = 1.0
    assert theta[0] == pytest.approx(1.0)
    # theta[2] = (0.75 - 0.7) / 0.2 = 0.25
    assert theta[2] == pytest.approx(0.25)
    # Нет Duffing-ключей
    from lib.renderer.theta_builder import build_theta_duffing
    duffing_keys = {"damping", "nonlinear_stiffness", "forcing", "forcing_frequency"}
    assert not duffing_keys.intersection(_SCATTERING_PARAMS.keys())


# ---------------------------------------------------------------------------
# test_procedural_runner
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gen_id,params", [
    ("orbital_field", {"flow_speed": 0.3, "orbit_radius": 0.5, "line_count": 0.3,
                       "amplitude": 0.5, "angular_break": 0.0, "rotation_deg": 0.0}),
    ("colored_noise_field", {"amplitude": 0.7, "frequency_scale": 0.4,
                              "grain_size": 2.0, "anisotropy": 0.0}),
    ("symmetry_snowflake", {"branch_count": 0.5, "branch_depth": 0.5,
                             "branch_jitter": 0.05, "radial_scale": 0.5, "rotation_deg": 0.0}),
])
def test_procedural_runner_shape(gen_id, params):
    from lib.renderer.procedural_runner import run_procedural
    result = run_procedural(gen_id, params, W=64, H=64, seed=0)
    assert result.shape == (64, 64)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# test_palette_mapper
# ---------------------------------------------------------------------------

def test_palette_mapper_output():
    from lib.renderer.palette_mapper import apply_palette
    orbit_map = np.linspace(0.0, 1.0, 64 * 64, dtype=np.float32).reshape(64, 64)
    palette = {
        "dominant_stops": [
            {"position": 0.0, "color": "#000000"},
            {"position": 0.5, "color": "#0055AA"},
            {"position": 1.0, "color": "#FFEECC"},
        ]
    }
    rgba = apply_palette(orbit_map, palette)
    assert rgba.shape == (64, 64, 4)
    assert rgba.dtype == np.uint8
    # alpha везде 255
    assert np.all(rgba[:, :, 3] == 255)


# ---------------------------------------------------------------------------
# test_blend_modes
# ---------------------------------------------------------------------------

def test_blend_modes_all():
    from lib.renderer.blend_compositor import composite_layers
    from lib.renderer.palette_mapper import apply_palette
    orbit = np.full((32, 32), 0.5, dtype=np.float32)
    palette = {
        "dominant_stops": [
            {"position": 0.0, "color": "#112233"},
            {"position": 1.0, "color": "#AABBCC"},
        ]
    }
    rgba = apply_palette(orbit, palette)
    modes = ["normal", "screen", "add", "multiply", "soft_light", "max"]
    for i, mode in enumerate(modes):
        layers = [
            {"rgba": rgba, "blend_mode": mode, "opacity": 0.8, "z_index": 0},
        ]
        result = composite_layers(layers, 32, 32)
        assert result.shape == (32, 32, 3), f"Failed for blend_mode={mode}"
        assert result.dtype == np.float32


# ---------------------------------------------------------------------------
# test_silence_mask
# ---------------------------------------------------------------------------

def test_silence_mask_coverage():
    from lib.renderer.silence_mask import build_silence_mask
    W, H = 64, 128
    coverage = 0.4
    mask = build_silence_mask(
        coverage=coverage,
        direction=0.5,
        edge_softness=0.0,  # без размытия для точного измерения
        W=W, H=H,
    )
    assert mask.shape == (H, W)
    assert mask.dtype == np.float32
    # Доля нулей должна быть близка к coverage (±0.05 с учётом дискретизации)
    zero_fraction = np.mean(mask < 0.5)
    assert abs(zero_fraction - coverage) < 0.05, \
        f"coverage={coverage}, actual={zero_fraction:.3f}"


# ---------------------------------------------------------------------------
# test_render
# ---------------------------------------------------------------------------

def test_render_output_shape(full_plan_path, tmp_path):
    from lib.renderer.reference_renderer import render
    out = render(full_plan_path, output_dir=tmp_path)
    assert out.exists()


def test_render_png_size(full_plan_path, tmp_path):
    from lib.renderer.reference_renderer import render
    from PIL import Image
    out = render(full_plan_path, output_dir=tmp_path)
    img = Image.open(out)
    assert img.size == (1024, 1024)


def test_render_deterministic(full_plan_path, tmp_path):
    from lib.renderer.reference_renderer import render
    out1 = render(full_plan_path, output_dir=tmp_path / "r1")
    out2 = render(full_plan_path, output_dir=tmp_path / "r2")
    data1 = out1.read_bytes()
    data2 = out2.read_bytes()
    assert data1 == data2, "Render is not deterministic!"
