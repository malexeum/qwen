import csv
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf

from lib.audio_analysis.analysis import (
    ANALYSIS_SAMPLE_RATE_HZ,
    HOP_LENGTH,
    N_FFT,
    analyze_audio_file,
)

AUDIO_DIR = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_TRACKS = 10
EPS = 1e-12

REFERENCE_SR = ANALYSIS_SAMPLE_RATE_HZ
TEST_SAMPLE_RATES_HZ = [44100, 22050]

FEATURES_TO_COMPARE = [
    "bpm",
    "energy",
    "spectral_centroid",
    "brightness",
    "onset_rate_hz",
    "beat_regularity",
    "dynamic_range",
    "repetition_score",
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate_hz",
    "spectral_flatness",
    "high_frequency_energy_ratio",
    "band_energy_0_250_hz",
    "band_energy_250_2000_hz",
    "band_energy_2000_6000_hz",
    "band_energy_6000_nyquist",
]

BAND_FEATURES = [
    "band_energy_0_250_hz",
    "band_energy_250_2000_hz",
    "band_energy_2000_6000_hz",
    "band_energy_6000_nyquist",
]

STFT_CONFIGS = [
    {
        "config_id": "fft2048_hop512",
        "n_fft": 2048,
        "hop_length": 512,
    },
    {
        "config_id": "fft4096_hop1024",
        "n_fft": 4096,
        "hop_length": 1024,
    },
]


def fail(message: str) -> None:
    print(f"\n❌ {message}")
    sys.exit(1)


def as_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if math.isfinite(result) else None


def format_number(value: Any, digits: int = 6) -> str:
    number = as_float(value)

    if number is None:
        return ""

    if math.isinf(number):
        return "inf"

    return f"{number:.{digits}f}"


def get_test_tracks() -> list[Path]:
    tracks = sorted(
        AUDIO_DIR.glob("*.mp3"),
        key=lambda path: path.name.lower(),
    )

    if len(tracks) < MAX_TRACKS:
        fail(
            f"Найдено MP3: {len(tracks)}. "
            f"Для Test8 требуется минимум: {MAX_TRACKS}."
        )

    return tracks[:MAX_TRACKS]


