import ast
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from lib.canonicalization import THETA_AXES
from lib.composition.d1_harmony_bridge import project_perceptual_to_harmony
from lib.composition.harmony_encoder import HARMONY_AXES, HarmonyEncoder


@pytest.fixture
def perceptual_payload():
    return {
        "symmetry_bias": 0.4,
        "tension": 0.3,
        "harmonic_stability": 0.8,
        "harmonic_change_rate": 0.2,
        "texture_complexity": 0.6,
        "recursion_depth": 0.5,
        "section_complexity": 0.7,
        "noise_level": 0.1,
    }


def test_bridge_preserves_input_and_matches_production_encoder(perceptual_payload):
    result = project_perceptual_to_harmony(perceptual_payload)
    direct_theta = HarmonyEncoder().encode(perceptual_payload).as_mapping_axes()

    assert dict(result.encoder_features) == perceptual_payload
    assert dict(result.named_theta) == direct_theta
    assert tuple(result.named_theta) == THETA_AXES
    assert result.bridge_name == "perceptual_projection"
    assert result.bridge_version == "v1"
    assert result.encoder_name == "crossproduct"
    assert result.encoder_version == HarmonyEncoder.VERSION


def test_bridge_result_mappings_are_immutable(perceptual_payload):
    result = project_perceptual_to_harmony(perceptual_payload)
    assert isinstance(result.encoder_features, MappingProxyType)
    assert isinstance(result.named_theta, MappingProxyType)
    with pytest.raises(TypeError):
        result.encoder_features["tension"] = 0.9
    with pytest.raises(TypeError):
        result.named_theta["harmony_theta_0"] = 0.9


def test_bridge_inputs_and_theta_are_finite_unit_interval(perceptual_payload):
    result = project_perceptual_to_harmony(perceptual_payload)
    assert tuple(result.encoder_features) == tuple(HARMONY_AXES)
    for value in (*result.encoder_features.values(), *result.named_theta.values()):
        assert math.isfinite(value)
        assert 0.0 <= value <= 1.0


def test_bridge_is_deterministic(perceptual_payload):
    assert project_perceptual_to_harmony(perceptual_payload) == project_perceptual_to_harmony(perceptual_payload)


@pytest.mark.parametrize(
    "axis,value",
    [
        ("tension", True),
        ("tension", "0.5"),
        ("tension", float("nan")),
        ("tension", float("inf")),
        ("tension", -0.000001),
        ("tension", 1.000001),
    ],
)
def test_bridge_rejects_invalid_axis_values(perceptual_payload, axis, value):
    perceptual_payload[axis] = value
    with pytest.raises(ValueError):
        project_perceptual_to_harmony(perceptual_payload)


def test_bridge_rejects_missing_and_unexpected_fields(perceptual_payload):
    missing = dict(perceptual_payload)
    missing.pop("noise_level")
    with pytest.raises(ValueError, match="missing"):
        project_perceptual_to_harmony(missing)

    for forbidden_key in (
        "variation_seed",
        "render_seed",
        "renderer_width",
        "style_slug",
        "interp_slug",
        "harmony_theta_0",
    ):
        invalid = {**perceptual_payload, forbidden_key: 0.5}
        with pytest.raises(ValueError, match="unexpected"):
            project_perceptual_to_harmony(invalid)


def test_bridge_dependency_policy_excludes_downstream_rendering_modules():
    bridge_path = Path("lib/composition/d1_harmony_bridge.py")
    tree = ast.parse(bridge_path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "lib.style_engine.engine",
        "lib.style_engine.seed_policy",
    }
    forbidden_names = {"RenderParams", "compute_render_variation_seed"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules
            assert not ({alias.name for alias in node.names} & forbidden_names)
        if isinstance(node, ast.Import):
            assert not ({alias.name for alias in node.names} & forbidden_modules)
