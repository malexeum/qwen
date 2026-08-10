"""E1 AudioFileAdapter — мост между analyze_audio_file() и пайплайном.

Интерфейс:
    extract_features(audio_path, style_hint=None) -> dict

Возвращает словарь из 17 перцептивных осей в том же формате,
что FEATURES[профиль] в run_full.py. Все значения float [0, 1]
кроме duration_sec (секунды).

Оси:
    energy, tension, repetition, tempo, section_complexity,
    silence_rate, harmonic_stability, harmonic_change_rate,
    spectral_flatness, high_frequency_energy, density_level,
    motion_intensity, texture_complexity, noise_level,
    symmetry_bias, layout_macro_shape, recursion_depth,
    duration_sec (сквозной — нужен для seed policy)
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
    """Анализирует аудиофайл и возвращает 17-осевой dict перцептивных признаков.

    Parameters
    ----------
    audio_path:
        Путь к аудиофайлу (MP3 / WAV / FLAC и другие форматы librosa).
    style_hint:
        Необязательная подсказка жанра (blues_jazz, electronic, jazz,
        ambient, classical, soundtrack, rock). Если None —
        используется suggested_music_style из analyze_audio_file().

    Returns
    -------
    dict с ключами:
        energy, tension, repetition, tempo, section_complexity,
        silence_rate, harmonic_stability, harmonic_change_rate,
        spectral_flatness, high_frequency_energy, density_level,
        motion_intensity, texture_complexity, noise_level,
        symmetry_bias, layout_macro_shape, recursion_depth,
        duration_sec, style (строка-жанр для логов)
    """
    raw = analyze_audio_file(str(audio_path))

    # ── Базовые измеренные значения ──────────────────────────────────────────
    duration_sec   = float(raw.get("duration_sec", 0.0))
    bpm            = float(raw.get("bpm", 0.0))
    energy_raw     = float(raw.get("energy", 0.0))
    brightness     = float(raw.get("brightness", 0.0))      # spectral_centroid / nyquist
    rhythm_density = float(raw.get("rhythm_density", 0.0))
    dynamic_range  = float(raw.get("dynamic_range", 0.0))
    repetition_raw = float(raw.get("repetition_score", 0.0))
    silence_rate   = float(raw.get("silence_rate", 0.0))

    harmonic_stability      = float(raw.get("harmonic_stability", 0.0))
    harmonic_change_rate_hz = float(raw.get("harmonic_change_rate_hz", 0.0))
    spectral_flatness       = float(raw.get("spectral_flatness", 0.0))
    high_freq_ratio         = float(raw.get("high_frequency_energy_ratio", 0.0))

    events   = raw.get("events", []) or []
    sections = raw.get("sections", []) or []

    suggested_style = raw.get("suggested_music_style", "blues_jazz")
    style = style_hint if style_hint else suggested_style

    # ── Нормировка в [0, 1] ──────────────────────────────────────────────────

    # energy: RMS среднее — обычно лежит в [0, 0.5] для музыки;
    #         нормируем через типовой максимум 0.5, клипируем в [0, 1]
    energy = float(np.clip(energy_raw / 0.50, 0.0, 1.0))

    # tension: динамический диапазон в дБ, типовой макс ~30 дБ
    tension = float(np.clip(dynamic_range / 30.0, 0.0, 1.0))

    # tempo: BPM / 220 → 0.5 ≈ 110 BPM (типичный джаз/поп)
    tempo = float(np.clip(bpm / 220.0, 0.0, 1.0))

    # section_complexity: len(sections) / 10
    section_complexity = float(np.clip(len(sections) / 10.0, 0.0, 1.0))

    # harmonic_change_rate: делим на 2 Hz — порог "быстрой" гармонической смены
    harmonic_change_rate = float(np.clip(harmonic_change_rate_hz / 2.0, 0.0, 1.0))

    # density_level: onset rhythm_density напрямую [0, 1]
    density_level = float(np.clip(rhythm_density, 0.0, 1.0))

    # motion_intensity: brightness (spectral_centroid / nyquist) — уже [0, 1]
    motion_intensity = float(np.clip(brightness, 0.0, 1.0))

    # texture_complexity: взвешенная сумма спектральных характеристик
    texture_complexity = float(np.clip(
        0.50 * spectral_flatness
        + 0.30 * brightness
        + 0.20 * rhythm_density,
        0.0, 1.0,
    ))

    # noise_level: alias spectral_flatness — мера шумоподобности спектра
    noise_level = float(np.clip(spectral_flatness, 0.0, 1.0))

    # symmetry_bias: harmonic_stability как мера тонально-симметричного материала
    symmetry_bias = float(np.clip(harmonic_stability, 0.0, 1.0))

    # layout_macro_shape: нормированная позиция первого энергетического пика
    # → 0.0 = пик в начале, 1.0 = пик в конце; 0.5 если событий нет
    if events and duration_sec > 0.0:
        first_peak_sec = float(events[0].get("time_sec", duration_sec * 0.5))
        layout_macro_shape = float(np.clip(first_peak_sec / duration_sec, 0.0, 1.0))
    else:
        layout_macro_shape = 0.5

    # recursion_depth: прокси спектральной «глубины» —
    # яркий+напряжённый трек даёт больше итераций фрактала
    recursion_depth = float(np.clip(
        0.50 * brightness
        + 0.30 * tension
        + 0.20 * spectral_flatness,
        0.0, 1.0,
    ))

    return {
        # 17 перцептивных осей
        "energy":               energy,
        "tension":              tension,
        "repetition":           float(np.clip(repetition_raw, 0.0, 1.0)),
        "tempo":                tempo,
        "section_complexity":   section_complexity,
        "silence_rate":         float(np.clip(silence_rate, 0.0, 1.0)),
        "harmonic_stability":   float(np.clip(harmonic_stability, 0.0, 1.0)),
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
        # сквозные
        "duration_sec":         duration_sec,
        "style":                style,
    }
