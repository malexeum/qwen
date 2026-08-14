from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.d1_extract as extractor


EXPECTED_MEASUREMENT_BACKEND = {
    "module": "lib.audio_analysis.analysis",
    "function": "analyze_audio_file",
    "implementation_contract": "e1_fix3_fixed_44100hz_mono_nfft2048_hop512",
}

EXPECTED_FORMULA_IDS = {
    "symmetry_bias": "symmetry_bias_identity_clip01",
    "tension": "dynamic_range_div_30_clip01",
    "harmonic_stability": "mfcc_variance_identity_clip01",
    "harmonic_change_rate": "harmonic_change_rate_div_2_clip01",
    "texture_complexity": "flatness_centroid_onset_weighted_v1",
    "recursion_depth": "centroid_tension_flatness_weighted_v1",
    "section_complexity": "section_complexity_identity_clip01",
    "noise_level": "noise_level_identity_clip01",
}

RAW = {
    "duration_sec": 12.5,
    "symmetry_bias": 0.8123456,
    "dynamic_range": 12.345678,
    "mfcc_variance_norm": 0.3456789,
    "harmonic_change_rate_hz": 0.9876543,
    "spectral_flatness": 0.2345678,
    "spectral_centroid_norm": 0.4567891,
    "onset_rate_norm": 0.6789123,
    "section_complexity": 0.5678912,
    "noise_level": 0.1234567,
}


def valid_config() -> dict:
    return {
        "adapter_name": extractor.ADAPTER_NAME,
        "adapter_version": extractor.ADAPTER_VERSION,
        "analysis_config_version": extractor.ANALYSIS_CONFIG_VERSION,
        "canonical_axes": list(extractor.CANONICAL_AXES),
        "decoder_policy": {
            "backend": "ffmpeg",
            "require_exact_version": True,
        },
        "measurement_backend": dict(EXPECTED_MEASUREMENT_BACKEND),
        "mapping": {
            axis: {"formula_id": formula_id}
            for axis, formula_id in EXPECTED_FORMULA_IDS.items()
        },
        "rounding": {
            "mode": "ROUND_HALF_EVEN",
            "decimal_places": 6,
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def committed_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "d1_perceptual_config.v1.json"
    )


def approved_source(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    source_dir = repo_root / "corpus" / "audio"
    source_dir.mkdir(parents=True)

    source_path = source_dir / "approved.mp3"
    source_path.write_bytes(b"synthetic-approved-d1-source")

    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    inventory_path = repo_root / "inventory.json"
    write_json(
        inventory_path,
        {
            "schema_version": extractor.INVENTORY_SCHEMA_VERSION,
            "entries": [
                {
                    "path": "corpus/audio/approved.mp3",
                    "byte_size": source_path.stat().st_size,
                    "sha256": f"sha256:{source_hash}",
                    "suffix": ".mp3",
                }
            ],
        },
    )

    config_path = repo_root / "config.json"
    write_json(config_path, valid_config())

    return repo_root, source_path, inventory_path, config_path


def test_production_measurement_backend_matches_independent_contract():
    assert extractor.MEASUREMENT_BACKEND == EXPECTED_MEASUREMENT_BACKEND


def test_committed_config_loads_successfully():
    config = extractor.load_config(committed_config_path())

    assert tuple(config["canonical_axes"]) == extractor.CANONICAL_AXES
    assert config["measurement_backend"] == EXPECTED_MEASUREMENT_BACKEND
    assert config["rounding"] == {
        "mode": "ROUND_HALF_EVEN",
        "decimal_places": 6,
    }


def test_committed_config_uses_exact_approved_formula_ids():
    config = extractor.load_config(committed_config_path())

    assert tuple(config["mapping"]) == extractor.CANONICAL_AXES
    assert {
        axis: config["mapping"][axis]["formula_id"]
        for axis in extractor.CANONICAL_AXES
    } == EXPECTED_FORMULA_IDS


def test_extract_perceptual_has_exactly_eight_axes_in_fixed_order():
    perceptual = extractor.extract_perceptual(RAW, valid_config())

    assert tuple(perceptual) == extractor.CANONICAL_AXES
    assert len(perceptual) == 8
    assert all(0.0 <= value <= 1.0 for value in perceptual.values())


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (0.1234565, 0.123456),
        (0.1234575, 0.123458),
    ],
)
def test_symmetry_bias_uses_decimal_round_half_even(raw_value, expected):
    raw = dict(RAW)
    raw["symmetry_bias"] = raw_value

    perceptual = extractor.extract_perceptual(raw, valid_config())

    assert perceptual["symmetry_bias"] == expected


def test_identical_measurements_produce_byte_identical_canonical_output():
    first = extractor.extract_perceptual(RAW, valid_config())
    second = extractor.extract_perceptual(dict(RAW), valid_config())

    assert first == second
    assert extractor.canonical_perceptual_bytes(first) == (
        extractor.canonical_perceptual_bytes(second)
    )


def test_recursion_depth_consumes_already_mapped_canonical_tension():
    raw = dict(RAW)
    raw["dynamic_range"] = 30.0

    perceptual = extractor.extract_perceptual(raw, valid_config())

    expected = extractor._round6(
        extractor._clip01(
            0.50 * raw["spectral_centroid_norm"]
            + 0.30 * perceptual["tension"]
            + 0.20 * raw["spectral_flatness"]
        )
    )

    assert perceptual["tension"] == 1.0
    assert perceptual["recursion_depth"] == expected


