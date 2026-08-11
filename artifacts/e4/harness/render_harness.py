"""
harness/render_harness.py
Шаг B: запускает resolve_render_params для каждого fixture из manifest,
вычисляет SHA-256 вывода, заполняет audit_matrix.csv.

Схема fixture (fixtures_manifest.yaml):
  id:                 ambient_A
  profile_slug:       ambient
  expected_palette:   lunar_mist
  harmony_theta:      [0.50, ...]      ← список, не dict
  harmony_theta_hash: sha256:...
  variation_seed:     104729           ← детерминированный seed из манифеста
  perceptual:         {energy: 0.25, ...}

E4 — аудит эталонных рендеров, user_preset отсутствует в манифесте.
Передаём NEUTRAL_PRESET (все слайдеры = 0.5 → нулевой сдвиг в слое 3).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))

from lib.style_engine.engine import resolve_render_params

MANIFEST  = Path(__file__).parents[1] / "fixtures_manifest.yaml"
AUDIT_CSV = Path(__file__).parents[1] / "e4_reference_render_audit_v1" / "audit_matrix.csv"

FIELDNAMES = [
    "fixture_id", "style_slug", "genre", "render_sha256", "theta_hash",
    "score_harmony", "score_density", "score_brightness", "score_tension",
    "score_energy", "score_stability", "score_smoothness", "auditor", "notes",
]

THETA_KEYS = [
    "harmony_theta_0", "harmony_theta_1", "harmony_theta_2", "harmony_theta_3",
    "harmony_theta_4", "harmony_theta_5", "harmony_theta_6", "harmony_theta_7",
]

# Нейтральный пресет: все слайдеры = 0.5 → сдвиг = (0.5-0.5)*0.5 = 0.0
# preset_id "neutral" попадёт в RenderParams.preset_id, что корректно для аудита.
NEUTRAL_PRESET: dict = {
    "id":         "neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}


def _sha256(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _theta_dict(theta_list: list) -> dict:
    """Преобразует harmony_theta список → именованный dict для perceptual."""
    return {k: float(v) for k, v in zip(THETA_KEYS, theta_list)}


def _genre_from_fixture_id(fixture_id: str) -> str:
    """ambient_A → ambient, blues_jazz_C → blues_jazz, default_smoke → default."""
    # Суффиксы тиров: _A, _B, _C. _smoke — особый случай default_smoke.
    for suffix in ("_smoke", "_A", "_B", "_C"):
        if fixture_id.endswith(suffix):
            return fixture_id[: -len(suffix)]
    return fixture_id


def run_harness(dry_run: bool = False) -> list:
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    rows: list = []
    for fx in manifest["fixtures"]:
        fid          = fx["id"]
        profile_slug = fx["profile_slug"]
        theta_list   = fx.get("harmony_theta", [])
        theta_hash   = fx.get("harmony_theta_hash", _sha256(theta_list))
        perceptual   = dict(fx.get("perceptual", {}))

        # Добавляем theta-компоненты в perceptual для движка
        if theta_list:
            perceptual.update(_theta_dict(theta_list))

        try:
            rp, sp, ip = resolve_render_params(
                project_id="e4_audit",
                analysis_id=fid,
                perceptual=perceptual,
                style_profile_slug=profile_slug,
                interpretation_profile_slug="default",
                user_preset=NEUTRAL_PRESET,
                strict_theta=True,
            )

            # Переопределяем variation_seed значением из манифеста
            # (движок вычисляет его по-своему, но E4-манифест задаёт эталон)
            manifest_seed = fx.get("variation_seed")
            if manifest_seed is not None:
                rp.variation_seed = int(manifest_seed)

            render_sha = _sha256(rp.__dict__ if hasattr(rp, "__dict__") else rp)

            row = {
                "fixture_id":       fid,
                "style_slug":       profile_slug,
                "genre":            _genre_from_fixture_id(fid),
                "render_sha256":    render_sha,
                "theta_hash":       theta_hash,
                "score_harmony":    "",
                "score_density":    "",
                "score_brightness": "",
                "score_tension":    "",
                "score_energy":     "",
                "score_stability":  "",
                "score_smoothness": "",
                "auditor":          "auto",
                "notes":            "",
            }
            print(f"  OK  {fid}")

        except Exception as exc:
            row = {k: "" for k in FIELDNAMES}
            row.update({
                "fixture_id": fid,
                "style_slug": profile_slug,
                "genre":      _genre_from_fixture_id(fid),
                "notes":      str(exc),
                "auditor":    "error",
            })
            print(f"  ERR {fid}: {exc}", file=sys.stderr)

        rows.append(row)

    if not dry_run:
        AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nАудит записан → {AUDIT_CSV.relative_to(ROOT)}")
    else:
        print("\n[dry-run] CSV не записан.")

    return rows


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run_harness(dry_run=args.dry_run)
