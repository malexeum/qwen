from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import librosa
import numpy as np

from lib.audio_analysis.analysis import HOP_LENGTH, N_FFT, analyze_audio_file
from .music_features_v2_normalization import NORMALIZATION_METADATA, normalize_features
from .music_features_v2_schema import validate_features


EXTRACTOR_NAME = "music_features_v2_extractor"
EXTRACTOR_VERSION = "2.0.0"
SAMPLE_RATE = 44100
EPSILON = 1e-12


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return float(np.clip(value, low, high))


def _mean(values: np.ndarray, fallback: float = 0.5) -> float:
    return float(np.mean(values)) if values.size else fallback


def _cv(values: np.ndarray, fallback: float = 0.5) -> float:
    if values.size == 0 or float(np.mean(values)) <= EPSILON:
        return fallback
    return _clip(float(np.std(values) / np.mean(values) / 0.5))


def _linear_arc(values: np.ndarray) -> float:
    if values.size < 2 or float(np.mean(values)) <= EPSILON:
        return 0.5
    x = np.linspace(0.0, 1.0, values.size)
    slope = float(np.polyfit(x, values, 1)[0])
    return _clip(0.5 + slope / (2.0 * max(float(np.max(values)), EPSILON)))


def _raw_measurements(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = analyze_audio_file(str(path), sr=SAMPLE_RATE)
    y, sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    y = np.asarray(y, dtype=float)
    rms = np.asarray(librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP_LENGTH)[0], dtype=float)
    duration = max(float(raw.get("duration_sec", 0.0)), EPSILON)
    onset_env = np.asarray(librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH), dtype=float)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH)
    chroma = np.asarray(librosa.feature.chroma_stft(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH), dtype=float)
    stft = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH))
    centroid = np.asarray(librosa.feature.spectral_centroid(S=stft, sr=sr)[0], dtype=float)
    rolloff = np.asarray(librosa.feature.spectral_rolloff(S=stft, sr=sr)[0], dtype=float)
    bandwidth = np.asarray(librosa.feature.spectral_bandwidth(S=stft, sr=sr)[0], dtype=float)
    flux = np.diff(stft, axis=1)
    flux_values = np.sqrt(np.mean(np.square(flux), axis=0)) if flux.size else np.array([])
    segments = np.array_split(rms, 6)
    segment_energy = np.asarray([_mean(segment, 0.0) for segment in segments], dtype=float)
    beat_tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP_LENGTH)
    beat_frames = np.asarray(beat_frames, dtype=int)
    bpm = float(np.asarray(beat_tempo).reshape(-1)[0]) if np.asarray(beat_tempo).size else 0.0
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP_LENGTH)
    intervals = np.diff(beat_times)
    regularity = 1.0 - _cv(intervals, 0.5) if intervals.size else 0.5
    if intervals.size and onset_frames.size and bpm > 0.0:
        beat_period = 60.0 / bpm
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP_LENGTH)
        phase = np.mod(onset_times, beat_period) / beat_period
        syncopation = _clip(float(np.mean(np.minimum(phase, 1.0 - phase) * 2.0)))
    else:
        syncopation = 0.5
    loudness_low = float(np.percentile(rms, 10)) if rms.size else EPSILON
    loudness_high = float(np.percentile(rms, 90)) if rms.size else EPSILON
    dynamic_db = max(0.0, 20.0 * math.log10(max(loudness_high, EPSILON)) - 20.0 * math.log10(max(loudness_low, EPSILON)))
    onset_strength = _clip(_mean(onset_env, 0.0) / max(float(np.percentile(onset_env, 95)) if onset_env.size else 1.0, EPSILON))
    first_onset = float(librosa.frames_to_time(onset_frames[0], sr=sr, hop_length=HOP_LENGTH)) if onset_frames.size else duration * 0.1
    last_onset = float(librosa.frames_to_time(onset_frames[-1], sr=sr, hop_length=HOP_LENGTH)) if onset_frames.size else duration * 0.9
    flatness = float(raw.get("spectral_flatness", 0.5))
    harmonic_stability = float(raw.get("harmonic_stability", 0.5))
    harmonic_change = _clip(float(raw.get("harmonic_change_rate_hz", 0.0)) / 2.0)
    tonal_stability = _clip(1.0 - float(raw.get("chroma_entropy_norm", 0.5)))
    self_similarity = _clip(float(raw.get("repetition_score", 0.5)))
    raw_values = {
        "duration_sec": duration, "rms": rms, "segments": segment_energy, "onset_frames": onset_frames,
        "onset_count": len(onset_frames), "bpm": bpm, "regularity": regularity, "syncopation": syncopation,
        "dynamic_db": dynamic_db, "onset_strength": onset_strength, "first_onset": first_onset,
        "last_onset": last_onset, "flatness": flatness, "harmonic_stability": harmonic_stability,
        "harmonic_change": harmonic_change, "tonal_stability": tonal_stability, "self_similarity": self_similarity,
        "centroid": _mean(centroid), "rolloff": _mean(rolloff), "bandwidth": _mean(bandwidth),
        "flux": _mean(flux_values, 0.0), "brightness": float(raw.get("brightness", 0.5)),
        "silence": float(raw.get("silence_rate", 0.5)), "symmetry": float(raw.get("symmetry_bias", 0.5)),
    }
    return raw_values, {"stereo_width": "mono source; neutral fallback 0.5"}


