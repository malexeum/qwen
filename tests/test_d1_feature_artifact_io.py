import json
from types import MappingProxyType

import pytest

from lib.canonicalization import canonical_feature_hash
from lib.d1_feature_artifact_io import (
    atomic_write_bytes,
    canonical_feature_envelope_bytes,
    read_feature_artifact,
    validate_feature_artifact,
    write_feature_artifact,
)
from lib.d1_feature_artifacts import (
    SCHEMA_V1,
    SCHEMA_V2,
    build_d1_feature_artifact,
)
from lib.d1_feature_manifest import (
    build_feature_manifest,
    canonical_manifest_bytes,
    feature_relative_path,
    write_feature_manifest,
)

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

SOURCE_V1 = {
    "kind": "synthetic_fixture",
    "fixture_id": "fixture",
    "fixture_spec_sha256": "sha256:" + "b" * 64,
}

SOURCE_V2 = {
    "kind": "audio_file",
    "inventory_source_id": "audio_source_inventory/v1/sha256:" + "c" * 64,
    "content_sha256": "sha256:" + "c" * 64,
    "byte_size": 1,
    "suffix": ".mp3",
    "adapter_name": "d1_perceptual_extractor",
    "adapter_version": "1.0.0",
    "analysis_config_version": "d1_perceptual_config/v1",
    "decoder_backend": "ffmpeg/7.1",
}

LOCATOR_V2 = {
    "registry_path": "tests/audio/Rock.mp3",
}


def artifact_v1(analysis_id="fixture_A", git_sha="a" * 40):
    return build_d1_feature_artifact(
        analysis_id=analysis_id,
        source_identity={**SOURCE_V1, "fixture_id": analysis_id},
        perceptual=PERCEPTUAL,
        git_sha=git_sha,
        schema_version=SCHEMA_V1,
    )


def artifact_v2(analysis_id="rock_A", git_sha="a" * 40, locator=LOCATOR_V2):
    return build_d1_feature_artifact(
        analysis_id=analysis_id,
        source_identity=SOURCE_V2,
        perceptual=PERCEPTUAL,
        git_sha=git_sha,
        schema_version=SCHEMA_V2,
        source_locator=locator,
    )


def write_envelope(path, envelope):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_v1_feature_write_read_and_lf_output(tmp_path):
    value = artifact_v1()
    expected_payload = value.semantic_payload()
    path = write_feature_artifact(tmp_path, value)
    envelope = json.loads(path.read_text(encoding="utf-8"))

    assert path.relative_to(tmp_path).as_posix() == "features/fixture_A.json"
    assert envelope == {
        "semantic_payload": expected_payload,
        "feature_sha256": value.feature_sha256,
        "git_sha": value.git_sha,
    }
    assert "source_locator" not in envelope
    assert canonical_feature_hash(envelope["semantic_payload"]) == (
        envelope["feature_sha256"]
    )
    assert isinstance(
        envelope["semantic_payload"]["named_theta"]["harmony_theta_0"],
        float,
    )
    assert b"\r" not in path.read_bytes()
    assert not list(tmp_path.rglob(".*.tmp"))

    loaded = read_feature_artifact(path)
    validate_feature_artifact(loaded)

    assert loaded == value
    assert loaded.source_locator is None
    assert canonical_feature_envelope_bytes(loaded) == path.read_bytes()


def test_v2_round_trip_persists_locator_without_changing_feature_hash(tmp_path):
    first = artifact_v2(locator={"registry_path": "tests/audio/Rock.mp3"})
    second = artifact_v2(locator={"registry_path": "registry/audio/Rock.mp3"})

    assert first.feature_sha256 == second.feature_sha256
    assert first.semantic_payload() == second.semantic_payload()
    assert first.source_locator != second.source_locator

    path = write_feature_artifact(tmp_path, first)
    envelope = json.loads(path.read_text(encoding="utf-8"))

    assert envelope["source_locator"] == LOCATOR_V2
    assert "source_locator" not in envelope["semantic_payload"]
    assert canonical_feature_hash(envelope["semantic_payload"]) == (
        first.feature_sha256
    )

    loaded = read_feature_artifact(path)
    validate_feature_artifact(loaded)

    assert loaded == first
    assert loaded.source_locator == LOCATOR_V2
    assert canonical_feature_envelope_bytes(loaded) == path.read_bytes()


def test_v2_build_requires_source_locator():
    with pytest.raises(ValueError, match="source_locator"):
        artifact_v2(locator=None)


def test_forged_or_mutated_artifact_is_rejected(tmp_path):
    value = artifact_v1()
    object.__setattr__(value, "feature_sha256", "sha256:" + "0" * 64)

    with pytest.raises(ValueError):
        write_feature_artifact(tmp_path, value)


def test_tampered_theta_hash_is_rejected_before_publish(tmp_path):
    value = artifact_v1()
    object.__setattr__(value, "canonical_theta_hash", "sha256:" + "0" * 64)

    with pytest.raises(ValueError, match="canonical_theta_hash"):
        write_feature_artifact(tmp_path, value)

    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.rglob(".*.tmp"))


