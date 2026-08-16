from __future__ import annotations

import json
from pathlib import Path

from lib.d1_feature_artifact_io import read_feature_artifact
from lib.d1_feature_manifest import (
    MANIFEST_SCHEMA_VERSION,
    build_feature_manifest,
    canonical_manifest_bytes,
    feature_relative_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "d1"
FEATURES_ROOT = ARTIFACT_ROOT / "features"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"


def _feature_paths() -> list[Path]:
    assert ARTIFACT_ROOT.is_dir(), f"missing D1 artifact root: {ARTIFACT_ROOT}"
    assert FEATURES_ROOT.is_dir(), f"missing D1 features directory: {FEATURES_ROOT}"

    paths = sorted(FEATURES_ROOT.glob("*.json"))
    assert paths, f"no D1 feature artifacts found in: {FEATURES_ROOT}"

    return paths


def test_d1_feature_registry_is_canonical_and_complete() -> None:
    paths = _feature_paths()
    artifacts = [read_feature_artifact(path) for path in paths]

    expected_paths = {
        feature_relative_path(artifact.analysis_id).as_posix()
        for artifact in artifacts
    }
    actual_paths = {
        path.relative_to(ARTIFACT_ROOT).as_posix()
        for path in paths
    }

    assert actual_paths == expected_paths, (
        "D1 feature filenames must exactly match their analysis_id-derived "
        f"registry paths; actual={sorted(actual_paths)!r}, "
        f"expected={sorted(expected_paths)!r}"
    )

    assert MANIFEST_PATH.is_file(), f"missing D1 manifest: {MANIFEST_PATH}"
    manifest_bytes = MANIFEST_PATH.read_bytes()
    expected_manifest_bytes = canonical_manifest_bytes(artifacts)

    assert manifest_bytes == expected_manifest_bytes, (
        "D1 manifest is not the canonical byte-for-byte rebuild of all "
        "validated feature artifacts"
    )

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    assert manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION

    entries = manifest.get("entries")
    assert isinstance(entries, list), "D1 manifest entries must be a list"

    manifest_paths = {
        entry["relative_path"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("relative_path"), str)
    }
    manifest_ids = {
        entry["analysis_id"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("analysis_id"), str)
    }
    manifest_hashes = {
        entry["feature_sha256"]
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("feature_sha256"), str)
    }

    assert len(entries) == len(manifest_paths), (
        "D1 manifest contains duplicate or malformed relative_path entries"
    )
    assert len(entries) == len(manifest_ids), (
        "D1 manifest contains duplicate or malformed analysis_id entries"
    )
    assert len(entries) == len(manifest_hashes), (
        "D1 manifest contains duplicate or malformed feature_sha256 entries"
    )

    assert manifest_paths == actual_paths, (
        "D1 manifest paths do not exactly match published feature files; "
        f"manifest={sorted(manifest_paths)!r}, "
        f"features={sorted(actual_paths)!r}"
    )