def extract_music_features_v2(audio_path: str | Path) -> dict[str, dict[str, Any]]:
    path = Path(audio_path).resolve(strict=True)
    raw, _ = _raw_measurements(path)
    features = {
        "pulse": {"bpm": raw["bpm"], "beat_confidence": _clip(raw["onset_count"] / max(raw["duration_sec"] * 4.0, 1.0)), "pulse_regularity": raw["regularity"], "onset_density": _clip(raw["onset_count"] / max(raw["duration_sec"] * 8.0, 1.0)), "syncopation_index": raw["syncopation"]},
        "envelope": {"dynamic_range": _clip(raw["dynamic_db"] / 30.0), "attack_sharpness": raw["onset_strength"], "sustain_ratio": _clip(_mean(raw["rms"]) / max(float(np.max(raw["rms"])) if raw["rms"].size else 1.0, EPSILON)), "macro_energy_arc": _linear_arc(raw["segments"]), "silence_ratio": raw["silence"]},
        "form": {"section_count": len(raw["segments"]), "section_contrast": _cv(raw["segments"], 0.5), "climax_position": float(np.argmax(raw["segments"]) / max(len(raw["segments"]) - 1, 1)), "intro_length_ratio": _clip(raw["first_onset"] / raw["duration_sec"]), "ending_decay_ratio": _clip(1.0 - raw["last_onset"] / raw["duration_sec"])},
        "recurrence": {"self_similarity": raw["self_similarity"], "motif_return_strength": raw["self_similarity"], "repetition_ratio": raw["self_similarity"], "variation_ratio": _clip(1.0 - raw["self_similarity"])},
        "timbre": {"spectral_centroid": _clip(raw["centroid"] / (SAMPLE_RATE / 2.0)), "spectral_rolloff": _clip(raw["rolloff"] / (SAMPLE_RATE / 2.0)), "spectral_flatness": _clip(raw["flatness"]), "spectral_flux": _clip(raw["flux"] / max(float(np.percentile(raw["rms"], 95)) if raw["rms"].size else 1.0, EPSILON)), "roughness": _clip(0.5 * raw["flatness"] + 0.5 * raw["flux"] / max(float(np.percentile(raw["rms"], 95)) if raw["rms"].size else 1.0, EPSILON)), "brightness": _clip(raw["brightness"])},
        "harmony": {"harmonic_ratio": _clip(1.0 - raw["flatness"]), "chroma_stability": _clip(raw["harmonic_stability"]), "harmonic_change_rate": raw["harmonic_change"], "tonal_stability": raw["tonal_stability"], "dissonance_proxy": _clip(1.0 - raw["symmetry"])},
        "space": {"spectral_bandwidth": _clip(raw["bandwidth"] / (SAMPLE_RATE / 2.0)), "stereo_width": 0.5, "reverb_proxy": _clip(raw["flatness"]), "depth_proxy": _clip(0.5 * raw["flatness"] + 0.5 * raw["silence"])},
    }
    features = normalize_features(features)
    validate_features(features)
    return features


def _canonical_feature_hash(features: dict) -> str:
    payload = json.dumps(features, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_music_features_v2_artifact(audio_path: str | Path, track_id: str | None = None) -> dict[str, Any]:
    path = Path(audio_path).resolve(strict=True)
    features = extract_music_features_v2(path)
    _, fallback_metadata = _raw_measurements(path)
    created_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    artifact = {
        "schema": "MusicFeaturesV2", "version": "v2.0.0",
        "artifact": {"track_id": track_id or path.stem, "audio_content_hash": _sha256_file(path), "feature_hash": _canonical_feature_hash(features), "extractor_name": EXTRACTOR_NAME, "extractor_version": EXTRACTOR_VERSION, "created_at": created_at, "synthetic_fixture": False},
        "normalization": dict(NORMALIZATION_METADATA),
        "features": features,
    }
    if fallback_metadata:
        artifact["normalization"]["fallbacks"] = fallback_metadata
    return artifact


extract = extract_music_features_v2
build_artifact = build_music_features_v2_artifact