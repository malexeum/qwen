from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from lib.canonicalization import canonical_feature_hash
from lib.d1_feature_artifacts import D1FeatureArtifact


def validate_feature_artifact(artifact: D1FeatureArtifact) -> None:
    payload = artifact.semantic_payload()
    actual_hash = canonical_feature_hash(payload)
    if actual_hash != artifact.feature_sha256:
        raise ValueError("feature_sha256 does not match the canonical semantic payload")
    if "feature_sha256" in payload or "git_sha" in payload:
        raise ValueError("semantic payload contains envelope-only fields")


def feature_envelope(artifact: D1FeatureArtifact) -> dict[str, Any]:
    validate_feature_artifact(artifact)
    return {
        "semantic_payload": artifact.semantic_payload(),
        "feature_sha256": artifact.feature_sha256,
        "git_sha": artifact.git_sha,
    }


def canonical_feature_envelope_bytes(artifact: D1FeatureArtifact) -> bytes:
    encoded = json.dumps(
        feature_envelope(artifact),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    if b"\r" in encoded:
        raise RuntimeError("canonical envelope must use LF only")
    return encoded


def _resolved_child(root: Path, relative_path: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    target = root / relative_path
    resolved_target = target.resolve(strict=False)
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError("target escapes D1 artifact root")
    return target


def _fsync_parent_directory(path: Path) -> bool:
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        return False
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return True


def atomic_write_bytes(target: Path, content: bytes, *, overwrite: bool) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    try:
        with open(temp_path, "xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temp_path, target)
        else:
            os.link(temp_path, target)
        return _fsync_parent_directory(target)
    finally:
        temp_path.unlink(missing_ok=True)


def write_feature_artifact(root: Path, artifact: D1FeatureArtifact) -> Path:
    if not root.is_dir():
        raise ValueError("D1 artifact root must already exist")
    from lib.d1_feature_manifest import feature_relative_path

    target = _resolved_child(root, feature_relative_path(artifact.analysis_id))
    atomic_write_bytes(target, canonical_feature_envelope_bytes(artifact), overwrite=False)
    return target
