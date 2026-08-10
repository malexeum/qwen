"""E1 AudioFileAdapter — мост между analyze_audio_file() и пайплайном.

Интерфейс:
    extract_features(audio_path, style_hint=None) -> dict

Возвращает словарь из 17 перцептивных осей + duration_sec + style.
Все значения float [0, 1] кроме duration_sec (секунды).

Изменения E1-fix2:
  density_level    ← onset_rate_norm  (онсеты/с, fix1)
  motion_intensity ← spectral_centroid / 1500 Hz  (fix2 v2)
  harmonic_stability ← mfcc_variance_norm  (fix3: MFCC std, не cosine)
  symmetry_bias    ← cosine harmonic_stability (raw, чтобы сохранить)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from lib.audio_analysis.analysis import analyze_audio_file


def extract_features(
    audio_path: str | Path,
    style_hint: str | None = None,
) -> dict[str, Any]:
    """17-осевой словарь признаков аудиофайла."""
    raw = analyze_audio_file(str(audio_path))

    # ── сырые значения ─────────────────────────────────────────────────────────────
    duration_sec         = float(raw.get("duration_sec", 0.0))
    bpm                  = float(raw.get("bpm", 0.0))
    energy_raw           = float(raw.get("energy", 0.0))
    dynamic_range        = float(raw.get("dynamic_range", 0.0))
    repetition_raw       = float(raw.get("repetition_score", 0.0))
    silence_rate         = float(raw.get("silence_rate", 0.0))
    harmonic_stability   = float(raw.get("harmonic_stability", 0.0))  # cosine raw
    harmonic_change_hz   = float(raw.get("harmonic_change_rate_hz", 0.0))
    spectral_flatness    = float(raw.get("spectral_flatness", 0.0))
    high_freq_ratio      = float(raw.get("high_frequency_energy_ratio", 0.0))

    # Фикс 1: onset rate
    onset_rate_norm      = float(raw.get("onset_rate_norm", 0.0))
    # Фикс 2 v2: centroid / 1500 Hz
    spectral_centroid_norm = float(raw.get("spectral_centroid_norm", 0.0))
    # Фикс 3: MFCC variance
    mfcc_variance_norm   = float(raw.get("mfcc_variance_norm", 0.0))

    events   = raw.get("events",   []) or []
    sections = raw.get("sections", []) or []
    style = style_hint if style_hint else raw.get("suggested_music_style", "mixed")

    # ── нормировка осей ──────────────────────────────────────────────────────────
    energy   = float(np.clip(energy_raw / 0.50, 0.0, 1.0))
    tension  = float(np.clip(dynamic_range / 30.0, 0.0, 1.0))
    tempo    = float(np.clip(bpm / 220.0, 0.0, 1.0))
    section_complexity   = float(np.clip(len(sections) / 10.0, 0.0, 1.0))
    harmonic_change_rate = float(np.clip(harmonic_change_hz / 2.0, 0.0, 1.0))

    # Фикс 1: density ← onset rate (Hz) — реальный разброс
    density_level = float(np.clip(onset_rate_norm, 0.0, 1.0))

    # Фикс 2 v2: motion ← centroid / 1500 Hz
    motion_intensity = float(np.clip(spectral_centroid_norm, 0.0, 1.0))

    # Фикс 3: harmonic_stability ← mfcc_variance_norm
    # джаз: широкий спектр → высокое std MFCC
    # классика: стабильный тембр → низкое std MFCC
    harmonic_stability_out = float(np.clip(mfcc_variance_norm, 0.0, 1.0))

    texture_complexity = float(np.clip(
        0.50 * spectral_flatness
        + 0.30 * spectral_centroid_norm
        + 0.20 * onset_rate_norm,
        0.0, 1.0,
    ))
    noise_level   = float(np.clip(spectral_flatness, 0.0, 1.0))
    # symmetry_bias: остаётся на cosine harmonic_stability (raw) — она стабильна
    symmetry_bias = float(np.clip(harmonic_stability, 0.0, 1.0))

    if events and duration_sec > 0.0:
        first_peak_sec = float(events[0].get("time_sec", duration_sec * 0.5))
        layout_macro_shape = float(np.clip(first_peak_sec / duration_sec, 0.0, 1.0))
    else:
        layout_macro_shape = 0.5

    recursion_depth = float(np.clip(
        0.50 * spectral_centroid_norm
        + 0.30 * tension
        + 0.20 * spectral_flatness,
        0.0, 1.0,
    ))

    return {
        "energy":               energy,
        "tension":              tension,
        "repetition":           float(np.clip(repetition_raw, 0.0, 1.0)),
        "tempo":                tempo,
        "section_complexity":   section_complexity,
        "silence_rate":         float(np.clip(silence_rate, 0.0, 1.0)),
        "harmonic_stability":   harmonic_stability_out,
        "harmonic_change_rate": harmonic_change_rate,
        "spectral_flatness":    float(np.clip(spectral_flatness, 0.0, 1.0)),
        "high_frequency_energy": float(np.clip(high_freq_ratio, 0.0, 1.0)),
        "density_level":        density_level,
        "motion_intensity":     motion_intensity,
        "texture_complexity":   texture_complexity,
        "noise_level":          noise_level,
        "symmetry_bias":        symmetry_bias,
        "layout_macro_shape":   layout_macro_shape,
        "recursion_depth":      recursion_depth,
        "duration_sec":         duration_sec,
        "style":                style,
    }
