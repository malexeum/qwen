"""
harness/render_harness.py
Шаг B: запускает resolve_render_params для каждого fixture из manifest,
вычисляет SHA-256 вывода, заполняет audit_matrix.csv.

Схема fixture (fixtures_manifest.yaml):
  id:              ambient_A
  profile_slug:    ambient          ← не style_slug
  expected_palette: lunar_mist
  harmony_theta:   [0.50, ...]      ← список, не dict
  harmony_theta_hash: sha256:...
  variation_seed:  104729
  perceptual:      {energy: 0.25, ...}
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


def _sha256(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _theta_dict(theta_list: list[float]) -> dict[str, float]:
    """Преобразует harmony_theta список в именованный dict для perceptual."""
    return {k: v for k, v in zip(THETA_KEYS, theta_list)}


def _genre_from_slug(profile_slug: str) -> str:
    """ambient_A → ambient, blues_jazz_B → blues_jazz."""
    # fixture id содержит суффикс _A/_B/_C/_smoke, profile_slug — нет
    return profile_slug


def run_harness(dry_run: bool = False) -> list[dict]:
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    rows: list[dict] = []
    for fx in manifest["fixtures"]:
        fid           = fx["id"]
        profile_slug  = fx["profile_slug"]          # ← правильный ключ манифеста
        theta_list    = fx.get("harmony_theta", [])
        theta_hash    = fx.get("harmony_theta_hash", _sha256(theta_list))
        perceptual    = dict(fx.get("perceptual", {}))

        # Добавляем theta-компоненты в perceptual если движок их ожидает
        if theta_list:
            perceptual.update(_theta_dict(theta_list))
        # Добавляем noise_proxy из perceptual (уже там, просто явно)
        if "noise_proxy" not in perceptual and "noise_proxy" in fx:
            perceptual["noise_proxy"] = fx["noise_proxy"]

        try:
            rp, sp, ip = resolve_render_params(
                project_id="e4_audit",
                analysis_id=fid,
                perceptual=perceptual,
                style_profile_slug=profile_slug,
                interpretation_profile_slug="default",
                strict_theta=True,
            )
            render_sha = _sha256(rp.__dict__ if hasattr(rp, "__dict__") else rp)
            row = {
                "fixture_id":       fid,
                "style_slug":       profile_slug,
                "genre":            _genre_from_slug(profile_slug),
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
                "genre":      _genre_from_slug(profile_slug),
                "notes":      str(exc),
                "auditor":    "error",
            })
            print(f"  ERR {fid}: {exc}", file=sys.stderr)
        rows.append(row)

    if not dry_run:
        with open(AUDIT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nАудит записан → {AUDIT_CSV.relative_to(ROOT)}")
    return rows


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run_harness(dry_run=args.dry_run)
