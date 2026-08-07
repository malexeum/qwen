"""Mapping builder для orbit_ifs_multi_trap.

Перевод осей:
  n_points   ← density_level
  map_diversity ← texture_complexity
  attractor_spread ← motion_intensity
  stochastic_scale ← noise_level
  rotation_deg ← motion_intensity
"""
from __future__ import annotations


def build_ifs_state(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    density_level: float = 0.5,
    texture_complexity: float = 0.5,
    motion_intensity: float = 0.5,
    noise_level: float = 0.1,
    recursion_depth: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # n_points: density_level → [50_000, 400_000]
    n_points = int(50_000 + density_level * 350_000)
    # map_diversity: texture_complexity → [0.2, 1.0]
    map_diversity = 0.2 + texture_complexity * 0.8
    # attractor_spread: motion_intensity → [0.5, 2.5]
    attractor_spread = 0.5 + motion_intensity * 2.0
    # stochastic_scale: noise_level → [0.0, 0.05]
    stochastic_scale = noise_level * 0.05
    # n_steps (iterations per point): recursion_depth → [50, 200]
    n_iter = int(50 + recursion_depth * 150)

    sim_state = {
        "generator_name": "orbit_ifs_multi_trap",
        "generator_version": "v1",
        "n_points": n_points,
        "n_iter": n_iter,
        "map_diversity": round(map_diversity, 4),
        "attractor_spread": round(attractor_spread, 4),
        "stochastic_scale": round(stochastic_scale, 6),
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
        "n_points": "density_level",
        "map_diversity": "texture_complexity",
        "attractor_spread": "motion_intensity",
        "stochastic_scale": "noise_level",
        "n_iter": "recursion_depth",
        "transform.rotation_deg": "motion_intensity",
    }

    return {
        "sim_state": sim_state,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }
