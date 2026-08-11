from lib.style_engine import seed_policy


def test_render_seed_adapter_delegates_the_complete_identity(monkeypatch):
    captured = {}

    def production_seed(*args):
        captured["args"] = args
        return 2718281828

    monkeypatch.setattr(seed_policy, "_compute_variation_seed", production_seed)
    theta_values = {f"harmony_theta_{index}": 0.5 for index in range(8)}

    result = seed_policy.compute_render_variation_seed(
        project_id="project-A",
        analysis_id="analysis-A",
        preset_id="preset-A",
        style_slug="ambient",
        interpretation_slug="default",
        theta_values=theta_values,
    )

    assert result == 2718281828
    assert captured["args"] == (
        "project-A",
        "analysis-A",
        "preset-A",
        "ambient",
        "default",
        theta_values,
    )
    assert captured["args"][-1] is not theta_values
