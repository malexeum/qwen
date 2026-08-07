import librosa
import numpy as np
from typing import Any, Dict, List


ANALYSIS_SAMPLE_RATE_HZ = 44100
N_FFT = 2048
HOP_LENGTH = 512
MIN_ONSET_SEPARATION_SEC = 0.10


def _to_python_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()

    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        return float(np.mean(value))

    return value


def _safe_mean(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    return float(np.mean(values)) if values.size > 0 else 0.0


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0

    return float(np.clip(numerator / denominator, 0.0, 1.0))


def _extract_tempo_bpm(y: np.ndarray, sr: int) -> float:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    if isinstance(tempo, (list, tuple)):
        tempo = tempo[0] if tempo else 0.0

    tempo_array = np.asarray(tempo, dtype=float)

    if tempo_array.ndim == 0:
        return float(tempo_array)

    return _safe_mean(tempo_array)


def _extract_onset_rate_hz(
    onset_envelope: np.ndarray,
    sr: int,
    duration_sec: float,
) -> tuple[float, int]:
    if onset_envelope.size == 0 or duration_sec <= 0.0:
        return 0.0, 0

    wait_frames = max(
        1,
        int(
            round(
                MIN_ONSET_SEPARATION_SEC
                * sr
                / HOP_LENGTH
            )
        ),
    )

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope,
        sr=sr,
        hop_length=HOP_LENGTH,
        units="frames",
        backtrack=False,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=5,
        delta=0.07,
        wait=wait_frames,
    )

    onset_count = int(np.asarray(onset_frames).size)
    onset_rate_hz = float(onset_count / duration_sec)

    return onset_rate_hz, onset_count


def _extract_beat_regularity(
    y: np.ndarray,
    sr: int,
) -> tuple[float, int]:
    _, beat_frames = librosa.beat.beat_track(
        y=y,
        sr=sr,
        hop_length=HOP_LENGTH,
        units="frames",
    )

    beat_frames = np.asarray(beat_frames, dtype=int)

    if beat_frames.size < 3:
        return 0.0, int(beat_frames.size)

    beat_times_sec = librosa.frames_to_time(
        beat_frames,
        sr=sr,
        hop_length=HOP_LENGTH,
    )
    intervals_sec = np.diff(beat_times_sec)
    intervals_sec = intervals_sec[intervals_sec > 0.0]

    if intervals_sec.size < 2:
        return 0.0, int(beat_frames.size)

    mean_interval_sec = float(np.mean(intervals_sec))

    if mean_interval_sec <= 0.0:
        return 0.0, int(beat_frames.size)

    beat_regularity = float(
        np.std(intervals_sec, ddof=1)
        / mean_interval_sec
    )

    return beat_regularity, int(beat_frames.size)