def test_tampered_theta_and_recomputed_feature_hash_but_stale_theta_hash_is_rejected(
    tmp_path,
):
    value = artifact_v1()
    theta = dict(value.named_theta)
    theta["harmony_theta_0"] = 0.123456
    object.__setattr__(value, "named_theta", MappingProxyType(theta))
    object.__setattr__(
        value,
        "feature_sha256",
        canonical_feature_hash(value.semantic_payload()),
    )

    with pytest.raises(ValueError, match="canonical_theta_hash"):
        write_feature_artifact(tmp_path, value)

    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.rglob(".*.tmp"))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda envelope: envelope.pop("source_locator"),
            "feature envelope has missing or unexpected fields",
        ),
        (
            lambda envelope: envelope.update(
                {"source_locator": {"registry_path": "../Rock.mp3"}}
            ),
            "registry_path",
        ),
        (
            lambda envelope: envelope["semantic_payload"].pop("perceptual"),
            "semantic_payload has missing or unexpected fields",
        ),
        (
            lambda envelope: envelope["semantic_payload"].update(
                {"unexpected": "field"}
            ),
            "semantic_payload has missing or unexpected fields",
        ),
        (
            lambda envelope: envelope.update(
                {"feature_sha256": "sha256:" + "0" * 64}
            ),
            "feature_sha256",
        ),
        (
            lambda envelope: envelope["semantic_payload"]["named_theta"].update(
                {"harmony_theta_0": 0.123456}
            ),
            "canonical_theta_hash",
        ),
        (
            lambda envelope: envelope["semantic_payload"].update(
                {"canonical_theta_hash": "sha256:" + "0" * 64}
            ),
            "canonical_theta_hash",
        ),
        (
            lambda envelope: envelope["semantic_payload"].update(
                {"schema_version": "d1_feature_artifact/v999"}
            ),
            "unsupported D1 feature artifact schema_version",
        ),
        (
            lambda envelope: envelope.update({"git_sha": "not-a-git-sha"}),
            "git_sha",
        ),
    ],
)
def test_reader_rejects_corrupted_v2_envelope(tmp_path, mutate, message):
    value = artifact_v2()
    path = write_feature_artifact(tmp_path, value)
    envelope = json.loads(path.read_text(encoding="utf-8"))

    mutate(envelope)
    write_envelope(path, envelope)

    with pytest.raises(ValueError, match=message):
        read_feature_artifact(path)


def test_reader_rejects_v1_envelope_with_source_locator(tmp_path):
    value = artifact_v1()
    path = write_feature_artifact(tmp_path, value)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["source_locator"] = LOCATOR_V2
    write_envelope(path, envelope)

    with pytest.raises(
        ValueError,
        match="feature envelope has missing or unexpected fields",
    ):
        read_feature_artifact(path)


def test_reader_rejects_noncanonical_but_semantically_equivalent_json(tmp_path):
    value = artifact_v2()
    path = write_feature_artifact(tmp_path, value)
    envelope = json.loads(path.read_text(encoding="utf-8"))

    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="feature envelope is not in canonical serialized representation",
    ):
        read_feature_artifact(path)


def test_feature_overwrite_is_forbidden(tmp_path):
    value = artifact_v1()
    write_feature_artifact(tmp_path, value)

    with pytest.raises(FileExistsError):
        write_feature_artifact(tmp_path, value)


def test_immutable_publish_race_preserves_winner_and_removes_temp_file(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "features" / "fixture_A.json"
    target.parent.mkdir()

    import lib.d1_feature_artifact_io as io

    def competing_publish(source, destination):
        destination.write_bytes(b"winner")
        raise FileExistsError("competing immutable writer won")

    monkeypatch.setattr(io.os, "link", competing_publish)

    with pytest.raises(FileExistsError, match="competing immutable writer won"):
        atomic_write_bytes(target, b"candidate", overwrite=False)

    assert target.read_bytes() == b"winner"
    assert not list(tmp_path.rglob(".*.tmp"))


def test_manifest_is_deterministic_rebuild_and_uses_lf(tmp_path):
    first = artifact_v1("fixture_A")
    second = artifact_v1("fixture_B")

    assert canonical_manifest_bytes([second, first]) == canonical_manifest_bytes(
        [first, second]
    )

    manifest_path = write_feature_manifest(tmp_path, [second, first])
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["entries"]

    assert [entry["analysis_id"] for entry in entries] == [
        "fixture_A",
        "fixture_B",
    ]
    assert b"\r" not in manifest_path.read_bytes()


def test_manifest_rejects_duplicate_entries():
    value = artifact_v1()

    with pytest.raises(ValueError):
        build_feature_manifest([value, value])


@pytest.mark.parametrize(
    "analysis_id",
    ["../escape", "features/escape", "C:\\escape", ".", "unicode_╤В╨╡╤Б╤В"],
)
def test_unsafe_analysis_id_is_rejected(analysis_id):
    with pytest.raises(ValueError):
        feature_relative_path(analysis_id)


def test_failed_manifest_replace_leaves_no_temp_file(tmp_path, monkeypatch):
    import lib.d1_feature_artifact_io as io

    monkeypatch.setattr(
        io.os,
        "replace",
        lambda source, target: (_ for _ in ()).throw(
            OSError("injected replace failure")
        ),
    )

    with pytest.raises(OSError):
        atomic_write_bytes(tmp_path / "manifest.json", b"{}\n", overwrite=True)

    assert not list(tmp_path.rglob(".*.tmp"))