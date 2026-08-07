# lib/fractal_backend/adapter.py

from typing import Dict, Any, Tuple
from dataclasses import dataclass, field

import numpy as np

# Прямой импорт лаборатории; если её нет — пусть реально упадёт ImportError,
# чтобы не маскировать проблему RuntimeError'ом.
from lib.fractal_lab.single_run import run_single_fractal


@dataclass
class RenderParams:
    style_profile_slug: str
    interpretation_profile_slug: str
    preset_id: str

    symmetry_bias: float
    recursion_depth: float
    density_level: float
    noise_level: float
    motion_intensity: float

    palette_id: str
    stochastic_term: float
    layout_macro_shape: str
    texture_complexity: float

    variation_seed: int


@dataclass
class SimState:
    generator_name: str
    theta: np.ndarray
    resolution: Tuple[int, int] = (400, 400)
    domain: Tuple[float, float, float, float] = (-2.0, 2.0, -2.0, 2.0)
    max_iter: int = 200
    escape_radius: float = 4.0
    trap_kind: str = "point"
    seed: int = 0
    stochastic_scale: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


def _build_sim_state_from_render_params(
    render_params: RenderParams,
    perceptual: Dict[str, float],
    generator_name: str,
) -> SimState:
    """
    Строит SimState из RenderParams и перцептивных осей для конкретного генератора.

    Использует связи из cheat sheet:
    - recursion_depth -> max_iter / n_steps / n_points
    - density_level   -> n_orbits, n_points, layers
    - symmetry_bias   -> theta-параметры симметрии
    - noise_level     -> stochastic_scale
    - motion_intensity-> физические параметры хаотичности
    - texture_complexity -> дополнительные веса/слои
    - layout_macro_shape -> domain / trap-центр
    """

    sym = float(render_params.symmetry_bias)
    rec = float(render_params.recursion_depth)
    dens = float(render_params.density_level)
    noise = float(render_params.noise_level)
    mot = float(render_params.motion_intensity)
    tex = float(render_params.texture_complexity)
    seed = int(render_params.variation_seed)

    resolution = (400, 400)
    domain = (-2.0, 2.0, -2.0, 2.0)
    max_iter = 200
    escape_radius = 4.0
    trap_kind = "point"
    stochastic_scale = noise * 0.02  # 0..~0.02

    if render_params.layout_macro_shape == "linear":
        domain = (-3.0, 3.0, -1.5, 1.5)

    extra: Dict[str, Any] = {}

    if generator_name == "duffing_lyapunov":
        # theta: [delta, alpha, beta, gamma0, omega0]
        base_steps = 240
        steps_range = 360
        n_steps = base_steps + int(rec * steps_range)
        extra["n_steps"] = n_steps

        delta = 0.1 + 0.25 * mot           # диссипация
        alpha = -1.0 + 0.5 * (sym - 0.5)   # линейная жёсткость
        beta = 1.0 + 0.5 * tex             # нелинейная жёсткость
        gamma0 = 0.2 + 0.6 * mot           # амплитуда форсинга
        omega0 = 0.8 + 0.6 * dens          # частота форсинга

        theta = np.array([delta, alpha, beta, gamma0, omega0], dtype=float)

        gamma_span = 0.1 + 0.2 * dens
        omega_span = 0.1 + 0.2 * dens
        extra["gamma_span"] = gamma_span
        extra["omega_span"] = omega_span

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

    if generator_name == "julia_orbit_trap":
        # theta: [c_real, c_imag, p_raw, trap_r_raw, trap_c_real, trap_c_imag]
        c_real = (sym - 0.5) * 1.5
        c_imag = (perceptual.get("tension", 0.5) - 0.5) * 1.5

        p_raw = 2.0 * tex - 1.0          # -1..+1 -> p ~ 2..3
        trap_r_raw = 2.0 * dens - 1.0    # -1..+1

        if render_params.layout_macro_shape == "ABA_like":
            trap_c_real = 0.0
            trap_c_imag = 0.0
        elif render_params.layout_macro_shape == "linear":
            trap_c_real = 0.8
            trap_c_imag = 0.0
        else:
            trap_c_real = 0.5 * (sym - 0.5)
            trap_c_imag = 0.5 * (perceptual.get("energy", 0.5) - 0.5)

        theta = np.array(
            [c_real, c_imag, p_raw, trap_r_raw, trap_c_real, trap_c_imag],
            dtype=float,
        )

        base_iter = 80
        iter_range = 240
        max_iter = base_iter + int(rec * iter_range)

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

    if generator_name == "orbit_ifs_multi_trap":
        # theta: базовый вектор для генерации карт (a, b, cx, cy)
        t0 = (sym - 0.5) * 2.0
        t1 = (mot - 0.5) * 2.0
        t2 = (dens - 0.5) * 2.0
        t3 = (tex - 0.5) * 2.0
        theta = np.array([t0, t1, t2, t3], dtype=float)

        base_points = 20000
        points_range = 60000
        n_points = base_points + int(dens * points_range) + int(rec * 20000)
        extra["n_points"] = n_points

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

    theta = np.array(
        [
            (sym - 0.5) * 2.0,
            (dens - 0.5) * 2.0,
            (noise - 0.5) * 2.0,
            (mot - 0.5) * 2.0,
        ],
        dtype=float,
    )

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


