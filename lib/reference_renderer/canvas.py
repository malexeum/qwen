"""Canvas buffer management — float32 RGBA, [0,1] range."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class Canvas:
    """Float32 RGBA buffer: shape (H, W, 4), values in [0, 1]."""
    width: int
    height: int
    data: np.ndarray  # (H, W, 4) float32

    @classmethod
    def black(cls, width: int = 1024, height: int = 1024) -> "Canvas":
        return cls(width=width, height=height,
                   data=np.zeros((height, width, 4), dtype=np.float32))

    def fill_background(self, rgba: tuple) -> None:
        """Заливка фона из uint8 RGBA (0-255)."""
        self.data[..., 0] = rgba[0] / 255.0
        self.data[..., 1] = rgba[1] / 255.0
        self.data[..., 2] = rgba[2] / 255.0
        self.data[..., 3] = rgba[3] / 255.0

    def to_uint8(self) -> np.ndarray:
        """Конвертация в uint8 (H, W, 4) с клиппингом."""
        return (np.clip(self.data, 0.0, 1.0) * 255.0).astype(np.uint8)
