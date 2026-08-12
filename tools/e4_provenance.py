from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

THETA_KEYS = tuple(f"harmony_theta_{index}" for index in range(8))
RENDER_FLOAT_FIELDS = (
    "symmetry_bias", "recursion_depth", "density_level", "noise_level",
    "motion_intensity", "texture_complexity", *THETA_KEYS, "stochastic_term",
)
RENDER_STRING_FIELDS = (
    "style_profile_slug", "interpretation_profile_slug", "preset_id",
    "palette_id", "layout_macro_shape",
)
MANIFEST_KEYS = {
    "schema_version", "experiment_id", "total_fixtures", "lifecycle_status",
    "source_manifests", "historical_render_sets",
    "historical_render_sets_are_reference_baselines", "fixture_defaults", "fixtures",
}
FIXTURE_KEYS = {
    "id", "tier", "fixture_category", "style_profile_slug",
    "interpretation_profile_slug", "preset_id", "expected_palette",
    "lifecycle_status", "audio_content_sha256", "feature_artifact_path",
    "feature_sha256", "canonical_theta_hash_short", "canonical_theta_sha256",
    "variation_seed", "canonical_render_params_sha256", "output_sha256", "audit_scores",
}


class E4ProvenanceError(ValueError):
    pass


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise E4ProvenanceError(f"{name} must be a finite number")
    return float(value)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_theta_payload(theta: Mapping[str, Any]) -> dict[str, float]:
    if set(theta) != set(THETA_KEYS):
        raise E4ProvenanceError("theta must contain exactly harmony_theta_0 through harmony_theta_7")
    payload = {key: round(_finite_number(theta[key], key), 6) for key in THETA_KEYS}
    if any(value < 0.0 or value > 1.0 for value in payload.values()):
        raise E4ProvenanceError("theta values must be within [0, 1]")
    return payload


def theta_hashes(theta: Mapping[str, Any]) -> tuple[str, str]:
    digest = hashlib.sha256(canonical_json_bytes(canonical_theta_payload(theta))).hexdigest()
    return f"sha256-64:{digest[:16]}", f"sha256:{digest}"


def canonical_render_params_payload(params: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in RENDER_STRING_FIELDS:
        value = getattr(params, field)
        if not isinstance(value, str) or not value:
            raise E4ProvenanceError(f"{field} must be a non-empty string")
        payload[field] = value
    for field in RENDER_FLOAT_FIELDS:
        payload[field] = round(_finite_number(getattr(params, field), field), 6)
    seed = getattr(params, "variation_seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise E4ProvenanceError("variation_seed must be a non-negative integer")
    payload["variation_seed"] = seed
    return payload


def render_params_sha256(params: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(canonical_render_params_payload(params))).hexdigest()


def _relative_posix_path(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise E4ProvenanceError(f"{name} must be a string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise E4ProvenanceError(f"{name} must be a relative POSIX path")


def validate_manifest(document: Mapping[str, Any]) -> None:
    if set(document) != MANIFEST_KEYS:
        raise E4ProvenanceError("manifest keys do not match e4a-v1 contract")
    if document["schema_version"] != "e4a_fixtures_manifest/v1":
        raise E4ProvenanceError("unsupported schema_version")
    if document["lifecycle_status"] != "planned":
        raise E4ProvenanceError("E4-A manifest lifecycle_status must be planned")
    fixtures = document["fixtures"]
    if not isinstance(fixtures, list) or document["total_fixtures"] != len(fixtures) or len(fixtures) != 22:
        raise E4ProvenanceError("e4a-v1 requires exactly 22 fixtures")
    if document["historical_render_sets_are_reference_baselines"] is not False:
        raise E4ProvenanceError("historical renders cannot be E4-A reference baselines")
    for name in ("source_manifests", "historical_render_sets"):
        if not isinstance(document[name], list) or not document[name]:
            raise E4ProvenanceError(f"{name} must be a non-empty list")
        for path in document[name]:
            _relative_posix_path(path, name)
    ids: set[str] = set()
    nullable = FIXTURE_KEYS - {"id", "tier", "fixture_category", "style_profile_slug", "interpretation_profile_slug", "preset_id", "expected_palette", "lifecycle_status"}
    for fixture in fixtures:
        if not isinstance(fixture, Mapping) or set(fixture) != FIXTURE_KEYS:
            raise E4ProvenanceError("fixture keys do not match e4a-v1 contract")
        fixture_id = fixture["id"]
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in ids:
            raise E4ProvenanceError("fixture ids must be unique non-empty strings")
        ids.add(fixture_id)
        if fixture["tier"] not in {"A", "B", "C", "smoke"} or fixture["fixture_category"] not in {"canonical", "smoke"}:
            raise E4ProvenanceError(f"{fixture_id}: invalid tier or category")
        if fixture["lifecycle_status"] != "planned":
            raise E4ProvenanceError(f"{fixture_id}: lifecycle_status must be planned")
        for key in ("style_profile_slug", "interpretation_profile_slug", "preset_id", "expected_palette"):
            if not isinstance(fixture[key], str) or not fixture[key]:
                raise E4ProvenanceError(f"{fixture_id}: {key} must be non-empty")
        if any(fixture[key] is not None for key in nullable):
            raise E4ProvenanceError(f"{fixture_id}: planned fixture must not contain materialized provenance")
