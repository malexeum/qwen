"""D2 Blues — Last Train v4.7  «Singularity Vortex & Phantom Roots»
- Глубокая черная воронка гравитации у основания (спектральные мягкие кольца).
- Полупрозрачная темно-зеленая аффинная тень (свет падает справа сверху).
- Деликатные, прозрачные ляпуновские корни строго из нижней границы контакта.
- Истинная графитовая крошка и редкие искры в негативном пространстве.
- Мягкий невидимый переход внизу без глухого гробового прямоугольника.
"""
from __future__ import annotations
import argparse, hashlib, json, math, random, sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blues_d2_physical_layers import (
    BurialConfig, burial_backdrop_svg, burial_foreground_svg,
    physical_defs, seed_int,
)

RENDERER_VERSION = "4.7"
VIEWBOX = "0 0 1080 1260"
P = {
    "bg": "#020408",
    "cobalt": "#1A5A9E",
    "teal": "#1A7058",
    "dark_green": "#041D12",
    "shadow_green": "#02120A",
    "violet": "#4A3F98",
    "amber": "#A87818",
    "white": "#C8DCF0",
    "spark": "#E2F0FF",
}

LAST_TRAIN_TUNE = {
    "solitude_level": 0.92,
    "groove_pulse": 0.08,
    "gravity_sink": 0.96,
    "ground_memory": 0.90,
    "body_opacity": 0.68,
    "light_pressure": 0.18,
    "root_visibility": 0.12,
    "particle_density": 0.62,
    "spectral_spread": 0.90,
    "warmth_residue": 0.12,
    "chaos_decay": 0.72,
    "void_openness": 0.46,
}


@dataclass(frozen=True)
class LastTrainParams:
    solitude_level: float = 0.92
    groove_pulse: float = 0.08
    gravity_sink: float = 0.96
    ground_memory: float = 0.90
    body_opacity: float = 0.68
    light_pressure: float = 0.18
    root_visibility: float = 0.12
    particle_density: float = 0.62
    spectral_spread: float = 0.90
    warmth_residue: float = 0.12
    chaos_decay: float = 0.72
    void_openness: float = 0.46


@dataclass(frozen=True)
class MassSpec:
    cx: float; cy: float; rx: float; ry: float; points: int; salt: str


def _j(d):
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha256p(d):
    return "sha256:" + hashlib.sha256(d).hexdigest()


def _last_train_params(seed, track_name="LAST TRAIN BLUES"):
    return LastTrainParams(**LAST_TRAIN_TUNE)

def _mass_spec(seed):
    r = random.Random(seed_int(seed, "lt-mass-v40"))
    return MassSpec(310+r.uniform(-10,10), 450+r.uniform(-15,15),
                    r.uniform(235,275), r.uniform(310,360), 32, "lt-body-v40")


def _surface_y(x, cfg):
    left = cfg.left_sink * math.exp(-((x - cfg.left_x) ** 2) / (2 * cfg.left_sigma**2))
    right = cfg.right_sink * math.exp(-((x - cfg.right_x) ** 2) / (2 * cfg.right_sigma**2))
    ridge = cfg.contact_ridge * math.exp(-((x - cfg.contact_x) ** 2) / (2 * cfg.ridge_sigma**2))
    return cfg.surface_y + left + right - ridge + 5 * math.sin(x / 155 + 0.35) + 2.5 * math.sin(x / 71 - 0.8)

def _blob(seed, m, salt, scale=1.0, rough=1.0):
    r = random.Random(seed_int(seed, salt))
    ph = [r.uniform(0, math.tau) for _ in range(5)]
    pts = []
    for i in range(m.points):
        a = math.tau*i/m.points
        mod = 1+rough*(0.062*math.sin(3*a+ph[0])+0.032*math.sin(5*a+ph[1])+
                       0.016*math.sin(7*a+ph[2])+0.008*math.sin(11*a+ph[3])+0.004*math.sin(17*a+ph[4]))
        pts.append((m.cx+m.rx*scale*mod*math.cos(a), m.cy+m.ry*scale*mod*math.sin(a)))
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(m.points):
        p0,p1,p2,p3 = pts[(i-1)%m.points],pts[i],pts[(i+1)%m.points],pts[(i+2)%m.points]
        c1 = (p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6)
        c2 = (p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6)
        d.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)+" Z"