def _band_energy_ratio(
    power_spectrogram: np.ndarray,
    frequencies_hz: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> float:
    if power_spectrogram.size == 0:
        return 0.0

    mask = (
        (frequencies_hz >= low_hz)
        & (frequencies_hz < high_hz)
    )

    total_power = float(np.sum(power_spectrogram))

    if not np.any(mask) or total_power <= 0.0:
        return 0.0

    band_power = float(np.sum(power_spectrogram[mask, :]))
    return _safe_ratio(band_power, total_power)


def _extract_spectral_band_energies(
    y: np.ndarray,
    sr: int,
) -> Dict[str, float]:
    stft = librosa.stft(
        y,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        window="hann",
        center=True,
    )
    power_spectrogram = np.abs(stft) ** 2
    frequencies_hz = librosa.fft_frequencies(
        sr=sr,
        n_fft=N_FFT,
    )
    nyquist_hz = sr / 2.0

    return {
        "band_energy_0_250_hz": _band_energy_ratio(
            power_spectrogram,
            frequencies_hz,
            0.0,
            min(250.0, nyquist_hz),
        ),
        "band_energy_250_2000_hz": _band_energy_ratio(
            power_spectrogram,
            frequencies_hz,
            250.0,
            min(2000.0, nyquist_hz),
        ),
        "band_energy_2000_6000_hz": _band_energy_ratio(
            power_spectrogram,
            frequencies_hz,
            2000.0,
            min(6000.0, nyquist_hz),
        ),
        "band_energy_6000_nyquist": _band_energy_ratio(
            power_spectrogram,
            frequencies_hz,
            6000.0,
            nyquist_hz + 1.0,
        ),
    }


def _extract_extended_features(
    y: np.ndarray,
    sr: int,
    rms: np.ndarray,
    chroma: np.ndarray,
    duration_sec: float,
) -> Dict[str, float]:
    if duration_sec <= 0.0:
        return {
            "silence_rate": 0.0,
            "harmonic_stability": 0.0,
            "harmonic_change_rate_hz": 0.0,
            "spectral_flatness": 0.0,
            "high_frequency_energy_ratio": 0.0,
        }

    silence_threshold = max(
        1e-5,
        float(np.percentile(rms, 10)) * 0.5,
    )
    silence_rate = float(np.mean(rms <= silence_threshold))

    if chroma.shape[1] >= 2:
        chroma_norm = librosa.util.normalize(
            chroma,
            norm=2,
            axis=0,
        )
        cosine_similarity = np.sum(
            chroma_norm[:, 1:] * chroma_norm[:, :-1],
            axis=0,
        )
        cosine_similarity = np.clip(
            cosine_similarity,
            -1.0,
            1.0,
        )
        harmonic_stability = float(
            np.clip(np.mean(cosine_similarity), 0.0, 1.0)
        )
        harmonic_change_rate_hz = float(
            np.sum(cosine_similarity < 0.90)
            / duration_sec
        )
    else:
        harmonic_stability = 0.0
        harmonic_change_rate_hz = 0.0

    flatness = librosa.feature.spectral_flatness(
        y=y,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )[0]
    spectral_flatness = _safe_mean(flatness)

    high_frequency_energy_ratio = _extract_spectral_band_energies(
        y=y,
        sr=sr,
    )["band_energy_6000_nyquist"]

    return {
        "silence_rate": silence_rate,
        "harmonic_stability": harmonic_stability,
        "harmonic_change_rate_hz": harmonic_change_rate_hz,
        "spectral_flatness": spectral_flatness,
        "high_frequency_energy_ratio": high_frequency_energy_ratio,
    }


def analyze_audio_file(
    path: str,
    sr: int = ANALYSIS_SAMPLE_RATE_HZ,
) -> Dict[str, Any]:
    y, sr = librosa.load(path, sr=sr, mono=True)

    if y.size == 0:
        raise ValueError("Audio contains no samples")

    duration_sec = float(librosa.get_duration(y=y, sr=sr))

    rms = librosa.feature.rms(
        y=y,
        frame_length=N_FFT,
        hop_length=HOP_LENGTH,
    )[0]
    rms = np.asarray(rms, dtype=float)
    energy = _safe_mean(rms)

    bpm = _extract_tempo_bpm(y, sr)

    spec_centroid = librosa.feature.spectral_centroid(
        y=y,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )[0]
    spec_centroid = np.asarray(spec_centroid, dtype=float)
    spectral_centroid = _safe_mean(spec_centroid)

    nyquist_hz = sr / 2.0
    brightness = _safe_ratio(
        spectral_centroid,
        nyquist_hz,
    )

    onset_envelope = librosa.onset.onset_strength(
        y=y,
        sr=sr,
        hop_length=HOP_LENGTH,
    )
    onset_envelope = np.asarray(
        onset_envelope,
        dtype=float,
    )
    onset_rate_hz, onset_count = _extract_onset_rate_hz(
        onset_envelope=onset_envelope,
        sr=sr,
        duration_sec=duration_sec,
    )

    beat_regularity, beat_count = _extract_beat_regularity(
        y=y,
        sr=sr,
    )

    if rms.size > 0:
        low_rms = float(np.percentile(rms, 10))
        high_rms = float(np.percentile(rms, 90))
        dynamic_range_db = float(
            20.0
            * np.log10(max(high_rms, 1e-8))
            - 20.0
            * np.log10(max(low_rms, 1e-8))
        )
    else:
        dynamic_range_db = 0.0

    chroma = librosa.feature.chroma_stft(
        y=y,
        sr=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
    )
    chroma = np.asarray(chroma, dtype=float)

    if chroma.size > 0:
        chroma_mean = np.mean(chroma, axis=1)
        chroma_mean = np.asarray(chroma_mean, dtype=float)

        correlation = np.correlate(
            chroma_mean,
            chroma_mean,
            mode="full",
        )
        center_index = correlation.size // 2
        local_correlation = correlation[
            max(0, center_index - 2):
            min(correlation.size, center_index + 3)
        ]

        if (
            local_correlation.size > 0
            and np.max(local_correlation) > 0.0
        ):
            repetition_score = float(
                np.mean(
                    local_correlation
                    / np.max(local_correlation)
                )
            )
        else:
            repetition_score = 0.0
    else:
        repetition_score = 0.0

    pitch_classes = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B",
    ]

    if chroma.size > 0:
        dominant_pitch_class = int(
            np.argmax(np.mean(chroma, axis=1))
        )
        key = pitch_classes[dominant_pitch_class]
    else:
        key = "unknown"

    extended_features = _extract_extended_features(
        y=y,
        sr=sr,
        rms=rms,
        chroma=chroma,
        duration_sec=duration_sec,
    )
    band_energies = _extract_spectral_band_energies(
        y=y,
        sr=sr,
    )

    suggested_style = suggest_style(
        bpm=bpm,
        energy=energy,
        brightness=brightness,
        onset_rate_hz=onset_rate_hz,
        dynamic_range=dynamic_range_db,
        repetition_score=repetition_score,
    )

    sections = build_simple_sections(
        duration_sec=duration_sec,
        num_sections=6,
    )
    recurrence_groups = build_simple_recurrence_groups(
        sections=sections,
    )
    events = build_simple_events(
        rms=rms,
        duration_sec=duration_sec,
    )

    features: Dict[str, Any] = {
        "bpm": bpm,
        "key": key,
        "energy": energy,
        "spectral_centroid": spectral_centroid,
        "brightness": brightness,
        "onset_rate_hz": onset_rate_hz,
        "onset_count": onset_count,
        "beat_regularity": beat_regularity,
        "beat_count": beat_count,
        "dynamic_range": dynamic_range_db,
        "duration_sec": duration_sec,
        "repetition_score": repetition_score,
        "suggested_music_style": suggested_style,
        **extended_features,
        **band_energies,
        "sections": sections,
        "recurrence_groups": recurrence_groups,
        "events": events,
    }

    clean_features: Dict[str, Any] = {}

    for key_name, value in features.items():
        if key_name in {
            "sections",
            "recurrence_groups",
            "events",
        }:
            clean_features[key_name] = value
        else:
            clean_features[key_name] = _to_python_scalar(value)

    return clean_features


