# lib/fractal_lab/single_run.py

from typing import Dict, Any
from pathlib import Path

import numpy as np

from ..core import SimState, RunResult
from .. import generators
from .renderer import render_runresult_to_image


def _state_from_config(generator_name: str, config: Dict[str, Any]) -> SimState:
    theta = np.array(config["theta"], dtype=float)
    resolution = tuple(config.get("resolution", (400, 400)))
    domain = tuple(config.get("domain", (-2.0, 2.0, -2.0, 2.0)))
    max_iter = int(config.get("max_iter", 200))
    escape_radius = float(config.get("escape_radius", 4.0))
    trap_kind = config.get("trap_kind", "point")
    seed = int(config.get("seed", 0))
    stochastic_scale = float(config.get("stochastic_scale", 0.0))
    extra = dict(config.get("extra", {}))

    return SimState(
        generator_name=generator_name,
        theta=theta,
        resolution=resolution,
        domain=domain,
        max_iter=max_iter,
        escape_radius=escape_radius,
        trap_kind=trap_kind,
        seed=seed,
        stochastic_scale=stochastic_scale,
        extra=extra,
    )


def _choose_generator_impl(generator_name: str):
    # Реальные генераторы
    if generator_name == "julia_orbit_trap":
        return generators.julia_orbit_trap
    if generator_name == "orbit_ifs_multi_trap":
        return generators.orbit_ifs_multi_trap
    if generator_name == "duffing_lyapunov":
        return generators.duffing_lyapunov_map
    if generator_name == "chaotic_scattering_basins":
        return generators.chaotic_scattering_basins

    # Алиасы для baseline'ов
    if generator_name == "single_parameter_map_baseline":
        return generators.orbit_ifs_multi_trap
    if generator_name == "smooth_geometric_baseline":
        return generators.julia_orbit_trap
    if generator_name == "random_baseline":
        return generators.chaotic_scattering_basins

    return None


def run_single_fractal(
    generator_name: str,
    generator_config: Dict[str, Any],
    output_path: str,
) -> Dict[str, Any]:
    impl = _choose_generator_impl(generator_name)
    state = _state_from_config(generator_name, generator_config)

    if impl is None:
        H, W = state.resolution[1], state.resolution[0]
        orbit = np.zeros((H, W), dtype=float)
        visit = np.zeros((H, W), dtype=float)
        result = RunResult(orbit_map=orbit, visit_density=visit, aux={})
        mode = "fallback"
    else:
        result = impl(state)
        mode = "normal"

    img = render_runresult_to_image(generator_name, state, result, target_size=(1200, 1200))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, dpi=(300, 300))

    meta: Dict[str, Any] = {
        "generator_version": f"{generator_name}_v2",
        "config_used": generator_config,
        "output_path": output_path,
        "mode": mode,
    }
    return meta