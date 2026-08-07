"""Mapping builder для chaotic_scattering_basins.

Перевод осей:
  basin_bias   ← tension
  perturbation ← motion_intensity
  complexity   ← texture_complexity
  stochastic_scale ← noise_level
  energy (общий масштаб) ← energy
"""
from __future__ import annotations


def build_scattering_state(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    tension: float = 0.5,
    motion_intensity: float = 0.5,
    texture_complexity: float = 0.5,
    noise_level: float = 0.1,
    energy: float = 0.5,
    density_level: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # basin_bias: tension → [-0.8, 0.8]
    basin_bias = -0.8 + tension * 1.6
    # perturbation: motion_intensity → [0.01, 0.25]
    perturbation = 0.01 + motion_intensity * 0.24
    # complexity: texture_complexity → [2, 8] (int number of basins)
    complexity = int(2 + texture_complexity * 6)
    # stochastic_scale: noise_level → [0.0, 0.05]
    stochastic_scale = noise_level * 0.05
    # energy scale
    energy_scale = 0.5 + energy * 0.5
    # n_samples: density_level → [100_000, 800_000]
    n_samples = int(100_000 + density_level * 700_000)

    sim_state = {
        "generator_name": "chaotic_scattering_basins",
        "generator_version": "v1",
        "basin_bias": round(basin_bias, 5),
        "perturbation": round(perturbation, 5),
        "complexity": complexity,
        "stochastic_scale": round(stochastic_scale, 6),
        "energy_scale": round(energy_scale, 4),
        "n_samples": n_samples,
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
        "basin_bias": "tension",
        "perturbation": "motion_intensity",
        "complexity": "texture_complexity",
        "stochastic_scale": "noise_level",
        "energy_scale": "energy",
        "transform.rotation_deg": "motion_intensity",
    }

    return {
        "sim_state": sim_state,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }
