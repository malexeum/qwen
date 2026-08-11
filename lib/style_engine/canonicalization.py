from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

THETA_AXES: tuple[str, ...] = tuple(f"harmony_theta_{index}" for index in range(8))
_FLOAT_QUANTUM = Decimal("0.000001")


def canonical_float(value: int | float | str | Decimal) -> str:
    """Return a six-place fixed-point decimal using ROUND_HALF_EVEN."""
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid canonical floats")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid numeric value: {value!r}") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"Non-finite numeric value: {value!r}")
    return format(decimal_value.quantize(_FLOAT_QUANTUM, rounding=ROUND_HALF_EVEN), "f")


def _canonicalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, (float, Decimal)):
        return canonical_float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Canonical JSON object keys must be strings")
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"Unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize semantic data as deterministic UTF-8 canonical JSON bytes."""
    return json.dumps(
        _canonicalize(data),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def canonical_file_hash(path: str | Path) -> str:
    """Hash a physical artifact exactly as stored, without any normalization."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def canonical_feature_hash(feature_artifact: Any) -> str:
    return sha256_prefixed(canonical_json_bytes(feature_artifact))


def canonical_theta_hash(theta: Mapping[str, Any]) -> str:
    """Hash the complete numeric named theta vector in fixed THETA_AXES order."""
    actual_axes = set(theta)
    expected_axes = set(THETA_AXES)
    if actual_axes != expected_axes:
        missing = sorted(expected_axes - actual_axes)
        extra = sorted(actual_axes - expected_axes)
        raise ValueError(f"Theta axes mismatch; missing={missing}, extra={extra}")

    ordered_pairs: list[list[str]] = []
    for axis in THETA_AXES:
        raw_value = theta[axis]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, Decimal)):
            raise ValueError(f"Theta axis {axis} must be a finite numeric scalar")
        canonical_value = canonical_float(raw_value)
        numeric_value = Decimal(canonical_value)
        if not Decimal("0") <= numeric_value <= Decimal("1"):
            raise ValueError(f"Theta axis {axis} is outside [0, 1]: {canonical_value}")
        ordered_pairs.append([axis, canonical_value])

    short_hex = hashlib.sha256(canonical_json_bytes(ordered_pairs)).hexdigest()[:16]
    return f"sha256:{short_hex}"
