import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import librosa
import numpy as np

from lib.audio_analysis.analysis import (
    ANALYSIS_SAMPLE_RATE_HZ,
    analyze_audio_file,
)

AUDIO_DIR = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_TRACKS = 10
WINDOW_SEC = 60.0
EPS = 1e-12

FEATURES_TO_EVALUATE = [
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


def fail(message: str) -> None:
    print(f"\n❌ {message}")
    sys.exit(1)


def as_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def format_number(value: Any, digits: int = 6) -> str:
    number = as_float(value)
    return "" if number is None else f"{number:.{digits}f}"


def sample_standard_deviation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0

    mean_value = sum(values) / len(values)
    variance = sum(
        (value - mean_value) ** 2
        for value in values
    ) / (len(values) - 1)

    return math.sqrt(variance)


def coefficient_of_variation(values: list[float]) -> float:
    if not values:
        return 0.0

    mean_value = sum(values) / len(values)
    std_value = sample_standard_deviation(values)

    if abs(mean_value) <= EPS:
        return 0.0 if std_value <= EPS else float("inf")

    return std_value / abs(mean_value)


def get_test_tracks() -> list[Path]:
    tracks = sorted(
        AUDIO_DIR.glob("*.mp3"),
        key=lambda path: path.name.lower(),
    )

    if len(tracks) < MAX_TRACKS:
        fail(
            f"Найдено MP3: {len(tracks)}. "
            f"Для Test7 требуется минимум: {MAX_TRACKS}."
        )

    return tracks[:MAX_TRACKS]


def get_window_specs(duration_sec: float) -> list[dict[str, float | str]]:
    if duration_sec <= 0.0:
        return []

    window_sec = min(WINDOW_SEC, duration_sec)
    max_start_sec = max(0.0, duration_sec - window_sec)

    return [
        {
            "window_id": "start",
            "start_sec": 0.0,
            "end_sec": window_sec,
        },
        {
            "window_id": "middle",
            "start_sec": max_start_sec / 2.0,
            "end_sec": max_start_sec / 2.0 + window_sec,
        },
        {
            "window_id": "end",
            "start_sec": max_start_sec,
            "end_sec": duration_sec,
        },
    ]


def analyze_signal_window(
    y: np.ndarray,
    sr: int,
    source_name: str,
    window_id: str,
    start_sec: float,
    end_sec: float,
    temp_dir: Path,
) -> dict[str, Any]:
    start_sample = max(0, int(round(start_sec * sr)))
    end_sample = min(y.size, int(round(end_sec * sr)))

    if end_sample <= start_sample:
        raise ValueError(
            f"{source_name}/{window_id}: пустое окно "
            f"{start_sec:.3f}..{end_sec:.3f} s"
        )

    segment = np.asarray(
        y[start_sample:end_sample],
        dtype=np.float32,
    )

    temp_path = temp_dir / f"{source_name}__{window_id}.wav"

    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(
            "Не найден пакет soundfile. "
            "Установите: pip install soundfile"
        ) from exc

    sf.write(temp_path, segment, sr, subtype="PCM_16")

    try:
        features = analyze_audio_file(
            str(temp_path),
            sr=sr,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return features


def validate_features(
    track_name: str,
    window_id: str,
    features: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for feature_name in FEATURES_TO_EVALUATE:
        value = as_float(features.get(feature_name))

        if value is None:
            errors.append(
                f"{track_name}/{window_id}: "
                f"{feature_name} не является finite-числом"
            )
            continue

        if value < 0.0:
            errors.append(
                f"{track_name}/{window_id}: "
                f"{feature_name} < 0: {value}"
            )

    band_sum = sum(
        as_float(features.get(feature_name)) or 0.0
        for feature_name in BAND_FEATURES
    )

    if not 0.999 <= band_sum <= 1.001:
        errors.append(
            f"{track_name}/{window_id}: сумма полос "
            f"{band_sum:.8f}, ожидалось 0.999..1.001"
        )

    return errors


def make_window_row(
    track_name: str,
    window_id: str,
    start_sec: float,
    end_sec: float,
    full_duration_sec: float,
    features: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "file": track_name,
        "window_id": window_id,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "window_duration_sec": end_sec - start_sec,
        "source_duration_sec": full_duration_sec,
        "suggested_music_style": features.get(
            "suggested_music_style",
            "",
        ),
    }

    for feature_name in FEATURES_TO_EVALUATE:
        row[feature_name] = features.get(feature_name)

    row["band_energy_sum"] = sum(
        as_float(features.get(feature_name)) or 0.0
        for feature_name in BAND_FEATURES
    )

    return row


def calculate_within_track_summary(
    window_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in window_rows:
        grouped.setdefault(str(row["file"]), []).append(row)

    summary_rows: list[dict[str, Any]] = []

    for track_name, track_rows in grouped.items():
        distinct_starts = {
            round(float(row["start_sec"]), 6)
            for row in track_rows
        }

        for feature_name in FEATURES_TO_EVALUATE:
            values = [
                as_float(row.get(feature_name))
                for row in track_rows
            ]
            values = [
                value
                for value in values
                if value is not None
            ]

            if not values:
                continue

            mean_value = sum(values) / len(values)
            std_value = sample_standard_deviation(values)
            cv_value = coefficient_of_variation(values)

            summary_rows.append(
                {
                    "file": track_name,
                    "feature": feature_name,
                    "window_count": len(values),
                    "distinct_window_positions": len(distinct_starts),
                    "mean": mean_value,
                    "std": std_value,
                    "cv_within_track": cv_value,
                    "min": min(values),
                    "max": max(values),
                    "range": max(values) - min(values),
                }
            )

    return summary_rows


def calculate_feature_separation(
    full_features: list[dict[str, Any]],
    within_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result_rows: list[dict[str, Any]] = []

    for feature_name in FEATURES_TO_EVALUATE:
        full_values = [
            as_float(row.get(feature_name))
            for row in full_features
        ]
        full_values = [
            value
            for value in full_values
            if value is not None
        ]

        within_cvs = [
            as_float(row.get("cv_within_track"))
            for row in within_summary
            if row.get("feature") == feature_name
            and int(row.get("distinct_window_positions", 0)) >= 2
        ]
        within_cvs = [
            value
            for value in within_cvs
            if value is not None and math.isfinite(value)
        ]

        if not full_values:
            continue

        between_mean = sum(full_values) / len(full_values)
        between_std = sample_standard_deviation(full_values)
        between_cv = coefficient_of_variation(full_values)

        median_within_cv = (
            float(np.median(np.asarray(within_cvs, dtype=float)))
            if within_cvs
            else 0.0
        )

        if median_within_cv <= EPS:
            separation_ratio = (
                float("inf")
                if between_cv > EPS
                else 0.0
            )
        else:
            separation_ratio = between_cv / median_within_cv

        if separation_ratio >= 3.0:
            verdict = "strong_candidate"
        elif separation_ratio >= 1.5:
            verdict = "diagnostic_candidate"
        else:
            verdict = "not_stable_enough"

        result_rows.append(
            {
                "feature": feature_name,
                "track_count": len(full_values),
                "between_mean": between_mean,
                "between_std": between_std,
                "between_cv": between_cv,
                "median_within_cv": median_within_cv,
                "separation_ratio": separation_ratio,
                "verdict": verdict,
            }
        )

    return result_rows


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
    full_rows: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    within_summary: list[dict[str, Any]],
    separation_rows: list[dict[str, Any]],
    errors: list[str],
) -> tuple[Path, Path, Path, Path]:
    json_path = OUTPUT_DIR / f"test7_window_features_{timestamp}.json"
    windows_csv_path = OUTPUT_DIR / f"test7_window_matrix_{timestamp}.csv"
    stability_csv_path = (
        OUTPUT_DIR / f"test7_stability_summary_{timestamp}.csv"
    )
    markdown_path = OUTPUT_DIR / f"test7_report_{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "test_name": "test7_window_stability_v0_4",
                "created_at_local": timestamp,
                "window_sec": WINDOW_SEC,
                "full_track_features": full_rows,
                "window_features": window_rows,
                "within_track_summary": within_summary,
                "feature_separation": separation_rows,
                "validation_errors": errors,
            },
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    window_fieldnames = [
        "file",
        "window_id",
        "start_sec",
        "end_sec",
        "window_duration_sec",
        "source_duration_sec",
        "suggested_music_style",
        *FEATURES_TO_EVALUATE,
        "band_energy_sum",
    ]
    write_csv(
        path=windows_csv_path,
        rows=window_rows,
        fieldnames=window_fieldnames,
    )

    stability_fieldnames = [
        "feature",
        "track_count",
        "between_mean",
        "between_std",
        "between_cv",
        "median_within_cv",
        "separation_ratio",
        "verdict",
    ]
    write_csv(
        path=stability_csv_path,
        rows=separation_rows,
        fieldnames=stability_fieldnames,
    )

    lines = [
        "# Test7 — Window Stability v0.4",
        "",
        f"Время запуска: `{timestamp}`",
        "",
        "## Статус",
        "",
        f"- Полных треков: **{len(full_rows)}**",
        f"- Анализов временных окон: **{len(window_rows)}**",
        f"- Ошибок contract/range: **{len(errors)}**",
        f"- Длина целевого окна: **{WINDOW_SEC:.1f} s**",
        "",
        "## Устойчивость и разделимость",
        "",
        "| Признак | Межтрековый CV | Median внутритрековый CV | "
        "Отношение | Вердикт |",
        "|---|---:|---:|---:|---|",
    ]

    for row in separation_rows:
        ratio = row["separation_ratio"]
        ratio_text = (
            "inf"
            if isinstance(ratio, float) and math.isinf(ratio)
            else format_number(ratio)
        )

        lines.append(
            "| "
            f"`{row['feature']}` | "
            f"{format_number(row['between_cv'])} | "
            f"{format_number(row['median_within_cv'])} | "
            f"{ratio_text} | "
            f"{row['verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Окна",
            "",
            "| Файл | Окно | Start, s | End, s | Длительность, s | Стиль |",
            "|---|---|---:|---:|---:|---|",
        ]
    )

    for row in window_rows:
        lines.append(
            "| "
            f"{row['file']} | "
            f"{row['window_id']} | "
            f"{format_number(row['start_sec'], 3)} | "
            f"{format_number(row['end_sec'], 3)} | "
            f"{format_number(row['window_duration_sec'], 3)} | "
            f"{row['suggested_music_style']} |"
        )

    lines.extend(
        [
            "",
            "## Ограничения",
            "",
            "- Для треков короче 60 s окна start, middle и end могут "
            "совпадать полностью или частично; такие треки исключаются "
            "из медианы внутритрекового CV, если имеют только одну "
            "уникальную позицию окна.",
            "- Test7 не использует FastAPI, SQLite, renderer или "
            "style-engine; он оценивает только повторяемость "
            "аудиоизмерений на фрагментах.",
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
        windows_csv_path,
        stability_csv_path,
        markdown_path,
    )


def main() -> None:
    tracks = get_test_tracks()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = OUTPUT_DIR / f"_test7_temp_{timestamp}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    full_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    runtime_errors: list[str] = []

    print("\n" + "=" * 80)
    print("TEST7 — WINDOW STABILITY v0.4")
    print("=" * 80)
    print(f"Треков в тесте: {len(tracks)}")
    print(f"Целевое окно: {WINDOW_SEC:.1f} s")

    try:
        for index, audio_path in enumerate(tracks, start=1):
            print("\n" + "-" * 80)
            print(f"[{index}/{len(tracks)}] 🎵 {audio_path.name}")

            try:
                full_features = analyze_audio_file(
                    str(audio_path),
                    sr=ANALYSIS_SAMPLE_RATE_HZ,
                )

                full_duration = as_float(
                    full_features.get("duration_sec")
                )

                if full_duration is None or full_duration <= 0.0:
                    raise ValueError(
                        "анализ полного трека вернул "
                        "некорректную duration_sec"
                    )

                full_rows.append(
                    {
                        "file": audio_path.name,
                        **{
                            feature_name: full_features.get(feature_name)
                            for feature_name in FEATURES_TO_EVALUATE
                        },
                    }
                )

                y, sr = librosa.load(
                    str(audio_path),
                    sr=ANALYSIS_SAMPLE_RATE_HZ,
                    mono=True,
                )

                if y.size == 0:
                    raise ValueError("пустой аудиосигнал")

                specs = get_window_specs(full_duration)

                for spec in specs:
                    window_id = str(spec["window_id"])
                    start_sec = float(spec["start_sec"])
                    end_sec = float(spec["end_sec"])

                    features = analyze_signal_window(
                        y=y,
                        sr=sr,
                        source_name=audio_path.stem,
                        window_id=window_id,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        temp_dir=temp_dir,
                    )

                    errors = validate_features(
                        track_name=audio_path.name,
                        window_id=window_id,
                        features=features,
                    )
                    validation_errors.extend(errors)

                    row = make_window_row(
                        track_name=audio_path.name,
                        window_id=window_id,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        full_duration_sec=full_duration,
                        features=features,
                    )
                    window_rows.append(row)

                    print(
                        f"  {window_id:>6}: "
                        f"{start_sec:7.2f}..{end_sec:7.2f} s | "
                        f"bpm={format_number(row['bpm'], 2)} | "
                        f"onsets={format_number(row['onset_rate_hz'], 3)} Hz | "
                        f"regularity="
                        f"{format_number(row['beat_regularity'], 4)}"
                    )

                print(
                    f"  full: duration={full_duration:.2f} s | "
                    f"style={full_features.get('suggested_music_style', '')}"
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
            for temp_path in temp_dir.glob("*"):
                if temp_path.is_file():
                    temp_path.unlink()
            temp_dir.rmdir()

    if runtime_errors:
        print("\n" + "=" * 80)
        print("КРИТИЧЕСКИЕ ОШИБКИ")
        print("=" * 80)

        for error in runtime_errors:
            print(f"- {error}")

        fail(
            "Test7 не завершён: не все треки "
            "прошли оконный анализ."
        )

    within_summary = calculate_within_track_summary(window_rows)
    separation_rows = calculate_feature_separation(
        full_features=full_rows,
        within_summary=within_summary,
    )

    (
        json_path,
        windows_csv_path,
        stability_csv_path,
        markdown_path,
    ) = write_reports(
        timestamp=timestamp,
        full_rows=full_rows,
        window_rows=window_rows,
        within_summary=within_summary,
        separation_rows=separation_rows,
        errors=validation_errors,
    )

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ TEST7")
    print("=" * 80)
    print(f"Полных треков: {len(full_rows)}")
    print(f"Оконных анализов: {len(window_rows)}")
    print(f"Ошибок валидации: {len(validation_errors)}")
    print("\nОтчёты:")
    print(f" JSON: {json_path}")
    print(f" CSV:  {windows_csv_path}")
    print(f" CSV:  {stability_csv_path}")
    print(f" MD:   {markdown_path}")

    if validation_errors:
        print(
            "\n⚠️ Test7 завершён, но найдены нарушения "
            "численных инвариантов."
        )
        sys.exit(2)

    print(
        "\n✅ Test7 завершён без ошибок. "
        "Признаки остаются диагностическими."
    )


if __name__ == "__main__":
    main()