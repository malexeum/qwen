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
    gen_module = None
    for mod_path in ("lib.fractal_core.generators", "lib.generators"):
        try:
            gen_module = importlib.import_module(mod_path)
            break
        except ImportError:
            continue
    if gen_module is None:
        raise ImportError(
            "Cannot import generators from lib.fractal_core.generators or lib.generators"
        )

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

    # Строим theta
    if generator_id == "julia_orbit_trap":
        theta = build_theta_julia(params)
    elif generator_id == "duffing_lyapunov":
        theta = build_theta_duffing(params)
    elif generator_id == "chaotic_scattering_basins":
        theta = build_theta_scattering(params)
    else:  # orbit_ifs_multi_trap
        theta = [0.0] * 8

    sim_kwargs = build_simstate_kwargs(generator_id, params)

    # Убираем поля, которые передаём явно — иначе TypeError: duplicate keyword
    sim_kwargs.pop("generator_name", None)
    sim_kwargs.pop("resolution", None)
    sim_kwargs.pop("theta", None)
    sim_kwargs.pop("seed", None)

    sim = SimState(
        generator_name=generator_id,
        resolution=(W, H),
        seed=seed,
        theta=np.asarray(theta, dtype=np.float64),
        **sim_kwargs,
    )

    func_map = {
        "julia_orbit_trap":          "julia_orbit_trap",
        "orbit_ifs_multi_trap":       "orbit_ifs_multi_trap",
        "duffing_lyapunov":           "duffing_lyapunov_map",
        "chaotic_scattering_basins":  "chaotic_scattering_basins",
    }
    func_name = func_map[generator_id]
    func = getattr(gen_module, func_name)
    result = func(sim)

    return _extract_orbit_map(result)


def _extract_orbit_map(result) -> np.ndarray:
    """Extract and normalise orbit_map from RunResult or np.ndarray."""
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
