"""Layer executor — вычисляет numpy-буфер (H, W, 4) float32 для одного LayerSpec.

Каждый генератор реализован как чистая numpy-функция без PIL.
PIL используется только в execute_plan.py для финального сохранения.
Параметры слоя читаются из LayerSpec.sim_state (dict | None).
"""
from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.composition.schema import LayerSpec

from .palette import resolve_palette, sample_gradient


# ─── Вспомогательные утилиты ──────────────────────────────────────────────────

def _make_grid(W: int, H: int):
    xs = np.linspace(-1.0, 1.0, W, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, H, dtype=np.float32)
    return np.meshgrid(xs, ys)


def _apply_rotation(xg, yg, angle_deg: float):
    rad = np.deg2rad(angle_deg)
    c, s = float(np.cos(rad)), float(np.sin(rad))
    return c * xg - s * yg, s * xg + c * yg


def _colorize(t: np.ndarray, palette, opacity: float) -> np.ndarray:
    rgb = sample_gradient(palette.stops, t)
    alpha = np.full(t.shape, opacity, dtype=np.float32)
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


# ─── Генераторы ───────────────────────────────────────────────────────────────

def _gen_julia_orbit_trap(W, H, params, rng):
    c_real = float(params.get("c_real", -0.7))
    c_imag = float(params.get("c_imag", 0.27))
    p = float(params.get("exponent_p", 2.0))
    trap_r = float(params.get("trap_radius", 0.5))
    max_iter = max(16, int(params.get("max_iter", 64)))
    stoch = float(params.get("stochastic_scale", 0.0))
    zoom = float(params.get("domain_zoom", 1.0))

    xg, yg = _make_grid(W, H)
    xg, yg = _apply_rotation(xg, yg, float(params.get("_rotation_deg", 0.0)))
    xg = xg / max(zoom, 0.1)
    yg = yg / max(zoom, 0.1)

    if stoch > 0:
        xg = xg + rng.standard_normal((H, W)).astype(np.float32) * stoch * 0.03
        yg = yg + rng.standard_normal((H, W)).astype(np.float32) * stoch * 0.03

    zr, zi = xg.copy(), yg.copy()
    c_r = np.full_like(zr, c_real)
    c_i = np.full_like(zi, c_imag)
    escape = np.full((H, W), float(max_iter), dtype=np.float32)
    trapped = np.zeros((H, W), dtype=np.float32)
    alive = np.ones((H, W), dtype=bool)

    for i in range(max_iter):
        r2 = zr * zr + zi * zi
        if p == 2.0:
            new_r = zr * zr - zi * zi + c_r
            new_i = 2.0 * zr * zi + c_i
        else:
            mod = np.maximum(r2, 1e-12)
            ang = np.arctan2(zi, zr) * p
            modp = mod ** (p / 2.0)
            new_r = modp * np.cos(ang) + c_r
            new_i = modp * np.sin(ang) + c_i
        zr = np.where(alive, new_r, zr)
        zi = np.where(alive, new_i, zi)
        dist = np.sqrt(zr * zr + zi * zi)
        just_trapped = alive & (dist < trap_r)
        trapped = np.where(just_trapped, float(i) / max_iter, trapped)
        escaped = alive & (r2 > 4.0)
        smooth_val = float(i) + 1.0 - np.log2(np.log2(np.maximum(r2, 1.01)))
        escape = np.where(escaped, smooth_val / max_iter, escape)
        alive = alive & ~escaped

    t = np.where(trapped > 0, trapped, np.clip(1.0 - escape / max_iter, 0, 1))
    return np.clip(t, 0.0, 1.0)


