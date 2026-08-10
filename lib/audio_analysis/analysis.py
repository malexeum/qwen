"""Audio analysis — E1-fix3: symmetry_bias консонанс, section_complexity CV, noise_level log."""
import math
import librosa
import numpy as np
from typing import Any, Dict, List


EPSILON = 1e-12
DEFAULT_SR_HZ = 44100
ANALYSIS_SAMPLE_RATE_HZ = DEFAULT_SR_HZ
N_FFT = 2048
HOP_LENGTH = 512
HIGH_FREQUENCY_CUTOFF_HZ = 4000.0
MOTION_NORM_HZ = 1500.0
ONSET_RATE_NORM = 8.0
MFCC_NORM = 50.0

# Issue #2: консонантные полутоны (унисон, м3, б3, кварта, квинта, м6, б6)
CONSONANT_SEMITONES: frozenset[int] = frozenset({0, 3, 4, 5, 7, 8, 9})

# Issue #4: границы log-шкалы для spectral flatness
SF_MIN = 1.0e-5   # чистый тон
SF_MAX = 0.50     # белый шум


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


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _estimate_tempo_bpm(y: np.ndarray, sr: int) -> float:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP_LENGTH)
    if isinstance(tempo, (list, tuple)):
        tempo = tempo[0] if tempo else 0.0
    tempo_array = np.asarray(tempo, dtype=float)
    if tempo_array.size == 0:
        return 0.0
    return float(np.mean(tempo_array))


def _compute_silence_rate(rms: np.ndarray) -> float:
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
    """Shannon-энтропия тональных классов, нормированная на log(12)."""
    chroma = np.asarray(chroma, dtype=float)
    if chroma.size == 0:
        return 0.5
    chroma_mean = np.mean(chroma, axis=1)
    total = float(np.sum(chroma_mean))
    if total <= EPSILON:
        return 0.5
    prob = np.clip(chroma_mean / total, EPSILON, 1.0)
    entropy = -float(np.sum(prob * np.log(prob)))
    return float(np.clip(entropy / float(np.log(12)), 0.0, 1.0))


def _compute_mfcc_variance(y: np.ndarray, sr: int) -> float:
    """Среднее std по 13 MFCC-коэффициентам / MFCC_NORM."""
    if y.size == 0 or sr <= 0:
        return 0.0
    mfcc = librosa.feature.mfcc(
        y=y, sr=sr, n_mfcc=13,
        n_fft=N_FFT, hop_length=HOP_LENGTH,
    )
    mfcc_std = float(np.mean(np.std(mfcc, axis=1)))
    return _clip01(mfcc_std / MFCC_NORM)


def _compute_symmetry_bias(chroma: np.ndarray) -> float:
    """Issue #2: доля консонантной chroma-энергии относительно локального
    доминирующего тона. Физически: насколько гармония трека строится на
    консонансах — в отличие от энтропии, разделяет жанры.

    Алгоритм (пофреймово, взвешенное по энергии среднее):
      1. root = argmax(chroma[:, frame])
      2. intervals = (pitch_class - root) % 12 для каждого из 12 классов
      3. consonant_ratio = sum(energy[consonant]) / sum(energy[all])
      4. итог = среднее по фреймам, вес = суммарная энергия фрейма

    Ожидаемые диапазоны: classical/ambient > blues_jazz > electronic.
    std >= 0.10 при 5 жанровых треках.
    """
    chroma = np.asarray(chroma, dtype=float)
    if chroma.ndim != 2 or chroma.shape[0] != 12 or chroma.shape[1] == 0:
        return 0.0

    frame_totals = np.sum(chroma, axis=0)          # (n_frames,)
    valid = frame_totals > EPSILON
    if not np.any(valid):
        return 0.0

    chroma_v = chroma[:, valid]                    # (12, n_valid)
    totals_v = frame_totals[valid]                 # (n_valid,)
    roots = np.argmax(chroma_v, axis=0)            # (n_valid,)  int

    pitch_idx = np.arange(12, dtype=np.int16)[:, None]          # (12, 1)
    intervals = (pitch_idx - roots[None, :]) % 12               # (12, n_valid)
    consonant_mask = np.isin(intervals, tuple(CONSONANT_SEMITONES))  # (12, n_valid)

    consonant_energy = np.sum(np.where(consonant_mask, chroma_v, 0.0), axis=0)
    frame_ratios = consonant_energy / totals_v     # (n_valid,)

    weights = totals_v / (np.sum(totals_v) + EPSILON)
    return _clip01(float(np.sum(frame_ratios * weights)))


