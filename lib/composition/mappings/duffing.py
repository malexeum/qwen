"""Mapping builder для duffing_lyapunov.

Перевод осей:
  forcing           ← energy
  damping           ← tension (инверсный: tension↑ → damping↓)
  forcing_frequency ← motion_intensity
  nonlinear_stiffness ← texture_complexity
  n_steps           ← recursion_depth
  stochastic_scale  ← noise_level
  gamma/omega window ← density_level
"""
from __future__ import annotations


def build_duffing_state(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    energy: float = 0.5,
    tension: float = 0.5,
    motion_intensity: float = 0.5,
    texture_complexity: float = 0.5,
    density_level: float = 0.5,
    noise_level: float = 0.1,
    recursion_depth: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # forcing: energy → [0.1, 0.8]
    forcing = 0.1 + energy * 0.7
    # damping: tension ↑ → damping ↓ (высокое напряжение = меньше затухания)
    damping = 0.5 - tension * 0.35
    # forcing_frequency (omega): motion_intensity → [0.8, 1.4]
    forcing_frequency = 0.8 + motion_intensity * 0.6
    # nonlinear_stiffness (beta): texture_complexity → [0.5, 2.0]
    nonlinear_stiffness = 0.5 + texture_complexity * 1.5
    # n_steps: recursion_depth → [5_000, 50_000]
    n_steps = int(5_000 + recursion_depth * 45_000)
    # stochastic_scale: noise_level → [0.0, 0.03]
    stochastic_scale = noise_level * 0.03
    # gamma/omega window: density_level → ширина окна
    gamma_window = 0.3 + density_level * 0.7
    omega_window = 0.3 + density_level * 0.7

    sim_state = {
        "generator_name": "duffing_lyapunov",
        "generator_version": "v1",
        "forcing": round(forcing, 5),
        "damping": round(damping, 5),
        "forcing_frequency": round(forcing_frequency, 5),
        "nonlinear_stiffness": round(nonlinear_stiffness, 5),
        "n_steps": n_steps,
        "stochastic_scale": round(stochastic_scale, 6),
        "gamma_window": round(gamma_window, 4),
        "omega_window": round(omega_window, 4),
        "resolution": list(resolution_px),
        "seed": seed,
        "extra": {},
    }

    transform = {
        "offset_norm": offset_norm or [0.0, 0.0],
        "scale_xy": scale_xy or [1.0, 1.0],
        "rotation_deg": round(rotation_deg, 2),
    }

    mapping_trace = {
        "forcing": "energy",
        "damping": "tension",
        "forcing_frequency": "motion_intensity",
        "nonlinear_stiffness": "texture_complexity",
        "n_steps": "recursion_depth",
        "stochastic_scale": "noise_level",
        "gamma_window": "density_level",
        "omega_window": "density_level",
        "transform.rotation_deg": "motion_intensity",
    }

    return {
        "sim_state": sim_state,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }
