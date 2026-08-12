from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from lib.canonicalization import canonical_feature_hash, canonical_json_bytes, canonical_theta_hash
from lib.composition.d1_harmony_bridge import D1HarmonyBridgeResult, project_perceptual_to_harmony


SCHEMA_VERSION = "d1_feature_artifact/v1"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_AUDIO_IDENTITY_KEYS = frozenset({"kind", "content_sha256", "adapter_name", "adapter_version", "analysis_config_version"})
_SYNTHETIC_IDENTITY_KEYS = frozenset({"kind", "fixture_id", "fixture_spec_sha256"})


@dataclass(frozen=True)
class D1FeatureArtifact:
    schema_version: str
    analysis_id: str
    source_identity: Mapping[str, str]
    perceptual: Mapping[str, float]
    bridge_name: str
    bridge_version: str
    encoder_name: str
    encoder_version: str
    named_theta: Mapping[str, float]
    canonical_theta_hash: str
    feature_sha256: str
    git_sha: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "source_identity": dict(self.source_identity),
            "perceptual": dict(self.perceptual),
            "bridge": {"name": self.bridge_name, "version": self.bridge_version},
            "encoder": {"name": self.encoder_name, "version": self.encoder_version},
            "named_theta": dict(self.named_theta),
            "canonical_theta_hash": self.canonical_theta_hash,
        }


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_source_identity(source_identity: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(source_identity, Mapping):
        raise ValueError("source_identity must be a mapping")
    identity = {str(key): value for key, value in source_identity.items()}
    kind = identity.get("kind")
    expected = _AUDIO_IDENTITY_KEYS if kind == "audio_file" else _SYNTHETIC_IDENTITY_KEYS if kind == "synthetic_fixture" else None
    if expected is None or set(identity) != expected:
        raise ValueError("source_identity does not match a supported strict schema")
    for key, value in identity.items():
        _require_nonempty_string(value, f"source_identity.{key}")
    hash_key = "content_sha256" if kind == "audio_file" else "fixture_spec_sha256"
    if not _SHA256_RE.fullmatch(identity[hash_key]):
        raise ValueError(f"source_identity.{hash_key} must be sha256:<64 lowercase hex>")
    return identity


def _build_semantic_payload(
    *, analysis_id: str, source_identity: Mapping[str, str], bridge_result: D1HarmonyBridgeResult
) -> dict[str, Any]:
    theta_hash = canonical_theta_hash(bridge_result.named_theta)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": analysis_id,
        "source_identity": dict(source_identity),
        "perceptual": dict(bridge_result.encoder_features),
        "bridge": {"name": bridge_result.bridge_name, "version": bridge_result.bridge_version},
        "encoder": {"name": bridge_result.encoder_name, "version": bridge_result.encoder_version},
        "named_theta": dict(bridge_result.named_theta),
        "canonical_theta_hash": theta_hash,
    }


def build_d1_feature_artifact(
    *, analysis_id: str, source_identity: Mapping[str, str], perceptual: Mapping[str, Any], git_sha: str
) -> D1FeatureArtifact:
    analysis_id = _require_nonempty_string(analysis_id, "analysis_id")
    git_sha = _require_nonempty_string(git_sha, "git_sha")
    if not _GIT_SHA_RE.fullmatch(git_sha):
        raise ValueError("git_sha must be 40 lowercase hexadecimal characters")
    validated_identity = _validate_source_identity(source_identity)
    bridge_result = project_perceptual_to_harmony(perceptual)
    semantic_payload = _build_semantic_payload(
        analysis_id=analysis_id, source_identity=validated_identity, bridge_result=bridge_result
    )
    feature_sha256 = canonical_feature_hash(semantic_payload)
    return D1FeatureArtifact(
        schema_version=SCHEMA_VERSION,
        analysis_id=analysis_id,
        source_identity=MappingProxyType(validated_identity),
        perceptual=MappingProxyType(dict(bridge_result.encoder_features)),
        bridge_name=bridge_result.bridge_name,
        bridge_version=bridge_result.bridge_version,
        encoder_name=bridge_result.encoder_name,
        encoder_version=bridge_result.encoder_version,
        named_theta=MappingProxyType(dict(bridge_result.named_theta)),
        canonical_theta_hash=semantic_payload["canonical_theta_hash"],
        feature_sha256=feature_sha256,
        git_sha=git_sha,
    )


def canonical_feature_payload_bytes(artifact: D1FeatureArtifact) -> bytes:
    return canonical_json_bytes(artifact.semantic_payload())


__all__ = ["D1FeatureArtifact", "SCHEMA_VERSION", "build_d1_feature_artifact", "canonical_feature_payload_bytes"]
