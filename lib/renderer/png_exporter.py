"""PNGExporter — сохранение PNG 1024×1024 с метаданными."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, PngImagePlugin


def export_png(
    canvas: np.ndarray,  # float32 [H, W, 3] in [0, 1] OR uint8 [H, W, 3]
    output_path: str | Path,
    plan_id: str = "",
    profile_id: str = "",
    palette_id: str = "",
) -> Path:
    """
    Сохраняет PNG. Если canvas float32 — конвертирует в uint8.
    Вписывает метаданные plan_id, profile_id, palette_id в PNG tEXt chunks.
    Возвращает Path к сохранённому файлу.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if canvas.dtype != np.uint8:
        arr = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
    else:
        arr = canvas

    img = Image.fromarray(arr, mode="RGB")

    meta = PngImagePlugin.PngInfo()
    meta.add_text("plan_id", plan_id)
    meta.add_text("profile_id", profile_id)
    meta.add_text("palette_id", palette_id)

    img.save(str(path), format="PNG", pnginfo=meta)
    return path