def _gen_orbit_ifs(W, H, params, rng):
    n_points = max(1000, int(float(params.get("n_points", 0.5)) * 800_000 + 50_000))
    n_iter = max(32, int(float(params.get("n_iter", 0.5)) * 200 + 32))
    spread = float(params.get("attractor_spread", 0.5))
    stoch = float(params.get("stochastic_scale", 0.0))
    rot_deg = float(params.get("_rotation_deg", 0.0))

    seed = int(params.get("_seed", 42)) % (2**31)
    rng2 = np.random.default_rng(seed)
    n_maps = 3
    a = rng2.uniform(-0.6, 0.6, n_maps).astype(np.float32)
    b = rng2.uniform(-0.3, 0.3, n_maps).astype(np.float32)
    c = rng2.uniform(-0.3, 0.3, n_maps).astype(np.float32)
    d = rng2.uniform(-0.6, 0.6, n_maps).astype(np.float32)
    e = rng2.uniform(-spread, spread, n_maps).astype(np.float32)
    f = rng2.uniform(-spread, spread, n_maps).astype(np.float32)

    xs = np.zeros(n_points, dtype=np.float32)
    ys = np.zeros(n_points, dtype=np.float32)
    choice = rng2.integers(0, n_maps, size=(n_iter, n_points)).astype(np.int8)

    for it in range(n_iter):
        idx = choice[it]
        xa = a[idx] * xs + b[idx] * ys + e[idx]
        ya = c[idx] * xs + d[idx] * ys + f[idx]
        xs, ys = xa, ya

    if stoch > 0:
        xs += rng.standard_normal(n_points).astype(np.float32) * stoch * 0.02
        ys += rng.standard_normal(n_points).astype(np.float32) * stoch * 0.02

    rad = np.deg2rad(rot_deg)
    c_rot, s_rot = float(np.cos(rad)), float(np.sin(rad))
    xs2 = c_rot * xs - s_rot * ys
    ys2 = s_rot * xs + c_rot * ys

    xi = ((xs2 + 1.0) * 0.5 * W).astype(np.int32)
    yi = ((ys2 + 1.0) * 0.5 * H).astype(np.int32)
    mask = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    density = np.zeros((H, W), dtype=np.float32)
    np.add.at(density, (yi[mask], xi[mask]), 1.0)

    density = np.log1p(density)
    mx = density.max()
    if mx > 0:
        density /= mx
    return density


def _gen_duffing(W, H, params, rng):
    forcing = float(params.get("forcing", 0.5))
    damping = 0.1 + float(params.get("damping", 0.5)) * 0.4
    freq = 0.5 + float(params.get("forcing_frequency", 0.5)) * 1.5
    stiff = 0.5 + float(params.get("nonlinear_stiffness", 0.5)) * 2.5
    n_steps = max(64, int(float(params.get("n_steps", 0.5)) * 512 + 64))
    stoch = float(params.get("stochastic_scale", 0.0))
    rot_deg = float(params.get("_rotation_deg", 0.0))

    xg, yg = _make_grid(W, H)
    xg, yg = _apply_rotation(xg, yg, rot_deg)

    dt = 2 * np.pi / (freq * n_steps)
    x = xg.copy()
    v = yg.copy() * 0.5
    lyap = np.zeros((H, W), dtype=np.float32)

    for step in range(n_steps):
        t_val = step * dt
        accel = forcing * np.cos(freq * t_val) - damping * v + x - stiff * x ** 3
        if stoch > 0:
            accel += rng.standard_normal((H, W)).astype(np.float32) * stoch * 0.02
        v = v + accel * dt
        x = x + v * dt
        lyap += np.abs(accel)

    lyap /= n_steps
    lyap = np.log1p(lyap)
    mx = lyap.max()
    if mx > 0:
        lyap /= mx
    return lyap.astype(np.float32)


