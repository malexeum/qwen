# lib/fractal_lab/renderer.py

from typing import Tuple
import numpy as np
from PIL import Image, ImageChops, ImageFilter
import matplotlib  # современный API colormaps доступен отсюда


from ..core import SimState, RunResult


def _norm01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).any():
        return np.zeros_like(x)
    mn, mx = float(np.nanmin(x)), float(np.nanmax(x))
    if mx - mn < 1e-12:
        return np.zeros_like(x)
    y = (x - mn) / (mx - mn)
    return np.clip(y, 0.0, 1.0)


def _get_cmap(name: str):
    """
    Унифицированный доступ к colormap для новых версий matplotlib (3.9+).
    Вместо устаревшего cm.get_cmap используем глобальный реестр colormaps. [web:201][web:202][web:208]
    """
    return matplotlib.colormaps.get_cmap(name)


def _to_colormap_img(data: np.ndarray, cmap_name: str, size: Tuple[int, int]) -> Image.Image:
    data01 = _norm01(data)
    cmap = _get_cmap(cmap_name)
    rgba = cmap(data01)        # H×W×4, float [0,1]
    rgb = (rgba[..., :3] * 255).astype("uint8")
    img = Image.fromarray(rgb, mode="RGB")
    if img.size != size:
        img = img.resize(size, Image.BICUBIC)
    return img


def _to_gray_img(data: np.ndarray, size: Tuple[int, int]) -> Image.Image:
    data01 = _norm01(data) * 255.0
    d8 = data01.astype("uint8")
    img = Image.fromarray(d8, mode="L")
    if img.size != size:
        img = img.resize(size, Image.BICUBIC)
    return img


def render_runresult_to_image(
    generator_name: str,
    state: SimState,
    result: RunResult,
    target_size: Tuple[int, int] = (1200, 1200),
) -> Image.Image:
    """
    Главный рендер: из RunResult делаем цветной постер фиксированного размера.
    Pillow отвечает за изображение, matplotlib — только за colormap. [web:186][web:179]
    """
    W, H = target_size
    orbit = np.asarray(result.orbit_map, dtype=float)
    visit = np.asarray(result.visit_density, dtype=float)

    if generator_name == "duffing_lyapunov":
        # Базовая карта — "magma": плотная, тёмно-тёплая палитра. [web:186]
        base = _to_colormap_img(orbit, "magma", (W, H))
        # Карта хаоса по отклонению от среднего
        chaos = np.abs(orbit - np.mean(orbit))
        chaos_img = _to_colormap_img(chaos, "plasma", (W, H)).filter(
            ImageFilter.GaussianBlur(radius=1.0)
        )
        # Логарифм плотности посещений как маска альфы
        visit_log = np.log1p(np.abs(visit))
        visit_img = _to_gray_img(visit_log, (W, H))
        alpha = visit_img.point(lambda v: min(255, int(v * 1.5)))
        img = Image.composite(chaos_img, base, alpha)

    elif generator_name in {"julia_orbit_trap", "orbit_ifs_multi_trap"}:
        # Основа — "viridis" по orbit_map; хвосты — "inferno" по visit_density. [web:186]
        base = _to_colormap_img(orbit, "viridis", (W, H))
        visit_log = np.log1p(np.abs(visit))
        visit_img = _to_colormap_img(visit_log, "inferno", (W, H))
        # Лёгкий сдвиг второго слоя, чтобы создать глубину
        shifted = visit_img.transform(
            (W, H),
            Image.AFFINE,
            (1, 0, 8, 0, 1, 8),
            resample=Image.BICUBIC,
        )
        img = ImageChops.screen(base, shifted)

    elif generator_name == "chaotic_scattering_basins":
        # Разные бассейны — через категориальный "tab10". [web:203]
        base = _to_colormap_img(orbit, "tab10", (W, H))
        esc = _to_gray_img(visit, (W, H))
        img = ImageChops.multiply(base, esc.convert("RGB"))

    else:
        # Общий fallback — "cividis": более равномерный по восприятию. [web:186]
        img = _to_colormap_img(orbit, "cividis", (W, H))

    return img