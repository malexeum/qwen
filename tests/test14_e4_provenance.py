from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "e4_provenance.py"
MANIFEST_PATH = ROOT / "artifacts" / "e4" / "fixtures_manifest.e4a.v1.yaml"


def _load_module():
    spec = importlib.util.spec_from_file_location("e4_provenance", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e4 = _load_module()


def _manifest():
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _params(**overrides):
    values = {
        "style_profile_slug": "ambient", "interpretation_profile_slug": "default",
        "preset_id": "default", "symmetry_bias": 0.1, "recursion_depth": 0.2,
        "density_level": 0.3, "noise_level": 0.4, "motion_intensity": 0.5,
        "texture_complexity": 0.6, "palette_id": "lunar_mist",
        "stochastic_term": 0.7, "layout_macro_shape": "drift", "variation_seed": 104729,
    }
    values.update({key: index / 10 for index, key in enumerate(e4.THETA_KEYS)})
    values.update(overrides)
    return SimpleNamespace(**values)


def test_planned_manifest_is_valid_e4a_contract():
    document = _manifest()
    e4.validate_manifest(document)
    assert document["total_fixtures"] == 22
    assert document["historical_render_sets_are_reference_baselines"] is False
    assert {fixture["id"] for fixture in document["fixtures"]} == {
        f"{profile}_{tier}" for profile in ("ambient", "blues_jazz", "classical", "electronic", "jazz", "pop", "rock") for tier in "ABC"
    } | {"default_smoke"}


def test_planned_fixtures_contain_no_materialized_identity():
    for fixture in _manifest()["fixtures"]:
        for key in ("audio_content_sha256", "feature_artifact_path", "feature_sha256", "canonical_theta_hash_short", "canonical_theta_sha256", "variation_seed", "canonical_render_params_sha256", "output_sha256", "audit_scores"):
            assert fixture[key] is None


def test_manifest_rejects_historical_renders_as_reference_baseline():
    document = _manifest()
    document["historical_render_sets_are_reference_baselines"] = True
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
    assert full_hash == "sha256:" + hashlib.sha256(e4.canonical_json_bytes(e4.canonical_theta_payload(theta))).hexdigest()
    assert short_hash == "sha256-64:" + full_hash.removeprefix("sha256:")[:16]


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
    assert set(e4.canonical_render_params_payload(params)) == set(e4.RENDER_STRING_FIELDS) | set(e4.RENDER_FLOAT_FIELDS) | {"variation_seed"}


def test_render_params_digest_changes_for_identity_change():
    assert e4.render_params_sha256(_params()) != e4.render_params_sha256(_params(variation_seed=104730))
