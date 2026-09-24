from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blues_d2_physical_layers import (
    BurialConfig,
    burial_backdrop_svg,
    burial_foreground_svg,
    physical_defs,
    seed_int,
    tactile_void_svg,
)

POSTER_ID = "d2_blues_v1_poster"
SCHEMA_VERSION = "d2_poster_metadata/v1"
RENDERER_NAME = "d2_blues_two_body_renderer"
RENDERER_VERSION = "1.3"
VIEWBOX = "0 0 1080 1260"
PALETTE = {
    "background": "#03050A",
    "ink": "#D8D8D5",
    "muted": "#737986",
    "blue": "#315E8E",
    "ember": "#A35B2B",
    "violet": "#44374F",
    "blue_note": "#6F91C6",
}


@dataclass(frozen=True)
class BodySpec:
    cx: float
    cy: float
    rx: float
    ry: float
    points: int
    salt: str

    @property
    def area_proxy(self) -> float:
        return self.rx * self.ry


def canonical_json_bytes(data: Any) -> bytes:
    return (
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _body_specs(seed: str) -> tuple[BodySpec, BodySpec]:
    """Create a deliberately broad but always smooth size asymmetry."""
    rng = random.Random(seed_int(seed, "body-proportions-v13"))
    left = BodySpec(
        cx=335 + rng.uniform(-11, 11),
        cy=602 + rng.uniform(-18, 18),
        rx=rng.uniform(250, 300),
        ry=rng.uniform(305, 365),
        points=28,
        salt="left-body-v13",
    )
    right = BodySpec(
        cx=690 + rng.uniform(-10, 10),
        cy=515 + rng.uniform(-22, 22),
        rx=rng.uniform(135, 190),
        ry=rng.uniform(175, 245),
        points=26,
        salt="right-body-v13",
    )
    return left, right


def _blob(
    seed: str,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    points: int,
    salt: str,
    roughness: float = 1.0,
) -> str:
    """A Catmull-Rom organic body with low-amplitude, long-wave deformation."""
    rng = random.Random(seed_int(seed, salt))
    p3 = rng.uniform(0, math.tau)
    p5 = rng.uniform(0, math.tau)
    p7 = rng.uniform(0, math.tau)
    coords: list[tuple[float, float]] = []
    for i in range(points):
        angle = math.tau * i / points
        modulation = (
            1
            + roughness * 0.052 * math.sin(3 * angle + p3)
            + roughness * 0.026 * math.sin(5 * angle + p5)
            + roughness * 0.012 * math.sin(7 * angle + p7)
        )
        drift_x = roughness * rx * 0.018 * math.sin(2 * angle + p5)
        drift_y = roughness * ry * 0.014 * math.sin(2 * angle + p3)
        coords.append(
            (
                cx + rx * modulation * math.cos(angle) + drift_x,
                cy + ry * modulation * math.sin(angle) + drift_y,
            )
        )
    path = [f"M {coords[0][0]:.2f} {coords[0][1]:.2f}"]
    for i in range(points):
        p0 = coords[(i - 1) % points]
        p1 = coords[i]
        p2 = coords[(i + 1) % points]
        p3c = coords[(i + 2) % points]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3c[0] - p1[0]) / 6, p2[1] - (p3c[1] - p1[1]) / 6)
        path.append(
            f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}"
        )
    return " ".join(path) + " Z"


def _smooth_open(points: list[tuple[float, float]]) -> str:
    path = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    last = len(points) - 1
    for i in range(last):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(last, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.append(
            f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}"
        )
    return " ".join(path)


