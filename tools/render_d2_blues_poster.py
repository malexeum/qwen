"""
TWO-BODY BLUES — render_d2_blues_poster.py  v1.4
Asymmetric smoky density fields, inner organs,
geometric contact seam, attraction/repulsion exchange,
blue-note phrasing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from blues_d2_physical_layers import (
    BurialConfig,
    burial_backdrop_svg,
    burial_foreground_svg,
    physical_defs,
    tactile_void_svg,
)

# ── Palette ──────────────────────────────────────────────────────────────────

PALETTE = {
    "bg":         "#05070D",
    "body_a":     "#1A3A6C",   # cold blue
    "body_b":     "#4A2510",   # ember brown
    "glow_a":     "#2255A0",
    "glow_b":     "#7A3A18",
    "organ_a":    "#0D2248",
    "organ_b":    "#2E1508",
    "void_a":     "#0B1830",
    "void_b":     "#1A0A04",
    "blue_note":  "#5B5FA8",   # the dissonant note
    "seam":       "#08080E",
    "attract":    "#344068",
    "repulse":    "#6B3A24",
    "text":       "#C8CCDA",
    "muted":      "#555870",
    "footer_line":"#1C1E2A",
}

W, H_ART, H_FOOTER = 1080, 1080, 180
H_TOTAL = H_ART + H_FOOTER
RENDERER_VERSION = "1.4"
DEFAULT_TRACK_NAME = "TWO-BODY BLUES"


# ── Deterministic seed helpers ────────────────────────────────────────────────

def _rng(seed: int, salt: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}{salt}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# ── Blob path (smooth density field boundary) ─────────────────────────────────

def _blob_path(
    cx: float, cy: float,
    rx: float, ry: float,
    wobble_amp: float,
    wobble_freq: int,
    wobble_phase: float,
    rng: random.Random,
    steps: int = 120,
) -> str:
    pts: list[tuple[float, float]] = []
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        # low-frequency density deformation — not a shape edge
        r_base = (rx * abs(math.cos(angle)) ** 0.78 +
                  ry * abs(math.sin(angle)) ** 0.82)
        r_base = (rx + ry) / 2 + (r_base - (rx + ry) / 2) * 0.6
        wobble = wobble_amp * math.sin(wobble_freq * angle + wobble_phase)
        r = r_base + wobble + rng.gauss(0, wobble_amp * 0.18)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    # smooth cubic bezier
    n = len(pts)
    d = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        cp1x = p1[0] + (p2[0] - p0[0]) / 6
        cp1y = p1[1] + (p2[1] - p0[1]) / 6
        cp2x = p2[0] - (p3[0] - p1[0]) / 6
        cp2y = p2[1] - (p3[1] - p1[1]) / 6
        d.append(f"C {cp1x:.2f},{cp1y:.2f} {cp2x:.2f},{cp2y:.2f} "
                 f"{p2[0]:.2f},{p2[1]:.2f}")
    d.append("Z")
    return " ".join(d)


def _body_material_defs() -> list[str]:
    els = [
        '<filter id="f-body-core" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="12"/></filter>',
        '<filter id="f-body-mass" x="-35%" y="-35%" width="170%" height="170%"><feGaussianBlur stdDeviation="17"/></filter>',
        '<filter id="f-body-edge" x="-45%" y="-45%" width="190%" height="190%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.035 0.052" numOctaves="2" seed="13" result="edge-noise"/>'
        '<feDisplacementMap in="SourceGraphic" in2="edge-noise" scale="14" xChannelSelector="R" yChannelSelector="G" result="broken-edge"/>'
        '<feGaussianBlur in="broken-edge" stdDeviation="6"/></filter>',
        '<filter id="f-body-internal" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="9"/></filter>',
        '<filter id="f-pocket-soft" x="-35%" y="-35%" width="170%" height="170%"><feGaussianBlur stdDeviation="5"/></filter>',
        '<filter id="f-cavity-soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5"/></filter>',
        '<filter id="f-filament-soft" x="-25%" y="-25%" width="150%" height="150%"><feGaussianBlur stdDeviation="1.2"/></filter>',
    ]
    for suffix, color in (("a", PALETTE["body_a"]), ("b", PALETTE["body_b"])):
        for layer, stops in (
                ("core", (("0%", "0.34"), ("52%", "0.20"), ("100%", "0"))),
                ("mass", (("0%", "0.27"), ("48%", "0.16"), ("82%", "0.045"), ("100%", "0"))),
            ("periphery", (("0%", "0.09"), ("54%", "0.035"), ("100%", "0"))),
        ):
            els.append(f'<radialGradient id="g-body-{layer}-{suffix}" cx="46%" cy="44%" r="58%">')
            for offset, opacity in stops:
                els.append(f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{opacity}"/>')
            els.append('</radialGradient>')
        pocket_color = "#4675B7" if suffix == "a" else "#A85B32"
        cavity_color = "#02050B" if suffix == "a" else "#100704"
        filament_color = "#628BC4" if suffix == "a" else "#9B5733"
        for name, color, inner_alpha, mid_alpha in (
             ("pocket", pocket_color, "0.82", "0.48"),
            ("cavity", cavity_color, "0.92", "0.58"),
            ("filament", filament_color, "0.72", "0.30"),
        ):
            els.extend([
                f'<radialGradient id="g-body-{name}-{suffix}" cx="48%" cy="46%" r="56%">',
                f'<stop offset="0%" stop-color="{color}" stop-opacity="{inner_alpha}"/>',
                f'<stop offset="62%" stop-color="{color}" stop-opacity="{mid_alpha}"/>',
                f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>',
                '</radialGradient>',
            ])
    return els


def _body_cloud_layers(
    seed: int, body_id: str, cx: float, cy: float, rx: float, ry: float,
) -> list[str]:
    rng = _rng(seed, f"body-cloud-{body_id}")
    els = [f'<g id="density-body-{body_id}">']

    els.append(f'<g id="body-{body_id}-core">')
    for dx, dy, sx, sy in ((-0.035, 0.02, 0.38, 0.36), (0.08, -0.06, 0.28, 0.31)):
        x, y = cx + rx * dx, cy + ry * dy
        els.append(
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx * sx:.1f}" ry="{ry * sy:.1f}"'
            f' fill="url(#g-body-core-{body_id})" filter="url(#f-body-core)"/>'
        )
    els.append('</g>')

    els.append(f'<g id="body-{body_id}-mass">')
    cloud_count = 8 if body_id == "a" else 5
    for _ in range(cloud_count):
        x = cx + rng.uniform(-0.22, 0.22) * rx
        y = cy + rng.uniform(-0.24, 0.24) * ry
        cloud_rx = rng.uniform(0.28, 0.48) * rx
        cloud_ry = rng.uniform(0.27, 0.44) * ry
        angle = rng.uniform(-35, 35)
        opacity = min(0.94, rng.uniform(0.46, 0.68) * (1.35 if body_id == "b" else 1.0))
        els.append(
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{cloud_rx:.1f}" ry="{cloud_ry:.1f}"'
            f' transform="rotate({angle:.1f},{x:.1f},{y:.1f})"'
            f' fill="url(#g-body-mass-{body_id})" fill-opacity="{opacity:.2f}"'
            ' filter="url(#f-body-mass)"/>'
        )
    els.append('</g>')

    els.append(f'<g id="body-{body_id}-periphery">')
    for _ in range(2):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(0.66, 0.80)
        x = cx + math.cos(angle) * rx * distance
        y = cy + math.sin(angle) * ry * distance
        puff_rx = rng.uniform(0.10, 0.16) * rx
        puff_ry = rng.uniform(0.10, 0.15) * ry
        opacity = rng.uniform(0.28, 0.48)
        els.append(
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{puff_rx:.1f}" ry="{puff_ry:.1f}"'
            f' fill="url(#g-body-periphery-{body_id})" fill-opacity="{opacity:.2f}"'
            ' filter="url(#f-body-edge)"/>'
        )
    els.extend(['</g>', '</g>'])
    return els


def _blob_right_x(cx: float, rx: float, ry: float,
                  wobble_amp: float, wobble_freq: int,
                  wobble_phase: float, y: float, cy: float) -> float:
    """Rightmost x of blob at given y — used for seam calculation."""
    dy = y - cy
    if abs(dy) >= ry:
        return cx
    angle = math.asin(max(-1.0, min(1.0, dy / ry)))
    r = (rx + ry) / 2
    wobble = wobble_amp * math.sin(wobble_freq * angle + wobble_phase)
    return cx + abs(r + wobble) * math.cos(angle)


def _blob_left_x(cx: float, rx: float, ry: float,
                 wobble_amp: float, wobble_freq: int,
                 wobble_phase: float, y: float, cy: float) -> float:
    dy = y - cy
    if abs(dy) >= ry:
        return cx
    angle = math.pi - math.asin(max(-1.0, min(1.0, dy / ry)))
    r = (rx + ry) / 2
    wobble = wobble_amp * math.sin(wobble_freq * angle + wobble_phase)
    return cx - abs(r + wobble) * abs(math.cos(angle))


# ── Inner organs ──────────────────────────────────────────────────────────────

def _body_density_pockets(
    cx: float, cy: float,
    rx: float, ry: float,
    clip_id: str,
    rng: random.Random,
    body_id: str,
) -> tuple[list[str], list[tuple[float, float, float, float, bool]]]:
    count = rng.randint(5, 6) if body_id == "a" else rng.randint(3, 4)
    els = [f'<g id="body-{body_id}-density-pockets">']
    anchors = []
    for index in range(count):
        if body_id == "a":
            ox = cx + rng.uniform(-0.48, 0.48) * rx
            oy = cy + rng.uniform(-0.46, 0.50) * ry
            pocket_rx = rng.uniform(0.12, 0.23) * rx
            pocket_ry = rng.uniform(0.055, 0.12) * ry
            is_dark = index % 3 == 0
            opacity = rng.uniform(0.54, 0.74)
        else:
            ox = cx + rng.uniform(-0.27, 0.27) * rx
            oy = cy + rng.uniform(-0.30, 0.30) * ry
            pocket_rx = rng.uniform(0.19, 0.32) * rx
            pocket_ry = rng.uniform(0.085, 0.16) * ry
            is_dark = index % 2 == 0
            opacity = rng.uniform(0.68, 0.88)
        angle = rng.uniform(-58, 58)
        path = _blob_path(
            ox, oy, pocket_rx, pocket_ry,
            min(pocket_rx, pocket_ry) * rng.uniform(0.18, 0.34),
            rng.randint(2, 4), rng.uniform(0, math.tau), rng, steps=24,
        )
        gradient = f"g-body-cavity-{body_id}" if is_dark else f"g-body-pocket-{body_id}"
        els.append(
            f'<path clip-path="url(#{clip_id})" d="{path}"'
            f' transform="rotate({angle:.1f},{ox:.1f},{oy:.1f})"'
            f' fill="url(#{gradient})" fill-opacity="{opacity:.2f}"'
            ' filter="url(#f-pocket-soft)"/>'
        )
        anchors.append((ox, oy, pocket_rx, pocket_ry, is_dark))
    els.append('</g>')
    return els, anchors


def _body_hollow_cavities(
    cx: float, cy: float, rx: float, ry: float, clip_id: str,
    rng: random.Random, body_id: str,
) -> tuple[list[str], list[tuple[float, float, float, float, bool]]]:
    count = 3 if body_id == "a" else 2
    els = [f'<g id="body-{body_id}-hollow-cavities">']
    anchors = []
    for index in range(count):
        if body_id == "a":
            ox = cx + rng.uniform(-0.42, 0.42) * rx
            oy = cy + rng.uniform(-0.42, 0.48) * ry
            cavity_rx = rng.uniform(0.09, 0.16) * rx
            cavity_ry = rng.uniform(0.08, 0.15) * ry
        else:
            ox = cx + rng.uniform(-0.24, 0.24) * rx
            oy = cy + rng.uniform(-0.24, 0.28) * ry
            cavity_rx = rng.uniform(0.13, 0.21) * rx
            cavity_ry = rng.uniform(0.12, 0.20) * ry
        angle = rng.uniform(-55, 55)
        path = _blob_path(
            ox, oy, cavity_rx, cavity_ry,
            min(cavity_rx, cavity_ry) * rng.uniform(0.24, 0.42),
            rng.randint(2, 5), rng.uniform(0, math.tau), rng, steps=20,
        )
        els.append(
            f'<path clip-path="url(#{clip_id})" d="{path}"'
            f' transform="rotate({angle:.1f},{ox:.1f},{oy:.1f})"'
            f' fill="url(#g-body-cavity-{body_id})"'
            f' fill-opacity="{rng.uniform(0.72, 0.94):.2f}" filter="url(#f-cavity-soft)"/>'
        )
        anchors.append((ox, oy, cavity_rx, cavity_ry, True))
    els.append('</g>')
    return els, anchors


def _body_filament_organs(
    cx: float, cy: float, rx: float, ry: float, clip_id: str,
    rng: random.Random, body_id: str, include_blue_note: bool,
    anchors: list[tuple[float, float, float, float, bool]],
    seam_pts: list[tuple[float, float]],
) -> tuple[list[str], list[tuple[float, float, int]]]:
    count = 3 if body_id == "a" else 2
    els = [f'<g id="body-{body_id}-filament-organs" fill="none" stroke-linecap="round">']
    if len(anchors) < 2:
        els.append('</g>')
        return els, []

    systems = ((0, 2), (1, 3), (4, 5)) if body_id == "a" else ((0, 1), (2, 3))
    seam_side = -1 if body_id == "a" else 1
    central_seam = seam_pts[int(len(seam_pts) * 0.34):max(int(len(seam_pts) * 0.34) + 1, int(len(seam_pts) * 0.66))]
    seam_endpoints = []
    for index, (source_index, target_index) in enumerate(systems[:count]):
        source = anchors[source_index % len(anchors)]
        target = anchors[target_index % len(anchors)]
        if central_seam:
            target_seam = min(central_seam, key=lambda point: abs(point[1] - source[1]))
            target_x = target_seam[0] + seam_side * rng.uniform(8, 16)
            target_y = target_seam[1] + rng.uniform(-5, 5)
        else:
            target_x, target_y = target[0], target[1]
        dx, dy = target_x - source[0], target_y - source[1]
        norm = math.hypot(dx / rx, dy / ry) or 1.0
        ux, uy = (dx / rx) / norm, (dy / ry) / norm
        x1 = source[0] + ux * source[2] * 0.76
        y1 = source[1] + uy * source[3] * 0.76
        if central_seam:
            x2, y2 = target_x, target_y
            seam_endpoints.append((x2, y2, seam_side))
            bend_x = rng.uniform(-0.035, 0.035) * rx
            bend_y = rng.uniform(-0.035, 0.035) * ry
        else:
            x2 = target[0] - ux * target[2] * 0.76
            y2 = target[1] - uy * target[3] * 0.76
            bend_x = rng.uniform(-0.10, 0.10) * rx
            bend_y = rng.uniform(-0.08, 0.08) * ry
        c1x, c1y = x1 + dx * 0.28 + bend_x, y1 + dy * 0.28 + bend_y
        c2x, c2y = x1 + dx * 0.72 - bend_x, y1 + dy * 0.72 - bend_y
        path = f'M {x1:.1f},{y1:.1f} C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {x2:.1f},{y2:.1f}'
        width = rng.uniform(1.15, 1.8) if body_id == "a" else rng.uniform(1.55, 2.2)
        opacity = rng.uniform(0.24, 0.36) if body_id == "a" else rng.uniform(0.30, 0.42)
        stroke = PALETTE["blue_note"] if include_blue_note and index == 0 else f"url(#g-body-filament-{body_id})"
        els.append(
            f'<path clip-path="url(#{clip_id})" d="{path}" stroke="{stroke}"'
            f' stroke-width="{width * 3.0:.2f}" stroke-opacity="0.10" filter="url(#f-body-internal)"/>'
        )
        els.append(
            f'<path clip-path="url(#{clip_id})" d="{path}" stroke="{stroke}"'
            f' stroke-width="{width:.2f}" stroke-opacity="{opacity:.2f}" filter="url(#f-filament-soft)"/>'
        )
        if body_id == "a":
            branch_x = (c1x + c2x) * 0.5
            branch_y = (c1y + c2y) * 0.5
            end_x = branch_x + rng.uniform(-0.10, 0.10) * rx
            end_y = branch_y + rng.uniform(-0.11, 0.11) * ry
            branch = f'M {branch_x:.1f},{branch_y:.1f} Q {branch_x + (end_x - branch_x) * 0.5:.1f},{branch_y + (end_y - branch_y) * 0.35:.1f} {end_x:.1f},{end_y:.1f}'
            els.append(
                f'<path clip-path="url(#{clip_id})" d="{branch}" stroke="{stroke}"'
                f' stroke-width="{width * 0.72:.2f}" stroke-opacity="{opacity * 0.76:.2f}"'
                ' filter="url(#f-filament-soft)"/>'
            )
    els.append('</g>')
    return els, seam_endpoints


def _inner_organs(
    cx: float, cy: float, rx: float, ry: float, clip_id: str,
    rng: random.Random, body_id: str, include_blue_note: bool,
    seam_pts: list[tuple[float, float]],
) -> tuple[list[str], list[tuple[float, float, int]]]:
    pockets, pocket_anchors = _body_density_pockets(cx, cy, rx, ry, clip_id, rng, body_id)
    cavities, cavity_anchors = _body_hollow_cavities(cx, cy, rx, ry, clip_id, rng, body_id)
    filaments, seam_endpoints = _body_filament_organs(
        cx, cy, rx, ry, clip_id, rng, body_id, include_blue_note,
        pocket_anchors + cavity_anchors, seam_pts,
    )
    return [
        *pockets,
        *cavities,
        *filaments,
    ], seam_endpoints


# ── Contact seam ──────────────────────────────────────────────────────────────

def _contact_seam(
    ax: float, ay: float, arx: float, ary: float,
    aw_amp: float, aw_freq: int, aw_phase: float,
    bx: float, by: float, brx: float, bry: float,
    bw_amp: float, bw_freq: int, bw_phase: float,
    rng: random.Random,
) -> tuple[list[str], list[tuple[float, float]]]:
    """
    Compute seam as midline between the two blobs where they are closest.
    Returns SVG elements + list of (x, y) seam points.
    """
    step = 6
    seam_pts: list[tuple[float, float]] = []
    threshold = max(arx, brx) * 0.55

    for yi in range(180, H_ART - 80, step):
        y = float(yi)
        rx_a = _blob_right_x(ax, arx, ary, aw_amp, aw_freq, aw_phase, y, ay)
        lx_b = _blob_left_x(bx, brx, bry, bw_amp, bw_freq, bw_phase, y, by)
        gap = lx_b - rx_a
        if 0 <= gap <= threshold:
            seam_pts.append(((rx_a + lx_b) / 2, y))

    if len(seam_pts) < 4:
        return [], seam_pts

    # build smooth path through seam points
    xs = [p[0] + rng.gauss(0, 1.8) for p in seam_pts]
    ys = [p[1] for p in seam_pts]
    d = [f"M {xs[0]:.2f} {ys[0]:.2f}"]
    for i in range(1, len(xs) - 1):
        cpx = (xs[i - 1] + xs[i + 1]) / 2
        d.append(f"C {xs[i-1]:.2f},{ys[i-1]:.2f} {cpx:.2f},{ys[i]:.2f} "
                 f"{xs[i]:.2f},{ys[i]:.2f}")
    d.append(f"L {xs[-1]:.2f} {ys[-1]:.2f}")

    els = [
        '<filter id="f-seam" x="-20%" y="-5%" width="140%" height="110%">',
        '  <feGaussianBlur stdDeviation="1.4"/>',
        '</filter>',
        f'<path id="seam-path" d="{" ".join(d)}"'
        f' fill="none" stroke="{PALETTE["seam"]}"'
        f' stroke-width="1.8" stroke-opacity="0.72"'
        f' stroke-linecap="round" filter="url(#f-seam)"/>',
    ]
    return els, seam_pts


# ── Contact exchange (attraction + repulsion) ─────────────────────────────────

def _body_seam_tendrils(
    seed: int, body_id: str, body_geometry: tuple[float, float, float, float, float, int, float],
    seam_pts: list[tuple[float, float]], clip_id: str,
    filament_endpoints: list[tuple[float, float, int]],
) -> tuple[list[str], list[tuple[float, float, int]]]:
    cx, cy, rx, ry, wobble_amp, wobble_freq, wobble_phase = body_geometry
    rng = _rng(seed, f"body-seam-tendrils-{body_id}")
    side = -1 if body_id == "a" else 1
    if not seam_pts or not filament_endpoints:
        return [f'<g id="body-{body_id}-seam-tendrils"/>'], []

    els = [f'<g id="body-{body_id}-seam-tendrils" fill="none" stroke-linecap="round">']
    sources = []
    for index, (start_x, start_y, source_side) in enumerate(filament_endpoints):
        seam_x, seam_y = min(seam_pts, key=lambda point: abs(point[1] - start_y))
        end_gap = rng.uniform(6, 14) if index == len(filament_endpoints) - 1 else rng.uniform(16, 28)
        end_x = seam_x + source_side * end_gap
        end_y = seam_y + rng.uniform(-5, 5)
        c1x = start_x + (end_x - start_x) * 0.36
        c1y = start_y + rng.uniform(-12, 12)
        c2x = start_x + (end_x - start_x) * 0.78
        c2y = end_y + rng.uniform(-9, 9)
        path = f'M {start_x:.1f},{start_y:.1f} C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {end_x:.1f},{end_y:.1f}'
        color = "#6D8FB8" if body_id == "a" else "#B56C43"
        opacity = rng.uniform(0.24, 0.36)
        width = rng.uniform(1.0, 1.6) if body_id == "a" else rng.uniform(1.3, 1.9)
        els.append(
            f'<path clip-path="url(#{clip_id})" d="{path}" stroke="{color}"'
            f' stroke-width="{width:.2f}" stroke-opacity="{opacity:.2f}"'
            ' filter="url(#f-filament-soft)"/>'
        )
        sources.append((end_x, end_y, source_side))
    els.append('</g>')
    return els, sources


def _contact_exchange(
    seam_pts: list[tuple[float, float]],
    rng: random.Random,
    count: int,
    blue_note: bool,
    seam_sources: list[tuple[float, float, int]],
) -> list[str]:
    if not seam_pts:
        return []
    els = ['<g id="contact-exchange">']
    els += [
        '<filter id="f-exchange" x="-60%" y="-30%" width="220%" height="160%">',
        '  <feGaussianBlur stdDeviation="2.4"/>',
        '</filter>',
    ]
    first_contact = int(len(seam_pts) * 0.32)
    last_contact = max(first_contact + 1, int(len(seam_pts) * 0.68))
    center_index = (first_contact + last_contact) // 2
    center_x, center_y = seam_pts[center_index]
    left_sources = [source for source in seam_sources if source[2] < 0]
    right_sources = [source for source in seam_sources if source[2] > 0]

    def nearest_source(sources: list[tuple[float, float, int]], y: float, side: int) -> tuple[float, float, int]:
        if sources:
            return min(sources, key=lambda source: abs(source[1] - y))
        return center_x + side * 42, y, side

    els.append('<g id="attraction-threads" fill="none" stroke-linecap="round">')
    offsets = (0, -max(1, (last_contact - first_contact) // 12), max(1, (last_contact - first_contact) // 12))
    for index, offset in enumerate(offsets):
        pt_x, pt_y = seam_pts[min(last_contact - 1, max(first_contact, center_index + offset))]
        strength = 0.34 if index == 0 else 0.15
        for side, sources in ((-1, left_sources), (1, right_sources)):
            source_x, source_y, _ = nearest_source(sources, pt_y, side)
            end_x = pt_x + side * rng.uniform(4, 9)
            control_x = (source_x + end_x) * 0.52
            control_y = (source_y + pt_y) * 0.5 + rng.uniform(-9, 9)
            color = PALETTE["blue_note"] if blue_note and index == 0 else PALETTE["attract"]
            els.append(
                f'<path d="M {source_x:.1f},{source_y:.1f} Q {control_x:.1f},{control_y:.1f} {end_x:.1f},{pt_y:.1f}"'
                f' stroke="{color}" stroke-width="{2.6 if index == 0 else 1.7:.1f}"'
                f' stroke-opacity="{strength:.2f}" filter="url(#f-exchange)"/>'
            )
    els.append('</g>')

    els.append('<g id="repulsion-kinks" fill="none" stroke-linecap="round">')
    for offset in (-max(1, (last_contact - first_contact) // 18), max(1, (last_contact - first_contact) // 18)):
        pt_x, pt_y = seam_pts[min(last_contact - 1, max(first_contact, center_index + offset))]
        side = rng.choice((-1, 1))
        end_x = pt_x + side * rng.uniform(18, 30)
        end_y = pt_y + rng.uniform(-24, 24)
        kink_x = pt_x + side * rng.uniform(6, 12)
        kink_y = pt_y + rng.uniform(-6, 6)
        els.append(
            f'<path d="M {pt_x:.1f},{pt_y:.1f} L {kink_x:.1f},{kink_y:.1f} L {end_x:.1f},{end_y:.1f}"'
            f' stroke="{PALETTE["repulse"]}" stroke-width="{rng.uniform(1.5, 2.4):.1f}"'
            f' stroke-opacity="{rng.uniform(0.16, 0.24):.2f}"/>'
        )
    els.append('</g>')

    pt_x, pt_y = seam_pts[center_index]
    els.append('<g id="failed-bridge" fill="none" stroke-linecap="round">')
    for side in (-1, 1):
        source_x, source_y, _ = nearest_source(left_sources if side < 0 else right_sources, pt_y, side)
        start_x = source_x
        stop_x = pt_x + side * rng.uniform(3, 6)
        els.append(
            f'<path d="M {start_x:.1f},{source_y:.1f} Q {pt_x + side * 16:.1f},{pt_y + rng.uniform(-4, 4):.1f} {stop_x:.1f},{pt_y:.1f}"'
            f' stroke="{PALETTE["blue_note"] if blue_note else PALETTE["attract"]}"'
            ' stroke-width="2.4" stroke-opacity="0.30" filter="url(#f-exchange)"/>'
        )
    els.append('</g>')

    if seam_sources:
        source_a = [source for source in seam_sources if source[2] < 0]
        source_b = [source for source in seam_sources if source[2] > 0]
        if source_a and source_b:
            source_left, source_right = min(
                ((left, right) for left in source_a for right in source_b),
                key=lambda pair: abs(pair[0][1] - pair[1][1]),
            )
            bridge_y = (source_left[1] + source_right[1]) * 0.5
            els.append('<g id="internal-contact-bridge" fill="none" stroke-linecap="round">')
            els.append(
                f'<path d="M {source_left[0]:.1f},{source_left[1]:.1f} Q {(source_left[0] + source_right[0]) * 0.5:.1f},{bridge_y + rng.uniform(-4, 4):.1f} {source_right[0]:.1f},{source_right[1]:.1f}"'
                f' stroke="{PALETTE["attract"]}" stroke-width="1.5" stroke-opacity="0.24" filter="url(#f-exchange)"/>'
            )
            els.append('</g>')
    els.append('</g>')
    return els


# ── Glow ──────────────────────────────────────────────────────────────────────

def _glow(cx: float, cy: float, rx: float, ry: float,
          color: str, fid: str) -> list[str]:
    grx, gry = rx * 1.02, ry * 1.02
    return [
        f'<filter id="{fid}" x="-60%" y="-50%" width="220%" height="200%">',
        f'  <feGaussianBlur stdDeviation="{rx * 0.12:.1f}"/>',
        '</filter>',
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{grx:.1f}" ry="{gry:.1f}"'
        f' fill="{color}" fill-opacity="0.025" filter="url(#{fid})"/>',
    ]


def _burial_surface_y(x: float, cfg: BurialConfig) -> float:
    left = cfg.left_sink * math.exp(-((x - cfg.left_x) ** 2) / (2 * cfg.left_sigma**2))
    right = cfg.right_sink * math.exp(-((x - cfg.right_x) ** 2) / (2 * cfg.right_sigma**2))
    ridge = cfg.contact_ridge * math.exp(-((x - cfg.contact_x) ** 2) / (2 * cfg.ridge_sigma**2))
    return cfg.surface_y + left + right - ridge + 5 * math.sin(x / 155 + 0.35) + 2.5 * math.sin(x / 71 - 0.8)


def _subterranean_spectra(cx: float, surface_y: float, rx: float) -> list[str]:
    els = ['<g id="subterranean-spectra">']
    for i, (scale, dy, opacity) in enumerate(((1.20, 24, 0.24), (1.55, 52, 0.17), (1.90, 82, 0.11))):
        els.append(
            f'<ellipse cx="{cx:.1f}" cy="{surface_y + dy:.1f}"'
            f' rx="{rx * scale:.1f}" ry="{rx * 0.18:.1f}"'
            f' fill="url(#g-subterranean)" fill-opacity="{opacity:.2f}"'
            ' filter="url(#f-ground-soft)"/>'
        )
    els.append('</g>')
    return els


def _transmitted_shadow(cx: float, surface_y: float, rx: float) -> list[str]:
    return [
        '<g id="transmitted-shadow">',
        f'<ellipse cx="{cx + rx * 0.12:.1f}" cy="{surface_y + 8:.1f}"'
        f' rx="{rx * 1.02:.1f}" ry="{max(22, rx * 0.085):.1f}"'
        ' fill="url(#g-transmitted-shadow)" fill-opacity="0.86" filter="url(#f-shadow-ground)"/>',
        '</g>',
    ]


def _ground_vortex(cx: float, surface_y: float, rx: float) -> list[str]:
    els = ['<g id="ground-vortex">']
    for scale, opacity in ((1.55, 0.42), (1.22, 0.54), (0.92, 0.64)):
        els.append(
            f'<ellipse cx="{cx:.1f}" cy="{surface_y + 10:.1f}"'
            f' rx="{rx * scale:.1f}" ry="{rx * scale * 0.20:.1f}"'
            f' fill="url(#g-ground-spectrum)" fill-opacity="{opacity:.2f}"'
            ' filter="url(#f-ground-soft)"/>'
        )
    els.append(
        f'<ellipse cx="{cx:.1f}" cy="{surface_y + 12:.1f}"'
        f' rx="{rx * 0.76:.1f}" ry="{rx * 0.15:.1f}"'
        ' fill="url(#g-ground-core)" filter="url(#f-ground-core)"/>'
    )
    els.append('</g>')
    return els


def _phantom_roots(seed: int, bodies: list[tuple[float, float, float, float]],
                   ground_x: float, surface_y: float) -> list[str]:
    rng = _rng(seed, "phantom-roots")
    els = ['<g id="phantom-roots" fill="none" stroke-linecap="round">']
    for cx, cy, rx, ry in bodies:
        for index in range(3):
            spread = index - 1
            sx = cx + spread * rx * 0.25 + rng.uniform(-8, 8)
            sy = cy + ry * rng.uniform(0.76, 0.88)
            ex = ground_x + spread * rx * 0.18 + rng.uniform(-18, 18)
            ey = surface_y + rng.uniform(18, 52)
            c1x, c1y = sx + (ex - sx) * 0.25, sy + (ey - sy) * 0.38
            c2x, c2y = ex + rng.uniform(-28, 28), ey - rng.uniform(12, 32)
            path = (f'M {sx:.1f},{sy:.1f} C {c1x:.1f},{c1y:.1f} '
                    f'{c2x:.1f},{c2y:.1f} {ex:.1f},{ey:.1f}')
            els.append(
                f'<path d="{path}" stroke="#12352E" stroke-width="3.2"'
                ' stroke-opacity="0.075" filter="url(#f-root-soft)"/>'
            )
            els.append(
                f'<path d="{path}" stroke="#31564A" stroke-width="0.9"'
                ' stroke-opacity="0.085"/>'
            )
    els.append('</g>')
    return els


def _right_pressure_field(cx: float, cy: float, rx: float, ry: float) -> list[str]:
    x0 = cx + rx * 0.42
    x1 = min(W - 12, cx + rx * 1.72)
    path = (
        f'M {x0:.1f},{cy - ry * 0.78:.1f} '
        f'C {x0 + rx * 0.55:.1f},{cy - ry * 0.60:.1f} {x1 - rx * 0.12:.1f},{cy - ry * 0.35:.1f} {x1:.1f},{cy:.1f} '
        f'C {x1 - rx * 0.05:.1f},{cy + ry * 0.30:.1f} {x0 + rx * 0.65:.1f},{cy + ry * 0.66:.1f} {x0:.1f},{cy + ry * 0.82:.1f} '
        f'C {x0 + rx * 0.26:.1f},{cy + ry * 0.25:.1f} {x0 + rx * 0.22:.1f},{cy - ry * 0.25:.1f} Z'
    )
    return [
        '<g id="right-pressure-field">',
        f'<path d="{path}" fill="url(#g-right-pressure)" filter="url(#f-right-pressure)"/>',
        '</g>',
    ]


def _graphite_crumbs(seed: int, cx: float, surface_y: float, spread: float) -> list[str]:
    rng = _rng(seed, "graphite-crumbs")
    els = ['<g id="graphite-crumbs">']
    for _ in range(150):
        x = min(W - 16, max(16, rng.gauss(cx, spread * 0.72)))
        y = rng.uniform(surface_y + 14, H_ART - 12)
        if rng.random() < 0.72:
            radius = rng.uniform(0.45, 1.25)
            color = "#59616D" if rng.random() < 0.10 else "#222832"
            opacity = rng.uniform(0.045, 0.12)
            els.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.2f}" fill="{color}" fill-opacity="{opacity:.3f}"/>')
        else:
            length = rng.uniform(1.5, 4.5)
            els.append(
                f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + length:.1f}" y2="{y + rng.uniform(-1, 1):.1f}"'
                f' stroke="#3C424D" stroke-width="0.6" stroke-opacity="{rng.uniform(0.04, 0.10):.3f}"/>'
            )
    els.append('</g>')
    return els


def _sparse_sparks(seed: int, bodies: list[tuple[float, float, float, float]]) -> list[str]:
    rng = _rng(seed, "sparse-sparks")
    els = ['<g id="sparse-sparks">']
    placed = 0
    attempts = 0
    while placed < 10 and attempts < 160:
        attempts += 1
        x = rng.uniform(70, W - 36)
        y = rng.uniform(70, 700)
        if any(((x - cx) / (rx * 1.15)) ** 2 + ((y - cy) / (ry * 1.15)) ** 2 < 1
               for cx, cy, rx, ry in bodies):
            continue
        if ((x - (bodies[0][0] + bodies[1][0]) * 0.5) / 260) ** 2 + ((y - 835) / 120) ** 2 < 1:
            continue
        if rng.random() < 0.65:
            els.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(0.8, 1.35):.2f}"'
                f' fill="#C8CCDA" fill-opacity="{rng.uniform(0.20, 0.36):.3f}"/>'
            )
        else:
            length = rng.uniform(2.5, 5.0)
            els.append(
                f'<path d="M {x:.1f},{y:.1f} l {length:.1f},{-length * 0.55:.1f}"'
                f' stroke="#C8CCDA" stroke-width="0.8" stroke-linecap="round"'
                f' stroke-opacity="{rng.uniform(0.18, 0.30):.3f}"/>'
            )
        placed += 1
    els.append('</g>')
    return els


# ── Main renderer ─────────────────────────────────────────────────────────────

def render(seed: int, out_svg: Path, out_meta: Path,
           track_name: str = DEFAULT_TRACK_NAME) -> None:
    rng_layout = _rng(seed, "layout")
    rng_a = _rng(seed, "body-a")
    rng_b = _rng(seed, "body-b")
    rng_exc = _rng(seed, "exchange")
    rng_void = _rng(seed, "void")

    # ── Body A (left, cold, larger) ──
    scale_a = rng_layout.uniform(0.86, 1.30)
    rx_a = 185 * scale_a
    ry_a = 242 * scale_a
    cx_a = rng_layout.uniform(260, 340)
    cy_a = rng_layout.uniform(390, 460)
    wamp_a = rng_layout.uniform(14, 38)
    wfreq_a = rng_layout.randint(3, 5)
    wphase_a = rng_layout.uniform(0, math.tau)

    # ── Body B (right, warm, smaller) ──
    scale_b = rng_layout.uniform(0.58, 0.96)
    rx_b = 175 * scale_b
    ry_b = 215 * scale_b
    cx_b = rng_layout.uniform(610, 700)
    cy_b = rng_layout.uniform(340, 500)
    wamp_b = rng_layout.uniform(12, 32)
    wfreq_b = rng_layout.randint(3, 6)
    wphase_b = rng_layout.uniform(0, math.tau)

    # blue note: one organ per body + one exchange current
    blue_note_a = rng_layout.random() < 0.55
    blue_note_b = rng_layout.random() < 0.40
    blue_note_exc = rng_layout.random() < 0.50

    organ_count_a = rng_layout.randint(5, 8)
    organ_count_b = rng_layout.randint(4, 7)
    exchange_count = rng_layout.randint(6, 9)

    # clip IDs for organs
    clip_a, clip_b = "clip-body-a", "clip-body-b"

    blob_a = _blob_path(cx_a, cy_a, rx_a, ry_a, wamp_a, wfreq_a, wphase_a, rng_a)
    blob_b = _blob_path(cx_b, cy_b, rx_b, ry_b, wamp_b, wfreq_b, wphase_b, rng_b)

    burial_cfg = BurialConfig(
        width=W,
        art_height=H_ART,
        surface_y=775.0,
        left_x=cx_a,
        right_x=cx_b,
        contact_x=(cx_a + cx_b) / 2,
        left_sink=52.0 * scale_a,
        right_sink=44.0 * scale_b,
        darkness=0.93,
        foreground_opacity=0.38,
        sediment_count=260,
    )

    # ── Seam + exchange ──
    seam_els, seam_pts = _contact_seam(
        cx_a, cy_a, rx_a, ry_a, wamp_a, wfreq_a, wphase_a,
        cx_b, cy_b, rx_b, ry_b, wamp_b, wfreq_b, wphase_b,
        rng_layout,
    )
    inner_organs_a, filament_ends_a = _inner_organs(
        cx_a, cy_a, rx_a, ry_a, clip_a, rng_a, "a", blue_note_a, seam_pts,
    )
    inner_organs_b, filament_ends_b = _inner_organs(
        cx_b, cy_b, rx_b, ry_b, clip_b, rng_b, "b", blue_note_b, seam_pts,
    )
    seam_tendrils_a, seam_sources_a = _body_seam_tendrils(
        seed, "a", (cx_a, cy_a, rx_a, ry_a, wamp_a, wfreq_a, wphase_a),
        seam_pts, clip_a, filament_ends_a,
    )
    seam_tendrils_b, seam_sources_b = _body_seam_tendrils(
        seed, "b", (cx_b, cy_b, rx_b, ry_b, wamp_b, wfreq_b, wphase_b),
        seam_pts, clip_b, filament_ends_b,
    )
    exchange_els = _contact_exchange(
        seam_pts, rng_exc, exchange_count, blue_note_exc,
        seam_sources_a + seam_sources_b,
    )

    svg: list[str] = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H_TOTAL}" '
        f'viewBox="0 0 {W} {H_TOTAL}">'
    )

    # ── defs ──
    svg.append("<defs>")
    svg.extend(physical_defs())

    # clip paths
    svg.append(f'<clipPath id="{clip_a}"><path d="{blob_a}"/></clipPath>')
    svg.append(f'<clipPath id="{clip_b}"><path d="{blob_b}"/></clipPath>')
    svg.extend(_body_material_defs())

    # turbulence for settling haze
    svg += [
        '<filter id="f-turb" x="-20%" y="-20%" width="140%" height="140%">',
        '  <feTurbulence type="fractalNoise" baseFrequency="0.018 0.012"'
        '   numOctaves="4" seed="7" result="noise"/>',
        '  <feDisplacementMap in="SourceGraphic" in2="noise"'
        '   scale="28" xChannelSelector="R" yChannelSelector="G"/>',
        '</filter>',
        '<filter id="f-haze" x="-30%" y="-30%" width="160%" height="160%">',
        '  <feGaussianBlur stdDeviation="22"/>',
        '</filter>',
        '<filter id="f-ground-soft" x="-25%" y="-70%" width="150%" height="240%"><feGaussianBlur stdDeviation="22 10"/></filter>',
        '<filter id="f-ground-core" x="-30%" y="-70%" width="160%" height="240%"><feGaussianBlur stdDeviation="14 8"/></filter>',
        '<filter id="f-shadow-ground" x="-30%" y="-100%" width="160%" height="300%"><feGaussianBlur stdDeviation="20 9"/></filter>',
        '<filter id="f-root-soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>',
        '<filter id="f-right-pressure" x="-20%" y="-20%" width="150%" height="140%"><feGaussianBlur stdDeviation="22 14"/></filter>',
        '<linearGradient id="g-right-pressure" x1="0" y1="0" x2="1" y2="0">'
        '  <stop offset="0%" stop-color="#344068" stop-opacity="0"/>'
        '  <stop offset="42%" stop-color="#344068" stop-opacity="0.20"/>'
        '  <stop offset="76%" stop-color="#26324B" stop-opacity="0.11"/>'
        '  <stop offset="100%" stop-color="#101725" stop-opacity="0.03"/>'
        '</linearGradient>',
        '<radialGradient id="g-ground-spectrum" cx="50%" cy="50%" r="50%">'
        '  <stop offset="0%" stop-color="#060A12" stop-opacity="0.86"/>'
        '  <stop offset="44%" stop-color="#183A3B" stop-opacity="0.72"/>'
        '  <stop offset="76%" stop-color="#202A46" stop-opacity="0.40"/>'
        '  <stop offset="100%" stop-color="#05070D" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="g-ground-core" cx="50%" cy="45%" r="55%">'
        '  <stop offset="0%" stop-color="#010207" stop-opacity="0.98"/>'
        '  <stop offset="68%" stop-color="#030812" stop-opacity="0.82"/>'
        '  <stop offset="100%" stop-color="#06100F" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="g-subterranean" cx="50%" cy="50%" r="50%">'
        '  <stop offset="0%" stop-color="#101A2B" stop-opacity="0"/>'
        '  <stop offset="42%" stop-color="#142D35" stop-opacity="0.62"/>'
        '  <stop offset="74%" stop-color="#18213A" stop-opacity="0.34"/>'
        '  <stop offset="100%" stop-color="#06080F" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="g-transmitted-shadow" cx="50%" cy="50%" r="50%">'
        '  <stop offset="0%" stop-color="#0A3523" stop-opacity="0.84"/>'
        '  <stop offset="62%" stop-color="#0B2B20" stop-opacity="0.62"/>'
        '  <stop offset="100%" stop-color="#07110E" stop-opacity="0"/>'
        '</radialGradient>',
    ]
    svg.append("</defs>")

    # ── Background ──
    svg.append(f'<rect width="{W}" height="{H_TOTAL}" fill="{PALETTE["bg"]}"/>')

    # ── Settling haze polygons ──
    svg.append('<g id="settling-haze" opacity="1">')
    rng_haze = _rng(seed, "haze")
    for _ in range(14):
        pts_h = []
        for _ in range(5):
            pts_h.append((rng_haze.uniform(0, W), rng_haze.uniform(200, H_ART)))
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_h)
        col = rng_haze.choice([PALETTE["body_a"], PALETTE["body_b"], "#0D111A"])
        op = rng_haze.uniform(0.012, 0.045)
        svg.append(
            f'<polygon points="{pts_str}" fill="{col}"'
            f' fill-opacity="{op:.3f}" filter="url(#f-haze)"/>'
        )
    svg.append('</g>')

    # ── Burial backdrop (behind bodies) ──
    svg.extend(burial_backdrop_svg(seed, burial_cfg))

    # ── Right pressure field ──
    svg.extend(_right_pressure_field(cx_b, cy_b, rx_b, ry_b))

    # ── Glow behind bodies ──
    svg.append('<g id="glow-layer">')
    svg.extend(_glow(cx_a, cy_a, rx_a, ry_a, PALETTE["glow_a"], "f-glow-a"))
    svg.extend(_glow(cx_b, cy_b, rx_b, ry_b, PALETTE["glow_b"], "f-glow-b"))
    svg.append('</g>')

    # ── Body A ──
    svg.extend(_body_cloud_layers(seed, "a", cx_a, cy_a, rx_a, ry_a))

    # ── Inner organs A ──
    svg.append('<g id="inner-density-organs-a">')
    svg.extend(inner_organs_a)
    svg.append('</g>')
    svg.extend(seam_tendrils_a)

    # ── Body B ──
    svg.extend(_body_cloud_layers(seed, "b", cx_b, cy_b, rx_b, ry_b))

    # ── Inner organs B ──
    svg.append('<g id="inner-density-organs-b">')
    svg.extend(inner_organs_b)
    svg.append('</g>')
    svg.extend(seam_tendrils_b)

    # ── Inter-body field ──
    svg.append('<g id="inter-body-field">')
    svg.append('<g id="contact-seam">')
    svg.extend(seam_els)
    svg.append('</g>')

    # ── Contact exchange ──
    svg.extend(exchange_els)
    svg.append('</g>')

    # ── Burial foreground (in front of bodies) ──
    svg.extend(burial_foreground_svg(seed, burial_cfg))

    # ── Shared ground node ──
    ground_x = (cx_a + cx_b) / 2
    ground_y = _burial_surface_y(ground_x, burial_cfg)
    ground_rx = (rx_a + rx_b) * 0.54
    svg.extend(_subterranean_spectra(ground_x, ground_y, ground_rx))
    svg.extend(_transmitted_shadow(ground_x, ground_y, ground_rx))
    svg.extend(_ground_vortex(ground_x, ground_y, ground_rx))
    svg.extend(_phantom_roots(
        seed,
        [(cx_a, cy_a, rx_a, ry_a), (cx_b, cy_b, rx_b, ry_b)],
        ground_x,
        ground_y,
    ))
    svg.extend(_graphite_crumbs(seed, ground_x, ground_y, ground_rx))

    # ── Global tactile microtexture ──
    svg.extend(tactile_void_svg(seed, W, H_ART, strength=0.55, grain_count=1800))
    svg.extend(_sparse_sparks(
        seed,
        [(cx_a, cy_a, rx_a, ry_a), (cx_b, cy_b, rx_b, ry_b)],
    ))

    # ── Footer ──
    fy = H_ART
    svg += [
        f'<rect x="0" y="{fy}" width="{W}" height="{H_FOOTER}" fill="{PALETTE["bg"]}"/>',
        f'<line x1="80" y1="{fy + 1}" x2="{W - 80}" y2="{fy + 1}"'
        f' stroke="{PALETTE["footer_line"]}" stroke-width="0.8"/>',
        f'<text x="540" y="{fy + 58}" fill="{PALETTE["text"]}"'
        f' text-anchor="middle" font-family="\'Helvetica Neue\',Arial,sans-serif"'
        f' font-size="28" letter-spacing="8" font-weight="300">'
        f'{track_name}</text>',
        f'<text x="540" y="{fy + 98}" fill="{PALETTE["muted"]}"'
        f' text-anchor="middle" font-family="\'Helvetica Neue\',Arial,sans-serif"'
        f' font-size="11" letter-spacing="5">',
        f'{seed}</text>',
    ]

    svg.append('</svg>')
    svg_text = "\n".join(svg)

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text(svg_text, encoding="utf-8")

    sha = hashlib.sha256(svg_text.encode()).hexdigest()
    meta = {
        "renderer": "render_d2_blues_poster",
        "version": RENDERER_VERSION,
        "track_name": track_name,
        "seed": seed,
        "svg_sha256": sha,
        "bodies": {
            "a": {"cx": cx_a, "cy": cy_a, "rx": rx_a, "ry": ry_a,
                  "organs": organ_count_a, "blue_note": blue_note_a},
            "b": {"cx": cx_b, "cy": cy_b, "rx": rx_b, "ry": ry_b,
                  "organs": organ_count_b, "blue_note": blue_note_b},
        },
        "seam_points": len(seam_pts),
        "exchange_events": exchange_count,
        "blue_note_exchange": blue_note_exc,
        "output_svg": str(out_svg),
    }
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"D2 Blues SVG:      {out_svg}")
    print(f"D2 Blues metadata: {out_meta}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Two-Body Blues renderer v1.4")
    parser.add_argument("--seed", type=int, default=24092026)
    parser.add_argument("--track-name", default=DEFAULT_TRACK_NAME)
    parser.add_argument(
        "--svg", type=Path,
        default=Path("artifacts/d2/posters/d2_blues_v1_poster.svg"),
    )
    parser.add_argument(
        "--meta", type=Path,
        default=Path("artifacts/d2/posters/d2_blues_v1_poster.metadata.json"),
    )
    args = parser.parse_args()
    render(args.seed, args.svg, args.meta, args.track_name)


if __name__ == "__main__":
    main()