def _compute_section_complexity(
    y: np.ndarray,
    sr: int,
    hop_length: int,
    n_segments: int = 6,
) -> float:
    """Issue #3: межсекционный энергетический контраст.

    CV (coefficient of variation) средних RMS-энергий n_segments
    равных временных сегментов, нормированный по 0.5.

    Ambient/drone: низкая CV → низкое значение.
    Рок/электроника с нарастаниями: высокая CV → высокое значение.
    std >= 0.10 при 5 жанровых треках.
    """
    if y.size == 0 or hop_length <= 0 or n_segments < 2:
        return 0.0

    y_f = np.asarray(y, dtype=np.float64)
    frame_count = max(1, int(np.ceil(y_f.size / hop_length)))
    pad = frame_count * hop_length - y_f.size
    if pad > 0:
        y_f = np.pad(y_f, (0, pad), mode="constant")

    frames = y_f.reshape(frame_count, hop_length)
    rms_frames = np.sqrt(np.mean(np.square(frames), axis=1))

    chunks = np.array_split(rms_frames, n_segments)
    seg_means = np.array(
        [float(np.mean(c)) if c.size else 0.0 for c in chunks],
        dtype=np.float64,
    )
    mean_energy = float(np.mean(seg_means))
    if mean_energy <= EPSILON:
        return 0.0

    cv = float(np.std(seg_means) / mean_energy)
    return _clip01(cv / 0.5)


def _compute_noise_level(spectral_flatness_raw: float) -> float:
    """Issue #4: log-шкалирование spectral flatness → perceptual noise.

    Музыкальные треки физически имеют SF ~ 0.001–0.01 (сильно тональный
    сигнал), поэтому линейное использование SF сжимает весь диапазон в 1%.
    Логарифмическое шкалирование растягивает музыкально значимую область.

    SF_MIN = 1e-5  (чистый синус),  SF_MAX = 0.5  (белый шум).
    noise_level != spectral_flatness (разные оси, разная семантика).
    """
    sf = max(float(spectral_flatness_raw), SF_MIN)
    numerator = math.log10(sf) - math.log10(SF_MIN)
    denominator = math.log10(SF_MAX) - math.log10(SF_MIN)
    return _clip01(numerator / denominator)


