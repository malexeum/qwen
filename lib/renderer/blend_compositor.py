"""BlendCompositor — наложение слоёв по z_index через blend_mode."""
from __future__ import annotations

import numpy as np


def _blend_normal(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    return src * opacity + dst * (1.0 - opacity)


def _blend_screen(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    screened = 1.0 - (1.0 - src) * (1.0 - dst)
    return screened * opacity + dst * (1.0 - opacity)


def _blend_add(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    return np.clip(src * opacity + dst, 0.0, 1.0)


def _blend_multiply(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    multiplied = src * dst
    return multiplied * opacity + dst * (1.0 - opacity)


def _blend_soft_light(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    # Photoshop soft-light formula
    low = 2.0 * src * dst + dst ** 2 * (1.0 - 2.0 * src)
    high = 2.0 * dst * (1.0 - src) + np.sqrt(dst) * (2.0 * src - 1.0)
    sl = np.where(src <= 0.5, low, high)
    return sl * opacity + dst * (1.0 - opacity)


def _blend_max(src: np.ndarray, dst: np.ndarray, opacity: float) -> np.ndarray:
    maxed = np.maximum(src, dst)
    return maxed * opacity + dst * (1.0 - opacity)


_BLEND_FUNCS = {
    "normal": _blend_normal,
    "screen": _blend_screen,
    "add": _blend_add,
    "multiply": _blend_multiply,
    "soft_light": _blend_soft_light,
    "max": _blend_max,
}


def composite_layers(
    layers: list[dict],  # [{"rgba": np.ndarray uint8 [H,W,4], "blend_mode": str, "opacity": float, "z_index": int}]
    W: int,
    H: int,
) -> np.ndarray:
    """
    Накладывает слои в порядке возрастания z_index.
    Возвращает float32 [H, W, 3] в [0, 1] (RGB без alpha).
    """
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    sorted_layers = sorted(layers, key=lambda x: x.get("z_index", 0))

    for layer in sorted_layers:
        rgba = layer["rgba"].astype(np.float32) / 255.0  # [H, W, 4]
        src = rgba[:, :, :3]  # RGB
        opacity = float(layer.get("opacity", 1.0))
        blend_mode = layer.get("blend_mode", "normal")
        func = _BLEND_FUNCS.get(blend_mode, _blend_normal)
        canvas = func(src, canvas, opacity)
        canvas = np.clip(canvas, 0.0, 1.0)

    return canvas
