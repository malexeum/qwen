from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from lib.d1_feature_artifact_io import read_feature_artifact
from tools.render_d1_four_track_fractal_batch import parse_args, run_batch, slugify


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = [
    "08. Monkberry Moon Delight.mp3",
    "12 - Sunny Afternoon.mp3",
    "19 - Picture Book.mp3",
    "Road_Trip.mp3",
]


def test_cli_accepts_user_required_flags_and_aliases(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "render_d1_four_track_fractal_batch.py",
            "--inventory",
            "corpus/inventory/audio_source_inventory.v1.json",
            "--source",
            "08. Monkberry Moon Delight.mp3",
            "12 - Sunny Afternoon.mp3",
            "--source",
            "19 - Picture Book.mp3",
            "Road_Trip.mp3",
            "--output-dir",
            "output/four_track_fractal_posters_v1_run_01",
        ],
    )

    args = parse_args()

    assert args.inventory == Path("corpus/inventory/audio_source_inventory.v1.json")
    assert args.sources == [
        "08. Monkberry Moon Delight.mp3",
        "12 - Sunny Afternoon.mp3",
        "19 - Picture Book.mp3",
        "Road_Trip.mp3",
    ]
    assert args.output == Path("output/four_track_fractal_posters_v1_run_01")


def test_batch_writes_valid_canonical_outputs_for_four_sources(tmp_path: Path):
    output_dir = tmp_path / "fractal_batch"
    manifest = run_batch(
        repo_root=REPO_ROOT,
        inventory_path=REPO_ROOT / "corpus/inventory/audio_source_inventory.v1.json",
        config_path=REPO_ROOT / "configs/d1_perceptual_config.v1.json",
        output_dir=output_dir,
        source_names=DEFAULT_SOURCES,
    )

    assert manifest["schema_version"] == "d1_four_track_batch/v1"
    assert manifest["source_count"] == 4
    assert (output_dir / "batch_manifest.json").is_file()

    for source_name in DEFAULT_SOURCES:
        expected_dir_name = slugify(Path(source_name).stem)
        source_dir = output_dir / expected_dir_name

        artifact_path = source_dir / "features" / "d1_rock_v1.json"
        svg_path = source_dir / "poster.fractal.svg"
        metadata_path = source_dir / "poster.fractal.metadata.json"
        diagnostics_path = source_dir / "diagnostics.json"

        assert artifact_path.is_file()
        assert svg_path.is_file()
        assert metadata_path.is_file()
        assert diagnostics_path.is_file()

        artifact = read_feature_artifact(artifact_path)
        assert artifact.schema_version == "d1_feature_artifact/v2"
        assert artifact.source_locator["registry_path"].endswith(f"/{source_name}")
        assert artifact.semantic_payload()["schema_version"] == "d1_feature_artifact/v2"

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["artifact"]["source_title"].upper().endswith(Path(source_name).name.upper())
        assert svg_path.read_bytes().startswith(b"<?xml")
        assert diagnostics_path.read_bytes().startswith(b"{")


def test_batch_rejects_non_empty_output_directory(tmp_path: Path):
    output_dir = tmp_path / "fractal_batch"
    output_dir.mkdir()
    (output_dir / "placeholder.txt").write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError, match="must be empty"):
        run_batch(
            repo_root=REPO_ROOT,
            inventory_path=REPO_ROOT / "corpus/inventory/audio_source_inventory.v1.json",
            config_path=REPO_ROOT / "configs/d1_perceptual_config.v1.json",
            output_dir=output_dir,
            source_names=DEFAULT_SOURCES,
        )

    assert (output_dir / "placeholder.txt").is_file()
