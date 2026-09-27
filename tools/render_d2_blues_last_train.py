"""
D2 Blues — Last Train v4.1  «Gravity Well + Standing Wave + Vortex Rings»

Математическая архитектура:
  • Кольца воронки: r_i(θ) = R_i · (1 + Σ aₙ sin(nθ + φₙ))  — модулированные
    изолинии гравитационного поля, 9 колец с цветовыми акцентами
  • Стоячие волны: y(x) = A·e^{-β|x−cx|}·sin(2πx/λ + φ)
    слева φ_L, справа φ_R = φ_L + π·k  (call & response)
  • Аффинная тень: [sx sh; 0 sy] · [lx; ly] + [dx; dy]
  • Ляпуновские корни: α_{i+1} = α_i + λ_i·δ,  λ = ляпунов(x, seq)
    хаос нарастает с глубиной, ветвления при |λ|>0.45
  • Тело: только дымные SVG-слои, без жёсткого контура
"""
from __future__ import annotations
import argparse, hashlib, json, math, random, sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blues_d2_physical_layers import (
    BurialConfig, burial_backdrop_svg, burial_foreground_svg,
    physical_defs, seed_int, tactile_void_svg,
)

RENDERER_VERSION = "4.1"
VIEWBOX = "0 0 1080 1260"

PALETTE = {
    "bg":       "#020408",
    "body":     "#1E2E42",
    "warm":     "#3A2210",
    "cobalt":   "#1A5A9E",
    "teal":     "#1A7058",
    "violet":   "#4A3F98",
    "amber":    "#A87818",
    "white":    "#C8DCF0",
    "shadow":   "#010804",
    "sediment": "#080604",
    # кольца — цветовые акценты воронки
    "ring0":       "#0A1E35",
    "ring1":       "#0E2840",
    "ring2":       "#122A3A",
    "ring3":       "#0A2230",
    "ring4":       "#142035",
    "ring5":       "#0C1A28",
    "ring_teal":   "#0A2820",
    "ring_violet": "#18102A",
}

