from __future__ import annotations

import argparse
import hashlib
import json
import math
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
        raise ExtractionContractError("source path resolves outside repository root") from exc


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionContractError(f"cannot load {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ExtractionContractError(f"{label} must be a JSON object")
    return payload


def load_config(config_path: Path) -> dict[str, Any]:
    config = _load_json(config_path, "D1 perceptual config")
    if config.get("analysis_config_version") != ANALYSIS_CONFIG_VERSION:
        raise ExtractionContractError("unsupported analysis_config_version")
    if config.get("adapter_name") != ADAPTER_NAME:
        raise ExtractionContractError("unexpected adapter_name in config")
    if config.get("adapter_version") != ADAPTER_VERSION:
        raise ExtractionContractError("unexpected adapter_version in config")
    if tuple(config.get("canonical_axes", ())) != CANONICAL_AXES:
        raise ExtractionContractError("config canonical_axes must match the D1 contract")
    if config.get("rounding") != {"mode": "ROUND_HALF_EVEN", "decimal_places": 6}:
        raise ExtractionContractError("config rounding policy must be six-place ROUND_HALF_EVEN")
    mapping = config.get("mapping")
    if not isinstance(mapping, dict) or set(mapping) != set(CANONICAL_AXES):
        raise ExtractionContractError("config mapping must define exactly the eight D1 axes")
    return config


def _inventory_entry(inventory: Mapping[str, Any], locator: str) -> dict[str, Any]:
    if inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        raise ExtractionContractError("unsupported audio inventory schema_version")
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        raise ExtractionContractError("inventory entries must be a list")
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == locator]
    if len(matches) != 1:
        raise ExtractionContractError("source locator must match exactly one inventory entry")
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
        raise ExtractionContractError("D1 extraction contract accepts only approved .mp3 sources")
    if not isinstance(entry["byte_size"], int) or entry["byte_size"] <= 0:
        raise ExtractionContractError("inventory byte_size must be a positive integer")
    if source_path.stat().st_size != entry["byte_size"]:
        raise ExtractionContractError("source byte_size does not match inventory")

    actual_hash = _sha256_raw_bytes(source_path)
    if actual_hash != entry["sha256"]:
        raise ExtractionContractError("source raw-byte sha256 does not match inventory")

    return {
        "inventory_source_id": f"{INVENTORY_SCHEMA_VERSION}/{actual_hash}",
        "content_sha256": actual_hash,
        "byte_size": entry["byte_size"],
        "suffix": ".mp3",
        "registry_path": locator,
    }


def detect_decoder_backend() -> str:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExtractionContractError("cannot detect ffmpeg decoder backend") from exc
    if completed.returncode != 0:
        raise ExtractionContractError("ffmpeg decoder backend is unavailable")
    first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
    parts = first_line.split()
    if len(parts) < 3 or parts[0].lower() != "ffmpeg" or parts[1].lower() != "version":
        raise ExtractionContractError("cannot determine exact ffmpeg decoder version")
    version = parts[2]
    if not version or any(character.isspace() for character in version):
        raise ExtractionContractError("invalid ffmpeg decoder version")
    return f"ffmpeg/{version}"


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExtractionContractError(f"measurement {name} must be a finite real number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ExtractionContractError(f"measurement {name} must be finite")
    return numeric


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _round6(value: float) -> float:
    return float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN))


def _measurement(raw: Mapping[str, Any], name: str) -> float:
    if name not in raw:
        raise ExtractionContractError(f"missing required measurement: {name}")
    return _finite(name, raw[name])


def extract_perceptual(raw: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, float]:
    """Map raw E1-fix3 measurements to the eight D1 canonical perceptual axes."""
    load_config_payload = dict(config)
    if tuple(load_config_payload.get("canonical_axes", ())) != CANONICAL_AXES:
        raise ExtractionContractError("invalid D1 extraction config")

    symmetry_bias = _measurement(raw, "symmetry_bias")
    dynamic_range = _measurement(raw, "dynamic_range")
    mfcc_variance_norm = _measurement(raw, "mfcc_variance_norm")
    harmonic_change_rate_hz = _measurement(raw, "harmonic_change_rate_hz")
    spectral_flatness = _measurement(raw, "spectral_flatness")
    spectral_centroid_norm = _measurement(raw, "spectral_centroid_norm")
    onset_rate_norm = _measurement(raw, "onset_rate_norm")
    section_complexity = _measurement(raw, "section_complexity")
    noise_level = _measurement(raw, "noise_level")

    tension = _clip01(dynamic_range / 30.0)
    values = {
        "symmetry_bias": _clip01(symmetry_bias),
        "tension": tension,
        "harmonic_stability": _clip01(mfcc_variance_norm),
        "harmonic_change_rate": _clip01(harmonic_change_rate_hz / 2.0),
        "texture_complexity": _clip01(
            0.50 * spectral_flatness
            + 0.30 * spectral_centroid_norm
            + 0.20 * onset_rate_norm
        ),
        "recursion_depth": _clip01(
            0.50 * spectral_centroid_norm
            + 0.30 * tension
            + 0.20 * spectral_flatness
        ),
        "section_complexity": _clip01(section_complexity),
        "noise_level": _clip01(noise_level),
    }
    return {axis: _round6(values[axis]) for axis in CANONICAL_AXES}


def build_extraction_result(
    *,
    repo_root: Path,
    source_path: Path,
    inventory_path: Path,
    config_path: Path,
    decoder_detector: Callable[[], str] = detect_decoder_backend,
    analyzer: Callable[[str], Mapping[str, Any]] = analyze_audio_file,
) -> dict[str, Any]:
    source = verify_source_identity(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
    )
    config = load_config(config_path)
    decoder_backend = decoder_detector()
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
        "harmonic_change_rate_hz": _measurement(raw, "harmonic_change_rate_hz"),
    }
    provenance = {
        **source,
        "adapter_name": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "analysis_config_version": ANALYSIS_CONFIG_VERSION,
        "decoder_backend": decoder_backend,
        "config_sha256": sha256_prefixed(canonical_json_bytes(config)),
    }
    return {
        "perceptual": perceptual,
        "diagnostics": diagnostics,
        "provenance": provenance,
    }


def canonical_perceptual_bytes(perceptual: Mapping[str, Any]) -> bytes:
    if tuple(perceptual) != CANONICAL_AXES:
        raise ExtractionContractError("perceptual output must use canonical D1 axis order")
    for axis in CANONICAL_AXES:
        value = _finite(axis, perceptual[axis])
        if not 0.0 <= value <= 1.0:
            raise ExtractionContractError(f"perceptual axis {axis} is outside [0, 1]")
        if _round6(value) != value:
            raise ExtractionContractError(f"perceptual axis {axis} is not rounded to six places")
    return canonical_json_bytes(dict(perceptual))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract the D1 canonical perceptual contract.")
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
    source_path = (repo_root / args.source).resolve(strict=True) if not args.source.is_absolute() else args.source.resolve(strict=True)
    inventory_path = (repo_root / args.inventory).resolve(strict=True)
    config_path = (repo_root / args.config).resolve(strict=True)
    result = build_extraction_result(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
        config_path=config_path,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
