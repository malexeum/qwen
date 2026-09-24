"""
D2 Blues Poster Renderer — v1.7 Lyapunov Painfall
Two-Body Blues: spectral embrace inside a waterfall of pain.
Lyapunov fractal threads + graphite grain + syncopated rhythm pulses.
"""
import sys, os, math, random, hashlib, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RENDERER_VERSION = "1.7"

W, H = 1000, 1400
SEED = 42

# ── палитра ──────────────────────────────────────────────────────────────────
BG          = "#0a0908"
BODY_A      = "#1a3a5c"   # большое тело — тёмно-синее
BODY_B      = "#4a2010"   # малое тело  — тёмно-коричневое
ORGAN_A     = "#0d2440"
ORGAN_B     = "#2e1208"
TENDON_A    = "#1e4870"
TENDON_B    = "#5a2a14"
FLOW_WARM   = "#3d1f08"
FLOW_COOL   = "#0c2035"
BLUE_NOTE   = "#5B4FA8"
COFFIN      = "#060504"
SEDIMENT    = "#0e0c0b"
WATERFALL   = "#112030"
GRAPHITE    = "#2a2520"


def rng(seed):
    r = random.Random(seed)
    return r


def lyapunov_value(x, sequence="AB", iterations=100):
    """Вычисляет показатель Ляпунова для логистического отображения."""
    lyap = 0.0
    r_a, r_b = 3.7, 3.9
    for i in range(iterations):
        r = r_a if sequence[i % len(sequence)] == 'A' else r_b
        x = r * x * (1 - x)
        if abs(x * (1 - x)) < 1e-10:
            break
        lyap += math.log(abs(r * (1 - 2 * x)) + 1e-10)
    return lyap / iterations


def blob_path(cx, cy, rx, ry, n_pts, seed, squeeze_bottom=0.0):
    """Генерирует органическую форму без рваных краёв."""
    r = rng(seed)
    pts = []
    for i in range(n_pts):
        angle = 2 * math.pi * i / n_pts
        # Ляпуновская модуляция радиуса — живая, но не рваная
        x0 = 0.5 + 0.3 * math.cos(angle)
        lyap = lyapunov_value(max(0.01, min(0.99, x0)), "AABB", 60)
        # нормируем в [-1, 1]
        modulation = max(-0.18, min(0.18, lyap * 0.06))
        base_r = 0.85 + 0.15 * math.sin(angle * 2.3 + r.uniform(0, math.pi))
        rad_x = rx * (base_r + modulation) * (1 + r.gauss(0, 0.03))
        rad_y = ry * (base_r + modulation * 0.7) * (1 + r.gauss(0, 0.03))
        # сдавливаем низ для ощущения веса
        if squeeze_bottom > 0 and math.sin(angle) > 0:
            rad_y *= (1 - squeeze_bottom * math.sin(angle) * 0.4)
        pts.append((cx + rad_x * math.cos(angle),
                    cy + rad_y * math.sin(angle)))
    # сглаженный path
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(n_pts):
        p1 = pts[i]
        p2 = pts[(i + 1) % n_pts]
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        d += f"Q {p1[0]:.1f},{p1[1]:.1f} {mx:.1f},{my:.1f} "
    d += "Z"
    return d


def lyapunov_thread(x_start, y_top, y_bottom, cx_drift, seed, sequence="AABB"):
    """Вертикальная нить водопада, модулированная показателем Ляпунова."""
    r = rng(seed)
    pts = []
    x = 0.3 + 0.4 * r.random()
    n_steps = 40
    for i in range(n_steps):
        t = i / (n_steps - 1)
        y = y_top + (y_bottom - y_top) * t
        lyap = lyapunov_value(x, sequence, 30)
        x = max(0.01, min(0.99, x + 0.02 * (1 if lyap > -0.5 else -1)))
        drift = cx_drift + lyap * 8 + r.gauss(0, 3)
        px = x_start + drift * math.sin(t * math.pi * 2.7) + r.gauss(0, 2)
        pts.append((px, y))
        # разрыв нити при неустойчивости
        if lyap < -1.2 and r.random() < 0.4:
            break
    return pts


