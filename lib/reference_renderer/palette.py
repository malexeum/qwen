"""Palette resolution: palette_id → background RGBA + gradient stops."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class PaletteSpec:
    background_rgba: Tuple[int, int, int, int]  # uint8
    stops: List[Tuple[float, Tuple[int, int, int]]]  # [(pos, (r,g,b)), ...]
    accent_rgb: Tuple[int, int, int]
    saturation_budget: float
    contrast: float


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def resolve_palette(palette_id: str, palettes_cfg: dict) -> PaletteSpec:
    """Извлекает PaletteSpec из словаря palettes_cfg['palettes']."""
    lib = palettes_cfg.get("palettes", {})
    if palette_id not in lib:
        raise KeyError(f"Palette '{palette_id}' not found in catalog")
    raw = lib[palette_id]
    bg = tuple(raw["background_rgba"])
    stops = [(s[0], _hex_to_rgb(s[1])) for s in raw["dominant"]["stops"]]
    accent = _hex_to_rgb(raw["accent"])
    return PaletteSpec(
        background_rgba=(int(bg[0]), int(bg[1]), int(bg[2]), int(bg[3])),
        stops=stops,
        accent_rgb=accent,
        saturation_budget=raw.get("saturation_budget", 1.0),
        contrast=raw.get("contrast", 1.0),
    )


def sample_gradient(stops: List[Tuple[float, Tuple[int, int, int]]],
                    t: np.ndarray) -> np.ndarray:
    """Интерполяция по N stops для массива t ∈ [0,1]. Возвращает (H,W,3) float32."""
    t = np.clip(t, 0.0, 1.0)
    result = np.zeros((*t.shape, 3), dtype=np.float32)
    stops_sorted = sorted(stops, key=lambda x: x[0])
    for i in range(len(stops_sorted) - 1):
        p0, c0 = stops_sorted[i]
        p1, c1 = stops_sorted[i + 1]
        if p1 <= p0:
            continue
        alpha = np.clip((t - p0) / (p1 - p0), 0.0, 1.0)
        mask = (t >= p0) & (t <= p1)
        for ch in range(3):
            result[..., ch] = np.where(
                mask,
                (c0[ch] / 255.0) * (1 - alpha) + (c1[ch] / 255.0) * alpha,
                result[..., ch]
            )
    p_first, c_first = stops_sorted[0]
    p_last, c_last = stops_sorted[-1]
    for ch in range(3):
        result[..., ch] = np.where(t < p_first, c_first[ch] / 255.0, result[..., ch])
        result[..., ch] = np.where(t > p_last,  c_last[ch]  / 255.0, result[..., ch])
    return result