def _dark_green_affine_shadow(seed, mass, cfg, params=None):
    """One flattened ground projection, offset from the body's contact point."""
    params = params or _last_train_params(seed)
    cx = mass.cx + mass.rx * 0.28
    cy = _surface_y(cx, cfg) + 10
    opacity = 0.74 + params.gravity_sink * 0.12
    return [
        '<g id="lt-dark-green-shadow">',
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{mass.rx * 0.84:.1f}" ry="34" '
        f'fill="url(#surface-shadow-grad)" fill-opacity="{opacity:.3f}" filter="url(#surface-shadow-soft)"/>',
        '</g>',
    ]


def _ground_vortex_singularity(seed, mass, cfg, params=None):
    """Dark basin and soft spectral fill-rings on the ground plane."""
    params = params or _last_train_params(seed)
    r = random.Random(seed_int(seed, "lt-ground-vortex-v47"))
    out = ['<g id="lt-singularity-ground-vortex">']

    vx = mass.cx + 24
    vy = _surface_y(vx, cfg) + 40
    perspective = 0.22
    basin_rx = mass.rx * 1.00
    basin_ry = basin_rx * perspective

    for ri, scale in enumerate((0.86, 1.13, 1.42)):
        rx = basin_rx * scale * (0.96 + params.spectral_spread * 0.04)
        out.append(
            f'<ellipse cx="{vx:.1f}" cy="{vy:.1f}" rx="{rx:.1f}" ry="{rx * perspective * 1.12:.1f}" '
            f'fill="url(#ground-ring-grad)" fill-opacity="{0.40 - ri * 0.08:.2f}" '
            'filter="url(#ground-ring-soft)"/>'
        )
    out.append(
        f'<ellipse cx="{vx:.1f}" cy="{vy:.1f}" rx="{basin_rx * 0.72:.1f}" ry="{basin_ry * 0.78:.1f}" '
        f'fill="url(#vortex-singularity-grad)" fill-opacity="{0.96 + params.gravity_sink * 0.04:.3f}" '
        'filter="url(#vortex-core-blur)"/>'
    )

    out.append('</g>')
    return out


