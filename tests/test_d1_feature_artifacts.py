from types import MappingProxyType

import pytest

from lib.canonicalization import THETA_AXES, canonical_feature_hash, canonical_theta_hash
from lib.d1_feature_artifacts import build_d1_feature_artifact, canonical_feature_payload_bytes


GIT_SHA = "a" * 40
PERCEPTUAL = {
    "symmetry_bias": 0.4,
    "tension": 0.3,
    "harmonic_stability": 0.8,
    "harmonic_change_rate": 0.2,
    "texture_complexity": 0.6,
    "recursion_depth": 0.5,
    "section_complexity": 0.7,
    "noise_level": 0.1,
}
AUDIO_SOURCE = {
    "kind": "audio_file",
    "content_sha256": "sha256:" + "b" * 64,
    "adapter_name": "audio_file_adapter",
    "adapter_version": "e1-fix3",
    "analysis_config_version": "d1-v1",
}


def build(**overrides):
    values = {
        "analysis_id": "fixture_A",
        "source_identity": AUDIO_SOURCE,
        "perceptual": PERCEPTUAL,
        "git_sha": GIT_SHA,
    }
    values.update(overrides)
    return build_d1_feature_artifact(**values)


def test_identical_inputs_produce_byte_identical_payload_and_hash():
    first = build()
    second = build(source_identity=dict(reversed(list(AUDIO_SOURCE.items()))), perceptual=dict(reversed(list(PERCEPTUAL.items()))))
    assert canonical_feature_payload_bytes(first) == canonical_feature_payload_bytes(second)
    assert first.feature_sha256 == second.feature_sha256


def test_feature_hash_is_semantic_not_build_provenance():
    first = build(git_sha="a" * 40)
    second = build(git_sha="c" * 40)
    assert first.feature_sha256 == second.feature_sha256
    assert first.git_sha != second.git_sha
    assert "git_sha" not in first.semantic_payload()
    assert "feature_sha256" not in first.semantic_payload()


@pytest.mark.parametrize(
    "override",
    [
        {"analysis_id": "fixture_B"},
        {"source_identity": {**AUDIO_SOURCE, "content_sha256": "sha256:" + "c" * 64}},
        {"perceptual": {**PERCEPTUAL, "tension": 0.6}},
    ],
)
def test_semantic_changes_modify_feature_hash(override):
    assert build().feature_sha256 != build(**override).feature_sha256


def test_artifact_matches_bridge_and_shared_theta_contract():
    artifact = build()
    assert tuple(artifact.named_theta) == THETA_AXES
    assert artifact.canonical_theta_hash == canonical_theta_hash(artifact.named_theta)
    assert artifact.feature_sha256 == canonical_feature_hash(artifact.semantic_payload())
    assert artifact.feature_sha256.startswith("sha256:")
    assert len(artifact.feature_sha256) == 71


def test_artifact_mappings_are_immutable():
    artifact = build()
    for mapping in (artifact.source_identity, artifact.perceptual, artifact.named_theta):
        assert isinstance(mapping, MappingProxyType)
        with pytest.raises(TypeError):
            mapping["mutate"] = "forbidden"


@pytest.mark.parametrize(
    "source_identity",
    [
        {**AUDIO_SOURCE, "path": "C:/audio.wav"},
        {**AUDIO_SOURCE, "uri": "file:///audio.wav"},
        {**AUDIO_SOURCE, "content_sha256": "sha256:UPPERCASE"},
        {"kind": "synthetic_fixture", "fixture_id": "rock_C", "fixture_spec_sha256": "sha256:" + "d" * 64, "path": "fixtures/rock_C"},
    ],
)
def test_source_identity_rejects_paths_and_invalid_schemas(source_identity):
    with pytest.raises(ValueError):
        build(source_identity=source_identity)


def test_synthetic_fixture_identity_is_supported():
    artifact = build(source_identity={
        "kind": "synthetic_fixture",
        "fixture_id": "rock_C",
        "fixture_spec_sha256": "sha256:" + "d" * 64,
    })
    assert artifact.source_identity["kind"] == "synthetic_fixture"


@pytest.mark.parametrize("field,value", [("analysis_id", ""), ("git_sha", "not-a-sha"), ("git_sha", "A" * 40)])
def test_artifact_rejects_invalid_identity_fields(field, value):
    with pytest.raises(ValueError):
        build(**{field: value})