def _gen_chaotic_scattering(W, H, params, rng):
    tension = float(params.get("tension", 0.5))
    energy = float(params.get("energy", 0.5))
    perturb = float(params.get("perturbation", 0.0))
    n_steps = max(32, int(float(params.get("n_steps", 0.5)) * 256 + 32))
    rot_deg = float(params.get("_rotation_deg", 0.0))

    xg, yg = _make_grid(W, H)
    xg, yg = _apply_rotation(xg, yg, rot_deg)

    seed = int(params.get("_seed", 0)) % (2**31)
    rng2 = np.random.default_rng(seed)
    centers = rng2.uniform(-0.5, 0.5, (3, 2)).astype(np.float32)
    strength = (0.3 + tension * 0.4) * (0.5 + energy * 0.5)

    x = xg.copy()
    y = yg.copy()
    if perturb > 0:
        x += rng.standard_normal((H, W)).astype(np.float32) * perturb * 0.02
        y += rng.standard_normal((H, W)).astype(np.float32) * perturb * 0.02

    basin = np.zeros((H, W), dtype=np.float32)
    dt = 0.02
    for _ in range(n_steps):
        fx = np.zeros_like(x)
        fy = np.zeros_like(y)
        for cx, cy in centers:
            dx = x - cx
            dy = y - cy
            r2 = dx * dx + dy * dy + 0.04
            f = strength / r2
            fx -= f * dx
            fy -= f * dy
        x = x + fx * dt
        y = y + fy * dt
        basin += np.sqrt(fx * fx + fy * fy)

    basin = np.log1p(basin / n_steps)
    mx = basin.max()
    if mx > 0:
        basin /= mx
    return basin.astype(np.float32)


def _gen_orbital_field(W, H, params, rng):
    energy = float(params.get("energy", 0.5))
    density = float(params.get("density_level", 0.5))
    motion = float(params.get("motion_intensity", 0.5))
    freq = 2.0 + density * 6.0

    xg, yg = _make_grid(W, H)
    xg, yg = _apply_rotation(xg, yg, float(params.get("_rotation_deg", 0.0)))

    field = (np.sin(freq * xg + motion * 2) * np.cos(freq * yg) +
             np.cos(freq * xg) * np.sin(freq * yg + motion))
    field = field * (0.5 + energy * 0.5)
    mn, mx = field.min(), field.max()
    field = (field - mn) / (mx - mn + 1e-9)
    return field.astype(np.float32)


