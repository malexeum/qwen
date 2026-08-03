"""
Семейство нелинейных генераторов v2.
Добавлено: контролируемый стохастический член (state.stochastic_scale) в детерминированные
генераторы (julia, duffing, chaotic_scattering). duffing_lyapunov и chaotic_scattering
векторизованы для работы на сетке 128x128.
"""
import numpy as np
from .core import SimState, RunResult

def julia_orbit_trap(state: SimState) -> RunResult:
    th = state.theta
    rng = np.random.default_rng(state.seed)
    c = complex(th[0] * 1.2, th[1] * 1.2)
    p = 2.0 + (th[2] + 1) * 1.0
    trap_r = 0.05 + 0.25 * (th[3] + 1) / 2
    trap_c = complex(th[4] * 0.5, th[5] * 0.5) if len(th) > 5 else 0j

    W, H = state.resolution
    xmin, xmax, ymin, ymax = state.domain
    xs = np.linspace(xmin, xmax, W)
    ys = np.linspace(ymin, ymax, H)
    X, Y = np.meshgrid(xs, ys)
    Z = X + 1j * Y

    trap_val = np.full(Z.shape, np.inf)
    visit = np.zeros(Z.shape)
    escaped = np.zeros(Z.shape, dtype=bool)
    esc_iter = np.zeros(Z.shape)

    Zc = Z.copy()
    s = state.stochastic_scale
    for n in range(state.max_iter):
        active = ~escaped
        if not active.any():
            break
        r = np.abs(Zc[active])
        theta_ang = np.angle(Zc[active])
        r_safe = np.where(r < 1e-12, 1e-12, r)
        Zp = (r_safe ** p) * np.exp(1j * p * theta_ang)
        if s > 0:
            noise = (rng.normal(0, s, size=Zp.shape) + 1j * rng.normal(0, s, size=Zp.shape))
            Zc[active] = Zp + c + noise
        else:
            Zc[active] = Zp + c

        dist_to_trap = np.abs(Zc[active] - trap_c)
        cur_trap = trap_val[active]
        trap_val[active] = np.minimum(cur_trap, dist_to_trap)
        visit[active] += np.exp(-dist_to_trap / (trap_r + 1e-6))

        mag = np.abs(Zc[active])
        newly_escaped_local = mag > state.escape_radius
        idx = np.where(active)
        esc_iter[idx[0][newly_escaped_local], idx[1][newly_escaped_local]] = n
        escaped_flat = escaped[active]
        escaped_flat[newly_escaped_local] = True
        escaped[active] = escaped_flat

    trap_val[np.isinf(trap_val)] = trap_r * 4
    orbit_map = 1.0 / (1.0 + trap_val / trap_r)
    return RunResult(orbit_map=orbit_map, visit_density=visit,
                      aux={"esc_iter": esc_iter, "c": c, "p": p, "trap_r": trap_r})


def orbit_ifs_multi_trap(state: SimState) -> RunResult:
    th = state.theta
    n_maps = 4
    rng = np.random.default_rng(state.seed)
    maps = []
    for i in range(n_maps):
        a = 0.5 + 0.3 * th[i % len(th)]
        b = 0.3 * th[(i + 1) % len(th)]
        cx = th[(i + 2) % len(th)] * 1.0
        cy = th[(i + 3) % len(th)] * 1.0
        maps.append((a, b, cx, cy))

    W, H = state.resolution
    xmin, xmax, ymin, ymax = state.domain
    visit = np.zeros((H, W))
    trap_response = np.zeros((H, W))
    traps = [complex(np.cos(2*np.pi*k/3)*0.6, np.sin(2*np.pi*k/3)*0.6) for k in range(3)]

    x, y = 0.0, 0.0
    n_points = state.extra.get("n_points", 20_000)
    burn = 20
    pts_x = np.empty(n_points)
    pts_y = np.empty(n_points)
    s = state.stochastic_scale
    for n in range(n_points + burn):
        i = rng.integers(0, n_maps)
        a, b, cx, cy = maps[i]
        x_new = a * x - b * y + cx * 0.3
        y_new = b * x + a * y + cy * 0.3
        if s > 0:
            x_new += rng.normal(0, s)
            y_new += rng.normal(0, s)
        x, y = np.tanh(x_new), np.tanh(y_new)
        if n >= burn:
            pts_x[n - burn] = x
            pts_y[n - burn] = y

    ix = ((pts_x - xmin) / (xmax - xmin) * (W - 1)).astype(int)
    iy = ((pts_y - ymin) / (ymax - ymin) * (H - 1)).astype(int)
    valid = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    np.add.at(visit, (iy[valid], ix[valid]), 1)

    z_pts = pts_x[valid] + 1j * pts_y[valid]
    trap_dist = np.min([np.abs(z_pts - t) for t in traps], axis=0)
    trap_score = np.exp(-trap_dist / 0.15)
    np.add.at(trap_response, (iy[valid], ix[valid]), trap_score)

    orbit_map = np.log1p(trap_response) / (np.log1p(trap_response).max() + 1e-9)
    return RunResult(orbit_map=orbit_map, visit_density=visit, aux={"maps": maps, "traps": traps})


