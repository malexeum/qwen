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


def _get_palettes_lib(palettes_cfg) -> dict:
    """Возвращает словарь {palette_id: raw_dict}.

    palettes_cfg может быть:
      - dict с ключом 'palettes' (полный YAML)
      - уже плоский {palette_id: raw} (если уже развернули)
      - объект с атрибутом .palettes (dataclass из config_loader)
    """
    if palettes_cfg is None:
        return {}
    # dataclass/object с атрибутом palettes
    if hasattr(palettes_cfg, "palettes"):
        raw = palettes_cfg.palettes
    elif isinstance(palettes_cfg, dict):
        raw = palettes_cfg.get("palettes", palettes_cfg)
    else:
        raw = {}
    # если внутри ещё раз вложен dict с ключом 'palettes'
    if isinstance(raw, dict) and "palettes" in raw:
        raw = raw["palettes"]
    return raw if isinstance(raw, dict) else {}


def resolve_palette(palette_id: str, palettes_cfg) -> PaletteSpec:
    """Извлекает PaletteSpec из palettes_cfg.

    Поддерживает структуру palettes.yaml v0.3:
      dominant_stops: [{position, color}, ...]
      accent_color: "#RRGGBB"
    """
    lib = _get_palettes_lib(palettes_cfg)

    raw = lib.get(palette_id)
    if raw is None:
        # fallback → neutral_noir
        raw = lib.get("neutral_noir")
    if raw is None:
        raise KeyError(f"Palette '{palette_id}' not found and no neutral_noir fallback")

    bg = tuple(raw["background_rgba"])

    # dominant_stops — ключ в palettes.yaml v0.3
    # обратная совместимость: dominant.stops (старый формат)
    if "dominant_stops" in raw:
        raw_stops = raw["dominant_stops"]
        stops = [(float(s["position"]), _hex_to_rgb(s["color"])) for s in raw_stops]
    elif "dominant" in raw and "stops" in raw["dominant"]:
        raw_stops = raw["dominant"]["stops"]
        stops = [(float(s[0]), _hex_to_rgb(s[1])) if isinstance(s, (list, tuple))
                 else (float(s["position"]), _hex_to_rgb(s["color"])) for s in raw_stops]
    else:
        # градиент по умолчанию: чёрный → белый
        stops = [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))]

    # accent_color — ключ в palettes.yaml v0.3
    # обратная совместимость: accent (старый ключ)
    accent_hex = raw.get("accent_color") or raw.get("accent", "#FFFFFF")
    accent = _hex_to_rgb(accent_hex)

    return PaletteSpec(
        background_rgba=(int(bg[0]), int(bg[1]), int(bg[2]), int(bg[3])),
        stops=stops,
        accent_rgb=accent,
        saturation_budget=float(raw.get("saturation_budget", 1.0)),
        contrast=float(raw.get("contrast", 1.0)),
    )


def sample_gradient(
    stops: List[Tuple[float, Tuple[int, int, int]]],
    t: np.ndarray,
) -> np.ndarray:
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
                result[..., ch],
            )
    p_first, c_first = stops_sorted[0]
    p_last,  c_last  = stops_sorted[-1]
    for ch in range(3):
        result[..., ch] = np.where(t < p_first, c_first[ch] / 255.0, result[..., ch])
        result[..., ch] = np.where(t > p_last,  c_last[ch]  / 255.0, result[..., ch])
    return result
