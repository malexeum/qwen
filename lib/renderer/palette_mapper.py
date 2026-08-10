"""PaletteMapper — применение цветовой палитры к orbit_map -> RGBA."""
from __future__ import annotations

import numpy as np


def apply_palette(orbit_map: np.ndarray, palette: dict) -> np.ndarray:
    """
    orbit_map: float32 [H, W] in [0, 1]
    palette: dict с ключом 'dominant_stops': [{position, color}, ...]
    Возвращает uint8 [H, W, 4] RGBA, alpha=255 везде.
    """
    stops = palette.get("dominant_stops", [])
    if not stops:
        # Fallback: grayscale
        H, W = orbit_map.shape
        grey = (orbit_map * 255).astype(np.uint8)
        rgba = np.stack([grey, grey, grey, np.full((H, W), 255, dtype=np.uint8)], axis=-1)
        return rgba

    positions = np.array([s["position"] for s in stops], dtype=np.float32)
    colors = np.array([
        [int(s["color"][1:3], 16),
         int(s["color"][3:5], 16),
         int(s["color"][5:7], 16)]
        for s in stops
    ], dtype=np.float32)

    H, W = orbit_map.shape
    flat = orbit_map.ravel().astype(np.float32)

    # Векторизованная интерполяция по каждому каналу
    r = np.interp(flat, positions, colors[:, 0]).astype(np.uint8)
    g = np.interp(flat, positions, colors[:, 1]).astype(np.uint8)
    b = np.interp(flat, positions, colors[:, 2]).astype(np.uint8)
    a = np.full(len(flat), 255, dtype=np.uint8)

    rgba = np.stack([r, g, b, a], axis=-1).reshape(H, W, 4)
    return rgba


def rgba_to_float(rgba: np.ndarray) -> np.ndarray:
    """uint8 [H, W, 4] -> float32 [H, W, 4] in [0, 1]"""
    return rgba.astype(np.float32) / 255.0


def float_to_rgba(arr: np.ndarray) -> np.ndarray:
    """float32 [H, W, 4] in [0, 1] -> uint8 [H, W, 4]"""
    return np.clip(arr * 255.0, 0, 255).astype(np.uint8)
