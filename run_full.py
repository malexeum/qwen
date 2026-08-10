"""run_full.py — полный прогон пайплайна для 5 стилей.

Цепочка:
  audio_features → PerceptualLatent / RenderParams
  → build_visual_composition_plan  (save_artifacts=True)
       → storage/poster_runs/{plan_id}/visual_composition_plan.json
       → storage/poster_runs/{plan_id}/parameter_coverage.json
       → storage/poster_runs/{plan_id}/planner_diagnostics.json
  → C1 render (lib/renderer/reference_renderer.py)
       → storage/poster_runs/{plan_id}/poster.png  (1024×1024 sRGB)

Запуск:
  python run_full.py
Необязательные флаги:
  python run_full.py --style electronic   # один стиль
  python run_full.py --no-render          # только plan.json, без PNG
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lib.audio_analysis.analysis import build_perceptual_latent
from lib.composition.planner import (
    PerceptualLatent,
    RenderParams,
    TrackMetadata,
    build_visual_composition_plan,
)

STORAGE_ROOT = Path(r"D:\WORK\AVCoder\storage\poster_runs")

# ── Стили ──────────────────────────────────────────────────────────────────
_SLUG_MAP = {
    "blues":      "blues_jazz",
    "jazz":       "jazz",
    "electronic": "electronic",
    "ambient":    "ambient",
    "classical":  "classical",
    "rock":       "electronic",
    "pop":        "blues_jazz",
    "soundtrack": "classical",
    "mixed":      "blues_jazz",
}
_SLUG_DEFAULT = "blues_jazz"

STYLES: list[tuple[str, dict]] = [
    ("blues",      {"suggested_music_style": "blues",      "bpm": 110.0, "brightness": 0.08,  "repetition_score": 0.90}),
    ("electronic", {"suggested_music_style": "electronic",  "bpm": 145.0, "energy": 0.30,    "brightness": 0.25, "rhythm_density": 0.65}),
    ("jazz",       {"suggested_music_style": "jazz",        "bpm": 115.0, "brightness": 0.12, "energy": 0.14}),
    ("ambient",    {"suggested_music_style": "ambient",     "bpm": 75.0,  "brightness": 0.05, "rhythm_density": 0.35, "energy": 0.08}),
    ("classical",  {"suggested_music_style": "classical",   "bpm": 90.0,  "brightness": 0.07, "energy": 0.09,   "repetition_score": 0.60}),
]

_BASE = {
    "bpm": 120.0, "key": "A", "energy": 0.15,
    "spectral_centroid": 2200.0, "brightness": 0.10,
    "rhythm_density": 0.50, "dynamic_range": 14.0,
    "duration_sec": 180.0, "repetition_score": 0.80,
    "silence_rate": 0.05, "harmonic_stability": 0.75,
    "harmonic_change_rate_hz": 0.3, "spectral_flatness": 0.10,
    "high_frequency_energy_ratio": 0.15,
    "suggested_music_style": "blues",
    "sections": [
        {"id": "S1", "label": "Section 1", "start_sec": 0.0,   "end_sec": 30.0},
        {"id": "S2", "label": "Section 2", "start_sec": 30.0,  "end_sec": 60.0},
        {"id": "S3", "label": "Section 3", "start_sec": 60.0,  "end_sec": 90.0},
        {"id": "S4", "label": "Section 4", "start_sec": 90.0,  "end_sec": 120.0},
        {"id": "S5", "label": "Section 5", "start_sec": 120.0, "end_sec": 150.0},
        {"id": "S6", "label": "Section 6", "start_sec": 150.0, "end_sec": 180.0},
    ],
    "recurrence_groups": [
        {"group_id": "G1", "sections": ["S1", "S3"]},
        {"group_id": "G2", "sections": ["S2", "S4"]},
    ],
    "events": [
        {"type": "energy_peak", "time_sec": 15.0,  "description": "High energy frame"},
        {"type": "energy_peak", "time_sec": 75.0,  "description": "High energy frame"},
        {"type": "energy_peak", "time_sec": 135.0, "description": "High energy frame"},
    ],
}


# ── Хелперы ────────────────────────────────────────────────────────────────

def _make_features(overrides: dict) -> dict:
    f = dict(_BASE)
    f.update(overrides)
    return f


def _make_latent(features: dict) -> PerceptualLatent:
    lat = build_perceptual_latent(features)
    max_bpm = 220.0
    return PerceptualLatent(
        energy=float(lat.get("energy", 0.5)),
        tension=float(lat.get("tension", 0.5)),
        repetition=float(lat.get("repetition", 0.5)),
        tempo=float(min(lat.get("tempo_bpm", 120.0) / max_bpm, 1.0)),
        section_complexity=float(lat.get("section_complexity", 0.5)),
        silence_rate=float(lat.get("silence_rate", 0.2)),
        harmonic_stability=float(lat.get("harmonic_stability", 0.5)),
        harmonic_change_rate=float(min(lat.get("harmonic_change_rate_hz", 0.0), 1.0)),
        spectral_flatness=float(lat.get("spectral_flatness", 0.5)),
        high_frequency_energy=float(lat.get("high_frequency_energy_ratio", 0.5)),
    )


def _make_render_params(features: dict) -> RenderParams:
    style = features.get("suggested_music_style", "blues")
    slug = _SLUG_MAP.get(style, _SLUG_DEFAULT)
    lat = build_perceptual_latent(features)
    return RenderParams(
        style_profile_slug=slug,
        symmetry_bias=float(lat.get("stability", 0.5)),
        density_level=float(lat.get("density", 0.5)),
        noise_level=float(lat.get("spectral_flatness", 0.1)),
        motion_intensity=float(lat.get("tension", 0.5)),
        texture_complexity=float(lat.get("section_complexity", 0.5)),
        palette_id="",
    )


def run_style(
    style_name: str,
    overrides: dict,
    do_render: bool = True,
) -> dict:
    """Прогон одного стиля. Возвращает словарь с результатами."""
    t0 = time.perf_counter()
    features = _make_features(overrides)
    perceptual = _make_latent(features)
    render_p   = _make_render_params(features)
    track_meta = TrackMetadata(
        audio_content_hash=f"full_run_{style_name}_0001",
        title=f"{style_name.capitalize()} Demo Track",
        artist="AVCoder Demo",
        duration_ms=180_000,
    )

    # ── Planner: сохраняет plan.json + coverage + diagnostics ──────────────────
    plan = build_visual_composition_plan(
        perceptual=perceptual,
        render_params=render_p,
        track_metadata=track_meta,
        save_artifacts=True,
        storage_root=STORAGE_ROOT,
    )
    plan_dir = STORAGE_ROOT / plan.plan_id
    t_plan = time.perf_counter() - t0

    png_path: Path | None = None
    t_render: float | None = None

    if do_render:
        # ── C1 Renderer: читает plan.json → poster.png ───────────────────────
        from lib.renderer.reference_renderer import render as c1_render
        t1 = time.perf_counter()
        plan_json_path = plan_dir / "visual_composition_plan.json"
        png_path = c1_render(plan_json_path, output_dir=plan_dir)
        # Переименуем preview_*.png → poster.png для удобства
        poster_path = plan_dir / "poster.png"
        if png_path.name != "poster.png":
            png_path.rename(poster_path)
            png_path = poster_path
        t_render = time.perf_counter() - t1

    return {
        "style":     style_name,
        "plan_id":   plan.plan_id,
        "plan_dir":  str(plan_dir),
        "png_path":  str(png_path) if png_path else None,
        "t_plan_s":  round(t_plan, 2),
        "t_render_s": round(t_render, 2) if t_render is not None else None,
        "layers_enabled": sum(1 for l in plan.layers if l.enabled),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline run")
    parser.add_argument("--style", default=None,
                        help="Run only this style (blues/electronic/jazz/ambient/classical)")
    parser.add_argument("--no-render", action="store_true",
                        help="Skip C1 render, only save plan.json")
    args = parser.parse_args()

    styles = STYLES
    if args.style:
        styles = [(n, o) for n, o in STYLES if n == args.style]
        if not styles:
            print(f"[ERROR] Unknown style '{args.style}'. Available: {[n for n,_ in STYLES]}")
            return

    do_render = not args.no_render
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Full Pipeline Run  |  styles: {len(styles)}  |  render: {do_render}")
    print(f"  storage: {STORAGE_ROOT}")
    print(f"{'='*60}\n")

    results = []
    for style_name, overrides in styles:
        print(f"[{style_name:12s}] building plan ...", end=" ", flush=True)
        try:
            r = run_style(style_name, overrides, do_render=do_render)
            results.append(r)
            render_info = f"render {r['t_render_s']:.1f}s" if r['t_render_s'] else "no render"
            print(f"✓  plan {r['t_plan_s']:.2f}s  {render_info}  layers={r['layers_enabled']}")
            print(f"             plan_id : {r['plan_id']}")
            print(f"             dir     : {r['plan_dir']}")
            if r['png_path']:
                print(f"             poster  : {r['png_path']}")
        except Exception as exc:
            print(f"✗  ERROR: {exc}")
            import traceback; traceback.print_exc()
        print()

    print(f"{'='*60}")
    print(f"  Done: {len(results)}/{len(styles)} styles")
    total_render = sum(r['t_render_s'] for r in results if r['t_render_s'])
    if total_render:
        print(f"  Total render time : {total_render:.1f}s")
    print(f"{'='*60}\n")

    # Сохраняем суммарь руна
    summary_path = STORAGE_ROOT / "run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Summary saved: {summary_path}\n")


if __name__ == "__main__":
    main()
