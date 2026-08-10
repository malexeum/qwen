"""E1 AudioFileAdapter — мост между analyze_audio_file() и пайплайном.

Интерфейс:
    extract_features(audio_path, style_hint=None) -> dict

Возвращает словарь из 17 перцептивных осей + duration_sec + style.
Все значения float [0, 1] кроме duration_sec (секунды).

Изменения E1-fix3 (Issues #2 #3 #4):
  symmetry_bias      ← _compute_symmetry_bias()   консонансная энергия   [#2]
  section_complexity ← _compute_section_complexity()  RMS CV              [#3]
  noise_level        ← _compute_noise_level()     log-шкала SF           [#4]

Предыдущие фиксы (без изменений):
  density_level      ← onset_rate_norm
  motion_intensity   ← spectral_centroid / 1500 Hz
  harmonic_stability ← mfcc_variance_norm
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

    # ── сырые значения ────────────────────────────────────────────────────────
    duration_sec           = float(raw.get("duration_sec", 0.0))
    bpm                    = float(raw.get("bpm", 0.0))
    energy_raw             = float(raw.get("energy", 0.0))
    dynamic_range          = float(raw.get("dynamic_range", 0.0))
    repetition_raw         = float(raw.get("repetition_score", 0.0))
    silence_rate           = float(raw.get("silence_rate", 0.0))
    harmonic_stability_cos = float(raw.get("harmonic_stability", 0.0))   # cosine raw
    harmonic_change_hz     = float(raw.get("harmonic_change_rate_hz", 0.0))
    spectral_flatness      = float(raw.get("spectral_flatness", 0.0))
    high_freq_ratio        = float(raw.get("high_frequency_energy_ratio", 0.0))

    onset_rate_norm        = float(raw.get("onset_rate_norm", 0.0))         # fix1
    spectral_centroid_norm = float(raw.get("spectral_centroid_norm", 0.0))  # fix2
    mfcc_variance_norm     = float(raw.get("mfcc_variance_norm", 0.0))      # fix3

    # Issue #2: консонансная симметрия — из analysis.py
    symmetry_bias_raw      = float(raw.get("symmetry_bias", 0.0))
    # Issue #3: CV-сложность секций — из analysis.py
    section_complexity_raw = float(raw.get("section_complexity", 0.0))
    # Issue #4: log-шкала шума — из analysis.py
    noise_level_raw        = float(raw.get("noise_level", 0.0))

    events   = raw.get("events",   []) or []
    style    = style_hint if style_hint else raw.get("suggested_music_style", "mixed")

    # ── нормировка осей ───────────────────────────────────────────────────────
    energy               = float(np.clip(energy_raw / 0.50, 0.0, 1.0))
    tension              = float(np.clip(dynamic_range / 30.0, 0.0, 1.0))
    tempo                = float(np.clip(bpm / 220.0, 0.0, 1.0))
    harmonic_change_rate = float(np.clip(harmonic_change_hz / 2.0, 0.0, 1.0))

    density_level        = float(np.clip(onset_rate_norm, 0.0, 1.0))          # fix1
    motion_intensity     = float(np.clip(spectral_centroid_norm, 0.0, 1.0))   # fix2
    harmonic_stability   = float(np.clip(mfcc_variance_norm, 0.0, 1.0))       # fix3

    # Issue #2: symmetry_bias — готова из analysis, просто clip
    symmetry_bias        = float(np.clip(symmetry_bias_raw, 0.0, 1.0))
    # Issue #3: section_complexity — готова из analysis, просто clip
    section_complexity   = float(np.clip(section_complexity_raw, 0.0, 1.0))
    # Issue #4: noise_level — готова из analysis, просто clip
    #           spectral_flatness остаётся отдельной осью (raw)
    noise_level          = float(np.clip(noise_level_raw, 0.0, 1.0))

    texture_complexity = float(np.clip(
        0.50 * spectral_flatness
        + 0.30 * spectral_centroid_norm
        + 0.20 * onset_rate_norm,
        0.0, 1.0,
    ))

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
        "energy":                energy,
        "tension":               tension,
        "repetition":            float(np.clip(repetition_raw, 0.0, 1.0)),
        "tempo":                 tempo,
        "section_complexity":    section_complexity,    # #3 CV-метрика
        "silence_rate":          float(np.clip(silence_rate, 0.0, 1.0)),
        "harmonic_stability":    harmonic_stability,
        "harmonic_change_rate":  harmonic_change_rate,
        "spectral_flatness":     float(np.clip(spectral_flatness, 0.0, 1.0)),
        "high_frequency_energy": float(np.clip(high_freq_ratio, 0.0, 1.0)),
        "density_level":         density_level,
        "motion_intensity":      motion_intensity,
        "texture_complexity":    texture_complexity,
        "noise_level":           noise_level,           # #4 log-шкала
        "symmetry_bias":         symmetry_bias,         # #2 консонанс
        "layout_macro_shape":    layout_macro_shape,
        "recursion_depth":       recursion_depth,
        "duration_sec":          duration_sec,
        "style":                 style,
    }