def validate_feature_dict(
    track_name: str,
    mode_name: str,
    features: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for feature_name in FEATURES_TO_COMPARE:
        value = as_float(features.get(feature_name))

        if value is None:
            errors.append(
                f"{track_name}/{mode_name}: {feature_name} "
                "не является finite-числом"
            )
            continue

        if value < 0.0:
            errors.append(
                f"{track_name}/{mode_name}: {feature_name} < 0: {value}"
            )

    band_sum = sum(
        as_float(features.get(feature_name)) or 0.0
        for feature_name in BAND_FEATURES
    )

    if not 0.999 <= band_sum <= 1.001:
        errors.append(
            f"{track_name}/{mode_name}: сумма полос "
            f"{band_sum:.8f}; ожидалось 0.999..1.001"
        )

    return errors


def resample_to_wav(
    source_path: Path,
    target_path: Path,
    sample_rate_hz: int,
) -> None:
    y, sr = librosa.load(
        str(source_path),
        sr=sample_rate_hz,
        mono=True,
    )

    if y.size == 0:
        raise ValueError("пустой аудиосигнал")

    sf.write(
        str(target_path),
        np.asarray(y, dtype=np.float32),
        sr,
        subtype="PCM_16",
    )


def spectral_band_energies(
    y: np.ndarray,
    sr: int,
    n_fft: int,
    hop_length: int,
) -> dict[str, float]:
    stft = librosa.stft(
        y=y,
        n_fft=n_fft,
        hop_length=hop_length,
        window="hann",
        center=True,
    )
    power = np.abs(stft) ** 2
    frequencies_hz = librosa.fft_frequencies(
        sr=sr,
        n_fft=n_fft,
    )
    total_power = float(np.sum(power))

    if total_power <= 0.0:
        return {
            feature_name: 0.0
            for feature_name in BAND_FEATURES
        }

    nyquist_hz = sr / 2.0

    intervals = {
        "band_energy_0_250_hz": (0.0, min(250.0, nyquist_hz)),
        "band_energy_250_2000_hz": (
            250.0,
            min(2000.0, nyquist_hz),
        ),
        "band_energy_2000_6000_hz": (
            2000.0,
            min(6000.0, nyquist_hz),
        ),
        "band_energy_6000_nyquist": (6000.0, nyquist_hz + 1.0),
    }

    result: dict[str, float] = {}

    for feature_name, (low_hz, high_hz) in intervals.items():
        mask = (
            (frequencies_hz >= low_hz)
            & (frequencies_hz < high_hz)
        )

        if not np.any(mask):
            result[feature_name] = 0.0
            continue

        band_power = float(np.sum(power[mask, :]))
        result[feature_name] = float(
            np.clip(band_power / total_power, 0.0, 1.0)
        )

    return result


def spearman_rank_correlation(
    reference_values: list[float],
    test_values: list[float],
) -> float:
    if len(reference_values) != len(test_values):
        raise ValueError("Размеры массивов не совпадают")

    if len(reference_values) < 3:
        return 0.0

    reference_array = np.asarray(reference_values, dtype=float)
    test_array = np.asarray(test_values, dtype=float)

    if (
        not np.all(np.isfinite(reference_array))
        or not np.all(np.isfinite(test_array))
    ):
        return 0.0

    if (
        np.allclose(reference_array, reference_array[0])
        or np.allclose(test_array, test_array[0])
    ):
        return 0.0

    reference_ranks = librosa.util.normalize(
        np.argsort(np.argsort(reference_array)).astype(float),
        norm=2,
    )
    test_ranks = librosa.util.normalize(
        np.argsort(np.argsort(test_array)).astype(float),
        norm=2,
    )

    correlation = float(
        np.corrcoef(reference_ranks, test_ranks)[0, 1]
    )

    return correlation if math.isfinite(correlation) else 0.0


def relative_difference(
    reference: float,
    test: float,
) -> float:
    scale = max(abs(reference), EPS)
    return abs(test - reference) / scale


def summarize_resampling(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    for feature_name in FEATURES_TO_COMPARE:
        reference_values: list[float] = []
        test_values: list[float] = []
        relative_differences: list[float] = []

        for row in rows:
            reference = as_float(
                row.get(f"ref_{feature_name}")
            )
            test = as_float(
                row.get(f"test_{feature_name}")
            )

            if reference is None or test is None:
                continue

            reference_values.append(reference)
            test_values.append(test)
            relative_differences.append(
                relative_difference(reference, test)
            )

        if not reference_values:
            continue

        median_relative_difference = float(
            np.median(
                np.asarray(relative_differences, dtype=float)
            )
        )
        max_relative_difference = max(relative_differences)
        spearman_rho = spearman_rank_correlation(
            reference_values,
            test_values,
        )

        if (
            spearman_rho >= 0.95
            and median_relative_difference <= 0.10
        ):
            verdict = "stable"
        elif (
            spearman_rho >= 0.80
            and median_relative_difference <= 0.25
        ):
            verdict = "diagnostic_only"
        else:
            verdict = "parameter_sensitive"

        summaries.append(
            {
                "feature": feature_name,
                "track_count": len(reference_values),
                "median_relative_difference": (
                    median_relative_difference
                ),
                "max_relative_difference": (
                    max_relative_difference
                ),
                "spearman_rank_correlation": spearman_rho,
                "verdict": verdict,
            }
        )

    return summaries


def summarize_stft(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    for feature_name in BAND_FEATURES:
        reference_values: list[float] = []
        test_values: list[float] = []
        absolute_differences: list[float] = []

        for row in rows:
            reference = as_float(
                row.get(f"fft2048_hop512_{feature_name}")
            )
            test = as_float(
                row.get(f"fft4096_hop1024_{feature_name}")
            )

            if reference is None or test is None:
                continue

            reference_values.append(reference)
            test_values.append(test)
            absolute_differences.append(abs(test - reference))

        if not reference_values:
            continue

        median_absolute_difference = float(
            np.median(
                np.asarray(absolute_differences, dtype=float)
            )
        )
        max_absolute_difference = max(absolute_differences)
        spearman_rho = spearman_rank_correlation(
            reference_values,
            test_values,
        )

        if (
            spearman_rho >= 0.95
            and median_absolute_difference <= 0.02
        ):
            verdict = "stable"
        elif (
            spearman_rho >= 0.80
            and median_absolute_difference <= 0.05
        ):
            verdict = "diagnostic_only"
        else:
            verdict = "parameter_sensitive"

        summaries.append(
            {
                "feature": feature_name,
                "track_count": len(reference_values),
                "median_absolute_difference": (
                    median_absolute_difference
                ),
                "max_absolute_difference": (
                    max_absolute_difference
                ),
                "spearman_rank_correlation": spearman_rho,
                "verdict": verdict,
            }
        )

    return summaries


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def write_reports(
    timestamp: str,
    resampling_rows: list[dict[str, Any]],
    resampling_summary: list[dict[str, Any]],
    stft_rows: list[dict[str, Any]],
    stft_summary: list[dict[str, Any]],
    errors: list[str],
) -> tuple[Path, Path, Path, Path]:
    json_path = OUTPUT_DIR / f"test8_parameter_stability_{timestamp}.json"
    resampling_csv_path = (
        OUTPUT_DIR / f"test8_resampling_matrix_{timestamp}.csv"
    )
    stft_csv_path = (
        OUTPUT_DIR / f"test8_stft_band_matrix_{timestamp}.csv"
    )
    markdown_path = OUTPUT_DIR / f"test8_report_{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "test_name": "test8_parameter_stability_v0_4",
                "created_at_local": timestamp,
                "reference_sample_rate_hz": REFERENCE_SR,
                "test_sample_rates_hz": TEST_SAMPLE_RATES_HZ,
                "stft_configs": STFT_CONFIGS,
                "resampling_rows": resampling_rows,
                "resampling_summary": resampling_summary,
                "stft_rows": stft_rows,
                "stft_summary": stft_summary,
                "validation_errors": errors,
            },
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    resampling_fieldnames = [
        "file",
        "reference_sr_hz",
        "test_sr_hz",
        *[
            f"ref_{feature_name}"
            for feature_name in FEATURES_TO_COMPARE
        ],
        *[
            f"test_{feature_name}"
            for feature_name in FEATURES_TO_COMPARE
        ],
    ]
    write_csv(
        path=resampling_csv_path,
        rows=resampling_rows,
        fieldnames=resampling_fieldnames,
    )

    stft_fieldnames = [
        "file",
        "sample_rate_hz",
        *[
            f"{config['config_id']}_{feature_name}"
            for config in STFT_CONFIGS
            for feature_name in BAND_FEATURES
        ],
        "fft2048_hop512_band_sum",
        "fft4096_hop1024_band_sum",
    ]
    write_csv(
        path=stft_csv_path,
        rows=stft_rows,
        fieldnames=stft_fieldnames,
    )

    lines = [
        "# Test8 — Parameter Stability v0.4",
        "",
        f"Время запуска: `{timestamp}`",
        "",
        "## Статус",
        "",
        f"- Треков: **{len(resampling_rows)}**",
        f"- Ошибок contract/range: **{len(errors)}**",
        f"- Reference sample rate: **{REFERENCE_SR} Hz**",
        "- Test sample rate: **22050 Hz**",
        "- Reference STFT: **N_FFT=2048, hop_length=512**",
        "- Test STFT: **N_FFT=4096, hop_length=1024**",
        "",
        "## Устойчивость к ресемплингу",
        "",
        "| Признак | Median относительное изменение | "
        "Max относительное изменение | Spearman rho | Вердикт |",
        "|---|---:|---:|---:|---|",
    ]

    for row in resampling_summary:
        lines.append(
            "| "
            f"`{row['feature']}` | "
            f"{format_number(row['median_relative_difference'])} | "
            f"{format_number(row['max_relative_difference'])} | "
            f"{format_number(row['spearman_rank_correlation'])} | "
            f"{row['verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Устойчивость полос к STFT",
            "",
            "| Полоса | Median абсолютное изменение | "
            "Max абсолютное изменение | Spearman rho | Вердикт |",
            "|---|---:|---:|---:|---|",
        ]
    )

    for row in stft_summary:
        lines.append(
            "| "
            f"`{row['feature']}` | "
            f"{format_number(row['median_absolute_difference'])} | "
            f"{format_number(row['max_absolute_difference'])} | "
            f"{format_number(row['spearman_rank_correlation'])} | "
            f"{row['verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Интерпретация",
            "",
            "- `stable`: rho >= 0.95 и малое численное изменение; "
            "признак устойчив к выбранному изменению процедуры.",
            "- `diagnostic_only`: ранжирование в основном сохраняется, "
            "но абсолютные значения заметно чувствительны.",
            "- `parameter_sensitive`: признак существенно зависит от "
            "ресемплинга или STFT-конфигурации.",
            "",
            "## Ошибки",
            "",
        ]
    )

    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append(
            "- Ошибок finite-значений, диапазонов и нормировки "
            "спектральных полос не обнаружено."
        )

    with markdown_path.open("w", encoding="utf-8") as output_file:
        output_file.write("\n".join(lines) + "\n")

    return (
        json_path,
        resampling_csv_path,
        stft_csv_path,
        markdown_path,
    )


