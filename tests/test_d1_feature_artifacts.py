from types import MappingProxyType

import pytest

from lib.canonicalization import THETA_AXES, canonical_feature_hash, canonical_theta_hash
from lib.d1_feature_artifacts import (
    SCHEMA_V1,
    SCHEMA_V2,
    build_d1_feature_artifact,
    canonical_feature_payload_bytes,
)

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
DIGEST = "sha256:" + "b" * 64
AUDIO_SOURCE = {
    "kind": "audio_file",
    "inventory_source_id": "audio_source_inventory/v1/" + DIGEST,
    "content_sha256": DIGEST,
    "byte_size": 1,
    "suffix": ".mp3",
    "adapter_name": "audio_file_adapter",
    "adapter_version": "e1-fix3",
    "analysis_config_version": "d1-v1",
    "decoder_backend": "ffmpeg/7.1",
}
LOCATOR = {"registry_path": "tests/audio/Rock.mp3"}


def build(**overrides):
    values = {
        "analysis_id": "fixture_A",
        "source_identity": AUDIO_SOURCE,
        "source_locator": LOCATOR,
        "perceptual": PERCEPTUAL,
        "git_sha": GIT_SHA,
        "schema_version": SCHEMA_V2,
    }
    values.update(overrides)
    return build_d1_feature_artifact(**values)


def test_identical_inputs_produce_byte_identical_payload_and_hash():
    first = build()
    second = build(
        source_identity=dict(reversed(list(AUDIO_SOURCE.items()))),
        perceptual=dict(reversed(list(PERCEPTUAL.items()))),
    )
    assert canonical_feature_payload_bytes(first) == canonical_feature_payload_bytes(second)
    assert first.feature_sha256 == second.feature_sha256


def test_feature_hash_is_semantic_not_build_provenance():
    first = build(git_sha="a" * 40)
    second = build(git_sha="c" * 40)
    assert first.feature_sha256 == second.feature_sha256
    assert first.git_sha != second.git_sha
    assert "git_sha" not in first.semantic_payload()


def test_semantic_changes_modify_feature_hash():
    changed_digest = "sha256:" + "c" * 64
    changed_source = {
        **AUDIO_SOURCE,
        "content_sha256": changed_digest,
        "inventory_source_id": "audio_source_inventory/v1/" + changed_digest,
    }
    for override in (
        {"analysis_id": "fixture_B"},
        {"source_identity": changed_source},
        {"perceptual": {**PERCEPTUAL, "tension": 0.6}},
        {"source_identity": {**AUDIO_SOURCE, "decoder_backend": "ffmpeg/7.2"}},
    ):
        assert build().feature_sha256 != build(**override).feature_sha256
    assert build().feature_sha256 == build(
        source_locator={"registry_path": "tests/audio/Renamed-Rock.mp3"}
    ).feature_sha256


def test_artifact_matches_bridge_and_shared_theta_contract():
    artifact = build()
    assert tuple(artifact.named_theta) == THETA_AXES
    assert artifact.canonical_theta_hash == canonical_theta_hash(artifact.named_theta)
    assert artifact.feature_sha256 == canonical_feature_hash(artifact.semantic_payload())


def test_artifact_mappings_are_immutable():
    artifact = build()
    for mapping in (
        artifact.source_identity,
        artifact.perceptual,
        artifact.named_theta,
        artifact.source_locator,
    ):
        assert isinstance(mapping, MappingProxyType)
        with pytest.raises(TypeError):
            mapping["mutate"] = "forbidden"


@pytest.mark.parametrize(
    "source_identity",
    [
        {**AUDIO_SOURCE, "path": "C:/audio.wav"},
        {**AUDIO_SOURCE, "content_sha256": "sha256:UPPERCASE"},
        {**AUDIO_SOURCE, "inventory_source_id": "wrong"},
    ],
)
def test_source_identity_rejects_invalid_schemas(source_identity):
    with pytest.raises(ValueError):
        build(source_identity=source_identity)


def test_synthetic_fixture_identity_is_supported_explicitly_as_v1():
    artifact = build_d1_feature_artifact(
        analysis_id="fixture_A",
        source_identity={
            "kind": "synthetic_fixture",
            "fixture_id": "rock_C",
            "fixture_spec_sha256": "sha256:" + "d" * 64,
        },
        perceptual=PERCEPTUAL,
        git_sha=GIT_SHA,
        schema_version=SCHEMA_V1,
    )
    assert artifact.source_identity["kind"] == "synthetic_fixture"


@pytest.mark.parametrize(
    "field,value",
    [("analysis_id", ""), ("git_sha", "not-a-sha"), ("git_sha", "A" * 40)],
)
def test_artifact_rejects_invalid_identity_fields(field, value):
    with pytest.raises(ValueError):
        build(**{field: value})