def _contact_points(
    seed: str,
    left: BodySpec,
    right: BodySpec,
) -> list[tuple[float, float]]:
    """Approximate the equal-pressure corridor inside the actual overlap."""
    rng = random.Random(seed_int(seed, "contact-corridor-v13"))
    top = max(left.cy - 0.82 * left.ry, right.cy - 0.86 * right.ry)
    bottom = min(left.cy + 0.82 * left.ry, right.cy + 0.86 * right.ry)
    candidates: list[tuple[float, float]] = []
    for i in range(81):
        y = top + (bottom - top) * i / 80
        ln = (y - left.cy) / left.ry
        rn = (y - right.cy) / right.ry
        if abs(ln) >= 1 or abs(rn) >= 1:
            continue
        left_edge = left.cx + left.rx * math.sqrt(max(0.0, 1 - ln * ln))
        right_edge = right.cx - right.rx * math.sqrt(max(0.0, 1 - rn * rn))
        overlap = left_edge - right_edge
        if overlap >= 7:
            x = (left_edge + right_edge) / 2
            x += 4.0 * math.sin((y - top) / 58 + 0.4) + rng.uniform(-1.2, 1.2)
            candidates.append((x, y))
    if len(candidates) < 7:
        mid_x = (left.cx + left.rx + right.cx - right.rx) / 2
        return [(mid_x + 3 * math.sin(i * 0.8), top + (bottom - top) * i / 8) for i in range(9)]
    indexes = [round(i * (len(candidates) - 1) / 10) for i in range(11)]
    return [candidates[i] for i in indexes]


def _mist(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "mist"))
    out = ['<g id="d2-settling-mist">']
    for _ in range(44):
        x, y = rng.uniform(70, 1010), rng.uniform(230, 925)
        out.append(
            f'<ellipse cx="{x:.2f}" cy="{y:.2f}" '
            f'rx="{rng.uniform(18,110):.2f}" ry="{rng.uniform(5,24):.2f}" '
            f'fill="#8A92A1" fill-opacity="{rng.uniform(.008,.036):.4f}" '
            f'filter="url(#mist)"/>'
        )
    out.append("</g>")
    return out


def _polygons(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "polygons"))
    out = ['<g id="d2-random-polygons">']
    for _ in range(17):
        cx, cy = rng.uniform(80, 1000), rng.uniform(80, 900)
        count = rng.randint(3, 6)
        pts = []
        for i in range(count):
            angle = math.tau * i / count + rng.uniform(-0.25, 0.25)
            radius = rng.uniform(12, 70)
            pts.append(f"{cx + radius * math.cos(angle):.2f},{cy + radius * math.sin(angle):.2f}")
        out.append(
            f'<polygon points="{" ".join(pts)}" fill="none" '
            f'stroke="#687386" stroke-width=".7" '
            f'stroke-opacity="{rng.uniform(.025,.09):.4f}"/>'
        )
    out.append("</g>")
    return out


def _organ_layers(
    seed: str,
    body: BodySpec,
    side: str,
    clip_id: str,
) -> list[str]:
    """Smudged organ-like densities: visible as pressure, never anatomy."""
    rng = random.Random(seed_int(seed, f"{side}-organs-v13"))
    colors = (
        ("#6385AA", "#263F61", "#111E33", "#7B8FA8")
        if side == "left"
        else ("#B36A39", "#684054", "#2A2333", "#7B6079")
    )
    count = 7 if side == "left" else 5
    out = [f'<g id="d2-{side}-internal-organs" clip-path="url(#{clip_id})">']
    for i in range(count):
        cx = body.cx + rng.uniform(-0.34, 0.34) * body.rx
        cy = body.cy + rng.uniform(-0.38, 0.38) * body.ry
        rx = body.rx * rng.uniform(0.12, 0.34)
        ry = body.ry * rng.uniform(0.08, 0.25)
        if i % 3 == 0:
            rx *= 1.35
            ry *= 0.72
        organ = _blob(
            seed,
            cx,
            cy,
            rx,
            ry,
            18,
            f"{side}-organ-{i}",
            roughness=0.62,
        )
        out.append(
            f'<path d="{organ}" fill="{colors[i % len(colors)]}" '
            f'fill-opacity="{rng.uniform(.055,.155):.4f}" '
            f'filter="url(#{"organ-deep" if i % 2 else "organ-soft"})"/>'
        )
    for i in range(4 if side == "left" else 3):
        y = body.cy + (i - 1.5) * body.ry * 0.18 + rng.uniform(-14, 14)
        start_x = body.cx - body.rx * rng.uniform(0.40, 0.62)
        end_x = body.cx + body.rx * rng.uniform(0.35, 0.58)
        bend = rng.uniform(-35, 35)
        out.append(
            f'<path d="M {start_x:.2f} {y:.2f} '
            f'C {body.cx-body.rx*.12:.2f} {y+bend:.2f} '
            f'{body.cx+body.rx*.12:.2f} {y-bend:.2f} {end_x:.2f} {y+rng.uniform(-10,10):.2f}" '
            f'fill="none" stroke="{colors[(i+1) % len(colors)]}" '
            f'stroke-width="{rng.uniform(2.5,7):.2f}" stroke-opacity="{rng.uniform(.055,.12):.4f}" '
            f'stroke-linecap="round" filter="url(#organ-soft)"/>'
        )
    out.append("</g>")
    return out


