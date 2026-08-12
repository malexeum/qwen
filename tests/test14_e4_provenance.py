from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "e4_provenance.py"
MANIFEST_PATH = ROOT / "artifacts" / "e4" / "fixtures_manifest.e4a.v1.yaml"
sys.path.insert(0, str(ROOT))

from lib.style_engine.engine import resolve_render_params


def _load_module():
    spec = importlib.util.spec_from_file_location("e4_provenance", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e4 = _load_module()


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _params(**overrides):
    values = {
        "style_profile_slug": "ambient",
        "interpretation_profile_slug": "default",
        "preset_id": "default",
        "symmetry_bias": 0.1,
        "recursion_depth": 0.2,
        "density_level": 0.3,
        "noise_level": 0.4,
        "motion_intensity": 0.5,
        "texture_complexity": 0.6,
        "palette_id": "lunar_mist",
        "stochastic_term": 0.7,
        "layout_macro_shape": "drift",
        "variation_seed": 104729,
    }
    values.update({key: index / 10 for index, key in enumerate(e4.THETA_KEYS)})
    values.update(overrides)
    return SimpleNamespace(**values)


def _neutral_perceptual() -> dict[str, float | str]:
    perceptual: dict[str, float | str] = {
        "energy": 0.5,
        "tension": 0.5,
        "density": 0.5,
        "brightness": 0.5,
        "stability": 0.5,
        "smoothness": 0.5,
        "repetition": 0.5,
        "section_complexity": 0.5,
        "noise_proxy": 0.5,
        "macro_shape_hint": "neutral",
    }
    perceptual.update({key: 0.5 for key in e4.THETA_KEYS})
    return perceptual


@pytest.mark.parametrize("fixture", _manifest()["fixtures"], ids=lambda fx: fx["id"])
def test_each_planned_fixture_resolves_to_declared_profiles_and_palette(fixture: dict):
    render_params, style_profile, interpretation_profile = resolve_render_params(
        project_id="e4a_contract",
        analysis_id=fixture["id"],
        perceptual=_neutral_perceptual(),
        style_profile_slug=fixture["style_profile_slug"],
        interpretation_profile_slug=fixture["interpretation_profile_slug"],
        user_preset={},
        strict_theta=True,
    )
    assert style_profile.slug == fixture["style_profile_slug"]
    assert interpretation_profile.slug == fixture["interpretation_profile_slug"]
    assert render_params.palette_id == fixture["expected_palette"]


def test_planned_manifest_is_valid_e4a_contract():
    document = _manifest()
    e4.validate_manifest(document)
    assert document["total_fixtures"] == 22
    assert document["historical_render_sets_are_reference_baselines"] is False


def test_planned_fixtures_contain_no_materialized_identity():
    for fixture in _manifest()["fixtures"]:
        for key in e4.MATERIALIZED_KEYS:
            assert fixture[key] is None


def test_manifest_rejects_invalid_fixture_defaults():
    document = _manifest()
    document["fixture_defaults"]["variation_seed"] = 1
    with pytest.raises(e4.E4ProvenanceError):
        e4.validate_manifest(document)


def test_manifest_rejects_historical_renders_as_reference_baseline():
    document = _manifest()
    document["historical_render_sets_are_reference_baselines"] = True
    with pytest.raises(e4.E4ProvenanceError):
        e4.validate_manifest(document)


def test_manifest_rejects_invalid_fixture_id_tier_pair():
    document = _manifest()
    document["fixtures"][0]["id"] = "ambient_Z"
    with pytest.raises(e4.E4ProvenanceError):
        e4.validate_manifest(document)


def test_manifest_rejects_materialized_value_for_planned_fixture():
    document = _manifest()
    document["fixtures"][0]["variation_seed"] = 1
    with pytest.raises(e4.E4ProvenanceError):
        e4.validate_manifest(document)


def test_theta_hashes_are_full_and_short_views_of_same_digest():
    theta = {key: (index + 1) / 10 for index, key in enumerate(e4.THETA_KEYS)}
    short_hash, full_hash = e4.theta_hashes(theta)
    expected = hashlib.sha256(
        e4.canonical_json_bytes(e4.canonical_theta_payload(theta))
    ).hexdigest()
    assert full_hash == f"sha256:{expected}"
    assert short_hash == f"sha256-64:{expected[:16]}"


def test_theta_hash_rejects_out_of_range_values():
    theta = {key: 0.5 for key in e4.THETA_KEYS}
    theta["harmony_theta_3"] = 1.1
    with pytest.raises(e4.E4ProvenanceError):
        e4.theta_hashes(theta)


def test_render_params_digest_uses_fixed_projection_only():
    params = _params()
    baseline = e4.render_params_sha256(params)
    params.mapping_trace = [object()]
    assert e4.render_params_sha256(params) == baseline
    expected_keys = set(e4.RENDER_STRING_FIELDS) | set(e4.RENDER_FLOAT_FIELDS) | {
        "variation_seed"
    }
    assert set(e4.canonical_render_params_payload(params)) == expected_keys


def test_render_params_digest_changes_for_identity_change():
    assert e4.render_params_sha256(_params()) != e4.render_params_sha256(
        _params(variation_seed=104730)
    )
