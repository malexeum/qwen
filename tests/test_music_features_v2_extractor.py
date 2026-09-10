from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.audio_features.music_features_v2_extractor import build_music_features_v2_artifact, extract_music_features_v2
from lib.audio_features.music_features_v2_schema import FEATURE_GROUPS


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["08. Monkberry Moon Delight.mp3", "12 - Sunny Afternoon.mp3", "19 - Picture Book.mp3", "Road_Trip.mp3"]


def test_real_four_track_extraction_matches_v2_shape_and_bounds():
    for source_name in SOURCES:
        features = extract_music_features_v2(ROOT / "tests" / "audio" / source_name)
        assert set(features) == set(FEATURE_GROUPS)
        for group, names in FEATURE_GROUPS.items():
            assert set(features[group]) == set(names)
            for name, value in features[group].items():
                if group == "pulse" and name == "bpm":
                    assert 0.0 <= value <= 220.0
                elif group == "form" and name == "section_count":
                    assert 1 <= value <= 12
                else:
                    assert 0.0 <= value <= 1.0


def test_artifact_has_real_provenance_and_named_feature_hash():
    path = ROOT / "tests" / "audio" / SOURCES[0]
    artifact = build_music_features_v2_artifact(path)
    expected_audio_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    expected_feature_hash = "sha256:" + hashlib.sha256(json.dumps(artifact["features"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert artifact["artifact"]["audio_content_hash"] == expected_audio_hash
    assert artifact["artifact"]["feature_hash"] == expected_feature_hash
    assert artifact["artifact"]["synthetic_fixture"] is False
    assert artifact["normalization"]["fallbacks"]["stereo_width"]


def test_extraction_is_deterministic_and_tracks_are_distinguishable():
    paths = [ROOT / "tests" / "audio" / source for source in SOURCES]
    first = [extract_music_features_v2(path) for path in paths]
    second = [extract_music_features_v2(path) for path in paths]
    assert first == second
    signatures = {(item["pulse"]["onset_density"], item["timbre"]["brightness"], item["harmony"]["harmonic_change_rate"]) for item in first}
    assert len(signatures) >= 2