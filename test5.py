import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
AUDIO_DIR = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT_SEC = 180

TRACKS = {
    "Rock.mp3": {
        "expected_music_style": "rock",
        "purpose": "Контрастный энергичный и яркий материал",
    },
    "Space.mp3": {
        "expected_music_style": "ambient",
        "purpose": "Контрастный спокойный/атмосферный материал",
    },
}

FEATURE_FIELDS = [
    "bpm",
    "energy",
    "spectral_centroid",
    "brightness",
    "rhythm_density",
    "dynamic_range",
    "duration_sec",
    "repetition_score",
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate_hz",
    "spectral_flatness",
    "high_frequency_energy_ratio",
]

PERCEPTUAL_FIELDS = [
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
]

NEW_FEATURE_FIELDS = [
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate_hz",
    "spectral_flatness",
    "high_frequency_energy_ratio",
]


def fail(message: str) -> None:
    print(f"\n❌ {message}")
    sys.exit(1)


def safe_get(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    return "" if value is None else value


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def get_api_health() -> None:
    try:
        response = requests.get(
            f"{BASE_URL}/openapi.json",
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.RequestException as exc:
        fail(
            "API недоступен. Сначала запустите сервер:\n"
            "uvicorn api.main:app --reload\n"
            f"Техническая причина: {exc}"
        )

    if response.status_code != 200:
        fail(
            f"API вернул {response.status_code} для /openapi.json:\n"
            f"{response.text}"
        )

    print("✅ API доступен: /openapi.json -> 200")


def post_json(
    endpoint: str,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> requests.Response:
    return requests.post(
        f"{BASE_URL}{endpoint}",
        json=payload,
        params=params or {},
        timeout=REQUEST_TIMEOUT_SEC,
    )


def post_audio_file(
    project_id: str,
    audio_path: Path,
) -> requests.Response:
    with audio_path.open("rb") as audio_file:
        return requests.post(
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


def create_project(track_name: str) -> str:
    response = post_json(
        "/project",
        {
            "user_id": "test5-audio-metrics",
            "name": f"Audio Metrics Comparison — {track_name}",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/project: HTTP {response.status_code}; {response.text}"
        )

    project_id = response.json().get("id")
    if not project_id:
        raise RuntimeError("/project: поле id отсутствует в ответе")

    return project_id


def upload_track(project_id: str, audio_path: Path) -> str:
    response = post_audio_file(project_id, audio_path)

    if response.status_code != 200:
        raise RuntimeError(
            f"/upload: HTTP {response.status_code}; {response.text}"
        )

    track_id = response.json().get("id")
    if not track_id:
        raise RuntimeError("/upload: поле id отсутствует в ответе")

    return track_id


def analyze_track(project_id: str, track_id: str) -> dict[str, Any]:
    response = post_json(
        "/analyze",
        payload={},
        params={
            "project_id": project_id,
            "track_id": track_id,
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"/analyze: HTTP {response.status_code}; {response.text}"
        )

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(
            f"/analyze: status={payload.get('status')}; "
            f"response={json.dumps(payload, ensure_ascii=False)}"
        )

    if not payload.get("analysis_id"):
        raise RuntimeError("/analyze: поле analysis_id отсутствует в ответе")

    return payload


def flatten_analysis_result(
    track_name: str,
    track_meta: dict[str, str],
    project_id: str,
    track_id: str,
    analysis_json: dict[str, Any],
) -> dict[str, Any]:
    features = analysis_json.get("features") or {}
    perceptual = analysis_json.get("perceptual") or {}

    row: dict[str, Any] = {
        "file": track_name,
        "expected_music_style": track_meta["expected_music_style"],
        "purpose": track_meta["purpose"],
        "suggested_music_style": analysis_json.get(
            "suggested_music_style",
            "",
        ),
        "project_id": project_id,
        "track_id": track_id,
        "analysis_id": analysis_json.get("analysis_id", ""),
    }

    for field in FEATURE_FIELDS:
        row[f"feature_{field}"] = safe_get(features, field)

    for field in PERCEPTUAL_FIELDS:
        row[f"perceptual_{field}"] = safe_get(perceptual, field)

    return row


def write_json_report(
    timestamp: str,
    results: list[dict[str, Any]],
) -> Path:
    path = OUTPUT_DIR / f"test5_analysis_raw_{timestamp}.json"

    payload = {
        "test_name": "test5_audio_metrics_comparison",
        "created_at_local": timestamp,
        "base_url": BASE_URL,
        "tracks": results,
    }

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return path


def write_csv_report(
    timestamp: str,
    rows: list[dict[str, Any]],
) -> Path:
    path = OUTPUT_DIR / f"test5_audio_metrics_{timestamp}.csv"

    fieldnames = [
        "file",
        "expected_music_style",
        "purpose",
        "suggested_music_style",
        "project_id",
        "track_id",
        "analysis_id",
        *[f"feature_{field}" for field in FEATURE_FIELDS],
        *[f"perceptual_{field}" for field in PERCEPTUAL_FIELDS],
    ]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


def value_as_float(value: Any) -> float | None:
    if value in ("", None):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def difference_label(
    first_value: Any,
    second_value: Any,
    first_name: str,
    second_name: str,
) -> str:
    first_number = value_as_float(first_value)
    second_number = value_as_float(second_value)

    if first_number is None or second_number is None:
        return "нет данных"

    difference = second_number - first_number
    if abs(difference) < 1e-9:
        return "равны"

    if difference > 0:
        return f"выше у {second_name} на {difference:.6f}"

    return f"выше у {first_name} на {abs(difference):.6f}"


def write_markdown_report(
    timestamp: str,
    rows: list[dict[str, Any]],
) -> Path:
    path = OUTPUT_DIR / f"test5_audio_metrics_{timestamp}.md"

    lines = [
        "# Test5 — сравнение аудиометрик",
        "",
        f"Время запуска: `{timestamp}`",
        "",
        "## Треки",
        "",
    ]

    for row in rows:
        lines.append(
            f"- **{row['file']}**: "
            f"ожидание `{row['expected_music_style']}`, "
            f"получено `{row['suggested_music_style']}`"
        )

    lines.extend(
        [
            "",
            "## Расширенные признаки",
            "",
            "| Метрика | Единица | "
            f"{rows[0]['file']} | {rows[1]['file']} | Разность |",
            "|---|---:|---:|---:|---|",
        ]
    )

    metric_units = {
        "silence_rate": "1",
        "harmonic_stability": "1",
        "harmonic_change_rate_hz": "Hz",
        "spectral_flatness": "1",
        "high_frequency_energy_ratio": "1",
    }

    first_row = rows[0]
    second_row = rows[1]

    for metric in NEW_FEATURE_FIELDS:
        first_value = first_row.get(f"feature_{metric}", "")
        second_value = second_row.get(f"feature_{metric}", "")

        lines.append(
            "| "
            f"`{metric}` | "
            f"{metric_units[metric]} | "
            f"{format_value(first_value)} | "
            f"{format_value(second_value)} | "
            f"{difference_label(first_value, second_value, first_row['file'], second_row['file'])} |"
        )

    lines.extend(
        [
            "",
            "## Основные признаки",
            "",
            "| Метрика | Единица | "
            f"{rows[0]['file']} | {rows[1]['file']} | Разность |",
            "|---|---:|---:|---:|---|",
        ]
    )

    core_units = {
        "bpm": "BPM",
        "energy": "1",
        "spectral_centroid": "Hz",
        "brightness": "1",
        "rhythm_density": "1",
        "dynamic_range": "dB",
        "duration_sec": "s",
        "repetition_score": "1",
    }

    for metric in core_units:
        first_value = first_row.get(f"feature_{metric}", "")
        second_value = second_row.get(f"feature_{metric}", "")

        lines.append(
            "| "
            f"`{metric}` | "
            f"{core_units[metric]} | "
            f"{format_value(first_value)} | "
            f"{format_value(second_value)} | "
            f"{difference_label(first_value, second_value, first_row['file'], second_row['file'])} |"
        )

    lines.extend(
        [
            "",
            "## Контроль структуры ответа",
            "",
        ]
    )

    for row in rows:
        missing_features = [
            metric
            for metric in NEW_FEATURE_FIELDS
            if row.get(f"feature_{metric}", "") == ""
        ]
        missing_perceptual = [
            metric
            for metric in NEW_FEATURE_FIELDS
            if row.get(f"perceptual_{metric}", "") == ""
        ]

        if not missing_features and not missing_perceptual:
            lines.append(
                f"- **{row['file']}**: "
                "все расширенные поля присутствуют "
                "в `features` и `perceptual`."
            )
            continue

        lines.append(
            f"- **{row['file']}**: "
            f"нет в `features`: {missing_features or 'нет'}; "
            f"нет в `perceptual`: {missing_perceptual or 'нет'}."
        )

    with path.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    return path


def print_compact_result(row: dict[str, Any]) -> None:
    print(
        f"  ✅ music: expected={row['expected_music_style']} | "
        f"actual={row['suggested_music_style']}"
    )

    print(
        "  ✅ core: "
        f"bpm={format_value(row['feature_bpm'])}, "
        f"energy={format_value(row['feature_energy'])}, "
        f"dynamic_range={format_value(row['feature_dynamic_range'])} dB"
    )

    print(
        "  ✅ extended: "
        f"silence_rate={format_value(row['feature_silence_rate'])}, "
        f"harmonic_stability={format_value(row['feature_harmonic_stability'])}, "
        f"harmonic_change_rate_hz="
        f"{format_value(row['feature_harmonic_change_rate_hz'])}, "
        f"spectral_flatness={format_value(row['feature_spectral_flatness'])}, "
        f"high_frequency_energy_ratio="
        f"{format_value(row['feature_high_frequency_energy_ratio'])}"
    )


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    get_api_health()

    rows: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    errors: list[str] = []

    print("\n" + "=" * 80)
    print("TEST5 — СРАВНЕНИЕ РАСШИРЕННЫХ АУДИОМЕТРИК ДВУХ ТРЕКОВ")
    print("=" * 80)

    for track_name, track_meta in TRACKS.items():
        audio_path = AUDIO_DIR / track_name

        print("\n" + "-" * 80)
        print(f"🎵 {track_name}")
        print(f"   Ожидаемый музыкальный класс: {track_meta['expected_music_style']}")
        print(f"   Назначение: {track_meta['purpose']}")

        if not audio_path.is_file():
            message = f"Файл не найден: {audio_path}"
            print(f"  ❌ {message}")
            errors.append(message)
            continue

        try:
            project_id = create_project(track_name)
            print(f"  ✅ project_id={project_id}")

            track_id = upload_track(project_id, audio_path)
            print(f"  ✅ track_id={track_id}")

            analysis_json = analyze_track(project_id, track_id)
            print(f"  ✅ analysis_id={analysis_json['analysis_id']}")

            row = flatten_analysis_result(
                track_name=track_name,
                track_meta=track_meta,
                project_id=project_id,
                track_id=track_id,
                analysis_json=analysis_json,
            )
            rows.append(row)

            raw_results.append(
                {
                    "file": track_name,
                    "expected_music_style": track_meta["expected_music_style"],
                    "purpose": track_meta["purpose"],
                    "response_analyze": analysis_json,
                }
            )

            print_compact_result(row)

        except (requests.RequestException, RuntimeError, ValueError) as exc:
            message = f"{track_name}: {exc}"
            print(f"  ❌ {message}")
            errors.append(message)

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ TEST5")
    print("=" * 80)
    print(f"Успешно проанализировано: {len(rows)} из {len(TRACKS)}")
    print(f"Ошибок: {len(errors)}")

    if len(rows) != len(TRACKS):
        if errors:
            print("\nОшибки:")
            for error in errors:
                print(f"  - {error}")

        fail(
            "Тест не завершён для двух треков. "
            "Исправьте ошибку выше и запустите test5.py повторно."
        )

    raw_json_path = write_json_report(timestamp, raw_results)
    csv_path = write_csv_report(timestamp, rows)
    markdown_path = write_markdown_report(timestamp, rows)

    print("\nСозданы отчёты:")
    print(f"  📄 JSON: {raw_json_path}")
    print(f"  📊 CSV:  {csv_path}")
    print(f"  📝 MD:   {markdown_path}")

    print("\nПришлите мне один файл:")
    print(f"  {markdown_path}")
    print("\nЕсли захотите передать полные значения и структуру API — также приложите:")
    print(f"  {raw_json_path}")


if __name__ == "__main__":
    main()