from __future__ import annotations

import hashlib
import json
import math
import re
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
DEFAULT_KEYS = FIXTURE_KEYS - {
    "id", "tier", "fixture_category", "style_profile_slug", "expected_palette",
}
MATERIALIZED_KEYS = {
    "audio_content_sha256", "feature_artifact_path", "feature_sha256",
    "canonical_theta_hash_short", "canonical_theta_sha256", "variation_seed",
    "canonical_render_params_sha256", "output_sha256", "audit_scores",
}
CANONICAL_PROFILES = {
    "ambient", "blues_jazz", "classical", "electronic", "jazz", "pop", "rock",
}
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FIXTURE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*_(?:[ABC]|smoke)$")


class E4ProvenanceError(ValueError):
    """Raised when an E4-A provenance contract invariant is violated."""


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise E4ProvenanceError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise E4ProvenanceError(f"{name} must be a finite number")
    return result


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_theta_payload(theta: Mapping[str, Any]) -> dict[str, float]:
    if set(theta) != set(THETA_KEYS):
        raise E4ProvenanceError(
            "theta must contain exactly harmony_theta_0 through harmony_theta_7"
        )
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
        if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
            raise E4ProvenanceError(f"{field} must be a canonical non-empty identifier")
        payload[field] = value
    for field in RENDER_FLOAT_FIELDS:
        payload[field] = round(_finite_number(getattr(params, field), field), 6)
    seed = getattr(params, "variation_seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise E4ProvenanceError("variation_seed must be a non-negative integer")
    payload["variation_seed"] = seed
    return payload


def render_params_sha256(params: Any) -> str:
    digest = hashlib.sha256(canonical_json_bytes(canonical_render_params_payload(params)))
    return f"sha256:{digest.hexdigest()}"


def _relative_posix_path(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise E4ProvenanceError(f"{name} must be a string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise E4ProvenanceError(f"{name} must be a relative POSIX path")


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise E4ProvenanceError(f"{name} must be a canonical identifier")
    return value


def _validate_defaults(defaults: Any) -> None:
    if not isinstance(defaults, Mapping) or set(defaults) != DEFAULT_KEYS:
        raise E4ProvenanceError("fixture_defaults keys do not match e4a-v1 contract")
    if defaults["interpretation_profile_slug"] != "default":
        raise E4ProvenanceError("fixture_defaults interpretation_profile_slug must be default")
    if defaults["preset_id"] != "default":
        raise E4ProvenanceError("fixture_defaults preset_id must be default")
    if defaults["lifecycle_status"] != "planned":
        raise E4ProvenanceError("fixture_defaults lifecycle_status must be planned")
    if any(defaults[key] is not None for key in MATERIALIZED_KEYS):
        raise E4ProvenanceError("fixture_defaults must not contain materialized provenance")


def _validate_fixture(fixture: Any, ids: set[str]) -> None:
    if not isinstance(fixture, Mapping) or set(fixture) != FIXTURE_KEYS:
        raise E4ProvenanceError("fixture keys do not match e4a-v1 contract")
    fixture_id = fixture["id"]
    if not isinstance(fixture_id, str) or not FIXTURE_ID_RE.fullmatch(fixture_id):
        raise E4ProvenanceError("fixture id must match <profile>_<A|B|C|smoke>")
    if fixture_id in ids:
        raise E4ProvenanceError("fixture ids must be unique")
    ids.add(fixture_id)

    tier = fixture["tier"]
    category = fixture["fixture_category"]
    profile = _identifier(fixture["style_profile_slug"], "style_profile_slug")
    _identifier(fixture["interpretation_profile_slug"], "interpretation_profile_slug")
    _identifier(fixture["preset_id"], "preset_id")
    _identifier(fixture["expected_palette"], "expected_palette")
    if fixture["lifecycle_status"] != "planned":
        raise E4ProvenanceError(f"{fixture_id}: lifecycle_status must be planned")
    if any(fixture[key] is not None for key in MATERIALIZED_KEYS):
        raise E4ProvenanceError(f"{fixture_id}: planned fixture contains materialized provenance")
    if category == "canonical":
        if profile not in CANONICAL_PROFILES or tier not in {"A", "B", "C"}:
            raise E4ProvenanceError(f"{fixture_id}: invalid canonical profile or tier")
        if fixture_id != f"{profile}_{tier}":
            raise E4ProvenanceError(f"{fixture_id}: canonical id must match profile and tier")
    elif category == "smoke":
        if fixture_id != "default_smoke" or profile != "default" or tier != "smoke":
            raise E4ProvenanceError("smoke fixture must be default_smoke")
    else:
        raise E4ProvenanceError(f"{fixture_id}: invalid fixture_category")


def validate_manifest(document: Mapping[str, Any]) -> None:
    if not isinstance(document, Mapping) or set(document) != MANIFEST_KEYS:
        raise E4ProvenanceError("manifest keys do not match e4a-v1 contract")
    if document["schema_version"] != "e4a_fixtures_manifest/v1":
        raise E4ProvenanceError("unsupported schema_version")
    if document["experiment_id"] != "e4a_planned_provenance_contract_v1":
        raise E4ProvenanceError("unexpected experiment_id")
    if document["lifecycle_status"] != "planned":
        raise E4ProvenanceError("E4-A manifest lifecycle_status must be planned")
    _validate_defaults(document["fixture_defaults"])
    fixtures = document["fixtures"]
    if not isinstance(fixtures, list) or document["total_fixtures"] != len(fixtures) or len(fixtures) != 22:
        raise E4ProvenanceError("e4a-v1 requires exactly 22 fixtures")
    if document["historical_render_sets_are_reference_baselines"] is not False:
        raise E4ProvenanceError("historical renders cannot be E4-A reference baselines")
    for name in ("source_manifests", "historical_render_sets"):
        values = document[name]
        if not isinstance(values, list) or not values:
            raise E4ProvenanceError(f"{name} must be a non-empty list")
        for path in values:
            _relative_posix_path(path, name)
    ids: set[str] = set()
    for fixture in fixtures:
        _validate_fixture(fixture, ids)
    expected_ids = {f"{profile}_{tier}" for profile in CANONICAL_PROFILES for tier in "ABC"} | {"default_smoke"}
    if ids != expected_ids:
        raise E4ProvenanceError("fixture ids do not match the E4-A profile/tier matrix")