def _subterranean_spectra(seed, mass, cfg, params=None):
    params = params or _last_train_params(seed)
    r = random.Random(seed_int(seed, "lt-subterranean-spectra"))
    out = ['<g id="lt-subterranean-spectra">']
    vx = mass.cx + r.uniform(-12, 12)
    vy = _surface_y(vx, cfg) + 30
    span = mass.rx * 1.30
    count = 4
    for i in range(count):
        ratio = (i + 1) / count
        rx = span * (0.66 + ratio * 0.42)
        ry = rx * 0.19
        y = vy + (i - (count - 1) * 0.5) * 22
        phase = r.uniform(0, math.tau)
        n_pts = 90
        pts = []
        for j in range(n_pts):
            theta = math.tau * j / n_pts
            mod = 1.0 + 0.16 * math.sin(2 * theta + phase) + 0.08 * math.sin(5 * theta + phase * 0.8)
            pts.append((vx + rx * mod * math.cos(theta), y + ry * mod * math.sin(theta)))
        d = [f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"]
        for j in range(n_pts):
            p0, p1, p2, p3 = pts[(j - 1) % n_pts], pts[j], pts[(j + 1) % n_pts], pts[(j + 2) % n_pts]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d.append(f"C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
        d.append("Z")
        color = ["#0F2D30", "#112C3D", "#1B2448", "#261C48", "#171621"][i % 5]
        opacity = 0.045 + (1.0 - ratio) * 0.05
        out.append(f'<path d="{" ".join(d)}" fill="{color}" fill-opacity="{opacity:.3f}" filter="url(#shadow-blur)"/>')
    out.append('</g>')
    return out


def _memory_shadows(seed):
    out = ['<g id="lt-memory-shadows">']
    echoes = [
        ("M 575 275 C 635 160 738 164 790 252 S 907 337 1038 226", 92, 0.46),
        ("M 635 520 C 742 488 728 352 824 392 S 930 538 1058 420", 82, 0.42),
    ]
    for path, width, opacity in echoes:
        out.append(f'<path d="{path}" fill="none" stroke="url(#memory-echo-grad)" stroke-width="{width}" stroke-linecap="round" stroke-opacity="{opacity}" filter="url(#memory-shadow-blur)"/>')
    out.append('</g>')
    return out


def _sparse_light_accents(seed):
    r = random.Random(seed_int(seed, "lt-sparse-light-v1"))
    out = ['<g id="lt-sparse-light-accents">']
    count = r.randint(7, 8)
    for _ in range(count):
        if r.random() < 0.72:
            x, y = r.uniform(680, 1040), r.uniform(45, 520)
        else:
            x, y = r.uniform(540, 1000), r.uniform(70, 590)
        while ((x - 316) / 270) ** 2 + ((y - 462) / 340) ** 2 < 1.18:
            x, y = r.uniform(650, 1040), r.uniform(45, 540)

        if r.random() < 0.64:
            radius = r.uniform(1.15, 1.65)
            opacity = r.uniform(0.34, 0.52)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.2f}" fill="{P["spark"]}" fill-opacity="{opacity:.3f}"/>')
        else:
            length = r.uniform(3.0, 6.0)
            angle = r.uniform(-0.82, -0.48)
            opacity = r.uniform(0.30, 0.46)
            x2, y2 = x + length * math.cos(angle), y + length * math.sin(angle)
            out.append(f'<path d="M {x:.1f} {y:.1f} L {x2:.1f} {y2:.1f}" fill="none" stroke="{P["spark"]}" stroke-width="1.0" stroke-linecap="round" stroke-opacity="{opacity:.3f}"/>')
    out.append('</g>')
    return out


def _standing_waves(seed, mass, params=None):
    """A very low-pulse, hidden groove field; it must never become the visual headline."""
    params = params or _last_train_params(seed)
    r = random.Random(seed_int(seed, "lt-waves-v47"))
    out = ['<g id="lt-standing-waves" fill="none">']
    if params.groove_pulse <= 0.12:
        out.append('</g>')
        return out

    n_waves = 4
    colors = [P["teal"], P["violet"], P["cobalt"], P["teal"]]

    for wi in range(n_waves):
        y_c = mass.cy - mass.ry * 0.52 + wi * mass.ry * 0.10 + r.uniform(-6, 6)
        amplitude = r.uniform(9, 20) * params.groove_pulse
        lam = r.uniform(240, 420)
        beta = r.uniform(0.00012, 0.00022)
        phi = r.uniform(0, math.tau)
        color = colors[wi % len(colors)]
        opacity = 0.05 + params.groove_pulse * 0.12
        w_str = 0.6 + params.groove_pulse * 0.8
        pts = []
        x0, x1 = 60, 1020
        for si in range(55):
            x = x0 + (x1 - x0) * si / 54
            env = amplitude * math.exp(-beta * abs(x - mass.cx))
            y = y_c + env * math.sin(2 * math.pi * x / lam + phi)
            pts.append((x, y))
        if not pts:
            continue
        dw = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
        for p in pts[1:]:
            dw += f" L {p[0]:.1f},{p[1]:.1f}"
        out.append(f'<path d="{dw}" stroke="{color}" stroke-width="{w_str:.1f}" stroke-opacity="{opacity:.3f}" stroke-linecap="round" filter="url(#wave-blur)"/>')

    out.append('</g>')
    return out


def _phantom_lyapunov_roots(seed, mass, cfg, params=None):
    """Thin double-layer roots, strongest mid-span and fading into body and basin."""
    params = params or _last_train_params(seed)

    def lyap(x, seq="AABB", iters=20):
        ra, rb = 3.68, 3.94
        s = 0.0
        for i in range(iters):
            rv = ra if seq[i % len(seq)] == 'A' else rb
            x = rv * x * (1 - x)
            s += math.log(abs(rv * (1 - 2 * x)) + 1e-9)
        return s / iters

    r = random.Random(seed_int(seed, "lt-phantom-roots-v47"))
    out = ['<g id="lt-phantom-lyapunov-roots" fill="none" stroke-linecap="round">']
    colors = [P["teal"], P["cobalt"], P["violet"], P["teal"], P["cobalt"]]
    n = r.randint(7, 11)

    def _trace(cx_, cy_, alpha, depth, col, w, op, lvl=0):
        if depth < 10 or lvl > 2:
            return []
        lines = []
        x_lp = 0.3 + 0.4 * r.random()
        seq = r.choice(["AABB", "ABAB"])
        steps = max(5, int(depth / 18))
        pts = [(cx_, cy_)]
        cur_x, cur_y = cx_, cy_
        for step in range(steps):
            t = step / steps
            sl = (depth / steps) * (0.5 + 0.6 * r.random())
            lam = lyap(x_lp, seq)
            x_lp = max(0.01, min(0.99, x_lp + 0.014 * (1 if lam > -0.3 else -1)))
            delta = lam * 0.08 * (1 + t * 1.6)
            alpha += delta + r.gauss(0, 0.04 + t * 0.06)
            alpha = alpha * 0.78 + (math.pi * 0.5 + r.gauss(0, 0.12)) * 0.22
            cur_x += sl * math.cos(alpha)
            cur_y += sl * math.sin(alpha) * 0.85
            pts.append((cur_x, cur_y))
        if len(pts) >= 2:
            dr = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
            for pi in range(1, len(pts) - 1):
                p0, p1, p2 = pts[pi - 1], pts[pi], pts[pi + 1]
                mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
                dr += f" Q {p1[0]:.1f},{p1[1]:.1f} {mx:.1f},{my:.1f}"
            dr += f" L {pts[-1][0]:.1f},{pts[-1][1]:.1f}"
            lines.append((dr, col, w, op, pts))
        return lines

    for i in range(n):
        col = colors[i % len(colors)]
        t_i = i / max(n - 1, 1)
        sx_ = mass.cx + (t_i - 0.5) * 2 * mass.rx * 0.38 + r.uniform(-5, 5)
        offset = (sx_ - mass.cx) / mass.rx
        body_bottom = mass.cy + mass.ry * math.sqrt(max(0.0, 1.0 - offset * offset))
        sy_ = min(body_bottom + 2, _surface_y(sx_, cfg) + 10)
        alpha = math.pi * 0.48 + r.uniform(-0.18, 0.18)
        depth = r.uniform(125, 185) * (0.85 + params.root_visibility)
        op = r.uniform(0.35, 0.45) * (0.65 + params.root_visibility) * 0.75
        w = r.uniform(0.62, 0.82)
        lines = _trace(sx_, sy_, alpha, depth, col, w, op, lvl=0)
        for dr, lc, lw, lo, points in lines:
            out.append(f'<path d="{dr}" stroke="url(#root-understroke-grad)" stroke-width="{lw * 4.0:.2f}" stroke-opacity="{lo * 0.90:.3f}" filter="url(#root-understroke-blur)"/>')
            for pi in range(1, len(points) - 1):
                t = pi / (len(points) - 1)
                if 0.20 <= t <= 0.82 and r.random() < 0.50:
                    p0, p1 = points[pi], points[pi + 1]
                    fragment_opacity = lo * 0.84 * math.sin(math.pi * t)
                    out.append(f'<path d="M {p0[0]:.1f} {p0[1]:.1f} L {p1[0]:.1f} {p1[1]:.1f}" stroke="{lc}" stroke-width="{lw:.2f}" stroke-opacity="{fragment_opacity:.3f}"/>')

    out.append('</g>')
    return out


def _graphite_crumbles(seed, params=None):
    """Local graphite residue below the surface node."""
    params = params or _last_train_params(seed)
    r = random.Random(seed_int(seed, "lt-particles-v47"))
    out = ['<g id="lt-graphite-crumbs">']

    crumb_count = int(260 * params.particle_density)
    for _ in range(crumb_count):
        gx = min(1060, max(20, r.gauss(340, 175)))
        gy = 765 + 315 * (r.random() ** 0.78)
        if r.random() < 0.70:
            rad = r.uniform(0.80, 1.65)
            op = r.uniform(0.12, 0.22)
            c = "#687181" if r.random() < 0.08 else "#282F3A"
            out.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="{rad:.2f}" fill="{c}" fill-opacity="{op:.3f}"/>')
        else:
            ln = r.uniform(1.2, 5.0)
            ang = math.radians(r.uniform(60, 120))
            op = r.uniform(0.08, 0.15)
            out.append(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{gx + ln * math.cos(ang):.1f}" y2="{gy + ln * math.sin(ang):.1f}" '
                       f'stroke="#4E5560" stroke-width="0.75" stroke-opacity="{op:.3f}"/>')

    out.append('</g>')
    return out


def _mist(seed, params=None):
    params = params or _last_train_params(seed)
    r = random.Random(seed_int(seed, "lt-mist-v47"))
    out = ['<g id="lt-void-mist">']
    for _ in range(int(12 + 18 * params.void_openness)):
        out.append(f'<ellipse cx="{r.uniform(40, 1040):.0f}" cy="{r.uniform(180, 840):.0f}" '
                   f'rx="{r.uniform(30, 160):.0f}" ry="{r.uniform(4, 20):.0f}" fill="#788294" '
                   f'fill-opacity="{r.uniform(.003, .012) * params.void_openness:.4f}" filter="url(#mist)"/>')
    out.append('</g>')
    return out


def render_svg(seed="d2-last-train-v1", track_name="LAST TRAIN BLUES"):
    params = _last_train_params(seed, track_name)
    footer_seed_id = seed_int(seed, "lt-footer-id")
    mass = _mass_spec(seed)
    mp = _blob(seed, mass, mass.salt)
    cfg = BurialConfig(
        surface_y=720,
        left_x=mass.cx - mass.rx * 0.4, right_x=mass.cx + mass.rx * 0.4,
        contact_x=mass.cx, left_sink=50, right_sink=30,
        left_sigma=max(150, mass.rx * 0.74), right_sigma=max(110, mass.rx * 0.62),
        contact_ridge=0, foreground_opacity=0.18,
        sediment_count=90,
    )
    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}">',
        '<defs>',
        '<filter id="smoke-body" x="-55%" y="-55%" width="210%" height="210%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".005 .011" numOctaves="3" seed="31" result="n"/>'
        '<feDisplacementMap in="SourceGraphic" in2="n" scale="20" result="d"/>'
        '<feGaussianBlur in="d" stdDeviation="14"/></filter>',
        '<filter id="organ-glow" x="-70%" y="-90%" width="240%" height="280%"><feGaussianBlur stdDeviation="16"/></filter>',
        '<filter id="organ-soft" x="-60%" y="-80%" width="220%" height="260%"><feGaussianBlur stdDeviation="9"/></filter>',
        '<filter id="vortex-core-blur" x="-30%" y="-40%" width="160%" height="180%"><feGaussianBlur stdDeviation="18"/></filter>',
        '<filter id="vortex-ring-soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2"/></filter>',
        '<filter id="wave-blur" x="-5%" y="-60%" width="110%" height="220%"><feGaussianBlur stdDeviation="1.8"/></filter>',
        '<filter id="mist" x="-40%" y="-100%" width="180%" height="300%"><feGaussianBlur stdDeviation="11"/></filter>',
        '<filter id="shadow-blur" x="-30%" y="-20%" width="160%" height="140%"><feGaussianBlur stdDeviation="26"/></filter>',
        '<filter id="echo-blur" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="42"/></filter>',
        '<filter id="memory-shadow-blur" x="-40%" y="-60%" width="180%" height="220%"><feGaussianBlur stdDeviation="30"/></filter>',
        '<filter id="root-understroke-blur" x="-80%" y="-50%" width="260%" height="200%"><feGaussianBlur stdDeviation="1.2 2"/></filter>',
        '<filter id="cone-blur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="30"/></filter>',
        '<filter id="bolt-glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="5"/></filter>',
        '<filter id="spark-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3.5"/></filter>',
        f'<clipPath id="clip-mass"><path d="{mp}"/></clipPath>',
        '<radialGradient id="body-main" cx="0.42" cy="0.40" r="0.58">'
        '<stop offset="0" stop-color="#1E2E42" stop-opacity=".94"/>'
        '<stop offset=".52" stop-color="#0C1620" stop-opacity=".62"/>'
        '<stop offset=".78" stop-color="#040608" stop-opacity=".035"/>'
        '<stop offset="1" stop-color="#040608" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="body-warm" cx="0.76" cy="0.28" r="0.44">'
        '<stop offset="0" stop-color="#3A2210" stop-opacity=".20"/>'
        '<stop offset="1" stop-color="#040608" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="vortex-singularity-grad" cx="50%" cy="40%" r="55%">'
        '<stop offset="0%" stop-color="#000000" stop-opacity="0.98"/>'
        '<stop offset="52%" stop-color="#020807" stop-opacity="0.90"/>'
        '<stop offset="88%" stop-color="#051410" stop-opacity="0.38"/>'
        '<stop offset="100%" stop-color="#020408" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="ground-ring-grad" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#020508" stop-opacity="0.26"/>'
        '<stop offset="34%" stop-color="#06130F" stop-opacity="0.38"/>'
        '<stop offset="64%" stop-color="#15503D" stop-opacity="0.27"/>'
        '<stop offset="86%" stop-color="#173A50" stop-opacity="0.16"/>'
        '<stop offset="100%" stop-color="#080A12" stop-opacity="0"/>'
        '</radialGradient>',
        '<linearGradient id="memory-echo-grad" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#1B3A40" stop-opacity="0"/>'
        '<stop offset="20%" stop-color="#1B3A40" stop-opacity="0.48"/>'
        '<stop offset="54%" stop-color="#263B47" stop-opacity="0.38"/>'
        '<stop offset="82%" stop-color="#1B3A40" stop-opacity="0.44"/>'
        '<stop offset="100%" stop-color="#1B3A40" stop-opacity="0"/>'
        '</linearGradient>',
        '<radialGradient id="surface-shadow-grad" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#041D12" stop-opacity="0.84"/>'
        '<stop offset="58%" stop-color="#041D12" stop-opacity="0.60"/>'
        '<stop offset="84%" stop-color="#02120A" stop-opacity="0.16"/>'
        '<stop offset="100%" stop-color="#02120A" stop-opacity="0"/>'
        '</radialGradient>',
        '<linearGradient id="root-understroke-grad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#15503D" stop-opacity="0"/>'
        '<stop offset="22%" stop-color="#15503D" stop-opacity="0.20"/>'
        '<stop offset="52%" stop-color="#15503D" stop-opacity="0.46"/>'
        '<stop offset="78%" stop-color="#15503D" stop-opacity="0.16"/>'
        '<stop offset="100%" stop-color="#15503D" stop-opacity="0"/>'
        '</linearGradient>',
        '<filter id="surface-shadow-soft" x="-25%" y="-80%" width="150%" height="260%"><feGaussianBlur stdDeviation="14 8"/></filter>',
        '<filter id="ground-ring-soft" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="20 12"/></filter>',
        '<linearGradient id="footer-smooth" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#020408" stop-opacity="0"/>'
        '<stop offset="40%" stop-color="#020408" stop-opacity="0.58"/>'
        '<stop offset="100%" stop-color="#020408" stop-opacity="0.92"/>'
        '</linearGradient>',
        *physical_defs(),
        '</defs>',
        f'<rect width="1080" height="1260" fill="{P["bg"]}"/>',
        '<g id="lt-artwork">',

        *_mist(seed, params),
        *_memory_shadows(seed),
        *_sparse_light_accents(seed),
        *burial_backdrop_svg(seed, cfg),
        *_subterranean_spectra(seed, mass, cfg, params),
        *_dark_green_affine_shadow(seed, mass, cfg, params),
        '<g id="lt-smoky-mass">',
        f'<path d="{mp}" fill="url(#body-main)" fill-opacity="{params.body_opacity:.3f}" filter="url(#smoke-body)"/>',
        f'<path d="{mp}" fill="url(#body-warm)" fill-opacity="{0.22 + params.warmth_residue * 0.28:.3f}"/>',
        '</g>',
        '<g id="lt-internal-organs" clip-path="url(#clip-mass)">',
    ]

    ro = random.Random(seed_int(seed, "lt-organs-v40"))
    od = [("#2E5A8A",0.44),("#1E4A72",0.36),("#4A3F8A",0.40),("#165A48",0.34),
          ("#0A1828",0.28),("#3A3278",0.32),("#1A4868",0.38)]
    for i in range(7):
        o = MassSpec(mass.cx+ro.uniform(-.46,.46)*mass.rx, mass.cy+ro.uniform(-.50,.50)*mass.ry,
                     mass.rx*ro.uniform(.09,.31), mass.ry*ro.uniform(.07,.23), 16, f"lt-org-{i}")
        col,op = od[i%len(od)]; op += ro.uniform(-.04,.06)
        flt = "organ-glow" if i%2==0 else "organ-soft"
        svg.append(f'<path d="{_blob(seed,o,o.salt,rough=.50)}" fill="{col}" fill-opacity="{max(0.18,op):.2f}" filter="url(#{flt})"/>')

    svg += [
        '</g>',
        *burial_foreground_svg(seed, cfg),
        *_ground_vortex_singularity(seed, mass, cfg, params),
        *_phantom_lyapunov_roots(seed, mass, cfg, params),
        *_graphite_crumbles(seed, params),
        '</g>',
        '<g id="lt-footer">',
        '<rect y="1040" width="1080" height="220" fill="url(#footer-smooth)"/>',
        '<line x1="84" x2="996" y1="1100" y2="1100" stroke="#737986" stroke-opacity=".20"/>',
        f'<text x="540" y="1152" text-anchor="middle" fill="#B0B0AC" font-family="Arial,sans-serif" '
        f'font-size="24" letter-spacing="6" font-weight="400">{track_name.upper()}</text>',
        f'<text x="540" y="1192" text-anchor="middle" fill="#505058" font-family="Arial,sans-serif" '
        f'font-size="10" letter-spacing="3">seed {footer_seed_id}</text>',
        '</g></svg>',
    ]
    return ("\n".join(svg)+"\n").encode("utf-8")


