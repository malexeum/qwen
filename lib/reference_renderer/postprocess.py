"""Post-processing: grain, contrast, vignette.

Применяется к финальному uint8 numpy-буферу (H, W, 3).
"""
from __future__ import annotations

import numpy as np


def apply_grain(img: np.ndarray, strength: float = 0.03,
                rng=None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(0)
    noise = rng.standard_normal(img.shape).astype(np.float32) * strength * 255.0
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def apply_contrast(img: np.ndarray, contrast: float = 1.0) -> np.ndarray:
    if abs(contrast - 1.0) < 1e-4:
        return img
    f = (img.astype(np.float32) - 128.0) * contrast + 128.0
    return np.clip(f, 0, 255).astype(np.uint8)


def apply_vignette(img: np.ndarray, strength: float = 0.25) -> np.ndarray:
    H, W = img.shape[:2]
    xs = np.linspace(-1.0, 1.0, W, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, H, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)
    r = np.sqrt(xg ** 2 + yg ** 2)
    vignette = np.clip(1.0 - r * strength, 0.0, 1.0)[..., None]
    return np.clip(img.astype(np.float32) * vignette, 0, 255).astype(np.uint8)


POSTPROCESS_STYLES = {
    "grainfilm": {"grain": 0.030, "contrast": 1.08, "vignette": 0.30},
    "fullcolor":  {"grain": 0.010, "contrast": 1.00, "vignette": 0.10},
    "darkroom":   {"grain": 0.055, "contrast": 1.15, "vignette": 0.45},
    "clean":      {"grain": 0.000, "contrast": 1.00, "vignette": 0.00},
}


def postprocess(img_rgb: np.ndarray, style_slug: str, seed: int = 0) -> np.ndarray:
    """Применяет полную цепочку postprocess к (H, W, 3) uint8."""
    cfg = POSTPROCESS_STYLES.get(style_slug, POSTPROCESS_STYLES["grainfilm"])
    rng = np.random.default_rng(seed)
    out = img_rgb
    if cfg["contrast"] != 1.0:
        out = apply_contrast(out, cfg["contrast"])
    if cfg["grain"] > 0:
        out = apply_grain(out, cfg["grain"], rng)
    if cfg["vignette"] > 0:
        out = apply_vignette(out, cfg["vignette"])
    return out