def main() -> None:
    tracks = get_test_tracks()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = OUTPUT_DIR / f"_test8_temp_{timestamp}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    resampling_rows: list[dict[str, Any]] = []
    stft_rows: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    runtime_errors: list[str] = []

    print("\n" + "=" * 80)
    print("TEST8 — PARAMETER STABILITY v0.4")
    print("=" * 80)
    print(f"Треков в тесте: {len(tracks)}")
    print(
        "Ресемплинг: "
        f"{REFERENCE_SR} Hz -> 22050 Hz"
    )
    print(
        "STFT: "
        f"N_FFT={N_FFT}, hop={HOP_LENGTH} "
        "vs N_FFT=4096, hop=1024"
    )

    try:
        for index, audio_path in enumerate(tracks, start=1):
            print("\n" + "-" * 80)
            print(f"[{index}/{len(tracks)}] 🎵 {audio_path.name}")

            try:
                reference_wav = (
                    temp_dir
                    / f"{audio_path.stem}__{REFERENCE_SR}.wav"
                )
                test_wav = (
                    temp_dir
                    / f"{audio_path.stem}__22050.wav"
                )

                resample_to_wav(
                    source_path=audio_path,
                    target_path=reference_wav,
                    sample_rate_hz=REFERENCE_SR,
                )
                resample_to_wav(
                    source_path=audio_path,
                    target_path=test_wav,
                    sample_rate_hz=22050,
                )

                reference_features = analyze_audio_file(
                    str(reference_wav),
                    sr=REFERENCE_SR,
                )
                test_features = analyze_audio_file(
                    str(test_wav),
                    sr=22050,
                )

                validation_errors.extend(
                    validate_feature_dict(
                        track_name=audio_path.name,
                        mode_name=f"sr_{REFERENCE_SR}",
                        features=reference_features,
                    )
                )
                validation_errors.extend(
                    validate_feature_dict(
                        track_name=audio_path.name,
                        mode_name="sr_22050",
                        features=test_features,
                    )
                )

                resampling_row: dict[str, Any] = {
                    "file": audio_path.name,
                    "reference_sr_hz": REFERENCE_SR,
                    "test_sr_hz": 22050,
                }

                for feature_name in FEATURES_TO_COMPARE:
                    resampling_row[
                        f"ref_{feature_name}"
                    ] = reference_features.get(feature_name)
                    resampling_row[
                        f"test_{feature_name}"
                    ] = test_features.get(feature_name)

                resampling_rows.append(resampling_row)

                y, sr = librosa.load(
                    str(reference_wav),
                    sr=REFERENCE_SR,
                    mono=True,
                )

                stft_row: dict[str, Any] = {
                    "file": audio_path.name,
                    "sample_rate_hz": sr,
                }

                for config in STFT_CONFIGS:
                    bands = spectral_band_energies(
                        y=y,
                        sr=sr,
                        n_fft=int(config["n_fft"]),
                        hop_length=int(config["hop_length"]),
                    )

                    config_id = str(config["config_id"])

                    for feature_name in BAND_FEATURES:
                        stft_row[
                            f"{config_id}_{feature_name}"
                        ] = bands[feature_name]

                    stft_row[
                        f"{config_id}_band_sum"
                    ] = sum(bands.values())

                stft_rows.append(stft_row)

                print(
                    f"  SR: bpm "
                    f"{format_number(reference_features['bpm'], 2)} -> "
                    f"{format_number(test_features['bpm'], 2)} | "
                    f"onsets "
                    f"{format_number(reference_features['onset_rate_hz'], 3)} -> "
                    f"{format_number(test_features['onset_rate_hz'], 3)} Hz"
                )

                print(
                    "  bands 2-6 kHz: "
                    f"{format_number(stft_row['fft2048_hop512_band_energy_2000_6000_hz'], 5)} -> "
                    f"{format_number(stft_row['fft4096_hop1024_band_energy_2000_6000_hz'], 5)}"
                )

            except (
                OSError,
                RuntimeError,
                ValueError,
                librosa.util.exceptions.ParameterError,
            ) as exc:
                message = f"{audio_path.name}: {exc}"
                runtime_errors.append(message)
                print(f"  ❌ {message}")

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    if runtime_errors:
        print("\n" + "=" * 80)
        print("КРИТИЧЕСКИЕ ОШИБКИ")
        print("=" * 80)

        for error in runtime_errors:
            print(f"- {error}")

        fail(
            "Test8 не завершён: не все треки "
            "прошли проверку параметров."
        )

    resampling_summary = summarize_resampling(resampling_rows)
    stft_summary = summarize_stft(stft_rows)

    (
        json_path,
        resampling_csv_path,
        stft_csv_path,
        markdown_path,
    ) = write_reports(
        timestamp=timestamp,
        resampling_rows=resampling_rows,
        resampling_summary=resampling_summary,
        stft_rows=stft_rows,
        stft_summary=stft_summary,
        errors=validation_errors,
    )

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ TEST8")
    print("=" * 80)
    print(f"Треков: {len(resampling_rows)}")
    print(f"Ошибок валидации: {len(validation_errors)}")
    print("\nОтчёты:")
    print(f" JSON: {json_path}")
    print(f" CSV:  {resampling_csv_path}")
    print(f" CSV:  {stft_csv_path}")
    print(f" MD:   {markdown_path}")

    if validation_errors:
        print(
            "\n⚠️ Test8 завершён, но обнаружены "
            "нарушения численных инвариантов."
        )
        sys.exit(2)

    print(
        "\n✅ Test8 завершён без ошибок. "
        "Признаки по-прежнему не подключены к renderer."
    )


if __name__ == "__main__":
    main()