def test_formula_dispatch_changes_only_declared_axis(monkeypatch):
    baseline = extractor.extract_perceptual(RAW, valid_config())

    monkeypatch.setitem(
        extractor._FORMULA_REGISTRY,
        "test_zero_noise_level",
        lambda measurements, mapped: 0.0,
    )

    config = valid_config()
    config["mapping"]["noise_level"] = {
        "formula_id": "test_zero_noise_level",
    }
    changed = extractor.extract_perceptual(RAW, config)

    assert changed["noise_level"] == 0.0
    assert changed["noise_level"] != baseline["noise_level"]

    for axis in extractor.CANONICAL_AXES:
        if axis != "noise_level":
            assert changed[axis] == baseline[axis]


def test_production_validation_rejects_test_only_formula_id(tmp_path):
    config_path = tmp_path / "config.json"
    config = valid_config()
    config["mapping"]["noise_level"] = {
        "formula_id": "test_zero_noise_level",
    }
    write_json(config_path, config)

    with pytest.raises(extractor.ExtractionContractError, match="formula_id"):
        extractor.load_config(config_path)


def test_load_config_rejects_unknown_formula_id(tmp_path):
    config_path = tmp_path / "config.json"
    config = valid_config()
    config["mapping"]["noise_level"] = {
        "formula_id": "unknown_formula_id",
    }
    write_json(config_path, config)

    with pytest.raises(extractor.ExtractionContractError, match="formula_id"):
        extractor.load_config(config_path)


def test_load_config_rejects_invalid_measurement_backend_contract(tmp_path):
    config_path = tmp_path / "config.json"
    config = valid_config()
    config["measurement_backend"]["implementation_contract"] = "unapproved"
    write_json(config_path, config)

    with pytest.raises(
        extractor.ExtractionContractError,
        match="measurement_backend",
    ):
        extractor.load_config(config_path)


@pytest.mark.parametrize(
    "decoder_identity",
    [
        "libmpg123/1.32.0",
        "ffmpeg/unknown version",
        "not-a-decoder",
    ],
)
def test_invalid_decoder_capability_identity_fails_closed(
    tmp_path,
    decoder_identity,
):
    repo_root, source_path, inventory_path, config_path = approved_source(tmp_path)

    with pytest.raises(extractor.ExtractionContractError, match="decoder"):
        extractor.build_extraction_result(
            repo_root=repo_root,
            source_path=source_path,
            inventory_path=inventory_path,
            config_path=config_path,
            decoder_detector=lambda: decoder_identity,
            analyzer=lambda _: RAW,
        )


def test_source_sha_mismatch_fails_before_decoder_or_analyzer_invocation(tmp_path):
    repo_root, source_path, inventory_path, config_path = approved_source(tmp_path)
    source_path.write_bytes(b"synthetic-modified-d1-source")

    calls = {
        "decoder": 0,
        "analyzer": 0,
    }

    def decoder_detector() -> str:
        calls["decoder"] += 1
        return "ffmpeg/7.1"

    def analyzer(_: str) -> dict:
        calls["analyzer"] += 1
        return RAW

    with pytest.raises(extractor.ExtractionContractError, match="sha256"):
        extractor.build_extraction_result(
            repo_root=repo_root,
            source_path=source_path,
            inventory_path=inventory_path,
            config_path=config_path,
            decoder_detector=decoder_detector,
            analyzer=analyzer,
        )

    assert calls == {
        "decoder": 0,
        "analyzer": 0,
    }


def test_inventory_mismatch_fails_before_decoder_or_analyzer_invocation(tmp_path):
    repo_root, source_path, inventory_path, config_path = approved_source(tmp_path)

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["entries"][0]["path"] = "corpus/audio/not-approved.mp3"
    write_json(inventory_path, inventory)

    calls = {
        "decoder": 0,
        "analyzer": 0,
    }

    def decoder_detector() -> str:
        calls["decoder"] += 1
        return "ffmpeg/7.1"

    def analyzer(_: str) -> dict:
        calls["analyzer"] += 1
        return RAW

    with pytest.raises(extractor.ExtractionContractError, match="inventory"):
        extractor.build_extraction_result(
            repo_root=repo_root,
            source_path=source_path,
            inventory_path=inventory_path,
            config_path=config_path,
            decoder_detector=decoder_detector,
            analyzer=analyzer,
        )

    assert calls == {
        "decoder": 0,
        "analyzer": 0,
    }


def test_diagnostics_are_not_perceptual_axes_or_canonical_perceptual_bytes(
    tmp_path,
):
    repo_root, source_path, inventory_path, config_path = approved_source(tmp_path)

    result = extractor.build_extraction_result(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
        config_path=config_path,
        decoder_detector=lambda: "ffmpeg/7.1",
        analyzer=lambda _: RAW,
    )

    perceptual = result["perceptual"]
    diagnostics = result["diagnostics"]

    assert tuple(perceptual) == extractor.CANONICAL_AXES
    assert "duration_sec" not in perceptual
    assert diagnostics["duration_sec"] == RAW["duration_sec"]

    canonical_bytes = extractor.canonical_perceptual_bytes(perceptual)
    assert b"duration_sec" not in canonical_bytes
    assert b"dynamic_range" not in canonical_bytes


def test_provenance_uses_decoder_capability_backend_not_decoder_backend(tmp_path):
    repo_root, source_path, inventory_path, config_path = approved_source(tmp_path)

    result = extractor.build_extraction_result(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
        config_path=config_path,
        decoder_detector=lambda: "ffmpeg/7.1",
        analyzer=lambda _: RAW,
    )

    provenance = result["provenance"]
    assert provenance["decoder_capability_backend"] == "ffmpeg/7.1"
    assert "decoder_backend" not in provenance


def test_invalid_measurement_fails_closed_without_real_audio_execution():
    raw = dict(RAW)
    raw["noise_level"] = float("nan")

    with pytest.raises(extractor.ExtractionContractError, match="finite"):
        extractor.extract_perceptual(raw, valid_config())