def _call_response(left: BodySpec, right: BodySpec) -> list[str]:
    return [
        '<g id="d2-call-response">',
        '<g clip-path="url(#clip-left-body)" fill="none" stroke-linecap="round" filter="url(#organ-soft)">',
        f'<path d="M {left.cx-left.rx*.58:.2f} {left.cy-left.ry*.22:.2f} Q {left.cx:.2f} {left.cy-left.ry*.38:.2f} {left.cx+left.rx*.53:.2f} {left.cy-left.ry*.12:.2f}" stroke="#7691AE" stroke-width="5" stroke-opacity=".085"/>',
        f'<path d="M {left.cx-left.rx*.50:.2f} {left.cy+left.ry*.08:.2f} Q {left.cx-left.rx*.05:.2f} {left.cy+left.ry*.24:.2f} {left.cx+left.rx*.42:.2f} {left.cy+left.ry*.02:.2f}" stroke="#315E8E" stroke-width="8" stroke-opacity=".075"/>',
        f'<path d="M {left.cx-left.rx*.42:.2f} {left.cy+left.ry*.34:.2f} Q {left.cx+.08*left.rx:.2f} {left.cy+left.ry*.18:.2f} {left.cx+left.rx*.36:.2f} {left.cy+left.ry*.39:.2f}" stroke="#8B7894" stroke-width="4" stroke-opacity=".055"/>',
        '</g>',
        '<g clip-path="url(#clip-right-body)" fill="none" stroke-linecap="round" filter="url(#organ-soft)">',
        f'<path d="M {right.cx-right.rx*.56:.2f} {right.cy-right.ry*.12:.2f} Q {right.cx:.2f} {right.cy-right.ry*.29:.2f} {right.cx+right.rx*.52:.2f} {right.cy-right.ry*.03:.2f}" stroke="#B77951" stroke-width="6" stroke-opacity=".09"/>',
        f'<path d="M {right.cx-right.rx*.45:.2f} {right.cy+right.ry*.20:.2f} Q {right.cx+.04*right.rx:.2f} {right.cy+right.ry*.36:.2f} {right.cx+right.rx*.43:.2f} {right.cy+right.ry*.12:.2f}" stroke="#6F91C6" stroke-width="4" stroke-opacity=".075"/>',
        '</g>',
        '</g>',
    ]


