"""E1 AudioFileAdapter — мост между analyze_audio_file() и пайплайном.

Интерфейс:
    extract_features(audio_path, style_hint=None) -> dict

Возвращает словарь из 17 перцептивных осей + duration_sec + style.
Все значения float [0, 1] кроме duration_sec (секунды).

Изменения E1-fix:
  density_level    ← onset_rate_norm  (онсеты/с, не медианный порог)
  motion_intensity ← spectral_centroid_norm  (/ 8000 Hz, не / nyquist)
  harmonic_stability ← 0.5*cosine_stability + 0.5*(1 - chroma_entropy)
    джаз (высокая энтропия) ←→ низкое значение
    классика (тональная концентрация) → высокое
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
    """Анализирует аудиофайл и возвращает 17-осевой dict.

    Parameters
    ----------
    audio_path : путь к MP3/WAV/FLAC.
    style_hint : жанр (blues_jazz, electronic, jazz, ambient, classical и др.).
                 Если None — используется suggested_music_style.
    """
    raw = analyze_audio_file(str(audio_path))

    # ── сырые значения ─────────────────────────────────────────────────────────────
    duration_sec        = float(raw.get("duration_sec", 0.0))
    bpm                 = float(raw.get("bpm", 0.0))
    energy_raw          = float(raw.get("energy", 0.0))
    brightness          = float(raw.get("brightness", 0.0))
    dynamic_range       = float(raw.get("dynamic_range", 0.0))
    repetition_raw      = float(raw.get("repetition_score", 0.0))
    silence_rate        = float(raw.get("silence_rate", 0.0))
    harmonic_stability  = float(raw.get("harmonic_stability", 0.0))
    harmonic_change_hz  = float(raw.get("harmonic_change_rate_hz", 0.0))
    spectral_flatness   = float(raw.get("spectral_flatness", 0.0))
    high_freq_ratio     = float(raw.get("high_frequency_energy_ratio", 0.0))

    # Фикс 1: onset rate — реальное число онсетов/с
    onset_rate_norm     = float(raw.get("onset_rate_norm", 0.0))
    # Фикс 2: centroid / 8000 Hz
    spectral_centroid_norm = float(raw.get("spectral_centroid_norm", 0.0))
    # Фикс 3: chroma entropy
    chroma_entropy_norm = float(raw.get("chroma_entropy_norm", 0.0))

    events   = raw.get("events",   []) or []
    sections = raw.get("sections", []) or []
    suggested_style = raw.get("suggested_music_style", "blues_jazz")
    style = style_hint if style_hint else suggested_style

    # ── нормировка ─────────────────────────────────────────────────────────────
    energy   = float(np.clip(energy_raw / 0.50, 0.0, 1.0))
    tension  = float(np.clip(dynamic_range / 30.0, 0.0, 1.0))
    tempo    = float(np.clip(bpm / 220.0, 0.0, 1.0))
    section_complexity = float(np.clip(len(sections) / 10.0, 0.0, 1.0))
    harmonic_change_rate = float(np.clip(harmonic_change_hz / 2.0, 0.0, 1.0))

    # Фикс 1: density = onset_rate_norm (онсеты/с → реальный разброс)
    density_level = float(np.clip(onset_rate_norm, 0.0, 1.0))

    # Фикс 2: motion = centroid / 8000 Hz (не / nyquist)
    motion_intensity = float(np.clip(spectral_centroid_norm, 0.0, 1.0))

    # Фикс 3: harmonic_stability = cosine_mean - entropy_penalty
    # классика: высокая cosine + низкая entropy → высокое значение
    # джаз: высокая cosine + высокая entropy → среднее значение
    harmonic_stability_mixed = float(np.clip(
        0.5 * harmonic_stability + 0.5 * (1.0 - chroma_entropy_norm),
        0.0, 1.0,
    ))

    texture_complexity = float(np.clip(
        0.50 * spectral_flatness
        + 0.30 * spectral_centroid_norm
        + 0.20 * onset_rate_norm,
        0.0, 1.0,
    ))
    noise_level    = float(np.clip(spectral_flatness, 0.0, 1.0))
    symmetry_bias  = harmonic_stability_mixed

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
        "harmonic_stability":   harmonic_stability_mixed,
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
