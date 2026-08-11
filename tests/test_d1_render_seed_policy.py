from lib.style_engine.seed_policy import compute_render_variation_seed


def render_identity(**overrides):
    identity = {
        "project_id": "e4_reference_render_audit_v2",
        "analysis_id": "ambient_A",
        "preset_id": "d1_neutral",
        "style_slug": "ambient",
        "interpretation_slug": "default",
        "theta_values": {f"harmony_theta_{index}": 0.5 for index in range(8)},
    }
    identity.update(overrides)
    return identity


def seed(**overrides):
    return compute_render_variation_seed(**render_identity(**overrides))


def test_render_seed_is_deterministic():
    assert seed() == seed()


def test_render_seed_changes_for_each_explicit_identity_component():
    baseline = seed()
    assert baseline != seed(project_id="different_project")
    assert baseline != seed(analysis_id="ambient_B")
    assert baseline != seed(preset_id="d1_dense")
    assert baseline != seed(style_slug="rock")
    assert baseline != seed(interpretation_slug="contrast")


def test_render_seed_changes_for_named_theta_value():
    changed_theta = {f"harmony_theta_{index}": 0.5 for index in range(8)}
    changed_theta["harmony_theta_5"] = 0.500001
    assert seed() != seed(theta_values=changed_theta)


def test_render_seed_is_a_32_bit_unsigned_integer():
    result = seed()
    assert isinstance(result, int)
    assert 0 <= result < 2**32
