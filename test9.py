"""Test9 — E1 AudioFileAdapter: extract_features() smoke test.

Проверяет, что:
  1. extract_features() возвращает dict с ровно 17 перцептивными осями
     (+ duration_sec + style) для каждого из 5 контрольных треков.
  2. Все числовые значения конечны и лежат в [0, 1] (duration_sec — >0).
  3. Адаптер реально различает треки: для ключевых осей межтрековый
     std > 0.05 (не константа).
  4. Suggested style не пустой, если style_hint не передан.

Запуск:
  python test9.py

Отчёты:
  output/test9_features_<timestamp>.json   — полный дамп
  output/test9_features_<timestamp>.csv    — матрица треки × оси
  output/test9_report_<timestamp>.md       — читаемый отчёт
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from lib.audio_analysis.audio_file_adapter import extract_features

# ── Пути ──────────────────────────────────────────────────────────────────────
AUDIO_DIR  = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Контрольные треки (5 профилей) ────────────────────────────────────────────
CONTROL_TRACKS: list[tuple[str, str]] = [
    ("Front_Porch_Blues.mp3",                      "blues_jazz"),
    ("Space.mp3",                                  "ambient"),
    ("04 - Autumn Leaves.mp3",                     "jazz"),
    ("13-Рубекин - Катенькин Вальс.mp3",            "classical"),
    ("Sing, Sing, Sing.mp3",                       "electronic"),
]

# ── 17 перцептивных осей ──────────────────────────────────────────────────────
AXES_17: list[str] = [
    "energy",
    "tension",
    "repetition",
    "tempo",
    "section_complexity",
    "silence_rate",
    "harmonic_stability",
    "harmonic_change_rate",
    "spectral_flatness",
    "high_frequency_energy",
    "density_level",
    "motion_intensity",
    "texture_complexity",
    "noise_level",
    "symmetry_bias",
    "layout_macro_shape",
    "recursion_depth",
]

# Оси где ожидаем реальный межтрековый разброс std > MIN_SPREAD
SPREAD_AXES: list[str] = [
    "energy",
    "tension",
    "tempo",
    "density_level",
    "motion_intensity",
    "harmonic_stability",
]
MIN_SPREAD = 0.05  # минимальный межтрековый std


def fail(message: str) -> None:
    print(f"\n❌ FATAL: {message}")
    sys.exit(1)


def as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fmt(value: Any, digits: int = 4) -> str:
    f = as_float(value)
    if f is None:
        return "—"
    return f"{f:.{digits}f}"


def validate_features(
    track_name: str,
    features: dict[str, Any],
) -> list[str]:
    """Проверяет наличие и диапазон всех 17 осей."""
    errors: list[str] = []

    for axis in AXES_17:
        value = as_float(features.get(axis))
        if value is None:
            errors.append(f"{track_name}: ось '{axis}' отсутствует или не-finite")
            continue
        if not (0.0 <= value <= 1.0):
            errors.append(f"{track_name}: '{axis}' = {value:.6f} вне [0, 1]")

    dur = as_float(features.get("duration_sec"))
    if dur is None or dur <= 0.0:
        errors.append(f"{track_name}: duration_sec = {dur} — некорректно")

    style = features.get("style", "")
    if not style:
        errors.append(f"{track_name}: style пустой")

    return errors


def write_reports(
    timestamp: str,
    results: list[dict[str, Any]],
    spread_check: list[dict[str, Any]],
    errors: list[str],
) -> tuple[Path, Path, Path]:
    json_path = OUTPUT_DIR / f"test9_features_{timestamp}.json"
    csv_path  = OUTPUT_DIR / f"test9_features_{timestamp}.csv"
    md_path   = OUTPUT_DIR / f"test9_report_{timestamp}.md"

    # JSON ────────────────────────────────────────────────────────────────────
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "test_name": "test9_audio_file_adapter_e1",
                "created_at_local": timestamp,
                "tracks": results,
                "spread_check": spread_check,
                "validation_errors": errors,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    # CSV — матрица треки × оси ───────────────────────────────────────────────
    fieldnames = ["track", "style_hint", "detected_style", "duration_sec"] + AXES_17
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({
                "track":          row["track"],
                "style_hint":     row["style_hint"],
                "detected_style": row["features"].get("style", ""),
                "duration_sec":   fmt(row["features"].get("duration_sec"), 1),
                **{axis: fmt(row["features"].get(axis)) for axis in AXES_17},
            })

    # Markdown ────────────────────────────────────────────────────────────────
    lines: list[str] = [
        "# Test9 — E1 AudioFileAdapter",
        "",
        f"Время запуска: `{timestamp}`",
        f"Ошибок: **{len(errors)}**",
        "",
        "## Матрица признаков",
        "",
    ]

    header_axes = ["energy", "tension", "tempo", "density_level",
                   "harmonic_stability", "symmetry_bias", "recursion_depth"]
    lines.append("| Трек | style | " + " | ".join(header_axes) + " |")
    lines.append("|---" * (2 + len(header_axes)) + "|")
    for row in results:
        f = row["features"]
        vals = " | ".join(fmt(f.get(ax)) for ax in header_axes)
        lines.append(f"| {row['track']} | {f.get('style','')} | {vals} |")  # noqa: E501

    lines.extend([
        "",
        "## Межтрековый разброс (std по 5 трекам)",
        "",
        "| Ось | std | Вердикт |",
        "|---|---:|---|",
    ])
    for sc in spread_check:
        verdict = "✅ разброс" if sc["ok"] else "⚠️ слабый разброс"
        lines.append(f"| `{sc['axis']}` | {fmt(sc['std'])} | {verdict} |")

    lines.extend(["", "## Ошибки валидации", ""])
    if errors:
        for e in errors:
            lines.append(f"- {e}")
    else:
        lines.append("- Ошибок не обнаружено.")

    with md_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    return json_path, csv_path, md_path


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "=" * 72)
    print("TEST9 — E1 AudioFileAdapter: extract_features() smoke test")
    print("=" * 72)
    print(f"Контрольных треков: {len(CONTROL_TRACKS)}")
    print(f"Осей: {len(AXES_17)}")

    # Проверяем что все треки существуют
    missing = [
        fname for fname, _ in CONTROL_TRACKS
        if not (AUDIO_DIR / fname).exists()
    ]
    if missing:
        fail("Не найдены аудиофайлы:\n" + "\n".join(f"  {m}" for m in missing))

    results: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    runtime_errors: list[str] = []

    for idx, (fname, style_hint) in enumerate(CONTROL_TRACKS, start=1):
        print(f"\n{'─' * 72}")
        print(f"[{idx}/{len(CONTROL_TRACKS)}] 🎵 {fname}")
        audio_path = AUDIO_DIR / fname

        try:
            features = extract_features(audio_path, style_hint=style_hint)
        except Exception as exc:
            msg = f"{fname}: {exc}"
            runtime_errors.append(msg)
            print(f"  ❌ {msg}")
            continue

        errs = validate_features(fname, features)
        validation_errors.extend(errs)

        results.append({
            "track":      fname,
            "style_hint": style_hint,
            "features":   features,
        })

        # Краткий прогресс-принт
        print(
            f"  style={features.get('style','?'):<12s}"
            f"  dur={fmt(features.get('duration_sec'),1)}s"
            f"  energy={fmt(features.get('energy'))}"
            f"  tempo={fmt(features.get('tempo'))}"
            f"  density={fmt(features.get('density_level'))}"
            f"  h_stab={fmt(features.get('harmonic_stability'))}"
        )
        if errs:
            for e in errs:
                print(f"  ⚠️  {e}")
        else:
            print("  ✅ все 17 осей корректны")

    if runtime_errors:
        print("\n" + "=" * 72)
        for e in runtime_errors:
            print(f"❌ {e}")
        fail("Test9: не все треки обработаны.")

    # ── Межтрековый разброс ──────────────────────────────────────────────────
    print(f"\n{'─' * 72}")
    print("Межтрековый разброс (std по 5 трекам):")
    spread_check: list[dict[str, Any]] = []
    spread_warnings: list[str] = []

    for axis in SPREAD_AXES:
        values = [
            as_float(row["features"].get(axis))
            for row in results
            if as_float(row["features"].get(axis)) is not None
        ]
        if len(values) < 2:
            std = 0.0
        else:
            std = float(np.std(values, ddof=0))

        ok = std >= MIN_SPREAD
        spread_check.append({"axis": axis, "std": std, "ok": ok})
        status = "✅" if ok else "⚠️ "
        print(f"  {status} {axis:<25s}  std = {std:.4f}")
        if not ok:
            spread_warnings.append(
                f"axis '{axis}': std={std:.4f} < {MIN_SPREAD} — "
                "адаптер плохо различает треки по этой оси"
            )

    # ── Отчёты ───────────────────────────────────────────────────────────────
    json_path, csv_path, md_path = write_reports(
        timestamp=timestamp,
        results=results,
        spread_check=spread_check,
        errors=validation_errors,
    )

    print("\n" + "=" * 72)
    print("РЕЗУЛЬТАТ TEST9")
    print("=" * 72)
    print(f"Треков обработано:    {len(results)}/{len(CONTROL_TRACKS)}")
    print(f"Ошибок валидации:     {len(validation_errors)}")
    print(f"Предупреждений spread:{len(spread_warnings)}")
    print("\nОтчёты:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  MD:   {md_path}")

    if validation_errors:
        for e in validation_errors:
            print(f"  ⚠️  {e}")
        sys.exit(2)

    if spread_warnings:
        print("\n⚠️  Test9 завершён с предупреждениями о разбросе:")
        for w in spread_warnings:
            print(f"  - {w}")
        sys.exit(2)

    print("\n✅ Test9 — extract_features() работает корректно на всех 5 треках.")


if __name__ == "__main__":
    main()
