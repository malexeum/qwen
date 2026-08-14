import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "d1_extract.py"
SPEC = importlib.util.spec_from_file_location("d1_extract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


RAW = {
    "duration_sec": 12.5,
    "symmetry_bias": 0.8123456,
    "dynamic_range": 12.345678,
    "mfcc_variance_norm": 0.3456789,
    "harmonic_change_rate_hz": 0.7654321,
    "spectral_flatness": 0.2345678,
    "spectral_centroid_norm": 0.4567891,
    "onset_rate_norm": 0.5678912,
    "section_complexity": 0.6789123,
    "noise_level": 0.7891234,
}


def write_config(path: Path, *, version: str = extractor.ANALYSIS_CONFIG_VERSION):
    payload = {
        "adapter_name": extractor.ADAPTER_NAME,
        "adapter_version": extractor.ADAPTER_VERSION,
        "analysis_config_version": version,
        "canonical_axes": list(extractor.CANONICAL_AXES),
        "rounding": {"mode": "ROUND_HALF_EVEN", "decimal_places": 6},
        "mapping": {axis: {"formula": axis} for axis in extractor.CANONICAL_AXES},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_inventory(path: Path, *, locator: str, byte_size: int, sha256: str):
    payload = {
        "schema_version": extractor.INVENTORY_SCHEMA_VERSION,
        "root": "tests/audio",
        "entries": [
            {
                "path": locator,
                "byte_size": byte_size,
                "sha256": sha256,
                "suffix": ".mp3",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def approved_source(tmp_path: Path):
    repo_root = tmp_path / "repo"
    source = repo_root / "tests" / "audio" / "fixture.mp3"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"approved synthetic MP3 bytes")
    locator = "tests/audio/fixture.mp3"
    source_hash = extractor._sha256_raw_bytes(source)
    inventory_path = repo_root / "inventory.json"
    config_path = repo_root / "config.json"
    write_inventory(
        inventory_path,
        locator=locator,
        byte_size=source.stat().st_size,
        sha256=source_hash,
    )
    write_config(config_path)
    return repo_root, source, inventory_path, config_path


def test_extract_perceptual_has_exactly_eight_axes_and_fixed_rounding():
    config = {
        "canonical_axes": list(extractor.CANONICAL_AXES),
        "mapping": {axis: {} for axis in extractor.CANONICAL_AXES},
    }
    perceptual = extractor.extract_perceptual(RAW, config)

    assert tuple(perceptual) == extractor.CANONICAL_AXES
    assert len(perceptual) == 8
    assert all(0.0 <= value <= 1.0 for value in perceptual.values())
    assert extractor.canonical_perceptual_bytes(perceptual)
    assert perceptual["symmetry_bias"] == 0.812346
    assert perceptual["tension"] == 0.411523


def test_identical_measurements_produce_byte_identical_output():
    config = {
        "canonical_axes": list(extractor.CANONICAL_AXES),
        "mapping": {axis: {} for axis in extractor.CANONICAL_AXES},
    }
    first = extractor.extract_perceptual(RAW, config)
    second = extractor.extract_perceptual(dict(reversed(list(RAW.items()))), config)
    assert extractor.canonical_perceptual_bytes(first) == extractor.canonical_perceptual_bytes(second)


def test_source_identity_is_verified_before_decoder_or_analyzer(tmp_path):
    repo_root, source, inventory_path, config_path = approved_source(tmp_path)
    source.write_bytes(b"tampered bytes")
    calls = {"decoder": 0, "analyzer": 0}

    def decoder():
        calls["decoder"] += 1
        return "ffmpeg/7.1"

    def analyzer(_: str):
        calls["analyzer"] += 1
        return RAW

    with pytest.raises(
        extractor.ExtractionContractError,
        match="byte_size|sha256",
    ):
        extractor.build_extraction_result(
            repo_root=repo_root,
            source_path=source,
            inventory_path=inventory_path,
            config_path=config_path,
            decoder_detector=decoder,
            analyzer=analyzer,
        )

    assert calls == {"decoder": 0, "analyzer": 0}


@pytest.mark.parametrize("field,value", [("byte_size", 1), ("suffix", ".wav")])
def test_source_preflight_rejects_inventory_mismatch(tmp_path, field, value):
    repo_root, source, inventory_path, _ = approved_source(tmp_path)
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    payload["entries"][0][field] = value
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(extractor.ExtractionContractError):
        extractor.verify_source_identity(
            repo_root=repo_root,
            source_path=source,
            inventory_path=inventory_path,
        )


def test_extraction_separates_diagnostics_from_perceptual_and_records_provenance(tmp_path):
    repo_root, source, inventory_path, config_path = approved_source(tmp_path)
    result = extractor.build_extraction_result(
        repo_root=repo_root,
        source_path=source,
        inventory_path=inventory_path,
        config_path=config_path,
        decoder_detector=lambda: "ffmpeg/7.1",
        analyzer=lambda _: RAW,
    )

    assert tuple(result["perceptual"]) == extractor.CANONICAL_AXES
    assert "spectral_flatness" not in result["perceptual"]
    assert result["diagnostics"]["spectral_flatness"] == RAW["spectral_flatness"]
    assert result["provenance"]["adapter_name"] == "d1_perceptual_extractor"
    assert result["provenance"]["adapter_version"] == "1.0.0"
    assert result["provenance"]["analysis_config_version"] == "d1_perceptual_config/v1"
    assert result["provenance"]["decoder_backend"] == "ffmpeg/7.1"
    assert result["provenance"]["inventory_source_id"].startswith(
        "audio_source_inventory/v1/sha256:"
    )


def test_unknown_decoder_identity_fails_closed(tmp_path):
    repo_root, source, inventory_path, config_path = approved_source(tmp_path)

    with pytest.raises(extractor.ExtractionContractError, match="decoder"):
        extractor.build_extraction_result(
            repo_root=repo_root,
            source_path=source,
            inventory_path=inventory_path,
            config_path=config_path,
            decoder_detector=lambda: (_ for _ in ()).throw(
                extractor.ExtractionContractError("cannot detect ffmpeg decoder backend")
            ),
            analyzer=lambda _: RAW,
        )


def test_invalid_measurement_fails_closed():
    config = {
        "canonical_axes": list(extractor.CANONICAL_AXES),
        "mapping": {axis: {} for axis in extractor.CANONICAL_AXES},
    }
    raw = dict(RAW)
    raw["noise_level"] = float("nan")
    with pytest.raises(extractor.ExtractionContractError, match="finite"):
        extractor.extract_perceptual(raw, config)


def test_config_version_is_part_of_provenance_identity(tmp_path):
    repo_root, source, inventory_path, config_path = approved_source(tmp_path)
    first = extractor.build_extraction_result(
        repo_root=repo_root,
        source_path=source,
        inventory_path=inventory_path,
        config_path=config_path,
        decoder_detector=lambda: "ffmpeg/7.1",
        analyzer=lambda _: RAW,
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["mapping"]["noise_level"]["formula"] = "changed"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    second = extractor.build_extraction_result(
        repo_root=repo_root,
        source_path=source,
        inventory_path=inventory_path,
        config_path=config_path,
        decoder_detector=lambda: "ffmpeg/7.1",
        analyzer=lambda _: RAW,
    )
    assert first["provenance"]["config_sha256"] != second["provenance"]["config_sha256"]
    assert first["perceptual"] == second["perceptual"]
