"""
harness/render_harness.py
Шаг B: запускает resolve_render_params для каждого fixture из manifest,
вычисляет SHA-256 вывода, заполняет audit_matrix.csv.
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

MANIFEST = Path(__file__).parents[1] / "fixtures_manifest.yaml"
AUDIT_CSV = Path(__file__).parents[1] / "e4_reference_render_audit_v1" / "audit_matrix.csv"

FIELDNAMES = [
    "fixture_id", "style_slug", "genre", "render_sha256", "theta_hash",
    "score_harmony", "score_density", "score_brightness", "score_tension",
    "score_energy", "score_stability", "score_smoothness", "auditor", "notes",
]


def _sha256(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def run_harness(dry_run: bool = False) -> list[dict]:
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    rows: list[dict] = []
    for fx in manifest["fixtures"]:
        fid = fx["id"]
        try:
            rp, sp, ip = resolve_render_params(
                project_id="e4_audit",
                analysis_id=fid,
                perceptual=fx["perceptual"] | fx.get("theta", {}),
                style_profile_slug=fx["style_slug"],
                interpretation_profile_slug="default",
                user_preset=fx["user_preset"],
                strict_theta=True,
            )
            render_sha = _sha256(rp.__dict__ if hasattr(rp, "__dict__") else rp)
            theta_hash = _sha256(fx.get("theta", {}))
            row = {
                "fixture_id":       fid,
                "style_slug":       fx["style_slug"],
                "genre":            fx["genre"],
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
            row.update({"fixture_id": fid, "style_slug": fx["style_slug"],
                         "genre": fx["genre"], "notes": str(exc), "auditor": "error"})
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
