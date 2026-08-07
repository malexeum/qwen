"""Mapping builders для процедурных слоёв.

Три builder-а:
  build_orbital_field_spec    → orbital_field
  build_colored_noise_spec    → colored_noise_field
  build_symmetry_snowflake_spec → symmetry_snowflake

Все возвращают layer_params (не SimState), так как это procedural_visual.
"""
from __future__ import annotations


def build_orbital_field_spec(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    tempo: float = 0.5,
    repetition: float = 0.5,
    density_level: float = 0.5,
    energy: float = 0.5,
    motion_intensity: float = 0.5,
    symmetry_bias: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # flow_speed: tempo → [0.3, 1.5]
    flow_speed = 0.3 + tempo * 1.2
    # orbit_radius: repetition → [0.2, 0.8]
    orbit_radius = 0.2 + repetition * 0.6
    # line_count: density_level → [6, 40]
    line_count = int(6 + density_level * 34)
    # amplitude: energy → [0.1, 0.9]
    amplitude = 0.1 + energy * 0.8
    # angular_break: motion_intensity → [0.0, 0.6]
    angular_break = motion_intensity * 0.6

    layer_params = {
        "generator_name": "orbital_field",
        "flow_speed": round(flow_speed, 4),
        "orbit_radius": round(orbit_radius, 4),
        "line_count": line_count,
        "amplitude": round(amplitude, 4),
        "angular_break": round(angular_break, 4),
        "rotation_deg": round(rotation_deg, 2),
        "resolution": list(resolution_px),
        "seed": seed,
    }

    transform = {
        "offset_norm": offset_norm or [0.0, 0.0],
        "scale_xy": scale_xy or [1.0, 1.0],
        "rotation_deg": round(rotation_deg, 2),
    }

    mapping_trace = {
        "flow_speed": "tempo",
        "orbit_radius": "repetition",
        "line_count": "density_level",
        "amplitude": "energy",
        "angular_break": "motion_intensity",
        "transform.rotation_deg": "motion_intensity",
    }

    return {
        "sim_state": layer_params,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }


def build_colored_noise_spec(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    noise_level: float = 0.1,
    spectral_flatness: float = 0.5,
    high_frequency_energy: float = 0.5,
    texture_complexity: float = 0.5,
    repetition: float = 0.5,
    tension: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # amplitude: noise_level → [0.01, 0.25]
    amplitude = 0.01 + noise_level * 0.24
    # frequency_scale: spectral_flatness → [0.5, 2.5]
    frequency_scale = 0.5 + spectral_flatness * 2.0
    # anisotropy: repetition → [0.0, 0.8]
    anisotropy = repetition * 0.8
    # grain_size: high_frequency_energy → [1.0, 8.0]
    grain_size = 1.0 + high_frequency_energy * 7.0
    # color_variation: tension → [0.0, 0.6]
    color_variation = tension * 0.6

    layer_params = {
        "generator_name": "colored_noise_field",
        "amplitude": round(amplitude, 5),
        "frequency_scale": round(frequency_scale, 4),
        "anisotropy": round(anisotropy, 4),
        "grain_size": round(grain_size, 4),
        "color_variation": round(color_variation, 4),
        "resolution": list(resolution_px),
        "seed": seed,
    }

    transform = {
        "offset_norm": offset_norm or [0.0, 0.0],
        "scale_xy": scale_xy or [1.0, 1.0],
        "rotation_deg": round(rotation_deg, 2),
    }

    mapping_trace = {
        "amplitude": "noise_level",
        "frequency_scale": "spectral_flatness",
        "anisotropy": "repetition",
        "grain_size": "high_frequency_energy",
        "color_variation": "tension",
    }

    return {
        "sim_state": layer_params,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }


def build_symmetry_snowflake_spec(
    *,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    symmetry_bias: float = 0.5,
    texture_complexity: float = 0.5,
    noise_level: float = 0.1,
    repetition: float = 0.5,
    harmonic_stability: float = 0.5,
    harmonic_change_rate: float = 0.5,
    rotation_deg: float = 0.0,
    offset_norm: list[float] | None = None,
    scale_xy: list[float] | None = None,
) -> dict:
    # branch_count: symmetry_bias → [4, 12]
    branch_count = int(4 + symmetry_bias * 8)
    # branch_depth: texture_complexity → [2, 7]
    branch_depth = int(2 + texture_complexity * 5)
    # branch_jitter: noise_level → [0.0, 0.4]
    branch_jitter = noise_level * 0.4
    # radial_scale: repetition → [0.3, 0.9]
    radial_scale = 0.3 + repetition * 0.6
    # rotation from harmonic_change_rate → [0°, 360°]
    rotation_from_harmonic = harmonic_change_rate * 360.0

    layer_params = {
        "generator_name": "symmetry_snowflake",
        "branch_count": branch_count,
        "branch_depth": branch_depth,
        "branch_jitter": round(branch_jitter, 4),
        "radial_scale": round(radial_scale, 4),
        "rotation_deg": round(rotation_from_harmonic, 2),
        "resolution": list(resolution_px),
        "seed": seed,
    }

    transform = {
        "offset_norm": offset_norm or [0.0, 0.0],
        "scale_xy": scale_xy or [1.0, 1.0],
        "rotation_deg": round(rotation_from_harmonic, 2),
    }

    mapping_trace = {
        "branch_count": "symmetry_bias",
        "branch_depth": "texture_complexity",
        "branch_jitter": "noise_level",
        "radial_scale": "repetition",
        "rotation_deg": "harmonic_change_rate",
    }

    return {
        "sim_state": layer_params,
        "transform": transform,
        "mapping_trace": mapping_trace,
    }
