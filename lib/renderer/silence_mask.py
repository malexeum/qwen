"""SilenceMaskApplicator — градиентная маска тишины."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def build_silence_mask(
    coverage: float,    # [0, 1] — доля затемнённой области
    direction: float,   # [0, 1] — 0=top, 0.5=center, 1=bottom
    edge_softness: float,  # [0, 1] — sigma размытия границы
    W: int,
    H: int,
) -> np.ndarray:
    """
    Возвращает float32 [H, W]: 0=чёрный (маска активна), 1=прозрачный.
    """
    # Строим вертикальный градиент
    y = np.linspace(0.0, 1.0, H, dtype=np.float32)
    mask_1d = np.ones(H, dtype=np.float32)

    center_y = float(direction)  # куда сдвигаем зону затемнения
    half = coverage / 2.0
    start = np.clip(center_y - half, 0.0, 1.0)
    end = np.clip(center_y + half, 0.0, 1.0)

    mask_1d = np.where((y >= start) & (y <= end), 0.0, 1.0).astype(np.float32)

    # Размываем границу
    if edge_softness > 0.0:
        sigma = edge_softness * H * 0.15
        mask_1d = gaussian_filter(mask_1d, sigma=sigma)
        mask_1d = np.clip(mask_1d, 0.0, 1.0)

    # Расширяем в 2D
    mask_2d = np.tile(mask_1d[:, np.newaxis], (1, W))
    return mask_2d.astype(np.float32)


def apply_silence_mask(
    canvas: np.ndarray,  # float32 [H, W, 3]
    mask: np.ndarray,    # float32 [H, W]
) -> np.ndarray:
    """Умножает каждый канал на маску."""
    return (canvas * mask[:, :, np.newaxis]).astype(np.float32)
