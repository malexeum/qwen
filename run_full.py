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
Опциональные флаги:
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

# ── Маппинг music style → profile slug ─────────────────────────────────────
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

# ── D1: дифференцированные features по 17 осям для каждого профиля ──────────
# Ключевые контрасты:
#   electronic : energy=0.88, silence_rate=0.08, density_level=0.85
#   ambient    : energy=0.22, silence_rate=0.52, harmonic_stability=0.88
#   classical  : symmetry_bias=0.72, harmonic_stability=0.82, noise_level=0.08
#   jazz       : silence_rate=0.32, symmetry_bias=0.30, density_level=0.42
#   blues_jazz : посредина по всем осям
FEATURES: dict[str, dict] = {
    "blues": {
        "suggested_music_style": "blues",
        "bpm": 110.0,
        "energy": 0.55,           "tension": 0.38,         "repetition_score": 0.62,
        "tempo": 0.42,            "section_complexity": 0.58, "silence_rate": 0.24,
        "harmonic_stability": 0.72, "harmonic_change_rate_hz": 0.28,
        "noise_level": 0.18,      "spectral_flatness": 0.22,
        "high_frequency_energy_ratio": 0.20, "density_level": 0.55,
        "motion_intensity": 0.40, "texture_complexity": 0.52,
        "symmetry_bias": 0.45,    "layout_macro_shape": 0.35,
        "recursion_depth": 0.62,
        "brightness": 0.08,       "rhythm_density": 0.50,  "dynamic_range": 14.0,
        "duration_sec": 180.0,
        "spectral_centroid": 2200.0,
        "sections": [
            {"id": "S1", "label": "Intro",   "start_sec": 0.0,   "end_sec": 30.0},
            {"id": "S2", "label": "Verse",   "start_sec": 30.0,  "end_sec": 90.0},
            {"id": "S3", "label": "Chorus",  "start_sec": 90.0,  "end_sec": 150.0},
            {"id": "S4", "label": "Outro",   "start_sec": 150.0, "end_sec": 180.0},
        ],
        "recurrence_groups": [{"group_id": "G1", "sections": ["S2", "S3"]}],
        "events": [{"type": "energy_peak", "time_sec": 75.0, "description": "Chorus peak"}],
    },
    "electronic": {
        "suggested_music_style": "electronic",
        "bpm": 145.0,
        "energy": 0.88,           "tension": 0.82,         "repetition_score": 0.70,
        "tempo": 0.78,            "section_complexity": 0.75, "silence_rate": 0.08,
        "harmonic_stability": 0.25, "harmonic_change_rate_hz": 0.72,
        "noise_level": 0.55,      "spectral_flatness": 0.80,
        "high_frequency_energy_ratio": 0.78, "density_level": 0.85,
        "motion_intensity": 0.88, "texture_complexity": 0.82,
        "symmetry_bias": 0.22,    "layout_macro_shape": 0.62,
        "recursion_depth": 0.90,
        "brightness": 0.25,       "rhythm_density": 0.65,  "dynamic_range": 10.0,
        "duration_sec": 240.0,
        "spectral_centroid": 4500.0,
        "sections": [
            {"id": "S1", "label": "Build",   "start_sec": 0.0,   "end_sec": 60.0},
            {"id": "S2", "label": "Drop",    "start_sec": 60.0,  "end_sec": 120.0},
            {"id": "S3", "label": "Break",   "start_sec": 120.0, "end_sec": 180.0},
            {"id": "S4", "label": "Climax",  "start_sec": 180.0, "end_sec": 240.0},
        ],
        "recurrence_groups": [{"group_id": "G1", "sections": ["S2", "S4"]}],
        "events": [
            {"type": "energy_peak", "time_sec": 60.0,  "description": "First drop"},
            {"type": "energy_peak", "time_sec": 180.0, "description": "Final drop"},
        ],
    },
    "jazz": {
        "suggested_music_style": "jazz",
        "bpm": 115.0,
        "energy": 0.52,           "tension": 0.48,         "repetition_score": 0.38,
        "tempo": 0.48,            "section_complexity": 0.65, "silence_rate": 0.32,
        "harmonic_stability": 0.55, "harmonic_change_rate_hz": 0.45,
        "noise_level": 0.22,      "spectral_flatness": 0.35,
        "high_frequency_energy_ratio": 0.28, "density_level": 0.42,
        "motion_intensity": 0.55, "texture_complexity": 0.60,
        "symmetry_bias": 0.30,    "layout_macro_shape": 0.48,
        "recursion_depth": 0.55,
        "brightness": 0.12,       "rhythm_density": 0.48,  "dynamic_range": 16.0,
        "duration_sec": 200.0,
        "spectral_centroid": 2800.0,
        "sections": [
            {"id": "S1", "label": "Head",    "start_sec": 0.0,   "end_sec": 50.0},
            {"id": "S2", "label": "Solo1",   "start_sec": 50.0,  "end_sec": 100.0},
            {"id": "S3", "label": "Solo2",   "start_sec": 100.0, "end_sec": 150.0},
            {"id": "S4", "label": "Outro",   "start_sec": 150.0, "end_sec": 200.0},
        ],
        "recurrence_groups": [{"group_id": "G1", "sections": ["S1", "S4"]}],
        "events": [{"type": "energy_peak", "time_sec": 80.0, "description": "Solo peak"}],
    },
    "ambient": {
        "suggested_music_style": "ambient",
        "bpm": 75.0,
        "energy": 0.22,           "tension": 0.12,         "repetition_score": 0.80,
        "tempo": 0.18,            "section_complexity": 0.30, "silence_rate": 0.52,
        "harmonic_stability": 0.88, "harmonic_change_rate_hz": 0.10,
        "noise_level": 0.08,      "spectral_flatness": 0.15,
        "high_frequency_energy_ratio": 0.08, "density_level": 0.22,
        "motion_intensity": 0.18, "texture_complexity": 0.25,
        "symmetry_bias": 0.70,    "layout_macro_shape": 0.50,
        "recursion_depth": 0.30,
        "brightness": 0.05,       "rhythm_density": 0.35,  "dynamic_range": 20.0,
        "duration_sec": 360.0,
        "spectral_centroid": 1200.0,
        "sections": [
            {"id": "S1", "label": "Drift1",  "start_sec": 0.0,   "end_sec": 90.0},
            {"id": "S2", "label": "Drift2",  "start_sec": 90.0,  "end_sec": 180.0},
            {"id": "S3", "label": "Drift3",  "start_sec": 180.0, "end_sec": 270.0},
            {"id": "S4", "label": "Fade",    "start_sec": 270.0, "end_sec": 360.0},
        ],
        "recurrence_groups": [{"group_id": "G1", "sections": ["S1", "S2", "S3"]}],
        "events": [],
    },
    "classical": {
        "suggested_music_style": "classical",
        "bpm": 90.0,
        "energy": 0.48,           "tension": 0.30,         "repetition_score": 0.68,
        "tempo": 0.38,            "section_complexity": 0.55, "silence_rate": 0.28,
        "harmonic_stability": 0.82, "harmonic_change_rate_hz": 0.22,
        "noise_level": 0.08,      "spectral_flatness": 0.18,
        "high_frequency_energy_ratio": 0.15, "density_level": 0.45,
        "motion_intensity": 0.30, "texture_complexity": 0.48,
        "symmetry_bias": 0.72,    "layout_macro_shape": 0.28,
        "recursion_depth": 0.65,
        "brightness": 0.07,       "rhythm_density": 0.40,  "dynamic_range": 22.0,
        "duration_sec": 300.0,
        "spectral_centroid": 1800.0,
        "sections": [
            {"id": "S1", "label": "Exposition",   "start_sec": 0.0,   "end_sec": 75.0},
            {"id": "S2", "label": "Development",  "start_sec": 75.0,  "end_sec": 150.0},
            {"id": "S3", "label": "Recapitulation","start_sec": 150.0, "end_sec": 225.0},
            {"id": "S4", "label": "Coda",          "start_sec": 225.0, "end_sec": 300.0},
        ],
        "recurrence_groups": [{"group_id": "G1", "sections": ["S1", "S3"]}],
        "events": [{"type": "energy_peak", "time_sec": 150.0, "description": "Recapitulation"}],
    },
}