# accent stroke colours for each ring (янтарь→тил→индиго→фиолет)
_RING_ACCENTS = [
    "#1A2840", "#0E3040", "#102830", "#0A2035",
    "#162030", "#0C1C2C", "#141828", "#0A1820", "#101828",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _jbytes(d) -> bytes:
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()

def sha256p(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


@dataclass(frozen=True)
class MassSpec:
    cx: float; cy: float; rx: float; ry: float; points: int; salt: str


def _mass_spec(seed: str) -> MassSpec:
    r = random.Random(seed_int(seed, "lt-mass-v40"))
    return MassSpec(
        310 + r.uniform(-12, 12),
        460 + r.uniform(-20, 18),
        r.uniform(235, 282),
        r.uniform(305, 368),
        32, "lt-body-v40",
    )


def _blob(seed: str, m: MassSpec, salt: str, scale: float = 1.0, rough: float = 1.0) -> str:
    r = random.Random(seed_int(seed, salt))
    ph = [r.uniform(0, math.tau) for _ in range(5)]
    pts = []
    for i in range(m.points):
        a = math.tau * i / m.points
        mod = 1 + rough * (
            0.062 * math.sin(3*a + ph[0]) + 0.032 * math.sin(5*a + ph[1]) +
            0.016 * math.sin(7*a + ph[2]) + 0.008 * math.sin(11*a + ph[3]) +
            0.004 * math.sin(17*a + ph[4])
        )
        pts.append((m.cx + m.rx * scale * mod * math.cos(a),
                    m.cy + m.ry * scale * mod * math.sin(a)))
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(m.points):
        p0, p1, p2, p3 = (pts[(i-1) % m.points], pts[i],
                          pts[(i+1) % m.points], pts[(i+2) % m.points])
        c1 = (p1[0] + (p2[0]-p0[0])/6, p1[1] + (p2[1]-p0[1])/6)
        c2 = (p2[0] - (p3[0]-p1[0])/6, p2[1] - (p3[1]-p1[1])/6)
        d.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d) + " Z"


# ── layer generators ──────────────────────────────────────────────────────────

def _vortex_rings(seed: str, mass: MassSpec) -> list[str]:
    """
    9 мрачных концентрических колец — воронка притяжения.
    r_i(θ) = R_i · (1 + Σ_{n=1}^{4} aₙ sin(nθ + φₙ))
    Ближние: тонкий stroke + цветной акцент.
    Дальние: тёмный fill + широкий stroke (добавляют глубину).
    """
    r = random.Random(seed_int(seed, "lt-rings-v41"))
    out = ['<g id="lt-vortex-rings">']
    gamma    = 1.38           # перспективное вертикальное сжатие
    n_rings  = 9
    base_R   = [mass.rx * (1.08 + i * 0.52) for i in range(n_rings)]

    for ri, R in enumerate(base_R):
        decay  = 1.0 / (1.0 + ri * 0.25)
        amps   = [r.uniform(0.025, 0.08) * decay / (n+1) for n in range(4)]
        phases = [r.uniform(0, math.tau) for _ in range(4)]
        n_pts  = 120
        pts    = []
        for i in range(n_pts):
            theta = math.tau * i / n_pts
            mod   = 1.0
            for n, (a, ph) in enumerate(zip(amps, phases), 1):
                mod += a * math.sin(n * theta + ph)
            pts.append((mass.cx + R * mod * math.cos(theta),
                        mass.cy + R * mod / gamma * math.sin(theta)))

        dp = [f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"]
        for i in range(n_pts):
            p0,p1,p2,p3 = pts[(i-1)%n_pts], pts[i], pts[(i+1)%n_pts], pts[(i+2)%n_pts]
            c1 = (p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6)
            c2 = (p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6)
            dp.append(f"C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
        dp.append("Z")
        pd  = " ".join(dp)
        col = _RING_ACCENTS[ri % len(_RING_ACCENTS)]

        if ri < 4:
            # тонкие stroke-кольца с цветным акцентом
            op_s = 0.18 - ri * 0.03
            w    = 1.0 + ri * 0.15
            out.append(f'<path d="{pd}" fill="none" stroke="{col}" '
                       f'stroke-width="{w:.2f}" stroke-opacity="{op_s:.3f}" '
                       f'filter="url(#ring-blur)"/>')
            op2 = max(0.02, 0.08 - ri * 0.015)
            accent = PALETTE["teal"] if ri % 2 == 0 else PALETTE["violet"]
            out.append(f'<path d="{pd}" fill="none" stroke="{accent}" '
                       f'stroke-width="0.6" stroke-opacity="{op2:.3f}"/>')
        else:
            # широкие fill-кольца — усиливают тёмную воронку
            op_f = 0.06 + (ri - 4) * 0.02
            out.append(f'<path d="{pd}" fill="{PALETTE["bg"]}" '
                       f'fill-opacity="{op_f:.3f}" filter="url(#ring-blur)"/>')
            op_s = max(0.02, 0.10 - (ri-4) * 0.015)
            w    = 1.4 + (ri-4) * 0.25
            out.append(f'<path d="{pd}" fill="none" stroke="{col}" '
                       f'stroke-width="{w:.2f}" stroke-opacity="{op_s:.3f}" '
                       f'filter="url(#ring-blur)"/>')

    out.append('</g>')
    return out


def _standing_waves(seed: str, mass: MassSpec) -> list[str]:
    """
    Стоячие волны отчуждения — call & response.
    y(x) = A · e^{-β|x−cx|} · sin(2πx/λ + φ)
    Слева φ_L, справа φ_R = φ_L + π·k.
    """
    r   = random.Random(seed_int(seed, "lt-waves-v41"))
    out = ['<g id="lt-standing-waves" fill="none">']
    for wi in range(8):
        y_c  = mass.cy - mass.ry*0.55 + wi*mass.ry*0.22 + r.uniform(-10, 10)
        A    = r.uniform(12, 32) * (1 - wi*0.05)
        lam  = r.uniform(160, 320)
        beta = r.uniform(0.0006, 0.0018)
        phi_L = r.uniform(0, math.tau)
        phi_R = phi_L + math.pi * r.uniform(0.85, 1.15)

        for _side, x0, x1, phi in [
            ("L", 0.0,                       mass.cx - mass.rx*0.80, phi_L),
            ("R", mass.cx + mass.rx*0.80, 1080.0,                    phi_R),
        ]:
            pts = []
            for si in range(81):
                x   = x0 + (x1-x0)*si/80
                env = A * math.exp(-beta * abs(x - mass.cx))
                y   = y_c + env * math.sin(2*math.pi*x/lam + phi)
                pts.append((x, y))
            if len(pts) < 2:
                continue
            dw  = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
            dw += " ".join(f"L {p[0]:.1f},{p[1]:.1f}" for p in pts[1:])
            op  = r.uniform(0.08, 0.18) * (1 - wi*0.06)
            col_map = {0: PALETTE["teal"], 1: "#0E1C30", 2: PALETTE["violet"]}
            col = col_map[wi % 3]
            w   = 0.8 + (0.3 if wi % 3 == 0 else 0.0)
            out.append(f'<path d="{dw}" stroke="{col}" stroke-width="{w:.1f}" '
                       f'stroke-opacity="{op:.3f}" stroke-linecap="round" '
                       f'filter="url(#wave-blur)"/>')
    out.append('</g>')
    return out


def _affine_shadow(seed: str, mass: MassSpec) -> list[str]:
    """
    Тень через аффинное преобразование:
    [x'] = [sx  sh] · [lx]  + [cx+dx]
    [y']   [0   sy]   [ly]    [cy+dy]
    """
    r   = random.Random(seed_int(seed, "lt-shadow-v40"))
    sx  = r.uniform(0.75, 0.92)
    sy  = r.uniform(1.20, 1.55)
    sh  = r.uniform(-0.35, -0.18)
    dx  = r.uniform(80, 160)
    dy  = r.uniform(60, 130)
    rng2 = random.Random(seed_int(seed, "lt-body-v40"))
    ph   = [rng2.uniform(0, math.tau) for _ in range(5)]

    def _make(ddx, ddy, s_scale):
        pts = []
        for i in range(mass.points):
            a   = math.tau * i / mass.points
            mod = 1 + s_scale * (
                0.062*math.sin(3*a+ph[0]) + 0.032*math.sin(5*a+ph[1]) +
                0.016*math.sin(7*a+ph[2]) + 0.008*math.sin(11*a+ph[3]) +
                0.004*math.sin(17*a+ph[4])
            )
            lx = mass.rx * mod * math.cos(a)
            ly = mass.ry * mod * math.sin(a)
            nx = min(max(sx*lx + sh*ly + mass.cx + ddx, 0), 1080)
            ny = sy*ly + mass.cy + ddy
            pts.append((nx, ny))
        d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
        for i in range(mass.points):
            p0,p1,p2,p3 = pts[(i-1)%mass.points], pts[i], pts[(i+1)%mass.points], pts[(i+2)%mass.points]
            c1 = (p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6)
            c2 = (p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6)
            d.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
        return " ".join(d) + " Z"

    sp1 = _make(dx,                         dy,                         0.80)
    r2  = random.Random(seed_int(seed, "lt-shadow2-v40"))
    sp2 = _make(dx + r2.uniform(18, 36),    dy + r2.uniform(25, 48),    0.70)
    return [
        '<g id="lt-shadow">',
        f'<path d="{sp1}" fill="{PALETTE["shadow"]}" fill-opacity="0.95" filter="url(#shadow-blur)"/>',
        f'<path d="{sp2}" fill="{PALETTE["shadow"]}" fill-opacity="0.52" filter="url(#echo-blur)"/>',
        '</g>',
    ]


def _lyapunov_roots(seed: str, mass: MassSpec) -> list[str]:
    """
    Корни — параметрические кривые с нарастающим Ляпуновым.
    λ(x, seq) = (1/N) Σ ln|r(1−2x)|   (логистический Ляпунов)
    α_{i+1} = α_i + λ_i · δ · (1 + t·2.2)
    Хаос нарастает с глубиной; ветвления при |λ|>0.45.
    """
    def _lyap(x, seq="AABB", iters=24):
        ra, rb = 3.68, 3.94
        s = 0.0
        for i in range(iters):
            rv = ra if seq[i % len(seq)] == 'A' else rb
            x  = rv * x * (1 - x)
            s += math.log(abs(rv * (1 - 2*x)) + 1e-9)
        return s / iters

    r   = random.Random(seed_int(seed, "lt-roots-v41"))
    out = ['<g id="lt-lyapunov-roots" fill="none" stroke-linecap="round">']
    colors = [PALETTE["cobalt"], PALETTE["teal"], PALETTE["violet"],
              PALETTE["cobalt"], PALETTE["teal"]]
    n = r.randint(4, 6)

    for i in range(n):
        col    = colors[i % len(colors)]
        spread = (i / (n-1) - 0.5) * 2 if n > 1 else 0.0
        sx_    = mass.cx + spread * mass.rx * 0.68 + r.uniform(-14, 14)
        sy_    = mass.cy + mass.ry * r.uniform(0.58, 0.90)
        x_lp   = 0.3 + 0.4 * r.random()
        seq    = r.choice(["AABB", "ABAB", "AAAB"])
        alpha  = math.pi * 0.5 + r.uniform(-0.28, 0.28)
        pts    = [(sx_, sy_)]
        cx_, cy_ = sx_, sy_
        depth  = r.uniform(130, 240)

        for step in range(30):
            t  = step / 29
            sl = (depth / 30) * (0.8 + 0.4 * r.random())
            lam = _lyap(x_lp, seq)
            x_lp = max(0.01, min(0.99, x_lp + 0.018 * (1 if lam > -0.3 else -1)))
            delta  = lam * 0.14 * (1 + t * 2.2)
            alpha += delta + r.gauss(0, 0.04 + t * 0.08)
            alpha  = alpha * 0.72 + (math.pi * 0.5 + r.gauss(0, 0.18)) * 0.28
            cx_   += sl * math.cos(alpha)
            cy_   += sl * math.sin(alpha) * 0.85
            pts.append((cx_, cy_))

            # ветвление
            if t > 0.28 and abs(lam) > 0.45 and r.random() < 0.28:
                bl  = sl * r.uniform(0.38, 0.65)
                ba  = alpha + r.uniform(0.28, 0.75) * (1 if r.random() > 0.5 else -1)
                bx  = cx_ + bl * math.cos(ba)
                by  = cy_ + bl * math.sin(ba) * 0.85
                bd  = f"M {cx_:.1f},{cy_:.1f} L {bx:.1f},{by:.1f}"
                out.append(f'<path d="{bd}" stroke="{col}" stroke-width="0.8" stroke-opacity="0.24"/>')
                out.append(f'<path d="{bd}" stroke="{PALETTE["white"]}" stroke-width="0.3" stroke-opacity="0.12"/>')

        if len(pts) < 2:
            continue
        dr = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
        for pi in range(1, len(pts)-1):
            p0,p1,p2 = pts[pi-1], pts[pi], pts[pi+1]
            mx, my   = (p0[0]+p2[0])/2, (p0[1]+p2[1])/2
            dr += f" Q {p1[0]:.1f},{p1[1]:.1f} {mx:.1f},{my:.1f}"
        dr += f" L {pts[-1][0]:.1f},{pts[-1][1]:.1f}"

        out.append(f'<g filter="url(#bolt-glow)"><path d="{dr}" stroke="{col}" stroke-width="8" stroke-opacity="0.10"/></g>')
        out.append(f'<path d="{dr}" stroke="{col}" stroke-width="1.6" stroke-opacity="0.36"/>')
        out.append(f'<path d="{dr}" stroke="{PALETTE["white"]}" stroke-width="0.5" stroke-opacity="0.18"/>')

    out.append('</g>')
    return out


def _light_cone(seed: str, mass: MassSpec) -> list[str]:
    r  = random.Random(seed_int(seed, "lt-cone-v40"))
    px = 1080 + r.uniform(60, 130); py = -r.uniform(40, 90)
    bx1 = mass.cx - mass.rx*1.1;  bx2 = mass.cx + mass.rx*0.55
    by  = mass.cy + mass.ry*0.95
    out = ['<g id="lt-light-cone">']
    for spread, op in [(1.0, 0.025), (1.6, 0.014), (2.4, 0.007)]:
        l  = bx1 - (spread-1)*mass.rx*0.35
        rb = bx2 + (spread-1)*mass.rx*0.25
        b  = by  + (spread-1)*35
        out.append(f'<path d="M {px:.0f},{py:.0f} L {l:.0f},{b:.0f} L {rb:.0f},{b:.0f} Z" '
                   f'fill="{PALETTE["amber"]}" fill-opacity="{op:.3f}" filter="url(#cone-blur)"/>')
    out.append('</g>')
    return out


def _temporal(seed: str) -> list[str]:
    r   = random.Random(seed_int(seed, "lt-temporal-v40"))
    out = ['<g id="lt-temporal-layers">']
    for i in range(6):
        y   = 875 + i*23 + r.uniform(-5, 5)
        amp = 6 + i*3
        op  = 0.30 + i*0.10
        out.append(f'<path d="M 0,{y:.0f} Q 270,{y-amp:.0f} 540,{y:.0f} '
                   f'Q 810,{y+amp:.0f} 1080,{y:.0f} L 1080,1080 L 0,1080 Z" '
                   f'fill="{PALETTE["sediment"]}" fill-opacity="{op:.3f}"/>')
    for i in range(2):
        y  = 660 + i*68 + r.uniform(-10, 10)
        cx = 320 + r.uniform(-50, 50)
        rx = r.uniform(150, 290); ry = r.uniform(12, 28)
        op = r.uniform(0.03, 0.07)
        out.append(f'<ellipse cx="{cx:.0f}" cy="{y:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" '
                   f'fill="{PALETTE["warm"]}" fill-opacity="{op:.3f}" filter="url(#floor-blur)"/>')
    out.append('</g>')
    return out


def _mist(seed: str) -> list[str]:
    r   = random.Random(seed_int(seed, "lt-mist-v40"))
    out = ['<g id="lt-void-mist">']
    for _ in range(22):
        cx = r.uniform(40, 1040); cy = r.uniform(260, 860)
        rx = r.uniform(20, 145);  ry = r.uniform(3, 20)
        op = r.uniform(0.003, 0.015)
        out.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" '
                   f'fill="#8A92A1" fill-opacity="{op:.4f}" filter="url(#mist)"/>')
    out.append('</g>')
    return out


def _dust(seed: str) -> list[str]:
    r   = random.Random(seed_int(seed, "lt-dust-v40"))
    out = ['<g id="lt-graphite-dust">']
    for _ in range(260):
        gy  = 1080 * (r.random()**0.50) * 0.95
        gx  = r.uniform(15, 1065)
        ln  = r.uniform(1, 5) if r.random() > 0.11 else r.uniform(6, 14)
        ang = math.radians(r.uniform(68, 102))
        light = r.random() < 0.05
        col = "#7A8090" if light else "#181410"
        op  = r.uniform(0.02, 0.07) * (0.4 if light else 1.0)
        out.append(f'<line x1="{gx:.0f}" y1="{gy:.0f}" '
                   f'x2="{gx + ln*math.cos(ang):.0f}" y2="{gy + ln*math.sin(ang):.0f}" '
                   f'stroke="{col}" stroke-width="0.65" stroke-opacity="{op:.4f}"/>')
    out.append('</g>')
    return out


# ── SVG assembly ──────────────────────────────────────────────────────────────

_DEFS = """\
<filter id="smoke-body" x="-55%" y="-55%" width="210%" height="210%">
  <feTurbulence type="fractalNoise" baseFrequency=".005 .011" numOctaves="3" seed="31" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="20" result="d"/>
  <feGaussianBlur in="d" stdDeviation="24"/>
</filter>
<filter id="glow-mass"   x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="48"/></filter>
<filter id="organ-glow"  x="-70%" y="-90%" width="240%" height="280%"><feGaussianBlur stdDeviation="16"/></filter>
<filter id="organ-soft"  x="-60%" y="-80%" width="220%" height="260%"><feGaussianBlur stdDeviation="9"/></filter>
<filter id="ring-blur"   x="-15%" y="-15%" width="130%" height="130%"><feGaussianBlur stdDeviation="2.5"/></filter>
<filter id="wave-blur"   x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="2"/></filter>
<filter id="mist"        x="-40%" y="-100%" width="180%" height="300%"><feGaussianBlur stdDeviation="11"/></filter>
<filter id="floor-blur"  x="-40%" y="-200%" width="180%" height="500%"><feGaussianBlur stdDeviation="24"/></filter>
<filter id="shadow-blur" x="-30%" y="-20%"  width="160%" height="140%"><feGaussianBlur stdDeviation="28"/></filter>
<filter id="echo-blur"   x="-60%" y="-60%"  width="220%" height="220%"><feGaussianBlur stdDeviation="44"/></filter>
<filter id="cone-blur"   x="-30%" y="-30%"  width="160%" height="160%"><feGaussianBlur stdDeviation="32"/></filter>
<filter id="bolt-glow"   x="-60%" y="-60%"  width="220%" height="220%"><feGaussianBlur stdDeviation="7"/></filter>
"""


def render_svg(seed: str = "d2-last-train-v1", track_name: str = "LAST TRAIN BLUES") -> bytes:
    mass = _mass_spec(seed)
    mp   = _blob(seed, mass, mass.salt)
    cfg  = BurialConfig(
        left_x   = mass.cx - mass.rx*0.4,
        right_x  = mass.cx + mass.rx*0.4,
        contact_x= mass.cx,
        left_sink =50, right_sink=30,
        left_sigma=max(150, mass.rx*0.74),
        right_sigma=max(110, mass.rx*0.62),
        contact_ridge=0, foreground_opacity=0.35, sediment_count=170,
    )

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}">',
        '<defs>',
        _DEFS,
        f'<clipPath id="clip-mass"><path d="{mp}"/></clipPath>',
        '<radialGradient id="body-main" cx="0.42" cy="0.40" r="0.58">',
        f'  <stop offset="0"   stop-color="{PALETTE["body"]}" stop-opacity=".94"/>',
        '  <stop offset=".52" stop-color="#0C1620"            stop-opacity=".88"/>',
        '  <stop offset="1"   stop-color="#040608"            stop-opacity=".12"/>',
        '</radialGradient>',
        '<radialGradient id="body-warm" cx="0.76" cy="0.28" r="0.44">',
        f'  <stop offset="0" stop-color="{PALETTE["warm"]}" stop-opacity=".24"/>',
        '  <stop offset="1" stop-color="#040608"             stop-opacity="0"/>',
        '</radialGradient>',
        *physical_defs(),
        '</defs>',
        f'<rect width="1080" height="1260" fill="{PALETTE["bg"]}"/>',
        '<g id="lt-artwork">',

        # layer order (back → front):
        # 1 temporal sediment floors
        *_temporal(seed),
        # 2 vortex rings — сразу после фона, видны везде
        *_vortex_rings(seed, mass),
        # 3 standing waves
        *_standing_waves(seed, mass),
        # 4 affine shadow
        *_affine_shadow(seed, mass),
        # 5 light cone
        *_light_cone(seed, mass),
        # 6 void mist
        *_mist(seed),
        # 7 burial backdrop (sediment за телом)
        *burial_backdrop_svg(seed, cfg),
        # 8 smoky body
        '<g id="lt-smoky-mass">',
        f'<path d="{mp}" fill="#162030" fill-opacity="0.72" filter="url(#glow-mass)"/>',
        f'<path d="{mp}" fill="url(#body-main)" fill-opacity="0.90" filter="url(#smoke-body)"/>',
        f'<path d="{mp}" fill="url(#body-warm)" fill-opacity="0.40"/>',
        '</g>',
        # 9 internal organs (clipped)
        '<g id="lt-internal-organs" clip-path="url(#clip-mass)">',
    ]

    ro = random.Random(seed_int(seed, "lt-organs-v40"))
    organ_defs = [
        ("#2E5A8A", 0.44), ("#1E4A72", 0.36), ("#4A3F8A", 0.40),
        ("#165A48", 0.34), ("#0A1828", 0.28), ("#3A3278", 0.32), ("#1A4868", 0.38),
    ]
    for i in range(7):
        om  = MassSpec(
            mass.cx + ro.uniform(-0.46, 0.46)*mass.rx,
            mass.cy + ro.uniform(-0.50, 0.50)*mass.ry,
            mass.rx * ro.uniform(0.09, 0.31),
            mass.ry * ro.uniform(0.07, 0.23),
            16, f"lt-org-{i}",
        )
        col, op = organ_defs[i % len(organ_defs)]
        op += ro.uniform(-0.04, 0.06)
        flt = "organ-glow" if i % 2 == 0 else "organ-soft"
        lines.append(f'<path d="{_blob(seed, om, om.salt, rough=0.50)}" '
                     f'fill="{col}" fill-opacity="{max(0.18, op):.2f}" filter="url(#{flt})"/>')

    lines += [
        '</g>',
        # 10 Lyapunov roots — ДО foreground, иначе накрываются sediment
        *_lyapunov_roots(seed, mass),
        # 11 graphite dust
        *_dust(seed),
        # 12 burial foreground
        *burial_foreground_svg(seed, cfg),
        *tactile_void_svg(seed, 1080, 1080, 0.34, 800),
        '</g>',
        # footer
        '<g id="lt-footer">',
        f'<rect y="1080" width="1080" height="180" fill="{PALETTE["bg"]}"/>',
        '<line x1="84" x2="996" y1="1100" y2="1100" stroke="#737986" stroke-opacity=".16"/>',
        f'<text x="540" y="1152" text-anchor="middle" fill="#B0B0AC" '
        f'font-family="Arial,sans-serif" font-size="24" letter-spacing="6" font-weight="400">'
        f'{track_name.upper()}</text>',
        f'<text x="540" y="1192" text-anchor="middle" fill="#505058" '
        f'font-family="Arial,sans-serif" font-size="10" letter-spacing="3">'
        f'd2_blues_last_train · seed {seed[:14]}</text>',
        '</g>',
        '</svg>',
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


# ── metadata & I/O ────────────────────────────────────────────────────────────

def build_metadata(seed: str, svg_bytes: bytes, track_name: str = "LAST TRAIN BLUES") -> bytes:
    m = _mass_spec(seed)
    return _jbytes({
        "renderer": {"name": "d2_blues_last_train_renderer", "version": RENDERER_VERSION},
        "seed": seed, "track_name": track_name,
        "mass_geometry": {"cx": m.cx, "cy": m.cy, "rx": m.rx, "ry": m.ry},
        "canonical_outputs": {"svg_sha256": sha256p(svg_bytes)},
    })


def write_outputs(seed: str, svg_path: str, metadata_path: str,
                  track_name: str = "LAST TRAIN BLUES"):
    svg = render_svg(seed, track_name)
    for p in (svg_path, metadata_path):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(svg_path).write_bytes(svg)
    Path(metadata_path).write_bytes(build_metadata(seed, svg, track_name))
    return svg_path, metadata_path


def _parse_args():
    p = argparse.ArgumentParser(description="D2 Blues Last Train poster renderer v4.1")
    p.add_argument("--seed",             default="d2-last-train-v1")
    p.add_argument("--track-name",       default="LAST TRAIN BLUES")
    p.add_argument("--svg-output",       default="artifacts/d2/posters/d2_blues_last_train.svg")
    p.add_argument("--metadata-output",  default="artifacts/d2/posters/d2_blues_last_train.metadata.json")
    return p.parse_args()


def main() -> int:
    a = _parse_args()
    write_outputs(a.seed, a.svg_output, a.metadata_output, track_name=a.track_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