def _contact_flows(seed: str, points: list[tuple[float, float]]) -> list[str]:
    rng = random.Random(seed_int(seed, "contact-flows-v13"))
    out = ['<g id="d2-contact-flows" fill="none" stroke-linecap="round">']
    fractions = (0.16, 0.33, 0.51, 0.69, 0.84)
    for i, fraction in enumerate(fractions):
        x, y = points[round(fraction * (len(points) - 1))]
        span = rng.uniform(42, 82)
        rise = rng.uniform(-24, 24)
        if i in (0, 2, 4):
            direction = "lr" if i != 2 else "rl"
            start_x, end_x = (x - span, x + span) if direction == "lr" else (x + span, x - span)
            path = (
                f"M {start_x:.2f} {y+rise:.2f} "
                f"C {x-span*.34:.2f} {y-rise*.45:.2f} "
                f"{x+span*.28:.2f} {y+rise*.30:.2f} {end_x:.2f} {y-rise*.55:.2f}"
            )
            gradient = "flow-lr" if direction == "lr" else "flow-rl"
            out.append(
                f'<path data-mode="attract" d="{path}" stroke="url(#{gradient})" '
                f'stroke-width="5.5" stroke-opacity=".13" filter="url(#flow-glow)"/>'
            )
            out.append(
                f'<path data-mode="attract" d="{path}" stroke="url(#{gradient})" '
                f'stroke-width=".85" stroke-opacity=".48" stroke-dasharray="{rng.uniform(7,13):.2f} {rng.uniform(18,31):.2f}"/>'
            )
        else:
            left_path = (
                f"M {x:.2f} {y:.2f} C {x-18:.2f} {y+rise:.2f} "
                f"{x-span*.55:.2f} {y-rise:.2f} {x-span:.2f} {y+rise*.75:.2f}"
            )
            right_path = (
                f"M {x:.2f} {y:.2f} C {x+18:.2f} {y-rise:.2f} "
                f"{x+span*.55:.2f} {y+rise:.2f} {x+span:.2f} {y-rise*.75:.2f}"
            )
            for path, color in ((left_path, "#557DA9"), (right_path, "#9B6549")):
                out.append(
                    f'<path data-mode="repel" d="{path}" stroke="{color}" '
                    f'stroke-width="4.5" stroke-opacity=".11" filter="url(#flow-glow)"/>'
                )
                out.append(
                    f'<path data-mode="repel" d="{path}" stroke="{color}" '
                    f'stroke-width=".75" stroke-opacity=".38" stroke-dasharray="5 21"/>'
                )
    out.append("</g>")
    return out


def _blue_note(points: list[tuple[float, float]]) -> list[str]:
    x, y = points[round(0.62 * (len(points) - 1))]
    note_path = (
        f"M {x-96:.2f} {y+28:.2f} "
        f"C {x-52:.2f} {y-16:.2f} {x-20:.2f} {y+24:.2f} {x+2:.2f} {y-2:.2f} "
        f"S {x+48:.2f} {y-36:.2f} {x+76:.2f} {y+7:.2f}"
    )
    return [
        '<g id="d2-blue-note">',
        f'<path d="{note_path}" fill="none" stroke="#6F91C6" stroke-width="9" stroke-opacity=".12" stroke-linecap="round" filter="url(#flow-glow)"/>',
        f'<path d="{note_path}" fill="none" stroke="#8DA8CD" stroke-width="1.1" stroke-opacity=".38" stroke-linecap="round" stroke-dasharray="11 17"/>',
        f'<ellipse cx="{x+23:.2f}" cy="{y-13:.2f}" rx="24" ry="11" fill="#5278AA" fill-opacity=".14" transform="rotate(-19 {x+23:.2f} {y-13:.2f})" filter="url(#organ-soft)"/>',
        '</g>',
    ]


