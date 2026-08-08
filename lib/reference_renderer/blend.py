"""Blend mode compositing — float32 RGBA buffers.

Все режимы работают с (H, W, 4) float32 ∈ [0, 1].
Returns composited (H, W, 4) float32.
"""
from __future__ import annotations

import numpy as np


def _alpha_composite(dst: np.ndarray, src: np.ndarray,
                     blended_rgb: np.ndarray) -> np.ndarray:
    """Porter-Duff over: src over dst с pre-multiplied alpha."""
    a_s = src[..., 3:4]
    a_d = dst[..., 3:4]
    a_out = a_s + a_d * (1.0 - a_s)
    safe = np.where(a_out > 1e-7, a_out, 1.0)
    rgb_out = (blended_rgb * a_s + dst[..., :3] * a_d * (1.0 - a_s)) / safe
    return np.concatenate([np.clip(rgb_out, 0, 1),
                           np.clip(a_out, 0, 1)], axis=-1).astype(np.float32)


def composite(dst: np.ndarray, src: np.ndarray, mode: str) -> np.ndarray:
    """Композит src поверх dst с заданным blend mode."""
    s = src[..., :3]
    d = dst[..., :3]

    if mode == "normal":
        blended = s
    elif mode == "screen":
        blended = 1.0 - (1.0 - s) * (1.0 - d)
    elif mode == "add":
        blended = np.clip(s + d, 0.0, 1.0)
    elif mode == "multiply":
        blended = s * d
    elif mode == "soft_light":
        blended = (1.0 - 2 * s) * d * d + 2 * s * d
    elif mode == "max":
        blended = np.maximum(s, d)
    else:
        blended = s  # fallback → normal

    return _alpha_composite(dst, src, blended)