def build_metadata(seed, svg_bytes, track_name="LAST TRAIN BLUES"):
    m = _mass_spec(seed)
    return _j({
        "renderer": {"name": "d2_blues_last_train_renderer", "version": RENDERER_VERSION},
        "seed": seed,
        "track_name": track_name,
        "mass_geometry": {"cx": m.cx, "cy": m.cy, "rx": m.rx, "ry": m.ry},
        "render_params": asdict(_last_train_params(seed, track_name)),
    })

def write_outputs(seed, svg_path, metadata_path, track_name="LAST TRAIN BLUES"):
    svg=render_svg(seed,track_name); Path(svg_path).parent.mkdir(parents=True,exist_ok=True)
    Path(metadata_path).parent.mkdir(parents=True,exist_ok=True)
    Path(svg_path).write_bytes(svg); Path(metadata_path).write_bytes(build_metadata(seed,svg,track_name))
    return svg_path, metadata_path

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--seed",default="d2-last-train-v1")
    p.add_argument("--track-name",default="LAST TRAIN BLUES")
    p.add_argument("--svg-output",default="artifacts/d2/posters/d2_blues_last_train.svg")
    p.add_argument("--metadata-output",default="artifacts/d2/posters/d2_blues_last_train.metadata.json")
    return p.parse_args()

def main():
    a=parse_args(); write_outputs(a.seed,a.svg_output,a.metadata_output,track_name=a.track_name); return 0

if __name__=="__main__": raise SystemExit(main())