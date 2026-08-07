"""Mapping builder для julia_orbit_trap.

Переводит перцептивные оси → SimState для Julia с orbit trap.
Ver: v0.3

theta[0] = c_real  ← symmetry_bias
theta[1] = c_imag  ← tension
theta[2] = exponent_p ← texture_complexity
theta[3] = trap_radius ← density_level (косвенно)
theta[4] = stochastic_scale ← noise_level
theta[5] = domain_zoom ← motion_intensity
"""
from __future__ import annotations

import math


def build_julia_state(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    # perceptual axes
    symmetry_bias: float = 0.5,
    tension: float = 0.5,
    texture_complexity: float = 0.5,
    density_level: float = 0.5,
    noise_level: float = 0.1,
    motion_intensity: float = 0.5,
    recursion_depth: float = 0.5,
    # transform
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    """Возвращает sim_state dict и mapping_trace."""
    # c_real: symmetry_bias → [-0.8, 0.3]
    c_real = -0.8 + symmetry_bias * 1.1
    # c_imag: tension → [0.0, 0.65]
    c_imag = tension * 0.65
    # exponent_p: texture_complexity → [1.8, 2.8]
    exponent_p = 1.8 + texture_complexity * 1.0
    # trap_radius: density_level → [0.3, 1.6]
    trap_radius = 0.3 + density_level * 1.3
    # max_iter: recursion_depth → [80, 320]
    max_iter = int(80 + recursion_depth * 240)
    # stochastic_scale: noise_level → [0.0, 0.04]
    stochastic_scale = noise_level * 0.04
    # domain zoom: motion_intensity → zoom = [1.0, 2.0] → domain half
    zoom = 1.0 + motion_intensity * 1.0
    half = 2.0 / zoom
    domain = [-half, half, -half, half]

    sim_state = {
        "generator_name": "julia_orbit_trap",
        "generator_version": "v2",
        "theta": [
            round(c_real, 5),
            round(c_imag, 5),
            round(exponent_p, 4),
            round(trap_radius, 4),
            round(stochastic_scale, 6),
            round(zoom, 4),
        ],
        "resolution": list(resolution_px),
        "domain": [round(v, 5) for v in domain],
        "max_iter": max_iter,
        "escape_radius": 4.0,
        "trap_kind": "point",
        "seed": seed,
        "stochastic_scale": round(stochastic_scale, 6),
        "extra": {},
    }

    transform = {
        "offset_norm": offset_norm or [0.0, 0.0],
        "scale_xy": scale_xy or [1.0, 1.0],
        "rotation_deg": round(rotation_deg, 2),
    }

    mapping_trace = {
        "theta[0]": "symmetry_bias",
        "theta[1]": "tension",
        "theta[2]": "texture_complexity",
        "theta[3]": "density_level",
        "theta[4]": "noise_level",
        "theta[5]": "motion_intensity",
        "max_iter": "recursion_depth",
        "transform.rotation_deg": "motion_intensity",
    }

    return {
        "sim_state": sim_state,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }
