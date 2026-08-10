"""FractalRunner — запускает generators.py через SimState."""
from __future__ import annotations

import importlib
import numpy as np

from .theta_builder import (
    build_theta_julia,
    build_theta_duffing,
    build_theta_scattering,
    build_simstate_kwargs,
)

_FRACTAL_GENERATORS = {
    "julia_orbit_trap",
    "orbit_ifs_multi_trap",
    "duffing_lyapunov",
    "chaotic_scattering_basins",
}


def run_fractal_layer(
    generator_id: str,
    params: dict,
    W: int,
    H: int,
    seed: int,
) -> np.ndarray:
    """
    Вызывает нужный генератор из lib.fractal_core.generators (или lib.generators).
    Возвращает orbit_map: float32 [H, W] in [0, 1].
    """
    # Пробуем оба возможных пути импорта
    gen_module = None
    for mod_path in ("lib.fractal_core.generators", "lib.generators"):
        try:
            gen_module = importlib.import_module(mod_path)
            break
        except ImportError:
            continue
    if gen_module is None:
        raise ImportError("Cannot import generators from lib.fractal_core.generators or lib.generators")

    # Получаем SimState
    SimState = None
    for mod_path in ("lib.fractal_core.core", "lib.core"):
        try:
            m = importlib.import_module(mod_path)
            SimState = m.SimState
            break
        except (ImportError, AttributeError):
            continue
    if SimState is None:
        raise ImportError("Cannot import SimState")

    # Строим theta и kwargs
    if generator_id == "julia_orbit_trap":
        theta = build_theta_julia(params)
    elif generator_id == "duffing_lyapunov":
        theta = build_theta_duffing(params)
    elif generator_id == "chaotic_scattering_basins":
        theta = build_theta_scattering(params)
    else:  # orbit_ifs_multi_trap
        theta = [0.0] * 8  # theta не используется напрямую

    sim_kwargs = build_simstate_kwargs(generator_id, params)
    sim = SimState(
        width=W,
        height=H,
        seed=seed,
        theta=theta,
        **sim_kwargs,
    )

    # Вызываем генератор
    func_map = {
        "julia_orbit_trap": "julia_orbit_trap",
        "orbit_ifs_multi_trap": "orbit_ifs_multi_trap",
        "duffing_lyapunov": "duffing_lyapunov_map",
        "chaotic_scattering_basins": "chaotic_scattering_basins",
    }
    func_name = func_map[generator_id]
    func = getattr(gen_module, func_name)
    result = func(sim)

    # Нормализуем orbit_map в [0, 1]
    orbit_map = _extract_orbit_map(result)
    return orbit_map


def _extract_orbit_map(result) -> np.ndarray:
    """Извлекает и нормализует orbit_map из RunResult или np.ndarray."""
    if hasattr(result, "orbit_map"):
        arr = np.asarray(result.orbit_map, dtype=np.float32)
    elif isinstance(result, np.ndarray):
        arr = result.astype(np.float32)
    else:
        raise TypeError(f"Unexpected generator result type: {type(result)}")
    mn, mx = arr.min(), arr.max()
    if mx > mn:
        arr = (arr - mn) / (mx - mn)
    else:
        arr = np.zeros_like(arr)
    return arr


def is_fractal(generator_id: str) -> bool:
    return generator_id in _FRACTAL_GENERATORS