def _compute_harmonic_metrics(
    chroma: np.ndarray,
    sr: int,
    hop_length: int,
) -> tuple[float, float]:
    """
    Возвращает:
    - harmonic_stability_cosine: средняя косинусная близость [0, 1];
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
    harmonic_stability_cosine = float(np.mean(valid_similarities))

    harmonic_distance = 1.0 - valid_similarities
    change_threshold = max(0.20, float(np.percentile(harmonic_distance, 75)))
    change_count = int(np.sum(harmonic_distance >= change_threshold))
    duration_sec = ((num_frames - 1) * hop_length) / float(sr)
    harmonic_change_rate_hz = _safe_ratio(change_count, duration_sec)

    return harmonic_stability_cosine, harmonic_change_rate_hz


def _compute_spectral_metrics(
    y: np.ndarray,
    sr: int,
) -> tuple[float, float]:
    """
    Возвращает:
    - spectral_flatness_raw [0, 1];
    - high_frequency_energy_ratio (мощность > 4 кГц) [0, 1].
    """
    if y.size == 0 or sr <= 0:
        return 0.0, 0.0
    magnitude = np.abs(
        librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH, center=True)
    )
    power = magnitude ** 2
    sf_frames = librosa.feature.spectral_flatness(S=magnitude + EPSILON)[0]
    spectral_flatness_raw = float(np.clip(_safe_mean(sf_frames), 0.0, 1.0))
    if power.size == 0:
        return spectral_flatness_raw, 0.0
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    nyquist_hz = sr / 2.0
    cutoff_hz = min(HIGH_FREQUENCY_CUTOFF_HZ, 0.45 * nyquist_hz)
    if cutoff_hz <= 0.0:
        return spectral_flatness_raw, 0.0
    mask = freqs >= cutoff_hz
    if not np.any(mask):
        return spectral_flatness_raw, 0.0
    total_power = float(np.sum(power))
    hf_ratio = _clip01(_safe_ratio(float(np.sum(power[mask, :])), total_power))
    return spectral_flatness_raw, hf_ratio


def analyze_audio_file(
    path: str,
    sr: int = DEFAULT_SR_HZ,
) -> Dict[str, Any]:
    """
    Анализирует MP3/WAV и возвращает сериализуемый словарь признаков.
    sr = 44100 Hz фиксирован для воспроизводимости.
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

    # ── spectral centroid ─────────────────────────────────────────────────────
    sc_frames = np.asarray(
        librosa.feature.spectral_centroid(
            y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH
        )[0],
        dtype=float,
    )
    spectral_centroid = _safe_mean(sc_frames)
    nyquist_hz = sr / 2.0
    brightness = _clip01(_safe_ratio(spectral_centroid, nyquist_hz))
    spectral_centroid_norm = _clip01(_safe_ratio(spectral_centroid, MOTION_NORM_HZ))

    # ── onset rate ────────────────────────────────────────────────────────────
    onset_env = np.asarray(
        librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH),
        dtype=float,
    )
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH
    )
    onset_rate_hz = (
        float(len(onset_frames)) / duration_sec if duration_sec > 0.0 else 0.0
    )
    onset_rate_norm = _clip01(onset_rate_hz / ONSET_RATE_NORM)
    if onset_env.size:
        rhythm_density = float(np.mean(onset_env > float(np.median(onset_env))))
    else:
        rhythm_density = 0.0

    # ── dynamic range ─────────────────────────────────────────────────────────
    if rms.size:
        rms_low  = float(np.percentile(rms, 10))
        rms_high = float(np.percentile(rms, 90))
        dynamic_range = float(
            20.0 * np.log10(max(rms_high, EPSILON))
            - 20.0 * np.log10(max(rms_low,  EPSILON))
        )
    else:
        dynamic_range = 0.0

    # ── chroma + repetition ───────────────────────────────────────────────────
    chroma = np.asarray(
        librosa.feature.chroma_stft(
            y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH
        ),
        dtype=float,
    )
    if chroma.size:
        chroma_mean = np.asarray(np.mean(chroma, axis=1), dtype=float)
        chroma_energy = float(np.dot(chroma_mean, chroma_mean))
        if chroma_energy > EPSILON:
            lag_frames = max(1, int(round(sr / HOP_LENGTH)))
            if chroma.shape[1] > lag_frames:
                sim = np.sum(
                    chroma[:, :-lag_frames] * chroma[:, lag_frames:], axis=0
                )
                ln = np.linalg.norm(chroma[:, :-lag_frames], axis=0)
                rn = np.linalg.norm(chroma[:, lag_frames:], axis=0)
                norm_lr = ln * rn
                valid = norm_lr > EPSILON
                repetition_score = (
                    _clip01(float(np.mean(sim[valid] / norm_lr[valid])))
                    if np.any(valid) else 0.0
                )
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

    chroma_entropy_norm = _compute_chroma_entropy(chroma)
    mfcc_variance_norm  = _compute_mfcc_variance(y=y, sr=sr)

    # Issue #2: новая symmetry_bias — консонансная энергия
    symmetry_bias_val   = _compute_symmetry_bias(chroma)

    # Issue #3: новая section_complexity — CV по RMS-сегментам
    section_complexity_val = _compute_section_complexity(
        y=y, sr=sr, hop_length=HOP_LENGTH
    )

    silence_rate = _compute_silence_rate(rms)
    harmonic_stability_cosine, harmonic_change_rate_hz = _compute_harmonic_metrics(
        chroma=chroma, sr=sr, hop_length=HOP_LENGTH
    )
    # spectral_flatness_raw нужен и для оси spectral_flatness, и для noise_level
    spectral_flatness_raw, high_frequency_energy_ratio = _compute_spectral_metrics(
        y=y, sr=sr
    )

    # Issue #4: noise_level через log-шкалу, отдельно от spectral_flatness
    noise_level_val = _compute_noise_level(spectral_flatness_raw)

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
        "bpm":                          bpm,
        "key":                          key,
        "energy":                       energy,
        "spectral_centroid":            spectral_centroid,
        "spectral_centroid_norm":       spectral_centroid_norm,
        "brightness":                   brightness,
        "rhythm_density":               rhythm_density,
        "onset_rate_hz":                onset_rate_hz,
        "onset_rate_norm":              onset_rate_norm,
        "dynamic_range":                dynamic_range,
        "duration_sec":                 duration_sec,
        "repetition_score":             repetition_score,
        "silence_rate":                 silence_rate,
        "harmonic_stability":           harmonic_stability_cosine,
        "harmonic_change_rate_hz":      harmonic_change_rate_hz,
        "chroma_entropy_norm":          chroma_entropy_norm,
        "mfcc_variance_norm":           mfcc_variance_norm,
        "spectral_flatness":            spectral_flatness_raw,
        "high_frequency_energy_ratio":  high_frequency_energy_ratio,
        "suggested_music_style":        suggested_style,
        # ── новые ключи E1-fix3 ────────────────────────────────────────────
        "symmetry_bias":                symmetry_bias_val,
        "section_complexity":           section_complexity_val,
        "noise_level":                  noise_level_val,
        # ── структурные ───────────────────────────────────────────────────
        "sections":                     sections,
        "recurrence_groups":            recurrence_groups,
        "events":                       events,
    }

    structural_keys = {"sections", "recurrence_groups", "events"}
    clean_features: Dict[str, Any] = {
        k: (v if k in structural_keys else _to_python_scalar(v))
        for k, v in features.items()
    }
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
    high_bpm = bpm > 140.0
    mid_bpm  = 100.0 <= bpm <= 140.0
    low_bpm  = bpm < 100.0
    high_energy = energy > 0.22
    mid_energy  = 0.12 <= energy <= 0.22
    low_energy  = energy < 0.12
    low_brightness  = brightness < 0.10
    mid_brightness  = 0.10 <= brightness <= 0.20
    high_brightness = brightness > 0.20
    high_rhythm = rhythm_density > 0.55
    mid_rhythm  = 0.45 <= rhythm_density <= 0.55
    low_rhythm  = rhythm_density < 0.45
    wide_dynamic   = dynamic_range > 12.0
    mid_dynamic    = 8.0 <= dynamic_range <= 12.0
    narrow_dynamic = dynamic_range < 8.0

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
    sec_len = duration_sec / num_sections
    return [
        {
            "id": f"S{i + 1}",
            "label": f"Section {i + 1}",
            "start_sec": float(i * sec_len),
            "end_sec": float(min(duration_sec, (i + 1) * sec_len)),
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
    Строит вектор восприятия. Отсутствующие поля = 0.0.
    Issue #3: section_complexity теперь берётся из features (CV-метрика),
    а не вычисляется как len(sections)/10.
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
    # Issue #3: CV-метрика из analyze_audio_file, не len(sections)/10
    section_complexity   = float(features.get("section_complexity", 0.0))
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
    macro_shape_hint = (
        "ABA_like" if section_complexity > 0.5
        else "linear" if section_complexity < 0.1
        else "unknown"
    )
    return {
        "energy":                       energy,
        "tension":                      tension,
        "density":                      density,
        "brightness":                   brightness,
        "stability":                    stability,
        "smoothness":                   smoothness,
        "repetition":                   repetition_score,
        "section_complexity":           section_complexity,
        "macro_shape_hint":             macro_shape_hint,
        "tempo_bpm":                    tempo_bpm,
        "silence_rate":                 silence_rate,
        "harmonic_stability":           harmonic_stability,
        "harmonic_change_rate_hz":      harmonic_change_rate_hz,
        "spectral_flatness":            spectral_flatness,
        "high_frequency_energy_ratio":  high_frequency_energy_ratio,
    }
