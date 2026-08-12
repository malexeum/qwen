import json

import pytest

from lib.canonicalization import canonical_feature_hash
from lib.d1_feature_artifact_io import atomic_write_bytes, write_feature_artifact
from lib.d1_feature_artifacts import build_d1_feature_artifact
from lib.d1_feature_manifest import build_feature_manifest, canonical_manifest_bytes, feature_relative_path, write_feature_manifest


PERCEPTUAL = {"symmetry_bias": 0.4, "tension": 0.3, "harmonic_stability": 0.8, "harmonic_change_rate": 0.2, "texture_complexity": 0.6, "recursion_depth": 0.5, "section_complexity": 0.7, "noise_level": 0.1}
SOURCE = {"kind": "synthetic_fixture", "fixture_id": "fixture", "fixture_spec_sha256": "sha256:" + "b" * 64}


def artifact(analysis_id="fixture_A", git_sha="a" * 40):
    return build_d1_feature_artifact(analysis_id=analysis_id, source_identity={**SOURCE, "fixture_id": analysis_id}, perceptual=PERCEPTUAL, git_sha=git_sha)


def test_feature_write_read_and_lf_output(tmp_path):
    value = artifact()
    path = write_feature_artifact(tmp_path, value)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert path.relative_to(tmp_path).as_posix() == "features/fixture_A.json"
    assert envelope["feature_sha256"] == value.feature_sha256
    assert envelope["semantic_payload"] == value.semantic_payload()
    assert canonical_feature_hash(envelope["semantic_payload"]) == envelope["feature_sha256"]
    assert isinstance(envelope["semantic_payload"]["named_theta"]["harmony_theta_0"], float)
    assert b"\r" not in path.read_bytes()
    assert not list(tmp_path.rglob(".*.tmp"))


def test_forged_or_mutated_artifact_is_rejected(tmp_path):
    value = artifact()
    object.__setattr__(value, "feature_sha256", "sha256:" + "0" * 64)
    with pytest.raises(ValueError):
        write_feature_artifact(tmp_path, value)


def test_feature_overwrite_is_forbidden(tmp_path):
    value = artifact()
    write_feature_artifact(tmp_path, value)
    with pytest.raises(FileExistsError):
        write_feature_artifact(tmp_path, value)


def test_immutable_publish_race_preserves_winner_and_removes_temp_file(tmp_path, monkeypatch):
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
    first, second = artifact("fixture_A"), artifact("fixture_B")
    assert canonical_manifest_bytes([second, first]) == canonical_manifest_bytes([first, second])
    manifest_path = write_feature_manifest(tmp_path, [second, first])
    assert [entry["analysis_id"] for entry in json.loads(manifest_path.read_text())["entries"]] == ["fixture_A", "fixture_B"]
    assert b"\r" not in manifest_path.read_bytes()
    write_feature_manifest(tmp_path, [first])
    assert [entry["analysis_id"] for entry in json.loads(manifest_path.read_text())["entries"]] == ["fixture_A"]


def test_manifest_rejects_duplicate_entries():
    value = artifact()
    with pytest.raises(ValueError):
        build_feature_manifest([value, value])


@pytest.mark.parametrize("analysis_id", ["../escape", "features/escape", "C:\\escape", ".", "unicode_тест"])
def test_unsafe_analysis_id_is_rejected(analysis_id):
    with pytest.raises(ValueError):
        feature_relative_path(analysis_id)


def test_failed_manifest_replace_leaves_no_temp_file(tmp_path, monkeypatch):
    import lib.d1_feature_artifact_io as io

    def fail_replace(source, target):
        raise OSError("injected replace failure")

    monkeypatch.setattr(io.os, "replace", fail_replace)
    target = tmp_path / "manifest.json"
    with pytest.raises(OSError):
        atomic_write_bytes(target, b"{}\n", overwrite=True)
    assert not list(tmp_path.rglob(".*.tmp"))
    assert not target.exists()
