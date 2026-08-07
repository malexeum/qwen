import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
AUDIO_DIR = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT_SEC = 240
MAX_TRACKS = 10

KNOWN_EXPECTED_STYLES = {
    "03 - 99 Miles from LA.mp3": "jazz",
    "04 - Autumn Leaves.mp3": "jazz",
    "Action_Movie.mp3": "electronic",
    "caravan - Ella.mp3": "soundtrack",
    "Front_Porch_Blues.mp3": "blues",
    "Man From Mars.mp3": "mixed",
    "Rock.mp3": "rock",
    "Space.mp3": "ambient",
    "Tom Waits New Year's Eve.mp3": "mixed",
}

RAW_FEATURES = [
    "bpm",
    "key",
    "energy",
    "spectral_centroid",
    "brightness",
    "onset_rate_hz",
    "onset_count",
    "beat_regularity",
    "beat_count",
    "dynamic_range",
    "duration_sec",
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

PERCEPTUAL_FEATURES = [
    "energy",
    "tension",
    "density",
    "brightness",
    "stability",
    "smoothness",
    "repetition",
    "section_complexity",
    "macro_shape_hint",
    "tempo_bpm",
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate_hz",
    "spectral_flatness",
    "high_frequency_energy_ratio",
    "onset_rate_hz",
    "beat_regularity",
    "band_energy_0_250_hz",
    "band_energy_250_2000_hz",
    "band_energy_2000_6000_hz",
    "band_energy_6000_nyquist",
]

SHARED_FEATURE_TO_PERCEPTUAL = {
    "energy": "energy",
    "brightness": "brightness",
    "onset_rate_hz": "onset_rate_hz",
    "beat_regularity": "beat_regularity",
    "silence_rate": "silence_rate",
    "harmonic_stability": "harmonic_stability",
    "harmonic_change_rate_hz": "harmonic_change_rate_hz",
    "spectral_flatness": "spectral_flatness",
    "high_frequency_energy_ratio": "high_frequency_energy_ratio",
    "band_energy_0_250_hz": "band_energy_0_250_hz",
    "band_energy_250_2000_hz": "band_energy_250_2000_hz",
    "band_energy_2000_6000_hz": "band_energy_2000_6000_hz",
    "band_energy_6000_nyquist": "band_energy_6000_nyquist",
}

BAND_ENERGY_FIELDS = [
    "band_energy_0_250_hz",
    "band_energy_250_2000_hz",
    "band_energy_2000_6000_hz",
    "band_energy_6000_nyquist",
]

UNIT_INTERVAL_FEATURES = [
    "brightness",
    "repetition_score",
    "silence_rate",
    "harmonic_stability",
    "spectral_flatness",
    "high_frequency_energy_ratio",
    *BAND_ENERGY_FIELDS,
]

NONNEGATIVE_FEATURES = [
    "bpm",
    "energy",
    "spectral_centroid",
    "brightness",
    "onset_rate_hz",
    "onset_count",
    "beat_regularity",
    "beat_count",
    "dynamic_range",
    "duration_sec",
    "repetition_score",
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate_hz",
    "spectral_flatness",
    "high_frequency_energy_ratio",
    *BAND_ENERGY_FIELDS,
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
    if number is None:
        return ""

    return f"{number:.{digits}f}"


def api_get(path: str) -> requests.Response:
    return requests.get(
        f"{BASE_URL}{path}",
        timeout=REQUEST_TIMEOUT_SEC,
    )


def api_post_json(
    path: str,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> requests.Response:
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        params=params or {},
        timeout=REQUEST_TIMEOUT_SEC,
    )


def check_api() -> None:
    try:
        response = api_get("/openapi.json")
    except requests.RequestException as exc:
        fail(
            "API недоступен. Запустите сервер:\n"
            "uvicorn api.main:app --reload\n"
            f"Причина: {exc}"
        )

    if response.status_code != 200:
        fail(
            f"/openapi.json вернул HTTP {response.status_code}: "
            f"{response.text}"
        )

    print("✅ API доступен")


def create_project(track_name: str) -> str:
    response = api_post_json(
        "/project",
        {
            "user_id": "test6-audio-feature-validation",
            "name": f"Test6 Feature Validation — {track_name}",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/project: HTTP {response.status_code}; "
            f"{response.text}"
        )

    project_id = response.json().get("id")

    if not project_id:
        raise RuntimeError("/project: отсутствует поле id")

    return str(project_id)


def upload_track(project_id: str, audio_path: Path) -> str:
    with audio_path.open("rb") as audio_file:
        response = requests.post(
            f"{BASE_URL}/upload",
            params={"project_id": project_id},
            files={
                "file": (
                    audio_path.name,
                    audio_file,
                    "audio/mpeg",
                )
            },
            timeout=REQUEST_TIMEOUT_SEC,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"/upload: HTTP {response.status_code}; "
            f"{response.text}"
        )

    track_id = response.json().get("id")

    if not track_id:
        raise RuntimeError("/upload: отсутствует поле id")

    return str(track_id)


def analyze_track(
    project_id: str,
    track_id: str,
) -> dict[str, Any]:
    response = api_post_json(
        "/analyze",
        payload={},
        params={
            "project_id": project_id,
            "track_id": track_id,
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/analyze: HTTP {response.status_code}; "
            f"{response.text}"
        )

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(
            f"/analyze: status={payload.get('status')}; "
            f"response={json.dumps(payload, ensure_ascii=False)}"
        )

    return payload


def get_test_tracks() -> list[Path]:
    tracks = sorted(
        AUDIO_DIR.glob("*.mp3"),
        key=lambda item: item.name.lower(),
    )

    if len(tracks) < MAX_TRACKS:
        fail(
            f"Найдено MP3: {len(tracks)}. "
            f"Для Test6 требуется минимум: {MAX_TRACKS}."
        )

    return tracks[:MAX_TRACKS]


def validate_feature_contract(
    track_name: str,
    features: dict[str, Any],
    perceptual: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for key in RAW_FEATURES:
        if key not in features:
            errors.append(
                f"{track_name}: features.{key} отсутствует"
            )

    for key in PERCEPTUAL_FEATURES:
        if key not in perceptual:
            errors.append(
                f"{track_name}: perceptual.{key} отсутствует"
            )

    for key in NONNEGATIVE_FEATURES:
        value = as_float(features.get(key))

        if value is None:
            errors.append(
                f"{track_name}: features.{key} "
                "не является finite-числом"
            )
            continue

        if value < 0.0:
            errors.append(
                f"{track_name}: features.{key} < 0: {value}"
            )

    for key in UNIT_INTERVAL_FEATURES:
        value = as_float(features.get(key))

        if value is None:
            continue

        if value > 1.0 + 1e-9:
            errors.append(
                f"{track_name}: features.{key} > 1: {value}"
            )

    for feature_key, perceptual_key in (
        SHARED_FEATURE_TO_PERCEPTUAL.items()
    ):
        feature_value = as_float(features.get(feature_key))
        perceptual_value = as_float(
            perceptual.get(perceptual_key)
        )

        if feature_value is None or perceptual_value is None:
            continue

        if abs(feature_value - perceptual_value) > 1e-9:
            errors.append(
                f"{track_name}: рассинхрон "
                f"features.{feature_key}="
                f"{feature_value} и "
                f"perceptual.{perceptual_key}="
                f"{perceptual_value}"
            )

    bpm = as_float(features.get("bpm"))
    tempo_bpm = as_float(perceptual.get("tempo_bpm"))

    if bpm is not None and tempo_bpm is not None:
        if abs(bpm - tempo_bpm) > 1e-9:
            errors.append(
                f"{track_name}: рассинхрон "
                f"features.bpm={bpm} и "
                f"perceptual.tempo_bpm={tempo_bpm}"
            )

    repetition_score = as_float(
        features.get("repetition_score")
    )
    repetition = as_float(perceptual.get("repetition"))

    if repetition_score is not None and repetition is not None:
        if abs(repetition_score - repetition) > 1e-9:
            errors.append(
                f"{track_name}: рассинхрон "
                f"features.repetition_score="
                f"{repetition_score} и "
                f"perceptual.repetition={repetition}"
            )

    band_energy_sum = sum(
        as_float(features.get(key)) or 0.0
        for key in BAND_ENERGY_FIELDS
    )

    if not 0.999 <= band_energy_sum <= 1.001:
        errors.append(
            f"{track_name}: сумма полос = "
            f"{band_energy_sum:.8f}; "
            "ожидался диапазон 0.999..1.001"
        )

    return errors


def build_row(
    audio_path: Path,
    project_id: str,
    track_id: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    features = response.get("features") or {}
    perceptual = response.get("perceptual") or {}

    row: dict[str, Any] = {
        "file": audio_path.name,
        "expected_music_style": KNOWN_EXPECTED_STYLES.get(
            audio_path.name,
            "unknown",
        ),
        "suggested_music_style": response.get(
            "suggested_music_style",
            "",
        ),
        "project_id": project_id,
        "track_id": track_id,
        "analysis_id": response.get("analysis_id", ""),
    }

    for key in RAW_FEATURES:
        row[key] = features.get(key, "")

    for key in PERCEPTUAL_FEATURES:
        row[f"perceptual_{key}"] = perceptual.get(key, "")

    row["band_energy_sum"] = sum(
        as_float(features.get(key)) or 0.0
        for key in BAND_ENERGY_FIELDS
    )

    return row


def calculate_summary(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []

    for feature_name in RAW_FEATURES:
        if feature_name == "key":
            continue

        values = [
            as_float(row.get(feature_name))
            for row in rows
        ]
        values = [
            value
            for value in values
            if value is not None
        ]

        if not values:
            continue

        min_value = min(values)
        max_value = max(values)
        mean_value = sum(values) / len(values)

        if len(values) > 1:
            variance = sum(
                (value - mean_value) ** 2
                for value in values
            ) / (len(values) - 1)
            std_value = math.sqrt(variance)
        else:
            std_value = 0.0

        coefficient_of_variation = (
            std_value / abs(mean_value)
            if abs(mean_value) > 1e-12
            else 0.0
        )

        summary_rows.append(
            {
                "feature": feature_name,
                "count": len(values),
                "min": min_value,
                "max": max_value,
                "range": max_value - min_value,
                "mean": mean_value,
                "std": std_value,
                "coefficient_of_variation": (
                    coefficient_of_variation
                ),
            }
        )

    return summary_rows


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
    rows: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    validation_errors: list[str],
) -> tuple[Path, Path, Path, Path]:
    raw_json_path = (
        OUTPUT_DIR
        / f"test6_raw_api_responses_{timestamp}.json"
    )
    matrix_csv_path = (
        OUTPUT_DIR
        / f"test6_feature_matrix_{timestamp}.csv"
    )
    summary_csv_path = (
        OUTPUT_DIR
        / f"test6_feature_summary_{timestamp}.csv"
    )
    markdown_path = (
        OUTPUT_DIR
        / f"test6_report_{timestamp}.md"
    )

    with raw_json_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            {
                "test_name": "test6_audio_features_v0_4",
                "created_at_local": timestamp,
                "base_url": BASE_URL,
                "tracks": raw_results,
            },
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    matrix_fieldnames = [
        "file",
        "expected_music_style",
        "suggested_music_style",
        "project_id",
        "track_id",
        "analysis_id",
        *RAW_FEATURES,
        *[
            f"perceptual_{key}"
            for key in PERCEPTUAL_FEATURES
        ],
        "band_energy_sum",
    ]
    write_csv(
        path=matrix_csv_path,
        rows=rows,
        fieldnames=matrix_fieldnames,
    )

    summary_fieldnames = [
        "feature",
        "count",
        "min",
        "max",
        "range",
        "mean",
        "std",
        "coefficient_of_variation",
    ]
    write_csv(
        path=summary_csv_path,
        rows=summary_rows,
        fieldnames=summary_fieldnames,
    )

    known_rows = [
        row
        for row in rows
        if row["expected_music_style"] != "unknown"
    ]
    matching_rows = [
        row
        for row in known_rows
        if row["expected_music_style"]
        == row["suggested_music_style"]
    ]

    lines = [
        "# Test6 — Audio Features v0.4",
        "",
        f"Время запуска: `{timestamp}`",
        "",
        "## Статус",
        "",
        f"- Проанализировано треков: **{len(rows)}**",
        f"- Ошибок контракта и диапазонов: "
        f"**{len(validation_errors)}**",
        f"- Совпадений с известным стилем: "
        f"**{len(matching_rows)} из {len(known_rows)}**",
        "",
        "## Матрица треков",
        "",
        "| Файл | Ожидание | Получено | BPM | "
        "Onset rate, Hz | Beat regularity | "
        "0-250 Hz | 250-2000 Hz | "
        "2000-6000 Hz | 6000-Nyquist Hz |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in rows:
        lines.append(
            "| "
            f"{row['file']} | "
            f"{row['expected_music_style']} | "
            f"{row['suggested_music_style']} | "
            f"{format_number(row['bpm'], 3)} | "
            f"{format_number(row['onset_rate_hz'], 4)} | "
            f"{format_number(row['beat_regularity'], 4)} | "
            f"{format_number(row['band_energy_0_250_hz'], 4)} | "
            f"{format_number(row['band_energy_250_2000_hz'], 4)} | "
            f"{format_number(row['band_energy_2000_6000_hz'], 4)} | "
            f"{format_number(row['band_energy_6000_nyquist'], 4)} |"
        )

    lines.extend(
        [
            "",
            "## Диапазоны признаков",
            "",
            "| Признак | Min | Max | Размах | "
            "Среднее | Std | CV |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for summary_row in summary_rows:
        lines.append(
            "| "
            f"`{summary_row['feature']}` | "
            f"{format_number(summary_row['min'])} | "
            f"{format_number(summary_row['max'])} | "
            f"{format_number(summary_row['range'])} | "
            f"{format_number(summary_row['mean'])} | "
            f"{format_number(summary_row['std'])} | "
            f"{format_number(summary_row['coefficient_of_variation'])} |"
        )

    lines.extend(
        [
            "",
            "## Проверка спектральных полос",
            "",
            "Сумма четырёх относительных полос должна "
            "быть равна 1.0 с численной погрешностью.",
            "",
            "| Файл | Сумма полос |",
            "|---|---:|",
        ]
    )

    for row in rows:
        lines.append(
            f"| {row['file']} | "
            f"{format_number(row['band_energy_sum'])} |"
        )

    lines.extend(
        [
            "",
            "## Ошибки",
            "",
        ]
    )

    if validation_errors:
        for error in validation_errors:
            lines.append(f"- {error}")
    else:
        lines.append(
            "- Ошибок API-контракта, finite-значений, "
            "диапазонов и нормировки спектральных полос "
            "не обнаружено."
        )

    with markdown_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        output_file.write("\n".join(lines) + "\n")

    return (
        raw_json_path,
        matrix_csv_path,
        summary_csv_path,
        markdown_path,
    )


def main() -> None:
    check_api()
    tracks = get_test_tracks()

    print("\n" + "=" * 80)
    print("TEST6 — AUDIO FEATURES v0.4")
    print("=" * 80)
    print(f"Треков в тесте: {len(tracks)}")

    rows: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    runtime_errors: list[str] = []

    for index, audio_path in enumerate(tracks, start=1):
        print("\n" + "-" * 80)
        print(f"[{index}/{len(tracks)}] 🎵 {audio_path.name}")

        try:
            project_id = create_project(audio_path.name)
            track_id = upload_track(project_id, audio_path)
            response = analyze_track(project_id, track_id)

            features = response.get("features") or {}
            perceptual = response.get("perceptual") or {}

            track_errors = validate_feature_contract(
                track_name=audio_path.name,
                features=features,
                perceptual=perceptual,
            )
            validation_errors.extend(track_errors)

            row = build_row(
                audio_path=audio_path,
                project_id=project_id,
                track_id=track_id,
                response=response,
            )
            rows.append(row)

            raw_results.append(
                {
                    "file": audio_path.name,
                    "expected_music_style": row[
                        "expected_music_style"
                    ],
                    "response_analyze": response,
                }
            )

            print(
                f"  style={row['suggested_music_style']} | "
                f"bpm={format_number(row['bpm'], 2)} | "
                f"onset_rate_hz="
                f"{format_number(row['onset_rate_hz'], 4)} | "
                f"beat_regularity="
                f"{format_number(row['beat_regularity'], 4)}"
            )

            print(
                "  bands: "
                f"low={format_number(row['band_energy_0_250_hz'], 4)}, "
                f"mid={format_number(row['band_energy_250_2000_hz'], 4)}, "
                f"high={format_number(row['band_energy_2000_6000_hz'], 4)}, "
                f"air={format_number(row['band_energy_6000_nyquist'], 4)}, "
                f"sum={format_number(row['band_energy_sum'], 6)}"
            )

            if track_errors:
                print(
                    f"  ⚠️ Ошибок проверки: "
                    f"{len(track_errors)}"
                )
            else:
                print("  ✅ Контракт и диапазоны: OK")

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as exc:
            message = f"{audio_path.name}: {exc}"
            runtime_errors.append(message)
            print(f"  ❌ {message}")

    if runtime_errors:
        print("\n" + "=" * 80)
        print("КРИТИЧЕСКИЕ ОШИБКИ")
        print("=" * 80)

        for error in runtime_errors:
            print(f"- {error}")

        fail(
            "Test6 не завершён: не все треки "
            "прошли upload/analyze."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows = calculate_summary(rows)

    (
        raw_json_path,
        matrix_csv_path,
        summary_csv_path,
        markdown_path,
    ) = write_reports(
        timestamp=timestamp,
        rows=rows,
        raw_results=raw_results,
        summary_rows=summary_rows,
        validation_errors=validation_errors,
    )

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ TEST6")
    print("=" * 80)
    print(f"Успешно проанализировано: {len(rows)}")
    print(f"Ошибок валидации: {len(validation_errors)}")
    print("\nОтчёты:")
    print(f"  JSON: {raw_json_path}")
    print(f"  CSV:  {matrix_csv_path}")
    print(f"  CSV:  {summary_csv_path}")
    print(f"  MD:   {markdown_path}")

    if validation_errors:
        print(
            "\n⚠️ Анализ завершён, но обнаружены "
            "ошибки API-контракта или численных инвариантов."
        )
        sys.exit(2)

    print(
        "\n✅ Test6 завершён без ошибок. "
        "Новые признаки пока остаются "
        "диагностическими и не подключены к renderer."
    )


if __name__ == "__main__":
    main()