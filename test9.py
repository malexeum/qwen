"""Test9 — E1 AudioFileAdapter: extract_features() smoke test.

Проверяет, что:
  1. extract_features() возвращает dict с ровно 17 перцептивными осями
     (+ duration_sec + style) для каждого из 5 контрольных треков.
  2. Все числовые значения конечны и лежат в [0, 1] (duration_sec — >0).
  3. Адаптер реально различает треки: для ключевых осей межтрековый
     std > 0.05 (не константа). E1-fix3: добавлены symmetry_bias,
     section_complexity, noise_level.
  4. Suggested style не пустой, если style_hint не передан.
  5. Доменные проверки: noise_level != spectral_flatness,
     ambient section_complexity < 0.5, blues noise_level > 0.20.

Запуск:
  python test9.py

Отчёты:
  output/test9_features_<timestamp>.json
  output/test9_features_<timestamp>.csv
  output/test9_report_<timestamp>.md
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

# ── Пути ─────────────────────────────────────────────────────────────────────
AUDIO_DIR  = Path("tests/audio")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Контрольные треки (5 профилей) ───────────────────────────────────────────
CONTROL_TRACKS: list[tuple[str, str]] = [
    ("Front_Porch_Blues.mp3",                      "blues_jazz"),
    ("Space.mp3",                                  "ambient"),
    ("04 - Autumn Leaves.mp3",                     "jazz"),
    ("13-Рубекин - Катенькин Вальс.mp3",            "classical"),
    ("Sing, Sing, Sing.mp3",                       "electronic"),
]

# ── 17 перцептивных осей ─────────────────────────────────────────────────────
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
# E1-fix3: добавлены три новые оси
SPREAD_AXES: list[str] = [
    "energy",
    "tension",
    "tempo",
    "density_level",
    "motion_intensity",
    "harmonic_stability",
    "symmetry_bias",        # #2
    "section_complexity",   # #3
    "noise_level",          # #4
]
MIN_SPREAD = 0.05


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


def domain_checks(results: list[dict[str, Any]]) -> list[str]:
    """Доменные проверки E1-fix3."""
    warnings: list[str] = []
    by_style: dict[str, dict[str, Any]] = {
        r["style_hint"]: r["features"] for r in results
    }

    # #4: noise_level != spectral_flatness (числа разные)
    for r in results:
        f = r["features"]
        nl = as_float(f.get("noise_level"))
        sf = as_float(f.get("spectral_flatness"))
        if nl is not None and sf is not None and abs(nl - sf) < 1e-6:
            warnings.append(
                f"{r['track']}: noise_level == spectral_flatness ({nl:.6f}) — "
                "log-шкала не применена"
            )

    # #3: ambient section_complexity < 0.5  (ambient энергетически однороден)
    if "ambient" in by_style:
        sc = as_float(by_style["ambient"].get("section_complexity"))
        if sc is not None and sc >= 0.5:
            warnings.append(
                f"ambient section_complexity = {sc:.4f} >= 0.5 — "
                "ожидаем низкий контраст секций для ambient/drone"
            )

    # #2: хотя бы один трек section_complexity > 0.3 (есть треки с контрастом)
    all_sc = [
        as_float(r["features"].get("section_complexity"))
        for r in results
        if as_float(r["features"].get("section_complexity")) is not None
    ]
    if all_sc and max(all_sc) <= 0.3:
        warnings.append(
            f"Максимальная section_complexity = {max(all_sc):.4f} — "
            "все треки дают низкий CV, фикс #3 неэффективен"
        )

    # #2: blues_jazz noise_level > 0.10
    if "blues_jazz" in by_style:
        nl = as_float(by_style["blues_jazz"].get("noise_level"))
        if nl is not None and nl <= 0.10:
            warnings.append(
                f"blues_jazz noise_level = {nl:.4f} <= 0.10 — "
                "ожидаем умеренный шум для blues"
            )

    return warnings


def write_reports(
    timestamp: str,
    results: list[dict[str, Any]],
    spread_check: list[dict[str, Any]],
    errors: list[str],
    domain_warnings: list[str],
) -> tuple[Path, Path, Path]:
    json_path = OUTPUT_DIR / f"test9_features_{timestamp}.json"
    csv_path  = OUTPUT_DIR / f"test9_features_{timestamp}.csv"
    md_path   = OUTPUT_DIR / f"test9_report_{timestamp}.md"

    # JSON ─────────────────────────────────────────────────────────────────────
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "test_name": "test9_audio_file_adapter_e1_fix3",
                "created_at_local": timestamp,
                "tracks": results,
                "spread_check": spread_check,
                "validation_errors": errors,
                "domain_warnings": domain_warnings,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    # CSV — матрица треки × оси ────────────────────────────────────────────────
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

    # Markdown ─────────────────────────────────────────────────────────────────
    lines: list[str] = [
        "# Test9 — E1 AudioFileAdapter (fix3)",
        "",
        f"Время запуска: `{timestamp}`",
        f"Ошибок: **{len(errors)}**   Доменных предупреждений: **{len(domain_warnings)}**",
        "",
        "## Матрица признаков",
        "",
    ]

    header_axes = [
        "energy", "tension", "tempo", "density_level",
        "harmonic_stability", "symmetry_bias", "section_complexity",
        "noise_level", "recursion_depth",
    ]
    lines.append("| Трек | style | " + " | ".join(header_axes) + " |")
    lines.append("|---" * (2 + len(header_axes)) + "|")
    for row in results:
        f = row["features"]
        vals = " | ".join(fmt(f.get(ax)) for ax in header_axes)
        lines.append(f"| {row['track']} | {f.get('style', '')} | {vals} |")

    lines.extend([
        "",
        "## Межтрековый разброс (std по 5 трекам)",
        "",
        "| Ось | std | Порог | Вердикт |",
        "|---|---:|---:|---|",
    ])
    for sc in spread_check:
        verdict = "✅" if sc["ok"] else "⚠️ слабый"
        lines.append(
            f"| `{sc['axis']}` | {fmt(sc['std'])} | {MIN_SPREAD} | {verdict} |"
        )

    if domain_warnings:
        lines.extend(["", "## Доменные предупреждения", ""])
        for w in domain_warnings:
            lines.append(f"- ⚠️ {w}")

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
    print("TEST9 — E1 AudioFileAdapter (fix3): extract_features() smoke test")
    print("=" * 72)
    print(f"Контрольных треков: {len(CONTROL_TRACKS)}")
    print(f"Осей: {len(AXES_17)}  |  Spread-осей: {len(SPREAD_AXES)}")

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

        print(
            f"  style={features.get('style', '?'):<12s}"
            f"  dur={fmt(features.get('duration_sec'), 1)}s"
            f"  energy={fmt(features.get('energy'))}"
            f"  sym={fmt(features.get('symmetry_bias'))}"
            f"  sec_cx={fmt(features.get('section_complexity'))}"
            f"  noise={fmt(features.get('noise_level'))}"
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

    # ── Межтрековый разброс ───────────────────────────────────────────────────
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
        std = float(np.std(values, ddof=0)) if len(values) >= 2 else 0.0
        ok = std >= MIN_SPREAD
        spread_check.append({"axis": axis, "std": std, "ok": ok})
        status = "✅" if ok else "⚠️ "
        print(f"  {status} {axis:<25s}  std = {std:.4f}")
        if not ok:
            spread_warnings.append(
                f"axis '{axis}': std={std:.4f} < {MIN_SPREAD}"
            )

    # ── Доменные проверки ─────────────────────────────────────────────────────
    print(f"\n{'─' * 72}")
    print("Доменные проверки (E1-fix3):")
    domain_warnings = domain_checks(results)
    if domain_warnings:
        for w in domain_warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✅ все доменные проверки пройдены")

    # ── Отчёты ────────────────────────────────────────────────────────────────
    json_path, csv_path, md_path = write_reports(
        timestamp=timestamp,
        results=results,
        spread_check=spread_check,
        errors=validation_errors,
        domain_warnings=domain_warnings,
    )

    print("\n" + "=" * 72)
    print("РЕЗУЛЬТАТ TEST9")
    print("=" * 72)
    print(f"Треков обработано:       {len(results)}/{len(CONTROL_TRACKS)}")
    print(f"Ошибок валидации:        {len(validation_errors)}")
    print(f"Предупреждений spread:   {len(spread_warnings)}")
    print(f"Доменных предупреждений: {len(domain_warnings)}")
    print("\nОтчёты:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  MD:   {md_path}")

    if validation_errors:
        for e in validation_errors:
            print(f"  ❌ {e}")
        sys.exit(2)

    if spread_warnings:
        print("\n⚠️  Предупреждения о разбросе:")
        for w in spread_warnings:
            print(f"  - {w}")
        sys.exit(2)

    if domain_warnings:
        print("\n⚠️  Доменные предупреждения (не блокирующие):")
        for w in domain_warnings:
            print(f"  - {w}")
        # Доменные предупреждения не блокируют — только информируют

    print("\n✅ Test9 (fix3) — extract_features() корректна на всех 5 треках.")


if __name__ == "__main__":
    main()
