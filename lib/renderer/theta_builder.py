"""ThetaBuilder — конвертация layer.params -> theta list[float] для SimState."""
from __future__ import annotations


def build_theta_julia(params: dict) -> list[float]:
    """
    theta[0] = c_real
    theta[1] = c_imag
    theta[2] = exponent_p
    theta[3] = trap_radius
    theta[4] = trap_center_x (default 0.0)
    theta[5] = trap_center_y (default 0.0)
    """
    return [
        float(params.get("c_real", 0.0)),
        float(params.get("c_imag", 0.0)),
        float(params.get("exponent_p", 2.0)),
        float(params.get("trap_radius", 0.5)),
        float(params.get("trap_center_x", 0.0)),
        float(params.get("trap_center_y", 0.0)),
    ]


def build_theta_duffing(params: dict) -> list[float]:
    """
    theta[0] = damping
    theta[1] = nonlinear_stiffness
    theta[2] = forcing
    theta[3] = forcing_frequency
    """
    return [
        float(params.get("damping", 0.0)),
        float(params.get("nonlinear_stiffness", 0.0)),
        float(params.get("forcing", 0.0)),
        float(params.get("forcing_frequency", 0.0)),
    ]


def build_theta_scattering(params: dict) -> list[float]:
    """
    theta[0] = scatterer_radius  -> radius = 0.15 + 0.05*th0
    theta[1] = center_phase_offset
    theta[2] = center_radius     -> r = 0.7 + 0.2*th2
    theta[3] = initial_velocity_x
    theta[4] = initial_velocity_y
    """
    sr = float(params.get("scatterer_radius", 0.15))
    cr = float(params.get("center_radius", 0.7))
    return [
        (sr - 0.15) / 0.05,
        float(params.get("center_phase_offset", 0.0)),
        (cr - 0.7) / 0.2,
        float(params.get("initial_velocity_x", 0.02)),
        float(params.get("initial_velocity_y", 0.015)),
    ]


def build_simstate_kwargs(generator_id: str, params: dict) -> dict:
    """Возвращает kwargs для SimState: max_iter, stochastic_scale, extra, domain."""
    kwargs: dict = {}

    if generator_id == "julia_orbit_trap":
        kwargs["max_iter"] = int(params.get("max_iter",
                                             params.get("recursion_depth", 256)))
        kwargs["stochastic_scale"] = float(params.get("stochastic_scale", 0.0))
        zoom = float(params.get("domain_zoom", 1.5))
        kwargs["domain"] = [-zoom, zoom, -zoom, zoom]

    elif generator_id == "orbit_ifs_multi_trap":
        kwargs["extra"] = {
            "n_points": int(params.get("n_points", 50000)),
            "map_diversity": float(params.get("map_diversity", 0.5)),
            "attractor_spread": float(params.get("attractor_spread", 0.5)),
            "n_iter": int(params.get("max_iter", 200)),
        }
        kwargs["stochastic_scale"] = float(params.get("stochastic_scale", 0.0))

    elif generator_id == "duffing_lyapunov":
        kwargs["extra"] = {
            "n_steps": int(params.get("n_steps", 500)),
        }
        kwargs["stochastic_scale"] = float(params.get("stochastic_scale", 0.0))
        gw = float(params.get("gamma_window", 0.15))
        ow = float(params.get("omega_window", 0.15))
        kwargs["domain"] = [gw, ow]

    elif generator_id == "chaotic_scattering_basins":
        kwargs["max_iter"] = int(params.get("max_steps", 500))
        kwargs["stochastic_scale"] = float(params.get("stochastic_scale", 0.0))

    return kwargs