def duffing_lyapunov_map(state: SimState) -> RunResult:
    th = state.theta
    delta = 0.1 + 0.25 * (th[0] + 1) / 2
    alpha = -1.0 + 0.5 * th[1]
    beta = 1.0 + 0.5 * th[2]
    gamma0 = 0.2 + 0.6 * (th[3] + 1) / 2
    omega0 = 0.8 + 0.6 * (th[4] + 1) / 2 if len(th) > 4 else 1.0

    W, H = state.resolution
    gamma_range = np.linspace(max(0.01, gamma0 - 0.15), gamma0 + 0.15, W)
    omega_range = np.linspace(max(0.1, omega0 - 0.15), omega0 + 0.15, H)
    Gamma, Omega = np.meshgrid(gamma_range, omega_range)

    dt = 0.01
    n_steps = state.extra.get("n_steps", 400)
    eps = 1e-8
    rng = np.random.default_rng(state.seed)
    s = state.stochastic_scale

    x0, v0 = 0.1, 0.0
    X = np.full_like(Gamma, x0)
    V = np.full_like(Gamma, v0)
    Xp = X + eps
    Vp = V.copy()
    log_sum = np.zeros_like(Gamma)
    t = 0.0

    def rhs(x, v, t, gamma):
        forcing = gamma * np.cos(Omega * t)
        return v, -delta * v - alpha * x - beta * x**3 + forcing

    def rk4_step(x, v, t, gamma, dv_noise):
        k1x, k1v = rhs(x, v, t, gamma)
        k2x, k2v = rhs(x + 0.5*dt*k1x, v + 0.5*dt*k1v, t + 0.5*dt, gamma)
        k3x, k3v = rhs(x + 0.5*dt*k2x, v + 0.5*dt*k2v, t + 0.5*dt, gamma)
        k4x, k4v = rhs(x + dt*k3x, v + dt*k3v, t + dt, gamma)
        x_new = x + (dt/6.0) * (k1x + 2*k2x + 2*k3x + k4x)
        v_new = v + (dt/6.0) * (k1v + 2*k2v + 2*k3v + k4v) + dv_noise
        return x_new, v_new

    for step in range(n_steps):
        noise = rng.normal(0, s, size=X.shape) if s > 0 else 0.0
        X, V = rk4_step(X, V, t, Gamma, noise)
        Xp, Vp = rk4_step(Xp, Vp, t, Gamma, noise)

        d = np.sqrt((Xp - X)**2 + (Vp - V)**2)
        d_safe = np.where(d > 0, d, 1e-15)
        log_sum += np.log(d_safe / eps)
        scale = eps / d_safe
        Xp = X + (Xp - X) * scale
        Vp = V + (Vp - V) * scale
        t += dt

        # защита от численного взрыва детерминированной нелинейности (не физика, а устойчивость схемы)
        X = np.clip(X, -50, 50)
        V = np.clip(V, -50, 50)

    lyap_map = log_sum / (n_steps * dt)

    def rhs_scalar(x, v, t, gamma):
        forcing = gamma * np.cos(omega0 * t)
        return v, -delta * v - alpha * x - beta * x**3 + forcing

    sv_x, sv_v = x0, v0
    traj = np.zeros((n_steps, 2))
    t2 = 0.0
    for step in range(n_steps):
        k1x, k1v = rhs_scalar(sv_x, sv_v, t2, gamma0)
        k2x, k2v = rhs_scalar(sv_x + 0.5*dt*k1x, sv_v + 0.5*dt*k1v, t2 + 0.5*dt, gamma0)
        k3x, k3v = rhs_scalar(sv_x + 0.5*dt*k2x, sv_v + 0.5*dt*k2v, t2 + 0.5*dt, gamma0)
        k4x, k4v = rhs_scalar(sv_x + dt*k3x, sv_v + dt*k3v, t2 + dt, gamma0)
        sv_x = sv_x + (dt/6.0) * (k1x + 2*k2x + 2*k3x + k4x)
        sv_v = sv_v + (dt/6.0) * (k1v + 2*k2v + 2*k3v + k4v)
        if s > 0:
            sv_v += rng.normal(0, s)
        traj[step] = [sv_x, sv_v]
        t2 += dt

    visit_density = np.abs(lyap_map - lyap_map.mean())
    return RunResult(orbit_map=lyap_map, visit_density=visit_density,
                      aux={"time_portrait": traj, "delta": delta, "alpha": alpha,
                           "beta": beta, "gamma0": gamma0, "omega0": omega0,
                           "gamma_range": gamma_range, "omega_range": omega_range})


