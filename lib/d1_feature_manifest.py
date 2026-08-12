from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lib.canonicalization import canonical_json_bytes
from lib.d1_feature_artifact_io import atomic_write_bytes, validate_feature_artifact
from lib.d1_feature_artifacts import D1FeatureArtifact


MANIFEST_SCHEMA_VERSION = "d1_feature_manifest/v1"
_ANALYSIS_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def feature_relative_path(analysis_id: str) -> Path:
    if not isinstance(analysis_id, str) or not _ANALYSIS_ID_RE.fullmatch(analysis_id):
        raise ValueError("analysis_id must be a safe ASCII filename component")
    return Path("features") / f"{analysis_id}.json"


def build_feature_manifest(artifacts: Sequence[D1FeatureArtifact]) -> dict[str, Any]:
    entries = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    for artifact in artifacts:
        validate_feature_artifact(artifact)
        relative_path = feature_relative_path(artifact.analysis_id).as_posix()
        if artifact.analysis_id in seen_ids or relative_path in seen_paths or artifact.feature_sha256 in seen_hashes:
            raise ValueError("manifest entries must have unique analysis_id, path, and feature_sha256")
        seen_ids.add(artifact.analysis_id)
        seen_paths.add(relative_path)
        seen_hashes.add(artifact.feature_sha256)
        entries.append({
            "analysis_id": artifact.analysis_id,
            "relative_path": relative_path,
            "feature_sha256": artifact.feature_sha256,
        })
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "entries": sorted(entries, key=lambda entry: entry["analysis_id"])}


def canonical_manifest_bytes(artifacts: Sequence[D1FeatureArtifact]) -> bytes:
    encoded = canonical_json_bytes(build_feature_manifest(artifacts)) + b"\n"
    if b"\r" in encoded:
        raise RuntimeError("canonical manifest must use LF only")
    return encoded


def write_feature_manifest(root: Path, artifacts: Sequence[D1FeatureArtifact]) -> Path:
    if not root.is_dir():
        raise ValueError("D1 artifact root must already exist")
    target = root / "manifest.json"
    atomic_write_bytes(target, canonical_manifest_bytes(artifacts), overwrite=True)
    return target