STYLES: list[tuple[str, str]] = [
    ("blues",      "blues_jazz"),
    ("electronic", "electronic"),
    ("jazz",       "jazz"),
    ("ambient",    "ambient"),
    ("classical",  "classical"),
]


# ── Хелперы ────────────────────────────────────────────────────────────────

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


def _make_render_params(features: dict, slug: str) -> RenderParams:
    lat = build_perceptual_latent(features)
    return RenderParams(
        style_profile_slug=slug,
        symmetry_bias=float(features.get("symmetry_bias", lat.get("stability", 0.5))),
        density_level=float(features.get("density_level", lat.get("density", 0.5))),
        noise_level=float(features.get("noise_level", lat.get("spectral_flatness", 0.1))),
        motion_intensity=float(features.get("motion_intensity", lat.get("tension", 0.5))),
        texture_complexity=float(features.get("texture_complexity", lat.get("section_complexity", 0.5))),
        palette_id="",
    )


def run_style(
    style_name: str,
    profile_slug: str,
    do_render: bool = True,
) -> dict:
    """Прогон одного стиля."""
    t0 = time.perf_counter()
    features = FEATURES[style_name]
    perceptual = _make_latent(features)
    render_p   = _make_render_params(features, profile_slug)
    track_meta = TrackMetadata(
        audio_content_hash=f"full_run_{style_name}_d1_0001",
        title=f"{style_name.capitalize()} Demo Track",
        artist="AVCoder Demo",
        duration_ms=int(features.get("duration_sec", 180) * 1000),
    )

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
        from lib.renderer.reference_renderer import render as c1_render
        t1 = time.perf_counter()
        plan_json_path = plan_dir / "visual_composition_plan.json"
        png_path = c1_render(plan_json_path, output_dir=plan_dir)
        poster_path = plan_dir / "poster.png"
        if png_path.name != "poster.png":
            png_path.rename(poster_path)
            png_path = poster_path
        t_render = time.perf_counter() - t1

    return {
        "style":      style_name,
        "slug":       profile_slug,
        "plan_id":    plan.plan_id,
        "plan_dir":   str(plan_dir),
        "png_path":   str(png_path) if png_path else None,
        "t_plan_s":   round(t_plan, 2),
        "t_render_s": round(t_render, 2) if t_render is not None else None,
        "layers_enabled": sum(1 for l in plan.layers if l.enabled),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline run — D1")
    parser.add_argument("--style", default=None,
                        help="Run only this style (blues/electronic/jazz/ambient/classical)")
    parser.add_argument("--no-render", action="store_true",
                        help="Skip C1 render, save plan.json only")
    args = parser.parse_args()

    styles = STYLES
    if args.style:
        styles = [(n, s) for n, s in STYLES if n == args.style]
        if not styles:
            print(f"[ERROR] Unknown style '{args.style}'. Available: {[n for n,_ in STYLES]}")
            return

    do_render = not args.no_render
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Full Pipeline Run D1  |  styles: {len(styles)}  |  render: {do_render}")
    print(f"  storage: {STORAGE_ROOT}")
    print(f"{'='*60}\n")

    results = []
    for style_name, slug in styles:
        print(f"[{style_name:12s}] building plan ...", end=" ", flush=True)
        try:
            r = run_style(style_name, slug, do_render=do_render)
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

    summary_path = STORAGE_ROOT / "run_summary_d1.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Summary saved: {summary_path}\n")


if __name__ == "__main__":
    main()