def base_metadata(seed: str) -> dict[str, Any]:
    left, right = _body_specs(seed)
    ratio = left.area_proxy / right.area_proxy
    return {
        "poster_id": POSTER_ID,
        "schema_version": SCHEMA_VERSION,
        "renderer": {"name": RENDERER_NAME, "version": RENDERER_VERSION},
        "seed": seed,
        "canonical_outputs": {
            "svg_filename": "d2_blues_v1_poster.svg",
            "svg_viewbox": VIEWBOX,
        },
        "body_geometry": {
            "left": {"cx": left.cx, "cy": left.cy, "rx": left.rx, "ry": left.ry},
            "right": {"cx": right.cx, "cy": right.cy, "rx": right.rx, "ry": right.ry},
            "area_proxy_ratio": ratio,
        },
        "visual_contract": {
            "metaphor": "two unequal smoky density bodies exchanging pressure in unresolved counterflow",
            "retained_layers": [
                "glow",
                "settling_mist",
                "random_polygons",
                "turbulence",
                "tactile_void",
            ],
            "structural_layers": [
                "internal_organs",
                "call_response",
                "aligned_contact_seam",
                "contact_flows",
                "blue_note",
            ],
            "warning": "CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM",
        },
        "palette": PALETTE,
    }


def render_svg(seed: str = "d2-blues-v1") -> bytes:
    left_spec, right_spec = _body_specs(seed)
    left = _blob(seed, left_spec.cx, left_spec.cy, left_spec.rx, left_spec.ry, left_spec.points, left_spec.salt)
    right = _blob(seed, right_spec.cx, right_spec.cy, right_spec.rx, right_spec.ry, right_spec.points, right_spec.salt)
    contact_points = _contact_points(seed, left_spec, right_spec)
    seam = _smooth_open(contact_points)
    contact_x = sum(x for x, _ in contact_points) / len(contact_points)
    cfg = BurialConfig(
        left_x=left_spec.cx,
        right_x=right_spec.cx,
        contact_x=contact_x,
        left_sink=68,
        right_sink=38,
        left_sigma=max(190, left_spec.rx * 0.82),
        right_sigma=max(130, right_spec.rx * 0.88),
        contact_ridge=21,
        foreground_opacity=0.37,
        sediment_count=250,
    )
    metadata = json.dumps(
        base_metadata(seed), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}" role="img" aria-labelledby="title desc">',
        f'<metadata>{metadata.replace("&", "&amp;").replace("<", "&lt;")}</metadata>',
        '<title id="title">D2 — TWO-BODY BLUES</title>',
        '<desc id="desc">Two unequal smoky densities hold blurred internal organs, exchange rare pressure currents, and bend around a blue note.</desc>',
        '<defs>',
        '<radialGradient id="body-left" cx="43%" cy="48%" r="68%"><stop offset="0" stop-color="#315E8E" stop-opacity=".80"/><stop offset=".58" stop-color="#182B43" stop-opacity=".56"/><stop offset="1" stop-color="#080B12" stop-opacity=".05"/></radialGradient>',
        '<radialGradient id="body-right" cx="46%" cy="45%" r="70%"><stop offset="0" stop-color="#A35B2B" stop-opacity=".66"/><stop offset=".55" stop-color="#44374F" stop-opacity=".49"/><stop offset="1" stop-color="#080B12" stop-opacity=".045"/></radialGradient>',
        '<linearGradient id="flow-lr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#315E8E" stop-opacity="0"/><stop offset=".48" stop-color="#9BB2D1"/><stop offset="1" stop-color="#A35B2B" stop-opacity="0"/></linearGradient>',
        '<linearGradient id="flow-rl" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#A35B2B" stop-opacity="0"/><stop offset=".52" stop-color="#829DC2"/><stop offset="1" stop-color="#315E8E" stop-opacity="0"/></linearGradient>',
        f'<clipPath id="clip-left-body"><path d="{left}"/></clipPath>',
        f'<clipPath id="clip-right-body"><path d="{right}"/></clipPath>',
        '<filter id="body-turbulence" x="-35%" y="-35%" width="170%" height="170%"><feTurbulence type="fractalNoise" baseFrequency=".006 .015" numOctaves="3" seed="19" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="18"/><feGaussianBlur stdDeviation="3.4"/></filter>',
        '<filter id="glow" x="-55%" y="-55%" width="210%" height="210%"><feGaussianBlur stdDeviation="22"/></filter>',
        '<filter id="mist" x="-40%" y="-100%" width="180%" height="300%"><feGaussianBlur stdDeviation="11"/></filter>',
        '<filter id="organ-soft" x="-60%" y="-80%" width="220%" height="260%"><feGaussianBlur stdDeviation="9"/></filter>',
        '<filter id="organ-deep" x="-70%" y="-90%" width="240%" height="280%"><feGaussianBlur stdDeviation="18"/></filter>',
        '<filter id="flow-glow" x="-70%" y="-150%" width="240%" height="400%"><feGaussianBlur stdDeviation="6"/></filter>',
        *physical_defs(),
        '</defs>',
        '<rect width="1080" height="1260" fill="#03050A"/>',
        '<g id="d2-artwork">',
        *_polygons(seed),
        *_mist(seed),
        *burial_backdrop_svg(seed, cfg),
        '<g id="d2-density-bodies">',
        f'<path d="{left}" fill="#315E8E" fill-opacity=".19" filter="url(#glow)"/>',
        f'<path id="d2-left-body" d="{left}" fill="url(#body-left)" filter="url(#body-turbulence)"/>',
        f'<path d="{right}" fill="#A35B2B" fill-opacity=".16" filter="url(#glow)"/>',
        f'<path id="d2-right-body" d="{right}" fill="url(#body-right)" filter="url(#body-turbulence)"/>',
        '<g id="d2-internal-organs">',
        *_organ_layers(seed, left_spec, "left", "clip-left-body"),
        *_organ_layers(seed, right_spec, "right", "clip-right-body"),
        '</g>',
        *_call_response(left_spec, right_spec),
        '</g>',
        '<g id="d2-contact-seam">',
        f'<path d="{seam}" fill="none" stroke="#7896BA" stroke-width="9" stroke-opacity=".10" filter="url(#flow-glow)"/>',
        f'<path d="{seam}" fill="none" stroke="#010207" stroke-width="2.7" stroke-opacity=".92" stroke-linecap="round"/>',
        '</g>',
        *_contact_flows(seed, contact_points),
        *_blue_note(contact_points),
        *burial_foreground_svg(seed, cfg),
        *tactile_void_svg(seed, 1080, 1080, 1.0, 2800),
        '</g>',
        '<line x1="90" y1="1100" x2="990" y2="1100" stroke="#737986" stroke-opacity=".28"/>',
        '<g id="d2-footer" font-family="Arial,Helvetica,sans-serif" text-anchor="middle">',
        '<text x="540" y="1150" fill="#D8D8D5" font-size="28" letter-spacing="5">TWO-BODY BLUES</text>',
        '<text x="540" y="1194" fill="#737986" font-size="13" letter-spacing="3">DENSITY · COUNTERFLOW · UNRESOLVED CONTACT</text>',
        '<text x="540" y="1225" fill="#737986" fill-opacity=".66" font-size="10" letter-spacing="2">CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM</text>',
        '</g>',
        '</svg>',
        '',
    ]
    return "\n".join(svg).encode("utf-8")


def build_metadata(seed: str, svg_bytes: bytes) -> bytes:
    data = base_metadata(seed)
    data["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    data["raster_outputs"] = []
    return canonical_json_bytes(data)


def write_outputs(seed: str, svg_path: Path, metadata_path: Path) -> tuple[Path, Path]:
    svg = render_svg(seed)
    metadata = build_metadata(seed, svg)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg)
    metadata_path.write_bytes(metadata)
    return svg_path, metadata_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the canonical D2 two-body Blues SVG and metadata."
    )
    parser.add_argument("--seed", default="d2-blues-v1")
    parser.add_argument("--svg-output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_outputs(args.seed, args.svg_output, args.metadata_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
