"""ProceduralRunner — orbital_field, colored_noise_field, symmetry_snowflake."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def run_orbital_field(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params: flow_speed, orbit_radius, line_count, amplitude, angular_break, rotation_deg
    Returns float32 [H, W] in [0, 1]
    """
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), dtype=np.float32)
    n = int(np.clip(params.get("line_count", 0.5) * 120 + 40, 40, 200))
    flow_speed = float(params.get("flow_speed", 0.5))
    amplitude = float(params.get("amplitude", 0.5))
    angular_break = float(params.get("angular_break", 0.0))
    for _ in range(n):
        x0 = rng.uniform(-1.0, 1.0)
        y0 = rng.uniform(-1.0, 1.0)
        angle = rng.uniform(0, 2 * np.pi)
        steps = int(flow_speed * 400 + 100)
        for _ in range(steps):
            r = np.sqrt(x0 ** 2 + y0 ** 2) + 1e-9
            dr = -amplitude * 0.02
            dtheta = (angular_break * 0.5 + 0.5) / r
            x0 += dr * np.cos(angle) - dtheta * np.sin(angle)
            y0 += dr * np.sin(angle) + dtheta * np.cos(angle)
            ix = int((x0 + 1.0) / 2.0 * (W - 1))
            iy = int((y0 + 1.0) / 2.0 * (H - 1))
            if 0 <= ix < W and 0 <= iy < H:
                canvas[iy, ix] += 1.0
    canvas = np.log1p(canvas)
    mx = canvas.max()
    if mx > 0:
        canvas /= mx
    return canvas.astype(np.float32)


def run_colored_noise_field(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params: amplitude, frequency_scale, anisotropy, grain_size, color_variation
    Returns float32 [H, W] in [0, 1]
    """
    rng = np.random.default_rng(seed)
    frequency_scale = float(params.get("frequency_scale", 0.5))
    grain_size = float(params.get("grain_size", 2.0))
    anisotropy = float(params.get("anisotropy", 0.0))
    amplitude = float(params.get("amplitude", 0.5))
    freqs = int(np.clip(frequency_scale * 8 + 2, 2, 12))
    canvas = np.zeros((H, W), dtype=np.float32)
    for f in range(1, freqs + 1):
        layer = rng.standard_normal((H, W)).astype(np.float32)
        sigma = max(1.0, grain_size * 8 * (1.0 / f))
        layer = gaussian_filter(layer, sigma=sigma)
        aniso_scale = 1.0 + anisotropy * (f - 1)
        canvas += layer / aniso_scale
    canvas -= canvas.min()
    mx = canvas.max()
    if mx > 0:
        canvas /= mx
    canvas *= amplitude
    return np.clip(canvas, 0.0, 1.0).astype(np.float32)


def run_symmetry_snowflake(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params: branch_count, branch_depth, branch_jitter, radial_scale, rotation_deg
    Returns float32 [H, W] in [0, 1]
    """
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), dtype=np.float32)
    n_branches = max(3, int(params.get("branch_count", 0.5) * 10 + 3))
    depth = max(1, int(params.get("branch_depth", 0.5) * 5 + 1))
    base_angle = np.radians(float(params.get("rotation_deg", 0.0)))
    scale = float(params.get("radial_scale", 0.5)) * 0.8 + 0.1
    jitter = float(params.get("branch_jitter", 0.05)) * 0.15

    def draw_branch(cx: float, cy: float, angle: float, length: float, d: int) -> None:
        if d == 0 or length < 2:
            return
        ex = cx + length * np.cos(angle)
        ey = cy + length * np.sin(angle)
        steps = int(length * 3)
        for t in range(steps):
            fx = cx + (ex - cx) * t / max(steps, 1)
            fy = cy + (ey - cy) * t / max(steps, 1)
            ix = int((fx + 1.0) / 2.0 * (W - 1))
            iy = int((fy + 1.0) / 2.0 * (H - 1))
            if 0 <= ix < W and 0 <= iy < H:
                canvas[iy, ix] += 1.0 / (depth - d + 1)
        j = rng.uniform(-jitter, jitter)
        draw_branch(ex, ey, angle + np.pi / 6 + j, length * 0.6, d - 1)
        draw_branch(ex, ey, angle - np.pi / 6 + j, length * 0.6, d - 1)

    for k in range(n_branches):
        angle = base_angle + 2 * np.pi * k / n_branches
        draw_branch(0.0, 0.0, angle, scale * 0.9, depth)

    mx = canvas.max()
    if mx > 0:
        canvas /= mx
    return canvas.astype(np.float32)


def run_procedural(
    generator_id: str,
    params: dict,
    W: int,
    H: int,
    seed: int,
) -> np.ndarray:
    """Диспетчер процедурных генераторов."""
    dispatch = {
        "orbital_field": run_orbital_field,
        "colored_noise_field": run_colored_noise_field,
        "symmetry_snowflake": run_symmetry_snowflake,
    }
    if generator_id not in dispatch:
        raise ValueError(f"Unknown procedural generator: {generator_id}")
    return dispatch[generator_id](params, W, H, seed)