def _gen_colored_noise(W, H, params, rng):
    amplitude = float(params.get("amplitude", 0.5))
    freq_scale = float(params.get("frequency_scale", 0.5))
    grain = max(1, int(float(params.get("grain_size", 0.5)) * 8 + 1))

    noise = rng.standard_normal((H // grain + 1, W // grain + 1)).astype(np.float32)
    noise = np.repeat(np.repeat(noise, grain, axis=0), grain, axis=1)[:H, :W]

    F = np.fft.rfft2(noise)
    freqs_y = np.fft.fftfreq(H).astype(np.float32)
    freqs_x = np.fft.rfftfreq(W).astype(np.float32)
    fy, fx = np.meshgrid(freqs_y, freqs_x, indexing="ij")
    power = 1.0 / (1.0 + (fy ** 2 + fx ** 2) * (1.0 + freq_scale * 20))
    F = F * power
    result = np.fft.irfft2(F, s=(H, W))
    mn, mx = result.min(), result.max()
    result = (result - mn) / (mx - mn + 1e-9)
    return (result * amplitude).astype(np.float32)


def _gen_symmetry_snowflake(W, H, params, rng):
    n_branches = max(3, int(float(params.get("branch_count", 0.5)) * 10 + 3))
    depth = max(1, int(float(params.get("branch_depth", 0.5)) * 5 + 1))
    jitter = float(params.get("branch_jitter", 0.0))
    scale = 0.3 + float(params.get("radial_scale", 0.5)) * 0.6
    rot_deg = float(params.get("rotation_deg", 0.0)) + float(params.get("_rotation_deg", 0.0))

    xg, yg = _make_grid(W, H)
    xg, yg = _apply_rotation(xg, yg, rot_deg)

    r = np.sqrt(xg ** 2 + yg ** 2)
    theta = np.arctan2(yg, xg)
    sym_angle = 2 * np.pi / n_branches
    theta_sym = (theta % sym_angle) - sym_angle / 2
    if jitter > 0:
        theta_sym = theta_sym + rng.standard_normal(theta_sym.shape).astype(np.float32) * jitter * 0.1

    field = np.zeros((H, W), dtype=np.float32)
    for d in range(1, depth + 1):
        freq = d * n_branches
        field += np.cos(freq * theta_sym) * np.exp(-r / (scale + 0.01)) / d

    field = np.clip(field, 0, None)
    mx = field.max()
    if mx > 0:
        field /= mx
    return field.astype(np.float32)


def _gen_silence_mask(W, H, params, rng):
    coverage = float(params.get("coverage", 0.2))
    edge_soft = float(params.get("edge_softness", 0.5))

    xg, yg = _make_grid(W, H)
    r = np.sqrt(xg ** 2 + yg ** 2)
    radius = 0.3 + coverage * 0.6
    softness = 0.1 + edge_soft * 0.4
    mask = 1.0 - np.clip((r - radius) / (softness + 1e-6), 0.0, 1.0)
    return mask.astype(np.float32)


# ─── Dispatch ───────────────────────────────────────────────────────────────

_GENERATOR_DISPATCH = {
    "julia_orbit_trap":          _gen_julia_orbit_trap,
    "orbit_ifs_multi_trap":      _gen_orbit_ifs,
    "duffing_lyapunov":          _gen_duffing,
    "chaotic_scattering_basins": _gen_chaotic_scattering,
    "orbital_field":             _gen_orbital_field,
    "colored_noise_field":       _gen_colored_noise,
    "symmetry_snowflake":        _gen_symmetry_snowflake,
    "silence_mask":              _gen_silence_mask,
}


def execute_layer(layer, palettes_cfg: dict, W: int, H: int) -> np.ndarray:
    """Рендер одного LayerSpec → (H, W, 4) float32 RGBA.

    Разрешение берётся из layer.computation_resolution_px (tuple[int,int] | list);
    если не задано — используется полное W×H.
    Параметры генератора читаются из layer.sim_state (dict | None).
    """
    # ── Разрешение вычисления: из computation_resolution_px или W×H ──────────────
    comp_res = getattr(layer, "computation_resolution_px", None)
    if comp_res and len(comp_res) == 2 and comp_res[0] > 0 and comp_res[1] > 0:
        cW = max(32, int(comp_res[0]))
        cH = max(32, int(comp_res[1]))
    else:
        cW, cH = W, H

    rng = np.random.default_rng(layer.seed)

    # ── Параметры читаем из sim_state, не из parameters ───────────────────────
    sim_state = getattr(layer, "sim_state", None)
    params: dict = dict(sim_state) if sim_state else {}
    params["_seed"] = layer.seed

    # rotation_range_deg может быть в sim_state или как отдельное поле
    rot_range = params.get("rotation_range_deg") or getattr(layer, "rotation_range_deg", None)
    if rot_range and len(rot_range) == 2:
        lo, hi = float(rot_range[0]), float(rot_range[1])
        params["_rotation_deg"] = float(rng.uniform(lo, hi))
    else:
        params["_rotation_deg"] = 0.0

    # ── Dispatch ───────────────────────────────────────────────────────────────
    gen_id = layer.generator_id
    if gen_id not in _GENERATOR_DISPATCH:
        return np.zeros((H, W, 4), dtype=np.float32)

    field = _GENERATOR_DISPATCH[gen_id](cW, cH, params, rng)  # (cH, cW)

    # ── Апскейл до W×H nearest-neighbor ──────────────────────────────────────────
    if cW != W or cH != H:
        fy = np.round(np.linspace(0, cH - 1, H)).astype(int)
        fx = np.round(np.linspace(0, cW - 1, W)).astype(int)
        field = field[np.ix_(fy, fx)]

    # ── Колоризация через палитру ────────────────────────────────────────────
    palette_id = getattr(layer, "palette_id", None) or "neutral_noir"
    try:
        palette = resolve_palette(palette_id, palettes_cfg)
    except KeyError:
        palette = resolve_palette("neutral_noir", palettes_cfg)

    opacity = float(getattr(layer, "opacity", 1.0))
    return _colorize(field, palette, opacity)