def render_fractal_image(
    generator_name: str,
    sim_state: SimState,
    output_path: str,
) -> Dict[str, Any]:
    """
    Рендерит одну картинку заданным генератором и SimState.

    Для лаборатории собирает generator_config (dict) из SimState,
    а в метаданные возвращает оба слоя: config и полный sim_state.
    """
    generator_config = {
        "theta": sim_state.theta.tolist(),
        "seed": sim_state.seed,
        "resolution": sim_state.resolution,
        "domain": sim_state.domain,
        "max_iter": sim_state.max_iter,
        "escape_radius": sim_state.escape_radius,
        "trap_kind": sim_state.trap_kind,
        "stochastic_scale": sim_state.stochastic_scale,
        "extra": sim_state.extra,
    }

    meta = run_single_fractal(generator_name, generator_config, output_path)

    result = {
        "generator_name": generator_name,
        "sim_state": {
            "generator_name": sim_state.generator_name,
            "theta": sim_state.theta.tolist(),
            "resolution": sim_state.resolution,
            "domain": sim_state.domain,
            "max_iter": sim_state.max_iter,
            "escape_radius": sim_state.escape_radius,
            "trap_kind": sim_state.trap_kind,
            "seed": sim_state.seed,
            "stochastic_scale": sim_state.stochastic_scale,
            "extra": sim_state.extra,
        },
        "output_path": output_path,
        "generator_config": generator_config,
    }
    if isinstance(meta, dict):
        result.update(meta)
    return result


def select_generator_for_render(render_params: RenderParams, perceptual: Dict[str, float]) -> str:
    """
    Простейший rule-based выбор генератора по RenderParams и перцептиву.
    """
    style = (render_params.style_profile_slug or "default").lower()
    energy = float(perceptual.get("energy", 0.5))
    tension = float(perceptual.get("tension", 0.5))
    section_complexity = float(perceptual.get("section_complexity", 0.5))

    if style in {"ambient", "space"}:
        generator = "smooth_geometric_baseline"
    elif style in {"rock", "electronic"}:
        generator = "duffing_lyapunov"
    elif style in {"blues_jazz", "blues", "jazz"}:
#       generator = "single_parameter_map_baseline"
        generator = "julia_orbit_trap"
    elif style in {"soundtrack"}:
        generator = "duffing_lyapunov"
    else:
        generator = "random_baseline"

    if energy > 0.7 and section_complexity > 0.6:
        generator = "duffing_lyapunov"
    if energy < 0.4 and tension < 0.4:
        generator = "smooth_geometric_baseline"

    return generator


def map_render_params_to_generator_config(
    render_params: RenderParams,
    generator_name: str,
) -> Dict[str, Any]:
    """
    Legacy mapping RenderParams -> generator_config для генераторов без SimState-специфики.
    """
    sym = float(render_params.symmetry_bias)
    rec = float(render_params.recursion_depth)
    dens = float(render_params.density_level)
    noise = float(render_params.noise_level)
    mot = float(render_params.motion_intensity)
    tex = float(render_params.texture_complexity)
    seed = int(render_params.variation_seed)

    if generator_name == "smooth_geometric_baseline":
        base_layers = 3
        layer_range = 5
        n_layers = base_layers + int(dens * layer_range)
        return {
            "seed": seed,
            "layers": n_layers,
            "symmetry": sym,
            "noise": noise * 0.5,
            "motion": mot * 0.5,
            "texture": tex,
        }

    if generator_name == "random_baseline":
        return {
            "seed": seed,
            "noise_scale": 0.5 + noise * 0.5,
            "motion_scale": 0.5 + mot * 0.5,
            "density_scale": dens,
            "texture_scale": tex,
        }

    return {
        "seed": seed,
        "symmetry": sym,
        "recursion": rec,
        "density": dens,
        "noise": noise,
        "motion": mot,
        "texture": tex,
    }


def render_poster(
    render_params: RenderParams,
    perceptual: Dict[str, float],
    output_path: str,
    width: int = 1200,
    height: int = 1200,
    mode: str = "final",
) -> Dict[str, Any]:
    """
    Серверный render_poster как thin wrapper над fractal backend adapter.

    Выбирает генератор, строит SimState или generator_config, рендерит PNG и
    возвращает метаданные постера.
    """
    generator_name = select_generator_for_render(render_params, perceptual)

    if generator_name in {"duffing_lyapunov", "julia_orbit_trap", "orbit_ifs_multi_trap"}:
        sim_state = _build_sim_state_from_render_params(render_params, perceptual, generator_name)
        meta = render_fractal_image(generator_name, sim_state, output_path)
    else:
        config = map_render_params_to_generator_config(render_params, generator_name)
        theta = np.array(
            [
                float(render_params.symmetry_bias),
                float(render_params.density_level),
                float(render_params.noise_level),
                float(render_params.motion_intensity),
            ],
            dtype=float,
        )
        sim_state = SimState(
            generator_name=generator_name,
            theta=theta,
            seed=int(render_params.variation_seed),
            extra={"generator_config": config},
        )
        meta = render_fractal_image(generator_name, sim_state, output_path)

    poster_meta = {
        "width": width,
        "height": height,
        "palette_id": render_params.palette_id,
        "style_profile_slug": render_params.style_profile_slug,
        "interpretation_profile_slug": render_params.interpretation_profile_slug,
        "visual_style_slug": render_params.style_profile_slug,
        "generator_name": generator_name,
        "generator_meta": meta,
        "mode": mode,
    }
    return poster_meta