"""Audio analysis — E1-fix: density, motion_intensity, harmonic_stability."""
import librosa
import numpy as np
from typing import Any, Dict, List


EPSILON = 1e-12
DEFAULT_SR_HZ = 44100
ANALYSIS_SAMPLE_RATE_HZ = DEFAULT_SR_HZ   # alias для test8
N_FFT = 2048
HOP_LENGTH = 512
HIGH_FREQUENCY_CUTOFF_HZ = 4000.0
MOTION_NORM_HZ = 8000.0   # нормировочная частота для spectral_centroid
ONSET_RATE_NORM = 8.0     # ударов/с → быстрый рок/поп ≈ 8 онсетов/с


def _to_python_scalar(value: Any) -> Any:
    """Преобразует numpy-значения в сериализуемые Python-типы."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        return float(np.mean(value))
    return value


def _safe_mean(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    return float(np.mean(values)) if values.size else 0.0


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= EPSILON:
        return 0.0
    return float(numerator / denominator)


def _estimate_tempo_bpm(y: np.ndarray, sr: int) -> float:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP_LENGTH)
    if isinstance(tempo, (list, tuple)):
        tempo = tempo[0] if tempo else 0.0
    tempo_array = np.asarray(tempo, dtype=float)
    if tempo_array.size == 0:
        return 0.0
    return float(np.mean(tempo_array))


def _compute_silence_rate(rms: np.ndarray) -> float:
    """
    Доля RMS-фреймов, лежащих ниже адаптивного порога тишины.
    Порог: max(1e-4, 0.10 * median(rms > 0)).
    Диапазон [0, 1].
    """
    rms = np.asarray(rms, dtype=float)
    if rms.size == 0:
        return 0.0
    positive_rms = rms[rms > EPSILON]
    if positive_rms.size == 0:
        return 1.0
    threshold = max(1e-4, 0.10 * float(np.median(positive_rms)))
    return float(np.mean(rms <= threshold))


def _normalize_chroma(chroma: np.ndarray) -> np.ndarray:
    chroma = np.asarray(chroma, dtype=float)
    if chroma.ndim != 2 or chroma.shape[0] != 12 or chroma.shape[1] == 0:
        return np.empty((12, 0), dtype=float)
    norms = np.linalg.norm(chroma, axis=0)
    normalized = np.zeros_like(chroma, dtype=float)
    valid = norms > EPSILON
    normalized[:, valid] = chroma[:, valid] / norms[valid]
    return normalized


def _compute_chroma_entropy(chroma: np.ndarray) -> float:
    """
    Фикс 3: энтропия тональных классов (Shannon, нормированная).

    0.0 = вся энергия в одном тоне (монотонная классика).
    1.0 = равномерное распределение по 12 классам (атональный шум).
    Джаз и блюз ожидаются высокими, классика — низкими.
    """
    chroma = np.asarray(chroma, dtype=float)
    if chroma.size == 0:
        return 0.5
    chroma_mean = np.mean(chroma, axis=1)          # [12]
    total = float(np.sum(chroma_mean))
    if total <= EPSILON:
        return 0.5
    prob = chroma_mean / total                     # вероятностное распределение
    prob = np.clip(prob, EPSILON, 1.0)
    entropy = -float(np.sum(prob * np.log(prob)))
    max_entropy = float(np.log(12))                # log(12) ≈ 2.485
    return float(np.clip(entropy / max_entropy, 0.0, 1.0))


def _compute_harmonic_metrics(
    chroma: np.ndarray,
    sr: int,
    hop_length: int,
) -> tuple[float, float]:
    """
    Возвращает:
    - harmonic_stability: средняя косинусная близость [0, 1];
    - harmonic_change_rate_hz: смен гармонии/с [Hz].
    """
    normalized_chroma = _normalize_chroma(chroma)
    num_frames = normalized_chroma.shape[1]
    if num_frames < 2 or sr <= 0 or hop_length <= 0:
        return 0.0, 0.0

    similarities = np.sum(
        normalized_chroma[:, 1:] * normalized_chroma[:, :-1], axis=0
    )
    similarities = np.clip(similarities, 0.0, 1.0)

    valid_pairs = (
        np.linalg.norm(normalized_chroma[:, 1:], axis=0) > EPSILON
    ) & (
        np.linalg.norm(normalized_chroma[:, :-1], axis=0) > EPSILON
    )
    if not np.any(valid_pairs):
        return 0.0, 0.0

    valid_similarities = similarities[valid_pairs]
    harmonic_stability = float(np.mean(valid_similarities))

    harmonic_distance = 1.0 - valid_similarities
    change_threshold = max(0.20, float(np.percentile(harmonic_distance, 75)))
    change_count = int(np.sum(harmonic_distance >= change_threshold))
    duration_sec = ((num_frames - 1) * hop_length) / float(sr)
    harmonic_change_rate_hz = _safe_ratio(change_count, duration_sec)

    return harmonic_stability, harmonic_change_rate_hz


def _compute_spectral_metrics(
    y: np.ndarray,
    sr: int,
) -> tuple[float, float]:
    """
    Возвращает:
    - spectral_flatness [0, 1];
    - high_frequency_energy_ratio (мощность > 4 кГц) [0, 1].
    """
    if y.size == 0 or sr <= 0:
        return 0.0, 0.0
    magnitude = np.abs(
        librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH, center=True)
    )
    power = magnitude ** 2
    spectral_flatness_frames = librosa.feature.spectral_flatness(
        S=magnitude + EPSILON
    )[0]
    spectral_flatness = float(np.clip(_safe_mean(spectral_flatness_frames), 0.0, 1.0))
    if power.size == 0:
        return spectral_flatness, 0.0
    frequencies_hz = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    nyquist_hz = sr / 2.0
    cutoff_hz = min(HIGH_FREQUENCY_CUTOFF_HZ, 0.45 * nyquist_hz)
    if cutoff_hz <= 0.0:
        return spectral_flatness, 0.0
    mask = frequencies_hz >= cutoff_hz
    if not np.any(mask):
        return spectral_flatness, 0.0
    total_power = float(np.sum(power))
    high_power = float(np.sum(power[mask, :]))
    hf_ratio = float(np.clip(_safe_ratio(high_power, total_power), 0.0, 1.0))
    return spectral_flatness, hf_ratio


def analyze_audio_file(
    path: str,
    sr: int = DEFAULT_SR_HZ,
) -> Dict[str, Any]:
    """
    Анализирует MP3/WAV и возвращает сериализуемый словарь признаков.

    Частота дискретизации фиксирована для воспроизводимости результата:
    sr = 44100 Hz. Сигнал сводится к моно только для анализа признаков.
    """
    y, sr = librosa.load(path, sr=sr, mono=True)
    y = np.asarray(y, dtype=float)

    duration_sec = float(librosa.get_duration(y=y, sr=sr))
    rms = np.asarray(
        librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP_LENGTH)[0],
        dtype=float,
    )
    energy = _safe_mean(rms)
    bpm = _estimate_tempo_bpm(y=y, sr=sr)

    # ── spectral centroid ──────────────────────────────────────────────────────────────
    spectral_centroid_frames = np.asarray(
        librosa.feature.spectral_centroid(
            y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH
        )[0],
        dtype=float,
    )
    spectral_centroid = _safe_mean(spectral_centroid_frames)
    nyquist_hz = sr / 2.0
    # старый brightness (/ nyquist) — остаётся для обратной совместимости
    brightness = float(np.clip(_safe_ratio(spectral_centroid, nyquist_hz), 0.0, 1.0))
    # Фикс 2: нормализуем по музыкальной верхней частоте 8 кГц — реальный диапазон
    spectral_centroid_norm = float(
        np.clip(_safe_ratio(spectral_centroid, MOTION_NORM_HZ), 0.0, 1.0)
    )

    # ── Фикс 1: onset rate вместо медианного порога ────────────────────────────────
    onset_env = np.asarray(
        librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH),
        dtype=float,
    )
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH
    )
    if duration_sec > 0.0:
        onset_rate_hz = float(len(onset_frames)) / duration_sec
    else:
        onset_rate_hz = 0.0
    # нормированный onset rate [0, 1]  (8 Hz = быстрый рок)
    onset_rate_norm = float(np.clip(onset_rate_hz / ONSET_RATE_NORM, 0.0, 1.0))
    # rhythm_density остаётся для обратной совместимости (suggest_style)
    if onset_env.size:
        onset_threshold = float(np.median(onset_env))
        rhythm_density = float(np.mean(onset_env > onset_threshold))
    else:
        rhythm_density = 0.0

    # ── dynamic range ────────────────────────────────────────────────────────────────
    if rms.size:
        rms_low  = float(np.percentile(rms, 10))
        rms_high = float(np.percentile(rms, 90))
        dynamic_range = float(
            20.0 * np.log10(max(rms_high, EPSILON))
            - 20.0 * np.log10(max(rms_low, EPSILON))
        )
    else:
        dynamic_range = 0.0

    # ── chroma ──────────────────────────────────────────────────────────────────
    chroma = np.asarray(
        librosa.feature.chroma_stft(
            y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH
        ),
        dtype=float,
    )

    if chroma.size:
        chroma_mean = np.mean(chroma, axis=1)
        chroma_mean = np.asarray(chroma_mean, dtype=float)
        chroma_energy = float(np.dot(chroma_mean, chroma_mean))

        if chroma_energy > EPSILON:
            lag_frames = max(1, int(round(sr / HOP_LENGTH)))
            if chroma.shape[1] > lag_frames:
                similarity = np.sum(
                    chroma[:, :-lag_frames] * chroma[:, lag_frames:], axis=0
                )
                left_norm  = np.linalg.norm(chroma[:, :-lag_frames], axis=0)
                right_norm = np.linalg.norm(chroma[:, lag_frames:], axis=0)
                normalization = left_norm * right_norm
                valid = normalization > EPSILON
                if np.any(valid):
                    repetition_score = float(
                        np.clip(
                            np.mean(similarity[valid] / normalization[valid]),
                            0.0, 1.0,
                        )
                    )
                else:
                    repetition_score = 0.0
            else:
                repetition_score = 0.0
        else:
            repetition_score = 0.0
    else:
        chroma_mean = np.zeros(12, dtype=float)
        repetition_score = 0.0

    pitch_classes = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    key = (
        pitch_classes[int(np.argmax(chroma_mean))]
        if chroma.size and float(np.sum(chroma_mean)) > EPSILON
        else "unknown"
    )

    # ── Фикс 3: chroma entropy ──────────────────────────────────────────────────
    chroma_entropy_norm = _compute_chroma_entropy(chroma)

    silence_rate = _compute_silence_rate(rms)
    harmonic_stability, harmonic_change_rate_hz = _compute_harmonic_metrics(
        chroma=chroma, sr=sr, hop_length=HOP_LENGTH
    )
    spectral_flatness, high_frequency_energy_ratio = _compute_spectral_metrics(
        y=y, sr=sr
    )

    suggested_style = suggest_style(
        bpm=bpm,
        energy=energy,
        brightness=brightness,
        rhythm_density=rhythm_density,
        dynamic_range=dynamic_range,
        repetition_score=repetition_score,
    )

    sections = build_simple_sections(duration_sec, num_sections=6)
    recurrence_groups = build_simple_recurrence_groups(sections)
    events = build_simple_events(
        rms=rms, duration_sec=duration_sec, sr=sr, hop_length=HOP_LENGTH
    )

    features: Dict[str, Any] = {
        "bpm":                       bpm,
        "key":                       key,
        "energy":                    energy,
        "spectral_centroid":         spectral_centroid,
        "spectral_centroid_norm":    spectral_centroid_norm,   # Фикс 2
        "brightness":                brightness,
        "rhythm_density":            rhythm_density,
        "onset_rate_hz":             onset_rate_hz,            # Фикс 1 (Hz)
        "onset_rate_norm":           onset_rate_norm,          # Фикс 1 ([0,1])
        "dynamic_range":             dynamic_range,
        "duration_sec":              duration_sec,
        "repetition_score":          repetition_score,
        "silence_rate":              silence_rate,
        "harmonic_stability":        harmonic_stability,
        "harmonic_change_rate_hz":   harmonic_change_rate_hz,
        "chroma_entropy_norm":       chroma_entropy_norm,      # Фикс 3
        "spectral_flatness":         spectral_flatness,
        "high_frequency_energy_ratio": high_frequency_energy_ratio,
        "suggested_music_style":     suggested_style,
        "sections":                  sections,
        "recurrence_groups":         recurrence_groups,
        "events":                    events,
    }

    clean_features: Dict[str, Any] = {}
    structural_keys = {"sections", "recurrence_groups", "events"}
    for key_name, value in features.items():
        clean_features[key_name] = (
            value if key_name in structural_keys
            else _to_python_scalar(value)
        )
    return clean_features


def suggest_style(
    bpm: float,
    energy: float,
    brightness: float,
    rhythm_density: float,
    dynamic_range: float,
    repetition_score: float,
) -> str:
    """Грубая rule-based классификация музыкального характера."""
    high_bpm  = bpm > 140.0
    mid_bpm   = 100.0 <= bpm <= 140.0
    low_bpm   = bpm < 100.0
    high_energy = energy > 0.22
    mid_energy  = 0.12 <= energy <= 0.22
    low_energy  = energy < 0.12
    low_brightness  = brightness < 0.10
    mid_brightness  = 0.10 <= brightness <= 0.20
    high_brightness = brightness > 0.20
    high_rhythm = rhythm_density > 0.55
    mid_rhythm  = 0.45 <= rhythm_density <= 0.55
    low_rhythm  = rhythm_density < 0.45
    wide_dynamic    = dynamic_range > 12.0
    mid_dynamic     = 8.0 <= dynamic_range <= 12.0
    narrow_dynamic  = dynamic_range < 8.0

    if mid_bpm and wide_dynamic and low_energy and low_brightness and repetition_score > 0.85:
        return "blues"
    if mid_bpm and wide_dynamic and (low_brightness or mid_brightness) and (low_energy or mid_energy):
        return "jazz"
    if (low_bpm or mid_bpm) and wide_dynamic and low_brightness and low_energy and repetition_score < 0.85:
        return "classical"
    if (mid_bpm or high_bpm) and high_energy and (mid_brightness or high_brightness) and (mid_rhythm or high_rhythm):
        return "rock"
    if mid_bpm and mid_energy and (mid_brightness or high_brightness) and mid_dynamic and mid_rhythm:
        return "pop"
    if (high_bpm or high_rhythm) and (mid_energy or high_energy):
        return "electronic"
    if (low_bpm or mid_bpm) and (mid_dynamic or wide_dynamic) and (mid_energy or high_energy) and not low_brightness:
        return "soundtrack"
    if low_brightness and (mid_dynamic or narrow_dynamic) and (low_rhythm or mid_rhythm) and (low_bpm or mid_bpm):
        return "ambient"
    return "mixed"


def build_simple_sections(
    duration_sec: float,
    num_sections: int = 6,
) -> List[Dict[str, Any]]:
    """Временная MVP-сегментация на равные интервалы."""
    if duration_sec <= 0.0 or num_sections <= 0:
        return []
    section_length_sec = duration_sec / num_sections
    return [
        {
            "id": f"S{i + 1}",
            "label": f"Section {i + 1}",
            "start_sec": float(i * section_length_sec),
            "end_sec": float(min(duration_sec, (i + 1) * section_length_sec)),
        }
        for i in range(num_sections)
    ]


def build_simple_recurrence_groups(
    sections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """MVP-представление повторяемости секций."""
    ids = [s["id"] for s in sections]
    groups: List[Dict[str, Any]] = []
    if len(ids) >= 3:
        groups.append({"group_id": "G1", "sections": ids[0:3:2]})
    if len(ids) >= 4:
        groups.append({"group_id": "G2", "sections": ids[1:4:2]})
    return groups


def build_simple_events(
    rms: np.ndarray,
    duration_sec: float,
    sr: int,
    hop_length: int,
) -> List[Dict[str, Any]]:
    """Выделяет до пяти локальных пиков RMS."""
    rms = np.asarray(rms, dtype=float)
    if rms.size == 0 or duration_sec <= 0.0 or sr <= 0:
        return []
    threshold = float(np.percentile(rms, 95))
    peak_indices = np.flatnonzero(rms > threshold)
    min_sep = max(1, int(round(0.25 * sr / hop_length)))
    selected: List[int] = []
    for idx in peak_indices:
        idx_int = int(idx)
        if not selected or (idx_int - selected[-1] >= min_sep):
            selected.append(idx_int)
        if len(selected) == 5:
            break
    return [
        {
            "type": "energy_peak",
            "time_sec": float(i * hop_length / sr),
            "description": "High energy frame",
        }
        for i in selected
    ]


def build_perceptual_latent(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Строит вектор восприятия и переносит расширенные признаки.
    Отсутствующие поля получают 0.0 для обратной совместимости.
    """
    energy               = float(features.get("energy", 0.0))
    rhythm_density       = float(features.get("rhythm_density", 0.0))
    brightness           = float(features.get("brightness", 0.0))
    repetition_score     = float(features.get("repetition_score", 0.0))
    dynamic_range        = float(features.get("dynamic_range", 0.0))
    silence_rate         = float(features.get("silence_rate", 0.0))
    harmonic_stability   = float(features.get("harmonic_stability", 0.0))
    harmonic_change_rate_hz = float(features.get("harmonic_change_rate_hz", 0.0))
    spectral_flatness    = float(features.get("spectral_flatness", 0.0))
    high_frequency_energy_ratio = float(features.get("high_frequency_energy_ratio", 0.0))
    tempo_bpm            = float(features.get("bpm", 0.0))
    sections             = features.get("sections", []) or []
    events               = features.get("events", []) or []

    tension  = float(np.clip(dynamic_range / 20.0, 0.0, 1.0))
    density  = float(np.clip(rhythm_density, 0.0, 1.0))
    stability = float(np.clip(
        0.55 * harmonic_stability + 0.25 * (1.0 - tension) + 0.20 * (1.0 - spectral_flatness),
        0.0, 1.0,
    ))
    smoothness = float(np.clip(
        0.45 * (1.0 - min(len(events) / 10.0, 1.0))
        + 0.30 * harmonic_stability
        + 0.25 * (1.0 - spectral_flatness),
        0.0, 1.0,
    ))
    section_complexity = float(np.clip(len(sections) / 10.0, 0.0, 1.0))
    macro_shape_hint = (
        "ABA_like" if len(sections) >= 3
        else "linear" if len(sections) == 1
        else "unknown"
    )
    return {
        "energy":                    energy,
        "tension":                   tension,
        "density":                   density,
        "brightness":                brightness,
        "stability":                 stability,
        "smoothness":                smoothness,
        "repetition":                repetition_score,
        "section_complexity":        section_complexity,
        "macro_shape_hint":          macro_shape_hint,
        "tempo_bpm":                 tempo_bpm,
        "silence_rate":              silence_rate,
        "harmonic_stability":        harmonic_stability,
        "harmonic_change_rate_hz":   harmonic_change_rate_hz,
        "spectral_flatness":         spectral_flatness,
        "high_frequency_energy_ratio": high_frequency_energy_ratio,
    }
