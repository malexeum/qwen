from types import MappingProxyType

from lib.composition.d1_harmony_bridge import project_perceptual_to_harmony
from lib.style_engine.seed_policy import compute_render_variation_seed


render_identity = MappingProxyType(
    {
        "project_id": "d1_contract_test",
        "analysis_id": "fixture_A",
        "preset_id": "neutral",
        "style_slug": "ambient",
        "interp_slug": "default",
    }
)


perceptual_payload = MappingProxyType(
    {
        "symmetry_bias": 0.4,
        "tension": 0.3,
        "harmonic_stability": 0.8,
        "harmonic_change_rate": 0.2,
        "texture_complexity": 0.6,
        "recursion_depth": 0.5,
        "section_complexity": 0.7,
        "noise_level": 0.1,
    }
)


def bridge_seed(perceptual=perceptual_payload, **identity_overrides):
    identity = {**render_identity, **identity_overrides}
    bridge_result = project_perceptual_to_harmony(perceptual)
    return compute_render_variation_seed(
        project_id=identity["project_id"],
        analysis_id=identity["analysis_id"],
        preset_id=identity["preset_id"],
        style_slug=identity["style_slug"],
        interpretation_slug=identity["interp_slug"],
        theta_values=bridge_result.named_theta,
    )


def test_render_seed_is_deterministic():
    assert bridge_seed() == bridge_seed()


def test_render_seed_changes_for_each_explicit_identity_component():
    baseline = bridge_seed()
    assert baseline != bridge_seed(project_id="different_project")
    assert baseline != bridge_seed(analysis_id="fixture_B")
    assert baseline != bridge_seed(preset_id="dense")
    assert baseline != bridge_seed(style_slug="rock")
    assert baseline != bridge_seed(interp_slug="contrast")


def test_same_perceptual_bridge_theta_and_seed_are_deterministic():
    first = project_perceptual_to_harmony(perceptual_payload)
    second = project_perceptual_to_harmony(perceptual_payload)
    assert first.encoder_features == second.encoder_features
    assert first.named_theta == second.named_theta
    assert bridge_seed() == bridge_seed()


def test_changed_upstream_perceptual_recomputes_seed_from_bridge_theta():
    modified = dict(perceptual_payload)
    modified["tension"] = 0.6
    baseline = project_perceptual_to_harmony(perceptual_payload)
    changed = project_perceptual_to_harmony(modified)

    assert baseline.encoder_features["tension"] != changed.encoder_features["tension"]
    assert isinstance(bridge_seed(modified), int)


def test_render_seed_is_a_32_bit_unsigned_integer():
    result = bridge_seed()
    assert isinstance(result, int)
    assert 0 <= result < 2**32
