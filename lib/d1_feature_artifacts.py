from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from lib.canonicalization import (
    canonical_feature_hash,
    canonical_json_bytes,
    canonical_theta_hash,
)
from lib.composition.d1_harmony_bridge import (
    D1HarmonyBridgeResult,
    project_perceptual_to_harmony,
)

SCHEMA_V1 = "d1_feature_artifact/v1"
SCHEMA_V2 = "d1_feature_artifact/v2"
SCHEMA_VERSION = SCHEMA_V1

_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_BACKEND_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*/[0-9][a-z0-9_.+-]*\Z")

_AUDIO_V1 = frozenset(
    {
        "kind",
        "content_sha256",
        "adapter_name",
        "adapter_version",
        "analysis_config_version",
    }
)
_AUDIO_V2 = frozenset(
    {
        "kind",
        "inventory_source_id",
        "content_sha256",
        "byte_size",
        "suffix",
        "adapter_name",
        "adapter_version",
        "analysis_config_version",
        "decoder_backend",
    }
)
_SYNTHETIC_V1 = frozenset({"kind", "fixture_id", "fixture_spec_sha256"})


@dataclass(frozen=True)
class D1FeatureArtifact:
    schema_version: str
    analysis_id: str
    source_identity: Mapping[str, Any]
    perceptual: Mapping[str, float]
    bridge_name: str
    bridge_version: str
    encoder_name: str
    encoder_version: str
    named_theta: Mapping[str, float]
    canonical_theta_hash: str
    feature_sha256: str
    git_sha: str
    source_locator: Mapping[str, str] | None = None

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "source_identity": dict(self.source_identity),
            "perceptual": dict(self.perceptual),
            "bridge": {
                "name": self.bridge_name,
                "version": self.bridge_version,
            },
            "encoder": {
                "name": self.encoder_name,
                "version": self.encoder_version,
            },
            "named_theta": dict(self.named_theta),
            "canonical_theta_hash": self.canonical_theta_hash,
        }


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _sha(value: Any, field: str) -> str:
    value = _string(value, field)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be sha256:<64 lowercase hex>")
    return value


def validate_git_sha(value: Any) -> str:
    value = _string(value, "git_sha")
    if not _GIT_SHA_RE.fullmatch(value):
        raise ValueError("git_sha must be 40 lowercase hexadecimal characters")
    return value


def validate_source_locator(locator: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(locator, Mapping) or set(locator) != {"registry_path"}:
        raise ValueError("source_locator must contain exactly registry_path")

    path = _string(locator["registry_path"], "source_locator.registry_path")
    parts = path.split("/")

    if (
        "\x00" in path
        or "\\" in path
        or ":" in path
        or path.startswith("/")
        or path.endswith("/")
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("registry_path must be a canonical relative POSIX file path")

    return {"registry_path": path}


def validate_source_identity(
    schema_version: str,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(identity, Mapping):
        raise ValueError("source_identity must be a mapping")

    data = dict(identity)
    kind = data.get("kind")

    if schema_version == SCHEMA_V1:
        expected = (
            _SYNTHETIC_V1
            if kind == "synthetic_fixture"
            else _AUDIO_V1
            if kind == "audio_file"
            else None
        )
    elif schema_version == SCHEMA_V2:
        expected = _AUDIO_V2 if kind == "audio_file" else None
    else:
        raise ValueError("unsupported D1 feature artifact schema_version")

    if expected is None or set(data) != expected:
        raise ValueError("source_identity does not match the strict schema")

    if kind == "synthetic_fixture":
        data["fixture_id"] = _string(
            data["fixture_id"],
            "source_identity.fixture_id",
        )
        data["fixture_spec_sha256"] = _sha(
            data["fixture_spec_sha256"],
            "source_identity.fixture_spec_sha256",
        )
        return data

    data["content_sha256"] = _sha(
        data["content_sha256"],
        "source_identity.content_sha256",
    )

    for key in (
        "adapter_name",
        "adapter_version",
        "analysis_config_version",
    ):
        data[key] = _string(data[key], f"source_identity.{key}")

    if schema_version == SCHEMA_V1:
        raise ValueError("new audio-derived artifacts must use d1_feature_artifact/v2")

    if data["inventory_source_id"] != (
        f"audio_source_inventory/v1/{data['content_sha256']}"
    ):
        raise ValueError(
            "inventory_source_id must equal "
            "audio_source_inventory/v1/<content_sha256>"
        )

    if (
        isinstance(data["byte_size"], bool)
        or not isinstance(data["byte_size"], int)
        or data["byte_size"] <= 0
    ):
        raise ValueError("source_identity.byte_size must be a positive integer")

    if data["suffix"] != ".mp3":
        raise ValueError("source_identity.suffix must be .mp3")

    data["decoder_backend"] = _string(
        data["decoder_backend"],
        "source_identity.decoder_backend",
    )
    if not _BACKEND_RE.fullmatch(data["decoder_backend"]):
        raise ValueError(
            "decoder_backend must use <backend>/<exact-version>"
        )

    return data


def build_d1_feature_artifact(
    *,
    analysis_id: str,
    source_identity: Mapping[str, Any],
    perceptual: Mapping[str, Any],
    git_sha: str,
    schema_version: str,
    source_locator: Mapping[str, Any] | None = None,
) -> D1FeatureArtifact:
    analysis_id = _string(analysis_id, "analysis_id")
    git_sha = validate_git_sha(git_sha)

    identity = validate_source_identity(schema_version, source_identity)

    if schema_version == SCHEMA_V2:
        locator = validate_source_locator(source_locator)
    elif source_locator is not None:
        raise ValueError("source_locator is only valid for v2")
    else:
        locator = None

    result: D1HarmonyBridgeResult = project_perceptual_to_harmony(perceptual)
    theta_hash = canonical_theta_hash(result.named_theta)

    payload = {
        "schema_version": schema_version,
        "analysis_id": analysis_id,
        "source_identity": identity,
        "perceptual": dict(result.encoder_features),
        "bridge": {
            "name": result.bridge_name,
            "version": result.bridge_version,
        },
        "encoder": {
            "name": result.encoder_name,
            "version": result.encoder_version,
        },
        "named_theta": dict(result.named_theta),
        "canonical_theta_hash": theta_hash,
    }

    return D1FeatureArtifact(
        schema_version=schema_version,
        analysis_id=analysis_id,
        source_identity=MappingProxyType(identity),
        perceptual=MappingProxyType(dict(result.encoder_features)),
        bridge_name=result.bridge_name,
        bridge_version=result.bridge_version,
        encoder_name=result.encoder_name,
        encoder_version=result.encoder_version,
        named_theta=MappingProxyType(dict(result.named_theta)),
        canonical_theta_hash=theta_hash,
        feature_sha256=canonical_feature_hash(payload),
        git_sha=git_sha,
        source_locator=MappingProxyType(locator) if locator is not None else None,
    )


def canonical_feature_payload_bytes(artifact: D1FeatureArtifact) -> bytes:
    return canonical_json_bytes(artifact.semantic_payload())


__all__ = [
    "D1FeatureArtifact",
    "SCHEMA_V1",
    "SCHEMA_V2",
    "SCHEMA_VERSION",
    "build_d1_feature_artifact",
    "canonical_feature_payload_bytes",
    "validate_git_sha",
    "validate_source_identity",
    "validate_source_locator",
]