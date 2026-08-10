"""ReferenceRenderer C1 — высокоуровневая точка входа."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .blend_compositor import composite_layers
from .fractal_runner import is_fractal, run_fractal_layer
from .palette_mapper import apply_palette
from .plan_loader import load_plan
from .png_exporter import export_png
from .procedural_runner import run_procedural
from .silence_mask import apply_silence_mask, build_silence_mask


def _load_palettes() -> dict:
    """Loads palettes.yaml from configs/.

    palettes.yaml v0.3 структура:
      palettes:
        neutral_noir: { background_rgba: ..., dominant_stops: [...], ... }
        nocturne_amber: { ... }
        ...
    То есть palettes — dict, не list.
    """
    try:
        import yaml
    except ImportError:
        return {}
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "configs" / "palettes.yaml"
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            raw = data.get("palettes", {})
            if isinstance(raw, dict):
                # Формат v0.3: {palette_id: {dominant_stops, ...}}
                return {pid: p for pid, p in raw.items()}
            elif isinstance(raw, list):
                # Старый формат (list собъектов с полем palette_id)
                return {p["palette_id"]: p for p in raw if "palette_id" in p}
            return {}
    return {}


def render(
    plan_path: str | Path,
    output_dir: str | Path = "output/previews",
) -> Path:
    """
    Главная точка входа C1.
    Вход:  plan_path — путь к plan.json (visual_composition_plan.json)
    Выход: Path к preview_<plan_id>.png 1024×1024 sRGB
    """
    plan = load_plan(plan_path)
    plan_id = plan["plan_id"]
    canvas_spec = plan.get("canvas", {})
    W = int(canvas_spec.get("width_px", 1024))
    H = int(canvas_spec.get("height_px", 1024))
    profile_id = plan.get("visual_identity", {}).get("profile_id", "")
    base_seed = plan.get("seed", 42)

    palettes = _load_palettes()

    layers_out: list[dict] = []

    for i, layer in enumerate(plan.get("layers", [])):
        if not layer.get("enabled", True):
            continue

        generator_id = layer.get("generator_id", "")
        params       = layer.get("params", {})
        palette_id   = layer.get("palette_id", "")
        blend_mode   = layer.get("blend_mode", "normal")
        opacity      = float(layer.get("opacity", 1.0))
        z_index      = int(layer.get("z_index", i))
        layer_seed   = int(layer.get("seed", base_seed + i))

        frac = float(layer.get("computation_resolution_fraction", 0.5))
        lW = max(64, int(W * frac))
        lH = max(64, int(H * frac))

        if is_fractal(generator_id):
            orbit_map = run_fractal_layer(generator_id, params, lW, lH, layer_seed)
        elif generator_id in {"orbital_field", "colored_noise_field", "symmetry_snowflake"}:
            orbit_map = run_procedural(generator_id, params, lW, lH, layer_seed)
        else:
            continue

        palette = palettes.get(palette_id, {})
        rgba = apply_palette(orbit_map, palette)  # uint8 [lH, lW, 4]

        if lW != W or lH != H:
            img  = Image.fromarray(rgba, mode="RGBA")
            img  = img.resize((W, H), Image.LANCZOS)
            rgba = np.asarray(img)

        layers_out.append({
            "rgba":       rgba,
            "blend_mode": blend_mode,
            "opacity":    opacity,
            "z_index":    z_index,
        })

    if not layers_out:
        canvas = np.zeros((H, W, 3), dtype=np.float32)
    else:
        canvas = composite_layers(layers_out, W, H)

    silence = plan.get("silence_mask", {})
    if silence.get("enabled", False):
        mask = build_silence_mask(
            coverage=float(silence.get("coverage", 0.0)),
            direction=float(silence.get("direction", 0.5)),
            edge_softness=float(silence.get("edge_softness", 0.3)),
            W=W,
            H=H,
        )
        canvas = apply_silence_mask(canvas, mask)

    if W != 1024 or H != 1024:
        img = Image.fromarray(
            np.clip(canvas * 255, 0, 255).astype(np.uint8), mode="RGB"
        )
        img    = img.resize((1024, 1024), Image.LANCZOS)
        canvas = np.asarray(img).astype(np.float32) / 255.0

    out_path = Path(output_dir) / f"preview_{plan_id}.png"
    return export_png(
        canvas,
        out_path,
        plan_id=plan_id,
        profile_id=profile_id,
        palette_id=plan.get("visual_identity", {}).get("palette_id", ""),
    )
