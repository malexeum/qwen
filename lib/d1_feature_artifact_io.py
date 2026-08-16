from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from lib.canonicalization import canonical_feature_hash, canonical_theta_hash
from lib.d1_feature_artifacts import (
    D1FeatureArtifact,
    SCHEMA_V1,
    SCHEMA_V2,
    validate_git_sha,
    validate_source_identity,
    validate_source_locator,
)


_SEMANTIC_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "analysis_id",
        "source_identity",
        "perceptual",
        "bridge",
        "encoder",
        "named_theta",
        "canonical_theta_hash",
    }
)


def validate_feature_artifact(artifact: D1FeatureArtifact) -> None:
    if not isinstance(artifact, D1FeatureArtifact):
        raise ValueError("artifact must be a D1FeatureArtifact")

    if artifact.schema_version not in {SCHEMA_V1, SCHEMA_V2}:
        raise ValueError("unsupported D1 feature artifact schema_version")

    if not isinstance(artifact.analysis_id, str) or not artifact.analysis_id:
        raise ValueError("analysis_id must be a non-empty string")

    validate_git_sha(artifact.git_sha)
    validate_source_identity(artifact.schema_version, artifact.source_identity)

    if artifact.schema_version == SCHEMA_V2:
        if artifact.source_locator is None:
            raise ValueError("source_locator is required for v2")
        validate_source_locator(artifact.source_locator)
    elif artifact.source_locator is not None:
        raise ValueError("source_locator is only valid for v2")

    expected_theta_hash = canonical_theta_hash(artifact.named_theta)
    if artifact.canonical_theta_hash != expected_theta_hash:
        raise ValueError("canonical_theta_hash does not match named_theta")

    payload = artifact.semantic_payload()
    if set(payload) != _SEMANTIC_PAYLOAD_FIELDS:
        raise ValueError("semantic payload fields are invalid")

    if "git_sha" in payload or "feature_sha256" in payload:
        raise ValueError("semantic payload must not contain envelope provenance")

    actual_hash = canonical_feature_hash(payload)
    if actual_hash != artifact.feature_sha256:
        raise ValueError(
            "feature_sha256 does not match the canonical semantic payload"
        )


def feature_envelope(artifact: D1FeatureArtifact) -> dict[str, Any]:
    validate_feature_artifact(artifact)

    envelope: dict[str, Any] = {
        "semantic_payload": artifact.semantic_payload(),
        "feature_sha256": artifact.feature_sha256,
        "git_sha": artifact.git_sha,
    }

    if artifact.schema_version == SCHEMA_V2:
        envelope["source_locator"] = dict(artifact.source_locator or {})

    return envelope


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


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return dict(value)


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_float_mapping(value: Any, field: str) -> dict[str, float]:
    data = _require_mapping(value, field)
    normalized: dict[str, float] = {}

    for key, item in data.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{field} keys must be non-empty strings")
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field}.{key} must be a finite number")
        numeric = float(item)
        if not __import__("math").isfinite(numeric):
            raise ValueError(f"{field}.{key} must be a finite number")
        normalized[key] = numeric

    return normalized


def _parse_semantic_payload(payload: Any) -> dict[str, Any]:
    data = _require_mapping(payload, "semantic_payload")

    if set(data) != _SEMANTIC_PAYLOAD_FIELDS:
        raise ValueError("semantic_payload has missing or unexpected fields")

    schema_version = data["schema_version"]
    if schema_version not in {SCHEMA_V1, SCHEMA_V2}:
        raise ValueError("unsupported D1 feature artifact schema_version")

    analysis_id = _require_nonempty_string(data["analysis_id"], "analysis_id")
    source_identity = validate_source_identity(
        schema_version,
        _require_mapping(data["source_identity"], "source_identity"),
    )

    perceptual = _require_float_mapping(data["perceptual"], "perceptual")

    bridge = _require_mapping(data["bridge"], "bridge")
    if set(bridge) != {"name", "version"}:
        raise ValueError("bridge must contain exactly name and version")

    encoder = _require_mapping(data["encoder"], "encoder")
    if set(encoder) != {"name", "version"}:
        raise ValueError("encoder must contain exactly name and version")

    named_theta = _require_float_mapping(data["named_theta"], "named_theta")
    canonical_theta_hash = _require_nonempty_string(
        data["canonical_theta_hash"],
        "canonical_theta_hash",
    )

    return {
        "schema_version": schema_version,
        "analysis_id": analysis_id,
        "source_identity": source_identity,
        "perceptual": perceptual,
        "bridge_name": _require_nonempty_string(bridge["name"], "bridge.name"),
        "bridge_version": _require_nonempty_string(
            bridge["version"],
            "bridge.version",
        ),
        "encoder_name": _require_nonempty_string(encoder["name"], "encoder.name"),
        "encoder_version": _require_nonempty_string(
            encoder["version"],
            "encoder.version",
        ),
        "named_theta": named_theta,
        "canonical_theta_hash": canonical_theta_hash,
    }


def read_feature_artifact(path: Path) -> D1FeatureArtifact:
    if not isinstance(path, Path):
        raise ValueError("path must be a pathlib.Path")

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read feature artifact: {path}") from exc

    try:
        decoded = raw.decode("utf-8")
        envelope = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("feature artifact must contain valid UTF-8 JSON") from exc

    data = _require_mapping(envelope, "feature envelope")
    payload = _parse_semantic_payload(data.get("semantic_payload"))

    schema_version = payload["schema_version"]
    expected_envelope_fields = (
        {"semantic_payload", "feature_sha256", "git_sha"}
        if schema_version == SCHEMA_V1
        else {
            "semantic_payload",
            "feature_sha256",
            "git_sha",
            "source_locator",
        }
    )

    if set(data) != expected_envelope_fields:
        raise ValueError("feature envelope has missing or unexpected fields")

    feature_sha256 = _require_nonempty_string(
        data["feature_sha256"],
        "feature_sha256",
    )
    git_sha = validate_git_sha(data["git_sha"])

    if schema_version == SCHEMA_V2:
        source_locator = validate_source_locator(
            _require_mapping(data["source_locator"], "source_locator")
        )
    else:
        source_locator = None

    artifact = D1FeatureArtifact(
        schema_version=schema_version,
        analysis_id=payload["analysis_id"],
        source_identity=MappingProxyType(payload["source_identity"]),
        perceptual=MappingProxyType(payload["perceptual"]),
        bridge_name=payload["bridge_name"],
        bridge_version=payload["bridge_version"],
        encoder_name=payload["encoder_name"],
        encoder_version=payload["encoder_version"],
        named_theta=MappingProxyType(payload["named_theta"]),
        canonical_theta_hash=payload["canonical_theta_hash"],
        feature_sha256=feature_sha256,
        git_sha=git_sha,
        source_locator=(
            MappingProxyType(source_locator)
            if source_locator is not None
            else None
        ),
    )
    validate_feature_artifact(artifact)

    expected_bytes = canonical_feature_envelope_bytes(artifact)
    if raw != expected_bytes:
        raise ValueError(
            "feature envelope is not in canonical serialized representation"
        )

    return artifact


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
    atomic_write_bytes(
        target,
        canonical_feature_envelope_bytes(artifact),
        overwrite=False,
    )
    return target