def render_svg(seed=SEED):
    r = rng(seed)

    # ── геометрия тел ────────────────────────────────────────────────────────
    # большое тело — левее и выше
    ax, ay = W * 0.36, H * 0.33
    arx, ary = 195, 220
    # малое тело — правее, ниже, вытянуто вертикально
    scale = r.uniform(1.55, 2.4)
    bx = ax + arx * 0.85
    by = ay + ary * 0.15
    brx = int(arx / math.sqrt(scale))
    bry = int(ary / math.sqrt(scale) * 1.15)

    blob_a = blob_path(ax, ay, arx, ary, 32, seed + 1, squeeze_bottom=0.3)
    blob_b = blob_path(bx, by, brx, bry, 28, seed + 2, squeeze_bottom=0.2)

    # afterimage — запоздавший след тела A
    ghost_dx = r.uniform(-18, -8)
    ghost_dy = r.uniform(-12, 6)
    blob_a_ghost = blob_path(ax + ghost_dx, ay + ghost_dy, arx, ary, 32, seed + 10, squeeze_bottom=0.25)

    # ── органы и полости ─────────────────────────────────────────────────────
    organs_a = []
    for i in range(6):
        ox = ax + r.uniform(-arx * 0.55, arx * 0.45)
        oy = ay + r.uniform(-ary * 0.5, ary * 0.55)
        orx = r.uniform(18, 55)
        ory = r.uniform(14, 42)
        organs_a.append(blob_path(ox, oy, orx, ory, 16, seed + 20 + i))

    # полости тела A
    cavities_a = []
    for i in range(2):
        ox = ax + r.uniform(-arx * 0.3, arx * 0.25)
        oy = ay + r.uniform(-ary * 0.3, ary * 0.35)
        cavities_a.append(blob_path(ox, oy, r.uniform(10, 25), r.uniform(8, 18), 12, seed + 30 + i))

    organs_b = []
    for i in range(4):
        ox = bx + r.uniform(-brx * 0.5, brx * 0.45)
        oy = by + r.uniform(-bry * 0.5, bry * 0.5)
        orx = r.uniform(12, 35)
        ory = r.uniform(10, 28)
        organs_b.append(blob_path(ox, oy, orx, ory, 14, seed + 40 + i))

    # сухожилия — вытянутые вниз
    tendons_a = []
    for i in range(3):
        tx = ax + r.uniform(-arx * 0.4, arx * 0.3)
        ty = ay + r.uniform(0, ary * 0.5)
        tendons_a.append(blob_path(tx, ty, r.uniform(5, 12), r.uniform(28, 55), 10, seed + 50 + i))

    # ── водопад Ляпунова ─────────────────────────────────────────────────────
    waterfall_threads = []
    n_threads = 16
    for i in range(n_threads):
        x_start = W * 0.08 + W * 0.84 * i / (n_threads - 1) + r.gauss(0, 12)
        y_top = r.uniform(-H * 0.05, H * 0.02)
        y_bottom = H * r.uniform(0.68, 0.82)
        seq = r.choice(["AABB", "ABAB", "AAAB", "ABBB"])
        thread_pts = lyapunov_thread(x_start, y_top, y_bottom, r.uniform(-15, 15), seed + 100 + i, seq)
        waterfall_threads.append(thread_pts)

    # ── синкопированные ритм-пульсы (слабая доля) ────────────────────────────
    rhythm_pulses = []
    # 8 горизонтальных импульсов, сдвинутых от метра
    for i in range(8):
        # слабая доля — между основными вертикальными позициями
        y = H * (0.15 + 0.07 * i) + r.gauss(0, 8)
        x1 = r.uniform(W * 0.05, W * 0.2)
        x2 = r.uniform(W * 0.75, W * 0.95)
        opacity = r.uniform(0.03, 0.07)
        rhythm_pulses.append((x1, y, x2, y, opacity))

    # ── контактные потоки через щель ────────────────────────────────────────
    # притяжение
    attract_x1, attract_y1 = ax + arx * 0.7, ay - ary * 0.1
    attract_x2, attract_y2 = bx - brx * 0.75, by - bry * 0.1
    # отталкивание
    repel_x1, repel_y1 = ax + arx * 0.65, ay + ary * 0.2
    repel_x2, repel_y2 = bx - brx * 0.7, by + bry * 0.15
    # оборванная фраза
    broken_x1, broken_y1 = ax + arx * 0.6, ay + ary * 0.4
    broken_xm = (broken_x1 + (bx - brx * 0.6)) * 0.45  # не доходит

    # дополнительные арки обмена
    extra_arcs = []
    for i in range(4):
        ex1 = ax + arx * r.uniform(0.55, 0.78)
        ey1 = ay + ary * r.uniform(-0.35, 0.45)
        ex2 = bx - brx * r.uniform(0.55, 0.78)
        ey2 = by + bry * r.uniform(-0.35, 0.35)
        completed = r.random() > 0.35  # часть обрывается
        extra_arcs.append((ex1, ey1, ex2, ey2, completed))

    # ── геометрия гроба времени ─────────────────────────────────────────────
    coffin_y = H * 0.72
    coffin_x1, coffin_x2 = W * 0.08, W * 0.92
    coffin_top_inset = W * 0.07

    # ── blue note — геометрическая красивая ошибка ──────────────────────────
    bn_x1 = ax + arx * 0.45
    bn_y1 = ay + ary * 0.18
    bn_cx = (bx + bn_x1) / 2
    bn_cy = bn_y1 - 35  # дуга идёт вверх
    bn_break_x = bn_cx + r.uniform(8, 22)  # точка провисания
    bn_break_y = bn_cy + r.uniform(14, 28)  # проседает

    # ── запоздавшие объятия (embrace arcs) ──────────────────────────────────
    embrace_arcs = []
    for i in range(5):
        t = (i + 1) / 6
        ex = ax + (bx - ax) * t
        ey = ay + (by - ay) * t + r.gauss(0, 20)
        delay = r.uniform(8, 25)  # смещение для lag-эффекта
        embrace_arcs.append((ex, ey, delay))

    # ── остаточные следы тактов ──────────────────────────────────────────────
    afterbeat_traces = []
    for i in range(3):
        tx = r.uniform(W * 0.55, W * 0.75)
        ty = r.uniform(H * 0.42, H * 0.62)
        length = r.uniform(80, 180)
        angle = r.uniform(-0.2, 0.15)
        afterbeat_traces.append((tx, ty, length, angle, r.uniform(0.02, 0.04)))

    # ── графитовый шум (следы карандаша) ────────────────────────────────────
    graphite_strokes = []
    for i in range(120):
        gx = r.uniform(W * 0.03, W * 0.97)
        gy = r.uniform(H * 0.02, H * 0.88)
        length = r.uniform(4, 28)
        angle = r.uniform(75, 95) * math.pi / 180  # почти вертикально
        gx2 = gx + length * math.cos(angle)
        gy2 = gy + length * math.sin(angle)
        opacity = r.uniform(0.025, 0.065)
        graphite_strokes.append((gx, gy, gx2, gy2, opacity))

    # ═══════════════════════════════════════════════════════════════════════
    # SVG
    # ═══════════════════════════════════════════════════════════════════════
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')

    # ── фильтры ──────────────────────────────────────────────────────────────
    lines.append('<defs>')

    # внешний glow тела A
    lines.append('''
  <filter id="glow-a" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="72" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>''')

    # внешний glow тела B
    lines.append('''
  <filter id="glow-b" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="65" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>''')

    # органы — средний blur
    lines.append('''
  <filter id="organ-blur">
    <feGaussianBlur stdDeviation="9"/>
  </filter>''')

    # водопад — лёгкий blur
    lines.append('''
  <filter id="waterfall-blur">
    <feGaussianBlur stdDeviation="3.5"/>
  </filter>''')

    # ghost след
    lines.append('''
  <filter id="ghost-blur">
    <feGaussianBlur stdDeviation="22"/>
  </filter>''')

    # слабые потоки
    lines.append('''
  <filter id="flow-blur">
    <feGaussianBlur stdDeviation="5"/>
  </filter>''')

    # grain
    lines.append('''
  <filter id="grain">
    <feTurbulence type="fractalNoise" baseFrequency="0.72" numOctaves="4" stitchTiles="stitch" result="noise"/>
    <feColorMatrix type="saturate" values="0" in="noise" result="gray"/>
    <feBlend in="SourceGraphic" in2="gray" mode="overlay" result="blend"/>
    <feComposite in="blend" in2="SourceGraphic" operator="in"/>
  </filter>''')

    # clipPath тела A
    lines.append(f'  <clipPath id="clip-a"><path d="{blob_a}"/></clipPath>')
    # clipPath тела B
    lines.append(f'  <clipPath id="clip-b"><path d="{blob_b}"/></clipPath>')

    lines.append('</defs>')

    # ── фон ──────────────────────────────────────────────────────────────────
    lines.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # ── гроб времени (скрытая геометрия) ────────────────────────────────────
    lines.append('<g id="d2-coffin-gravity" opacity="0.85">')
    lines.append(f'  <path d="M {coffin_x1+coffin_top_inset},{coffin_y} '
                 f'L {coffin_x1},{coffin_y+H*0.18} '
                 f'L {coffin_x2},{coffin_y+H*0.18} '
                 f'L {coffin_x2-coffin_top_inset},{coffin_y} Z" '
                 f'fill="{COFFIN}" opacity="0.92"/>')
    # видимы только два угла
    lines.append(f'  <line x1="{coffin_x1+coffin_top_inset}" y1="{coffin_y}" '
                 f'x2="{coffin_x1+coffin_top_inset+30}" y2="{coffin_y}" '
                 f'stroke="{SEDIMENT}" stroke-width="1" opacity="0.3"/>')
    lines.append(f'  <line x1="{coffin_x2-coffin_top_inset-30}" y1="{coffin_y}" '
                 f'x2="{coffin_x2-coffin_top_inset}" y2="{coffin_y}" '
                 f'stroke="{SEDIMENT}" stroke-width="1" opacity="0.3"/>')
    lines.append('</g>')

    # ── нижний осадок (foreground sediment) ─────────────────────────────────
    lines.append('<g id="d2-sediment">')
    for i in range(5):
        sy = H * (0.82 + i * 0.028)
        amp = 12 + i * 4
        lines.append(f'  <path d="M 0,{sy:.0f} '
                     f'Q {W*0.25:.0f},{sy-amp:.0f} {W*0.5:.0f},{sy:.0f} '
                     f'Q {W*0.75:.0f},{sy+amp:.0f} {W:.0f},{sy:.0f} '
                     f'L {W},{H} L 0,{H} Z" '
                     f'fill="{SEDIMENT}" opacity="{0.45 + i*0.1:.2f}"/>')
    lines.append('</g>')

    # ── водопад Ляпунова ─────────────────────────────────────────────────────
    lines.append('<g id="d2-pain-waterfall" filter="url(#waterfall-blur)">')
    for i, thread in enumerate(waterfall_threads):
        if len(thread) < 2:
            continue
        opacity = 0.06 + 0.06 * (i % 3)
        color = WATERFALL if i % 2 == 0 else FLOW_WARM
        d = f"M {thread[0][0]:.1f},{thread[0][1]:.1f} "
        for pt in thread[1:]:
            d += f"L {pt[0]:.1f},{pt[1]:.1f} "
        lines.append(f'  <path d="{d}" stroke="{color}" stroke-width="1.2" '
                     f'fill="none" opacity="{opacity:.3f}"/>')
    lines.append('</g>')

    # ── синкопированные ритм-пульсы (слабая доля) ────────────────────────────
    lines.append('<g id="d2-syncopated-rhythm">')
    for x1, y1, x2, y2, op in rhythm_pulses:
        lines.append(f'  <line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                     f'stroke="{FLOW_COOL}" stroke-width="0.8" opacity="{op:.3f}"/>')
    lines.append('</g>')

    # ── afterimage тела A ────────────────────────────────────────────────────
    lines.append('<g id="d2-afterimages">')
    lines.append(f'  <path d="{blob_a_ghost}" fill="{BODY_A}" opacity="0.06" '
                 f'filter="url(#ghost-blur)"/>')
    lines.append('</g>')

    # ── тело A (большое, синее) ──────────────────────────────────────────────
    lines.append('<g id="d2-body-heavy">')
    lines.append(f'  <path d="{blob_a}" fill="{BODY_A}" opacity="0.82" '
                 f'filter="url(#glow-a)"/>')
    lines.append('</g>')

    # органы и полости тела A (внутри clipPath)
    lines.append('<g id="d2-organs-heavy" clip-path="url(#clip-a)" filter="url(#organ-blur)">')
    for i, org in enumerate(organs_a):
        op = 0.28 + 0.12 * (i % 3)
        lines.append(f'  <path d="{org}" fill="{ORGAN_A}" opacity="{op:.2f}"/>')
    for cav in cavities_a:
        lines.append(f'  <path d="{cav}" fill="{BG}" opacity="0.35"/>')
    for ten in tendons_a:
        # сухожилия вытянуты вниз
        lines.append(f'  <path d="{ten}" fill="{TENDON_A}" opacity="0.22"/>')
    lines.append('</g>')

    # ── тело B (малое, коричневое) ───────────────────────────────────────────
    lines.append('<g id="d2-body-answer">')
    lines.append(f'  <path d="{blob_b}" fill="{BODY_B}" opacity="0.78" '
                 f'filter="url(#glow-b)"/>')
    lines.append('</g>')

    # органы тела B
    lines.append('<g id="d2-organs-answer" clip-path="url(#clip-b)" filter="url(#organ-blur)">')
    for i, org in enumerate(organs_b):
        op = 0.25 + 0.1 * (i % 3)
        lines.append(f'  <path d="{org}" fill="{ORGAN_B}" opacity="{op:.2f}"/>')
    lines.append('</g>')

    # ── контактные потоки ────────────────────────────────────────────────────
    lines.append('<g id="d2-contact-flows" filter="url(#flow-blur)">')
    # притяжение
    cy_a = (attract_y1 + attract_y2) / 2 - 30
    lines.append(f'  <path d="M {attract_x1:.0f},{attract_y1:.0f} '
                 f'Q {(attract_x1+attract_x2)/2:.0f},{cy_a:.0f} '
                 f'{attract_x2:.0f},{attract_y2:.0f}" '
                 f'stroke="{FLOW_WARM}" stroke-width="2.5" fill="none" opacity="0.18"/>')
    # отталкивание
    cy_r = (repel_y1 + repel_y2) / 2 + 40
    lines.append(f'  <path d="M {repel_x1:.0f},{repel_y1:.0f} '
                 f'Q {(repel_x1+repel_x2)/2:.0f},{cy_r:.0f} '
                 f'{repel_x2:.0f},{repel_y2:.0f}" '
                 f'stroke="{FLOW_COOL}" stroke-width="1.5" fill="none" opacity="0.14"/>')
    # оборванная фраза
    lines.append(f'  <path d="M {broken_x1:.0f},{broken_y1:.0f} '
                 f'Q {broken_xm:.0f},{broken_y1-20:.0f} '
                 f'{broken_xm+15:.0f},{broken_y1+10:.0f}" '
                 f'stroke="{FLOW_WARM}" stroke-width="1.2" fill="none" opacity="0.10"/>')
    # дополнительные арки
    for ex1, ey1, ex2, ey2, completed in extra_arcs:
        cy_e = (ey1 + ey2) / 2 + r.uniform(-30, 30)
        if completed:
            lines.append(f'  <path d="M {ex1:.0f},{ey1:.0f} '
                         f'Q {(ex1+ex2)/2:.0f},{cy_e:.0f} '
                         f'{ex2:.0f},{ey2:.0f}" '
                         f'stroke="{FLOW_WARM}" stroke-width="1" fill="none" opacity="0.09"/>')
        else:
            xm = (ex1 + ex2) * 0.4
            lines.append(f'  <path d="M {ex1:.0f},{ey1:.0f} '
                         f'Q {xm:.0f},{cy_e:.0f} '
                         f'{xm+10:.0f},{(ey1+cy_e)/2:.0f}" '
                         f'stroke="{FLOW_COOL}" stroke-width="0.8" fill="none" opacity="0.07"/>')
    lines.append('</g>')

    # ── запоздавшие объятия ──────────────────────────────────────────────────
    lines.append('<g id="d2-embrace-arcs" filter="url(#ghost-blur)">')
    for i, (ex, ey, delay) in enumerate(embrace_arcs):
        lines.append(f'  <circle cx="{ex:.0f}" cy="{ey:.0f}" r="{delay:.0f}" '
                     f'fill="none" stroke="{BODY_A}" stroke-width="0.8" opacity="0.05"/>')
    lines.append('</g>')

    # ── blue note — красивая ошибка ──────────────────────────────────────────
    lines.append('<g id="d2-beautiful-error">')
    # правильная часть дуги
    lines.append(f'  <path d="M {bn_x1:.0f},{bn_y1:.0f} Q {bn_cx-20:.0f},{bn_cy:.0f} {bn_cx:.0f},{bn_cy:.0f}" '
                 f'stroke="{BLUE_NOTE}" stroke-width="1.5" fill="none" opacity="0.18"/>')
    # провисающая часть — красивая ошибка
    lines.append(f'  <path d="M {bn_cx:.0f},{bn_cy:.0f} Q {bn_break_x:.0f},{bn_break_y:.0f} '
                 f'{bn_cx+40:.0f},{bn_cy+5:.0f}" '
                 f'stroke="{BLUE_NOTE}" stroke-width="1.5" fill="none" opacity="0.22"/>')
    # blue note как тёплое нарушение внутри тела A
    lines.append(f'  <ellipse cx="{ax - arx*0.15:.0f}" cy="{ay + ary*0.1:.0f}" '
                 f'rx="38" ry="28" fill="{BLUE_NOTE}" opacity="0.07" '
                 f'clip-path="url(#clip-a)"/>')
    lines.append('</g>')

    # ── остаточные следы тактов ──────────────────────────────────────────────
    lines.append('<g id="d2-afterbeat-traces">')
    for tx, ty, length, angle, op in afterbeat_traces:
        ex = tx + length * math.cos(angle)
        ey = ty + length * math.sin(angle) * 0.3
        lines.append(f'  <line x1="{tx:.0f}" y1="{ty:.0f}" x2="{ex:.0f}" y2="{ey:.0f}" '
                     f'stroke="{FLOW_COOL}" stroke-width="0.7" opacity="{op:.3f}"/>')
    lines.append('</g>')

    # ── графитовый шум ───────────────────────────────────────────────────────
    lines.append('<g id="d2-graphite-grain">')
    for gx1, gy1, gx2, gy2, op in graphite_strokes:
        lines.append(f'  <line x1="{gx1:.0f}" y1="{gy1:.0f}" x2="{gx2:.0f}" y2="{gy2:.0f}" '
                     f'stroke="{GRAPHITE}" stroke-width="0.6" opacity="{op:.3f}"/>')
    lines.append('</g>')

    # ── footer ────────────────────────────────────────────────────────────────
    footer_y = H * 0.928
    lines.append(f'<line x1="{W*0.07:.0f}" y1="{footer_y:.0f}" '
                 f'x2="{W*0.93:.0f}" y2="{footer_y:.0f}" '
                 f'stroke="#2a2825" stroke-width="0.5"/>')

    lines.append('<g id="d2-footer" font-family="\'Courier New\', monospace" fill="#3a3835">')
    lines.append(f'  <text x="{W//2}" y="{H*0.948:.0f}" '
                 f'text-anchor="middle" font-size="22" letter-spacing="8" font-weight="300">'
                 f'TWO-BODY BLUES</text>')
    lines.append(f'  <text x="{W//2}" y="{H*0.963:.0f}" '
                 f'text-anchor="middle" font-size="10" letter-spacing="5" opacity="0.7">'
                 f'DENSITY · COUNTERFLOW · UNRESOLVED CONTACT</text>')
    lines.append(f'  <text x="{W//2}" y="{H*0.975:.0f}" '
                 f'text-anchor="middle" font-size="9" letter-spacing="3" opacity="0.5">'
                 f'CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM</text>')
    lines.append('</g>')

    lines.append('</svg>')
    return "\n".join(lines)


def build_metadata(seed=SEED, svg_sha=""):
    return {
        "renderer": "render_d2_blues_poster",
        "version": RENDERER_VERSION,
        "seed": seed,
        "canvas": {"width": W, "height": H},
        "pole": "painfall_embrace",
        "layers": [
            "d2-coffin-gravity",
            "d2-sediment",
            "d2-pain-waterfall",
            "d2-syncopated-rhythm",
            "d2-afterimages",
            "d2-body-heavy",
            "d2-organs-heavy",
            "d2-body-answer",
            "d2-organs-answer",
            "d2-contact-flows",
            "d2-embrace-arcs",
            "d2-beautiful-error",
            "d2-afterbeat-traces",
            "d2-graphite-grain",
            "d2-footer",
        ],
        "blue_note": {"color": BLUE_NOTE, "type": "geometric_error"},
        "svg_sha256": svg_sha,
    }


def sha256_prefixed(content: str) -> str:
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


def write_outputs(svg_path: Path, meta_path: Path):
    svg_content = render_svg(SEED)
    svg_sha = sha256_prefixed(svg_content)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")
    meta = build_metadata(SEED, svg_sha)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return svg_sha


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="D2 Blues Poster Renderer v1.7")
    parser.add_argument("--svg-output",  default="artifacts/d2/posters/d2_blues_v1_poster.svg")
    parser.add_argument("--metadata-output", default="artifacts/d2/posters/d2_blues_v1_poster.metadata.json")
    args = parser.parse_args()

    svg_path  = Path(args.svg_output)
    meta_path = Path(args.metadata_output)
    sha = write_outputs(svg_path, meta_path)
    print(f"[D2 v{RENDERER_VERSION}] SVG  → {svg_path}")
    print(f"[D2 v{RENDERER_VERSION}] META → {meta_path}")
    print(f"[D2 v{RENDERER_VERSION}] SHA  → {sha[:32]}…")