def suggest_style(
    bpm: float,
    energy: float,
    brightness: float,
    onset_rate_hz: float,
    dynamic_range: float,
    repetition_score: float,
) -> str:
    high_bpm = bpm > 140.0
    mid_bpm = 100.0 <= bpm <= 140.0
    low_bpm = bpm < 100.0

    high_energy = energy > 0.22
    mid_energy = 0.12 <= energy <= 0.22
    low_energy = energy < 0.12

    low_brightness = brightness < 0.10
    mid_brightness = 0.10 <= brightness <= 0.20
    high_brightness = brightness > 0.20

    high_onset_rate = onset_rate_hz > 2.5
    mid_onset_rate = 0.8 <= onset_rate_hz <= 2.5
    low_onset_rate = onset_rate_hz < 0.8

    wide_dynamic_range = dynamic_range > 12.0
    mid_dynamic_range = 8.0 <= dynamic_range <= 12.0
    narrow_dynamic_range = dynamic_range < 8.0

    if (
        mid_bpm
        and wide_dynamic_range
        and low_energy
        and low_brightness
        and repetition_score > 0.85
    ):
        return "blues"

    if (
        mid_bpm
        and wide_dynamic_range
        and (low_brightness or mid_brightness)
        and (low_energy or mid_energy)
    ):
        return "jazz"

    if (
        (low_bpm or mid_bpm)
        and wide_dynamic_range
        and low_brightness
        and low_energy
        and repetition_score < 0.85
    ):
        return "classical"

    if (
        (mid_bpm or high_bpm)
        and high_energy
        and (mid_brightness or high_brightness)
        and (mid_onset_rate or high_onset_rate)
    ):
        return "rock"

    if (
        mid_bpm
        and mid_energy
        and (mid_brightness or high_brightness)
        and mid_dynamic_range
        and mid_onset_rate
    ):
        return "pop"

    if (
        (high_bpm or high_onset_rate)
        and (mid_energy or high_energy)
    ):
        return "electronic"

    if (
        (low_bpm or mid_bpm)
        and (mid_dynamic_range or wide_dynamic_range)
        and (mid_energy or high_energy)
        and not low_brightness
    ):
        return "soundtrack"

    if (
        low_brightness
        and (mid_dynamic_range or narrow_dynamic_range)
        and (low_onset_rate or mid_onset_rate)
        and (low_bpm or mid_bpm)
    ):
        return "ambient"

    return "mixed"


