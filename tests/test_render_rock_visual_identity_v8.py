from __future__ import annotations

import json
from pathlib import Path

from lib.d1_feature_artifact_io import read_feature_artifact
from tools.render_rock_visual_identity_v8_batch import run_batch

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = [
    "08. Monkberry Moon Delight.mp3",
    "12 - Sunny Afternoon.mp3",
    "19 - Picture Book.mp3",
    "Road_Trip.mp3",
]


def test_v8_batch_generates_four_canonical_outputs(tmp_path: Path):
    output_dir = tmp_path / "v8_batch"
    manifest = run_batch(
        repo_root=REPO_ROOT,
        inventory_path=REPO_ROOT / "corpus/inventory/audio_source_inventory.v1.json",
        config_path=REPO_ROOT / "configs/d1_perceptual_config.v1.json",
        output_dir=output_dir,
        source_names=DEFAULT_SOURCES,
    )

    assert manifest["schema_version"] == "rock_visual_identity_v8_batch/v1"
    assert manifest["source_count"] == 4
    assert (output_dir / "batch_manifest.json").is_file()

    for source_name in DEFAULT_SOURCES:
        source_dir = output_dir / source_name.replace(".mp3", "").replace(" ", "_").replace("-", "_")
        artifact_path = source_dir / "features" / "d1_rock_v1.json"
        svg_path = source_dir / "poster.rock_visual_identity_v8.svg"
        metadata_path = source_dir / "poster.rock_visual_identity_v8.metadata.json"
        diagnostics_path = source_dir / "diagnostics.json"

        assert artifact_path.is_file()
        assert svg_path.is_file()
        assert metadata_path.is_file()
        assert diagnostics_path.is_file()

        artifact = read_feature_artifact(artifact_path)
        assert artifact.schema_version == "d1_feature_artifact/v2"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["renderer"]["name"] == "rock_visual_identity_v8"
        assert svg_path.read_bytes().startswith(b"<svg")

        assert metadata["resolved_visual_parameters"]["composition_mode"] in {"monolithic", "kinetic_break", "recursive_grove", "fragmented_signal"}
