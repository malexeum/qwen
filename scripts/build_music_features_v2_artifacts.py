from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.audio_features.music_features_v2_extractor import build_music_features_v2_artifact
from lib.style_engine.musical_portrait import build_musical_portrait


DEFAULT_SOURCES = ("08. Monkberry Moon Delight.mp3", "12 - Sunny Afternoon.mp3", "19 - Picture Book.mp3", "Road_Trip.mp3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MusicFeaturesV2 artifacts for four real test tracks.")
    parser.add_argument("sources", nargs="*", default=list(DEFAULT_SOURCES))
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "tests" / "fixtures" / "music_features_v2")
    parser.add_argument("--preview", action="store_true", help="print a compact MusicalPortraitV1 sanity table")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if len(args.sources) != 4:
        raise SystemExit("exactly four source tracks are required")
    output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_rows = []
    for source_name in args.sources:
        source = REPO_ROOT / "tests" / "audio" / source_name
        artifact = build_music_features_v2_artifact(source)
        output_path = output_dir / f"{source.stem}.music_features_v2.json"
        output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{output_path} feature_hash={artifact['artifact']['feature_hash']} synthetic={artifact['artifact']['synthetic_fixture']}")
        if args.preview:
            portrait = build_musical_portrait(artifact["features"] | {"artifact": {"track_id": artifact["artifact"]["track_id"], "feature_hash": artifact["artifact"]["feature_hash"]}})
            profiles = portrait["profiles"]
            preview_rows.append((
                artifact["artifact"]["track_id"],
                portrait["identity_core"]["dominant_interpretation_mode"],
                profiles["pulse_profile"]["drive"],
                profiles["form_profile"]["structural_clarity"],
                profiles["material_profile"]["grain"],
                profiles["affect_profile"]["tension"],
                profiles["spatial_profile"]["resonance"],
            ))
    if args.preview:
        print("track_id mode pulse.drive form.clarity material.grain affect.tension spatial.resonance")
        for row in preview_rows:
            print(row[0], row[1], *(f"{value:.3f}" if isinstance(value, float) else value for value in row[2:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())