def build_simple_sections(
    duration_sec: float,
    num_sections: int = 6,
) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []

    if duration_sec <= 0.0 or num_sections <= 0:
        return sections

    section_duration_sec = duration_sec / num_sections

    for index in range(num_sections):
        start_sec = float(index * section_duration_sec)
        end_sec = float(
            min(
                duration_sec,
                (index + 1) * section_duration_sec,
            )
        )

        sections.append(
            {
                "id": f"S{index + 1}",
                "label": f"Section {index + 1}",
                "start_sec": start_sec,
                "end_sec": end_sec,
            }
        )

    return sections


def build_simple_recurrence_groups(
    sections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    section_ids = [section["id"] for section in sections]
    groups: List[Dict[str, Any]] = []

    if len(section_ids) >= 3:
        groups.append(
            {
                "group_id": "G1",
                "sections": section_ids[0:3:2],
            }
        )

    if len(section_ids) >= 4:
        groups.append(
            {
                "group_id": "G2",
                "sections": section_ids[1:4:2],
            }
        )

    return groups


def build_simple_events(
    rms: np.ndarray,
    duration_sec: float,
) -> List[Dict[str, Any]]:
    rms = np.asarray(rms, dtype=float)
    events: List[Dict[str, Any]] = []

    if rms.size == 0 or duration_sec <= 0.0:
        return events

    threshold = float(np.percentile(rms, 95))
    peak_indices = np.argwhere(rms > threshold).flatten()

    if peak_indices.size == 0:
        return events

    for index in peak_indices[:5]:
        time_sec = float(
            int(index)
            * duration_sec
            / rms.size
        )
        events.append(
            {
                "type": "energy_peak",
                "time_sec": time_sec,
                "description": "High energy frame",
            }
        )

    return events


def build_perceptual_latent(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    energy = float(features.get("energy", 0.0))
    onset_rate_hz = float(
        features.get("onset_rate_hz", 0.0)
    )
    brightness = float(features.get("brightness", 0.0))
    repetition_score = float(
        features.get("repetition_score", 0.0)
    )
    dynamic_range = float(
        features.get("dynamic_range", 0.0)
    )

    sections = features.get("sections", []) or []
    events = features.get("events", []) or []

    tension = float(
        np.clip(dynamic_range / 20.0, 0.0, 1.0)
    )

    density = float(
        np.clip(onset_rate_hz / 5.0, 0.0, 1.0)
    )

    stability = float(
        np.clip(1.0 - tension, 0.0, 1.0)
    )

    smoothness = float(
        np.clip(1.0 - len(events) / 10.0, 0.0, 1.0)
    )

    section_complexity = float(
        np.clip(len(sections) / 10.0, 0.0, 1.0)
    )

    if len(sections) >= 3:
        macro_shape_hint = "ABA_like"
    elif len(sections) == 1:
        macro_shape_hint = "linear"
    else:
        macro_shape_hint = "unknown"

    return {
        "energy": energy,
        "tension": tension,
        "density": density,
        "brightness": brightness,
        "stability": stability,
        "smoothness": smoothness,
        "repetition": repetition_score,
        "section_complexity": section_complexity,
        "macro_shape_hint": macro_shape_hint,
        "tempo_bpm": float(features.get("bpm", 0.0)),
        "silence_rate": float(
            features.get("silence_rate", 0.0)
        ),
        "harmonic_stability": float(
            features.get("harmonic_stability", 0.0)
        ),
        "harmonic_change_rate_hz": float(
            features.get(
                "harmonic_change_rate_hz",
                0.0,
            )
        ),
        "spectral_flatness": float(
            features.get("spectral_flatness", 0.0)
        ),
        "high_frequency_energy_ratio": float(
            features.get(
                "high_frequency_energy_ratio",
                0.0,
            )
        ),
        "onset_rate_hz": onset_rate_hz,
        "beat_regularity": float(
            features.get("beat_regularity", 0.0)
        ),
        "band_energy_0_250_hz": float(
            features.get(
                "band_energy_0_250_hz",
                0.0,
            )
        ),
        "band_energy_250_2000_hz": float(
            features.get(
                "band_energy_250_2000_hz",
                0.0,
            )
        ),
        "band_energy_2000_6000_hz": float(
            features.get(
                "band_energy_2000_6000_hz",
                0.0,
            )
        ),
        "band_energy_6000_nyquist": float(
            features.get(
                "band_energy_6000_nyquist",
                0.0,
            )
        ),
    }