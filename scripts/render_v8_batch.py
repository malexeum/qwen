from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.d1_feature_artifact_io import write_feature_artifact
from lib.d1_feature_artifacts import SCHEMA_V2, build_d1_feature_artifact
from lib.style_engine.musical_portrait import build_musical_portrait
from lib.style_engine.rock_composition_v8 import portrait_hash, resolve_rock_composition_v8
from tools.render_d1_rock_fractal_poster import write_canonical_outputs


SOURCES = (
    "08. Monkberry Moon Delight.music_features_v2.json",
    "12 - Sunny Afternoon.music_features_v2.json",
    "19 - Picture Book.music_features_v2.json",
    "Road_Trip.music_features_v2.json",
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if len(value) == 40 else "0" * 40


def _build_d1_artifact(source: dict, portrait: dict, bridge: dict):
    audio_hash = source["artifact"]["audio_content_hash"]
    source_name = f"tests/audio/{source['artifact']['track_id']}.mp3"
    source_path = REPO_ROOT / source_name
    identity = {
        "kind": "audio_file",
        "inventory_source_id": f"audio_source_inventory/v1/{audio_hash}",
        "content_sha256": audio_hash,
        "byte_size": source_path.stat().st_size,
        "suffix": ".mp3",
        "adapter_name": "music_features_v2_extractor",
        "adapter_version": "2.0.0",
        "analysis_config_version": "music_features_v2/v2.0.0",
        "decoder_backend": "ffmpeg/7.1",
    }
    return build_d1_feature_artifact(
        analysis_id="d1_rock_v1",
        source_identity=identity,
        perceptual=bridge["d1_perceptual"],
        git_sha=_git_sha(),
        schema_version=SCHEMA_V2,
        source_locator={"registry_path": source_name},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render MusicalPortraitV1 through the canonical V7 D1 fractal poster renderer.")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "output" / "v8_milestone")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    feature_root = REPO_ROOT / "tests" / "fixtures" / "music_features_v2"
    manifest_entries = []

    for feature_name in SOURCES:
        source = json.loads((feature_root / feature_name).read_text(encoding="utf-8"))
        features = dict(source["features"])
        features["artifact"] = source["artifact"]
        portrait = build_musical_portrait(features)
        bridge, bridge_trace = resolve_rock_composition_v8(portrait)
        artifact = _build_d1_artifact(source, portrait, bridge)

        stem = feature_name.removesuffix(".music_features_v2.json")
        track_dir = output / "v7_d1" / stem.replace("/", "_")
        track_dir.mkdir(parents=True, exist_ok=True)
        write_feature_artifact(track_dir, artifact)
        artifact_path = track_dir / "features" / "d1_rock_v1.json"
        svg_path = track_dir / "poster.v8.d1.svg"
        metadata_path = track_dir / "poster.v8.d1.metadata.json"
        # богащаем bridge осями BPM, Skewness и Dynamic Range
        bridge["bpm"] = float(features.get("pulse", {}).get("bpm", 120.0) or 120.0)
        bridge["spectral_skewness"] = float(features.get("spectral", {}).get("skewness", 0.5) or 0.5)
        bridge["dynamic_range"] = float(features.get("dynamics", {}).get("dynamic_range", 0.5) or 0.5)

        write_canonical_outputs(
            artifact_path=artifact_path,
            svg_path=svg_path,
            metadata_path=metadata_path,
            bridge_params=bridge,
        )

        provenance = {
            "schema": "rock_composition_grammar_v8_provenance/v2",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "track_id": source["artifact"]["track_id"],
            "dominant_mode": bridge["dominant_mode"],
            "audio_content_hash": source["artifact"]["audio_content_hash"],
            "feature_hash": source["artifact"]["feature_hash"],
            "portrait_hash": portrait_hash(portrait),
            "bridge_params": bridge,
            "bridge_trace": bridge_trace,
            "d1_artifact_feature_sha256": artifact.feature_sha256,
            "renderer": {"name": "d1_rock_fractal_poster_renderer", "version": "7"},
            "rendered_visual_sha256": _sha256_file(svg_path),
            "passport": {
                "track_id": source["artifact"]["track_id"],
                "dominant_mode": bridge["dominant_mode"],
                "portrait_hash_short": portrait_hash(portrait).removeprefix("sha256:")[:12],
                "bpm": features.get("pulse", {}).get("bpm", "n/a"),
                "drive": bridge["drive"],
                "tension": bridge["tension"],
                "grain": bridge["grain"],
            },
            "source_feature_artifact": feature_name,
        }
        provenance_path = track_dir / "provenance.v2.json"
        provenance_path.write_bytes(_json_bytes(provenance))
        manifest_entries.append({
            "track_id": provenance["track_id"],
            "dominant_mode": provenance["dominant_mode"],
            "renderer": provenance["renderer"],
            "visual": str(svg_path.relative_to(REPO_ROOT)),
            "provenance": str(provenance_path.relative_to(REPO_ROOT)),
            "visual_sha256": provenance["rendered_visual_sha256"],
        })
        print(f"{provenance['track_id']}: {provenance['dominant_mode']} -> {svg_path}")

    (output / "manifest_v8.json").write_bytes(_json_bytes({
        "schema": "rock_composition_grammar_v8_batch/v2",
        "count": len(manifest_entries),
        "renderer": "d1_rock_fractal_poster_renderer/v7",
        "entries": manifest_entries,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


