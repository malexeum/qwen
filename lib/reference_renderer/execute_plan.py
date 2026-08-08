"""execute_plan — главная точка входа Этапа 6.

Принимает VisualCompositionPlan → рендерит 1024×1024 PNG.
PIL используется ТОЛЬКО здесь для финального сохранения.
lib.composition остаётся без PIL.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from lib.composition.schema import VisualCompositionPlan
from .canvas import Canvas
from .blend import composite
from .layer_executor import execute_layer
from .postprocess import postprocess


@dataclass
class RenderResult:
    plan_id: str
    output_path: Optional[Path]
    width: int
    height: int
    layers_rendered: int
    layers_skipped: int


def execute_plan(
    plan: VisualCompositionPlan,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    save_png: bool = True,
) -> RenderResult:
    """Рендер VisualCompositionPlan → PNG.

    Args:
        plan:        Готовый VisualCompositionPlan из build_visual_composition_plan().
        output_dir:  Папка для сохранения PNG. По умолчанию poster_runs/{plan_id}/.
        filename:    Имя файла PNG. По умолчанию poster.png.
        save_png:    Если False — рендер без записи на диск (для тестов).

    Returns:
        RenderResult с путём к PNG и статистикой рендера.
    """
    W = plan.canvas.width_px
    H = plan.canvas.height_px

    # ── Загрузка палитры ──────────────────────────────────────────────────────
    palettes_cfg = getattr(plan, "_palettes_cfg", None)
    if palettes_cfg is None:
        from lib.composition.config_loader import load_composition_config
        cfg = load_composition_config()
        palettes_cfg = cfg.palettes

    # ── Canvas ────────────────────────────────────────────────────────────────
    canvas = Canvas.black(W, H)
    bg_palette_id = (
        plan.visual_identity.palette_id
        if plan.visual_identity else "neutral_noir"
    )
    try:
        from .palette import resolve_palette
        bg_palette = resolve_palette(bg_palette_id, palettes_cfg)
        canvas.fill_background(bg_palette.background_rgba)
    except Exception:
        canvas.fill_background((7, 9, 18, 255))

    # ── Рендер слоёв в порядке z_index ────────────────────────────────────────
    layers_rendered = 0
    layers_skipped = 0
    layers_sorted = sorted(plan.layers, key=lambda l: l.z_index)

    for layer in layers_sorted:
        if not layer.enabled:
            layers_skipped += 1
            continue
        try:
            layer_rgba = execute_layer(layer, palettes_cfg, W, H)
        except Exception as exc:
            import warnings
            warnings.warn(f"Layer '{layer.layer_id}' render failed: {exc}")
            layers_skipped += 1
            continue

        canvas.data = composite(canvas.data, layer_rgba,
                                mode=layer.blend_mode or "normal")
        layers_rendered += 1

    # ── Post-processing ───────────────────────────────────────────────────────
    img_uint8 = canvas.to_uint8()          # (H, W, 4) uint8
    img_rgb   = img_uint8[..., :3]         # (H, W, 3) uint8
    style_slug = (
        plan.visual_identity.postprocess_style_slug
        if plan.visual_identity else "grainfilm"
    )
    base_seed = int(getattr(plan, "base_seed", 0) % (2**31))
    img_rgb = postprocess(img_rgb, style_slug, seed=base_seed)

    # ── Сохранение PNG (PIL только здесь) ────────────────────────────────────
    output_path: Optional[Path] = None
    if save_png:
        from PIL import Image
        if output_dir is None:
            output_dir = Path("poster_runs") / plan.plan_id
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = filename or "poster.png"
        output_path = output_dir / fname
        Image.fromarray(img_rgb, mode="RGB").save(str(output_path), "PNG")

    return RenderResult(
        plan_id=plan.plan_id,
        output_path=output_path,
        width=W,
        height=H,
        layers_rendered=layers_rendered,
        layers_skipped=layers_skipped,
    )
