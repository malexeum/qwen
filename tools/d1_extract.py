from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Callable, Mapping

from lib.audio_analysis.analysis import analyze_audio_file
from lib.canonicalization import canonical_json_bytes, sha256_prefixed

ADAPTER_NAME = "d1_perceptual_extractor"
ADAPTER_VERSION = "1.0.0"
ANALYSIS_CONFIG_VERSION = "d1_perceptual_config/v1"
INVENTORY_SCHEMA_VERSION = "audio_source_inventory/v1"
MEASUREMENT_BACKEND = {
    "module": "lib.audio_analysis.analysis",
    "function": "analyze_audio_file",
    "implementation_contract": "e1_fix3_fixed_44100hz_mono_nfft2048_hop512",
}
CANONICAL_AXES = (
    "symmetry_bias",
    "tension",
    "harmonic_stability",
    "harmonic_change_rate",
    "texture_complexity",
    "recursion_depth",
    "section_complexity",
    "noise_level",
)
_QUANTUM = Decimal("0.000001")
_CHUNK_SIZE = 1024 * 1024
_BACKEND_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*/[0-9][a-z0-9_.+-]*\Z")


class ExtractionContractError(ValueError):
    """Raised when an input violates the D1 extraction contract."""


def _sha256_raw_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _canonical_relative_path(repo_root: Path, source_path: Path) -> str:
    resolved_root = repo_root.resolve(strict=True)
    resolved_source = source_path.resolve(strict=True)
    try:
        return resolved_source.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ExtractionContractError(
            "source path resolves outside repository root"
        ) from exc


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionContractError(f"cannot load {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ExtractionContractError(f"{label} must be a JSON object")
    return payload


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExtractionContractError(
            f"measurement {name} must be a finite real number"
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ExtractionContractError(f"measurement {name} must be finite")
    return numeric


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _round6(value: float) -> float:
    return float(
        Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
    )


def _measurement(raw: Mapping[str, Any], name: str) -> float:
    if name not in raw:
        raise ExtractionContractError(f"missing required measurement: {name}")
    return _finite(name, raw[name])


def _formula_identity_clip01(
    raw: Mapping[str, Any],
    mapped: Mapping[str, float],
    measurement_name: str,
) -> float:
    return _clip01(_measurement(raw, measurement_name))


def _formula_dynamic_range_div_30_clip01(
    raw: Mapping[str, Any],
    mapped: Mapping[str, float],
) -> float:
    return _clip01(_measurement(raw, "dynamic_range") / 30.0)


def _formula_harmonic_change_rate_div_2_clip01(
    raw: Mapping[str, Any],
    mapped: Mapping[str, float],
) -> float:
    return _clip01(_measurement(raw, "harmonic_change_rate_hz") / 2.0)


def _formula_flatness_centroid_onset_weighted_v1(
    raw: Mapping[str, Any],
    mapped: Mapping[str, float],
) -> float:
    return _clip01(
        0.50 * _measurement(raw, "spectral_flatness")
        + 0.30 * _measurement(raw, "spectral_centroid_norm")
        + 0.20 * _measurement(raw, "onset_rate_norm")
    )


def _formula_centroid_tension_flatness_weighted_v1(
    raw: Mapping[str, Any],
    mapped: Mapping[str, float],
) -> float:
    if "tension" not in mapped:
        raise ExtractionContractError(
            "recursion_depth requires already mapped canonical tension"
        )
    return _clip01(
        0.50 * _measurement(raw, "spectral_centroid_norm")
        + 0.30 * mapped["tension"]
        + 0.20 * _measurement(raw, "spectral_flatness")
    )


_FORMULA_REGISTRY: dict[str, Callable[..., float]] = {
    "symmetry_bias_identity_clip01": lambda raw, mapped: (
        _formula_identity_clip01(raw, mapped, "symmetry_bias")
    ),
    "dynamic_range_div_30_clip01": _formula_dynamic_range_div_30_clip01,
    "mfcc_variance_identity_clip01": lambda raw, mapped: (
        _formula_identity_clip01(raw, mapped, "mfcc_variance_norm")
    ),
    "harmonic_change_rate_div_2_clip01": (
        _formula_harmonic_change_rate_div_2_clip01
    ),
    "flatness_centroid_onset_weighted_v1": (
        _formula_flatness_centroid_onset_weighted_v1
    ),
    "centroid_tension_flatness_weighted_v1": (
        _formula_centroid_tension_flatness_weighted_v1
    ),
    "section_complexity_identity_clip01": lambda raw, mapped: (
        _formula_identity_clip01(raw, mapped, "section_complexity")
    ),
    "noise_level_identity_clip01": lambda raw, mapped: (
        _formula_identity_clip01(raw, mapped, "noise_level")
    ),
}


def load_config(config_path: Path) -> dict[str, Any]:
    config = _load_json(config_path, "D1 perceptual config")

    if config.get("analysis_config_version") != ANALYSIS_CONFIG_VERSION:
        raise ExtractionContractError("unsupported analysis_config_version")
    if config.get("adapter_name") != ADAPTER_NAME:
        raise ExtractionContractError("unexpected adapter_name in config")
    if config.get("adapter_version") != ADAPTER_VERSION:
        raise ExtractionContractError("unexpected adapter_version in config")
    if tuple(config.get("canonical_axes", ())) != CANONICAL_AXES:
        raise ExtractionContractError(
            "config canonical_axes must match the D1 contract"
        )
    if config.get("rounding") != {
        "mode": "ROUND_HALF_EVEN",
        "decimal_places": 6,
    }:
        raise ExtractionContractError(
            "config rounding policy must be six-place ROUND_HALF_EVEN"
        )
    if config.get("measurement_backend") != MEASUREMENT_BACKEND:
        raise ExtractionContractError(
            "measurement_backend does not match the E1-fix3 implementation contract"
        )

    decoder_policy = config.get("decoder_policy")
    if decoder_policy != {"backend": "ffmpeg", "require_exact_version": True}:
        raise ExtractionContractError("unsupported decoder capability policy")

    mapping = config.get("mapping")
    if not isinstance(mapping, dict) or tuple(mapping) != CANONICAL_AXES:
        raise ExtractionContractError(
            "config mapping must use exactly the canonical D1 axis order"
        )

    for axis in CANONICAL_AXES:
        definition = mapping[axis]
        if not isinstance(definition, dict) or set(definition) != {"formula_id"}:
            raise ExtractionContractError(
                f"mapping for {axis} must contain exactly formula_id"
            )
        formula_id = definition["formula_id"]
        if not isinstance(formula_id, str) or formula_id not in _FORMULA_REGISTRY:
            raise ExtractionContractError(
                f"mapping for {axis} uses an unknown formula_id"
            )

    return config


def _inventory_entry(inventory: Mapping[str, Any], locator: str) -> dict[str, Any]:
    if inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        raise ExtractionContractError("unsupported audio inventory schema_version")
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        raise ExtractionContractError("inventory entries must be a list")

    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("path") == locator
    ]
    if len(matches) != 1:
        raise ExtractionContractError(
            "source locator must match exactly one inventory entry"
        )

    entry = matches[0]
    if set(entry) != {"path", "byte_size", "sha256", "suffix"}:
        raise ExtractionContractError("inventory entry has an unsupported schema")
    return entry


def verify_source_identity(
    *,
    repo_root: Path,
    source_path: Path,
    inventory_path: Path,
) -> dict[str, Any]:
    locator = _canonical_relative_path(repo_root, source_path)
    inventory = _load_json(inventory_path, "audio inventory")
    entry = _inventory_entry(inventory, locator)

    if source_path.suffix.lower() != ".mp3" or entry["suffix"] != ".mp3":
        raise ExtractionContractError(
            "D1 extraction contract accepts only approved .mp3 sources"
        )
    if not isinstance(entry["byte_size"], int) or entry["byte_size"] <= 0:
        raise ExtractionContractError(
            "inventory byte_size must be a positive integer"
        )
    if source_path.stat().st_size != entry["byte_size"]:
        raise ExtractionContractError(
            "source byte_size does not match inventory"
        )

    actual_hash = _sha256_raw_bytes(source_path)
    if actual_hash != entry["sha256"]:
        raise ExtractionContractError(
            "source raw-byte sha256 does not match inventory"
        )

    return {
        "inventory_source_id": f"{INVENTORY_SCHEMA_VERSION}/{actual_hash}",
        "content_sha256": actual_hash,
        "byte_size": entry["byte_size"],
        "suffix": ".mp3",
        "registry_path": locator,
    }


def detect_decoder_capability_backend() -> str:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExtractionContractError(
            "cannot detect ffmpeg decoder capability"
        ) from exc

    if completed.returncode != 0:
        raise ExtractionContractError("ffmpeg decoder capability is unavailable")

    first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
    parts = first_line.split()
    if (
        len(parts) < 3
        or parts[0].lower() != "ffmpeg"
        or parts[1].lower() != "version"
    ):
        raise ExtractionContractError(
            "cannot determine exact ffmpeg capability version"
        )

    return validate_decoder_capability_backend(
        f"ffmpeg/{parts[2]}",
        {"backend": "ffmpeg", "require_exact_version": True},
    )


def validate_decoder_capability_backend(
    value: Any,
    decoder_policy: Mapping[str, Any],
) -> str:
    if not isinstance(value, str) or not _BACKEND_RE.fullmatch(value):
        raise ExtractionContractError("invalid decoder capability backend identity")

    backend, _version = value.split("/", 1)
    if backend != decoder_policy["backend"]:
        raise ExtractionContractError("unexpected decoder capability backend")
    if decoder_policy["require_exact_version"] is not True:
        raise ExtractionContractError("decoder capability policy must require exact version")

    return value


def extract_perceptual(
    raw: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, float]:
    """Apply the approved formula registry in canonical D1 axis order."""
    mapping = config["mapping"]
    mapped: dict[str, float] = {}

    for axis in CANONICAL_AXES:
        formula_id = mapping[axis]["formula_id"]
        handler = _FORMULA_REGISTRY[formula_id]
        mapped[axis] = _round6(handler(raw, mapped))

    return mapped


def build_extraction_result(
    *,
    repo_root: Path,
    source_path: Path,
    inventory_path: Path,
    config_path: Path,
    decoder_detector: Callable[[], str] = detect_decoder_capability_backend,
    analyzer: Callable[[str], Mapping[str, Any]] = analyze_audio_file,
) -> dict[str, Any]:
    source = verify_source_identity(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
    )
    config = load_config(config_path)

    decoder_capability_backend = validate_decoder_capability_backend(
        decoder_detector(),
        config["decoder_policy"],
    )

    raw = analyzer(str(source_path))
    if not isinstance(raw, Mapping):
        raise ExtractionContractError("analyzer must return a mapping")

    perceptual = extract_perceptual(raw, config)
    diagnostics = {
        "duration_sec": _measurement(raw, "duration_sec"),
        "spectral_flatness": _measurement(raw, "spectral_flatness"),
        "spectral_centroid_norm": _measurement(raw, "spectral_centroid_norm"),
        "onset_rate_norm": _measurement(raw, "onset_rate_norm"),
        "dynamic_range": _measurement(raw, "dynamic_range"),
        "harmonic_change_rate_hz": _measurement(
            raw,
            "harmonic_change_rate_hz",
        ),
    }
    provenance = {
        **source,
        "adapter_name": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "analysis_config_version": ANALYSIS_CONFIG_VERSION,
        "decoder_capability_backend": decoder_capability_backend,
        "config_sha256": sha256_prefixed(canonical_json_bytes(config)),
    }
    return {
        "perceptual": perceptual,
        "diagnostics": diagnostics,
        "provenance": provenance,
    }


def canonical_perceptual_bytes(perceptual: Mapping[str, Any]) -> bytes:
    if tuple(perceptual) != CANONICAL_AXES:
        raise ExtractionContractError(
            "perceptual output must use canonical D1 axis order"
        )

    for axis in CANONICAL_AXES:
        value = _finite(axis, perceptual[axis])
        if not 0.0 <= value <= 1.0:
            raise ExtractionContractError(
                f"perceptual axis {axis} is outside [0, 1]"
            )
        if _round6(value) != value:
            raise ExtractionContractError(
                f"perceptual axis {axis} is not rounded to six places"
            )

    return canonical_json_bytes(dict(perceptual))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the D1 canonical perceptual contract."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("corpus/inventory/audio_source_inventory.v1.json"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/d1_perceptual_config.v1.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    source_path = (
        (repo_root / args.source).resolve(strict=True)
        if not args.source.is_absolute()
        else args.source.resolve(strict=True)
    )
    inventory_path = (repo_root / args.inventory).resolve(strict=True)
    config_path = (repo_root / args.config).resolve(strict=True)

    result = build_extraction_result(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
        config_path=config_path,
    )
    print(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())