def chaotic_scattering_basins(state: SimState) -> RunResult:
    th = state.theta
    n_scatterers = 3
    radius = 0.15 + 0.05 * (th[0] + 1) / 2
    centers = []
    for k in range(n_scatterers):
        ang = 2 * np.pi * k / n_scatterers + th[1] * 0.5
        r = 0.7 + 0.2 * th[2]
        centers.append((r * np.cos(ang), r * np.sin(ang)))
    centers = np.array(centers)

    W, H = state.resolution
    xmin, xmax, ymin, ymax = state.domain
    xs = np.linspace(xmin, xmax, W)
    ys = np.linspace(ymin, ymax, H)
    X0, Y0 = np.meshgrid(xs, ys)

    vx0 = 0.02 * (1 + 0.5 * th[3])
    vy0 = 0.015 * (1 + 0.5 * th[4]) if len(th) > 4 else 0.015
    dt = 1.0
    max_steps = state.max_iter
    rng = np.random.default_rng(state.seed)
    s = state.stochastic_scale

    X = X0.copy()
    Y = Y0.copy()
    VX = np.full_like(X, vx0)
    VY = np.full_like(Y, vy0)
    basin_map = np.full(X.shape, -1, dtype=int)
    escape_time = np.zeros(X.shape)
    active = np.ones(X.shape, dtype=bool)

    for step in range(max_steps):
        if not active.any():
            break
        for k, (cx, cy) in enumerate(centers):
            dx = X - cx
            dy = Y - cy
            d2 = dx*dx + dy*dy
            hit = active & (d2 < radius**2)
            if hit.any():
                basin_map[hit] = k
                escape_time[hit] = step
                active[hit] = False

        if not active.any():
            break

        fx = np.zeros_like(X)
        fy = np.zeros_like(Y)
        for cx, cy in centers:
            dx = X - cx
            dy = Y - cy
            d2 = dx*dx + dy*dy + 0.01
            f = 0.002 / d2
            ang = np.arctan2(dy, dx)
            fx += f * np.cos(ang)
            fy += f * np.sin(ang)
        if s > 0:
            fx = fx + rng.normal(0, s, size=fx.shape)
            fy = fy + rng.normal(0, s, size=fy.shape)

        VX = np.where(active, VX + fx, VX)
        VY = np.where(active, VY + fy, VY)
        X = np.where(active, X + VX * dt, X)
        Y = np.where(active, Y + VY * dt, Y)

    escape_time[active] = max_steps

    orbit_map = basin_map.astype(float)
    visit_density = escape_time
    return RunResult(orbit_map=orbit_map, visit_density=visit_density,
                      aux={"centers": centers, "radius": radius})
