from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
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
RENDERER_VERSION = "1.1"
VIEWBOX = "0 0 1080 1260"
PALETTE = {
    "background": "#03050A",
    "ink": "#D8D8D5",
    "muted": "#737986",
    "blue": "#315E8E",
    "ember": "#A35B2B",
    "violet": "#44374F",
}


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


def _closed_spline(coords: list[tuple[float, float]]) -> str:
    path = [f"M {coords[0][0]:.2f} {coords[0][1]:.2f}"]
    count = len(coords)
    for i in range(count):
        p0 = coords[(i - 1) % count]
        p1 = coords[i]
        p2 = coords[(i + 1) % count]
        p3 = coords[(i + 2) % count]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.append(
            f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} "
            f"{p2[0]:.2f} {p2[1]:.2f}"
        )
    return " ".join(path) + " Z"


def _advected_body(
    seed: str,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    points: int,
    salt: str,
    shear: float,
    top_taper: float,
    bottom_spread: float,
    contact_side: float,
    contact_pull: float,
) -> str:
    """Build an asymmetric density body deformed by gravity and counterflow."""
    rng = random.Random(seed_int(seed, salt))
    phase3 = rng.uniform(0, math.tau)
    phase5 = rng.uniform(0, math.tau)
    phase9 = rng.uniform(0, math.tau)
    coords: list[tuple[float, float]] = []

    for i in range(points):
        angle = math.tau * i / points
        cosine = math.cos(angle)
        sine = math.sin(angle)
        top = max(0.0, -sine)
        bottom = max(0.0, sine)
        irregularity = (
            1
            + 0.075 * math.sin(3 * angle + phase3)
            + 0.045 * math.sin(5 * angle + phase5)
            + 0.022 * math.sin(9 * angle + phase9)
        )
        horizontal_scale = 1 - top_taper * top + bottom_spread * bottom
        contact = (
            contact_side
            * contact_pull
            * max(0.0, contact_side * cosine) ** 2
            * math.exp(-((sine / 0.62) ** 2))
        )
        x = (
            cx
            + rx * irregularity * horizontal_scale * cosine
            + shear * sine
            + 14 * math.sin(2 * angle + phase5)
            + contact
        )
        y = cy + ry * irregularity * sine + 9 * math.sin(angle + phase3)
        coords.append((x, y))

    return _closed_spline(coords)


def _mist(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "mist"))
    out = ['<g id="d2-settling-mist">']
    for _ in range(38):
        x = rng.uniform(90, 990)
        y = rng.uniform(250, 900)
        out.append(
            f'<ellipse cx="{x:.2f}" cy="{y:.2f}" '
            f'rx="{rng.uniform(18, 95):.2f}" ry="{rng.uniform(5, 22):.2f}" '
            f'fill="#8A92A1" fill-opacity="{rng.uniform(.008, .035):.4f}" '
            f'filter="url(#mist)"/>'
        )
    out.append("</g>")
    return out


def _polygons(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "polygons"))
    out = ['<g id="d2-random-polygons">']
    for _ in range(17):
        cx = rng.uniform(80, 1000)
        cy = rng.uniform(80, 900)
        count = rng.randint(3, 6)
        points = []
        for i in range(count):
            angle = math.tau * i / count + rng.uniform(-0.25, 0.25)
            radius = rng.uniform(12, 70)
            points.append(
                f"{cx + radius * math.cos(angle):.2f},"
                f"{cy + radius * math.sin(angle):.2f}"
            )
        out.append(
            f'<polygon points="{" ".join(points)}" fill="none" '
            f'stroke="#687386" stroke-width=".7" '
            f'stroke-opacity="{rng.uniform(.025, .09):.4f}"/>'
        )
    out.append("</g>")
    return out


def _internal_strata(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "internal-strata"))
    out = ['<g id="d2-internal-strata" fill="none" stroke-linecap="round">']

    for index in range(7):
        y = 438 + index * 55 + rng.uniform(-8, 8)
        bend = rng.uniform(-18, 18)
        out.append(
            f'<path d="M 95 {y:.2f} C 225 {y-25+bend:.2f} '
            f'420 {y+24-bend:.2f} 574 {y-7:.2f}" '
            f'clip-path="url(#clip-left-body)" stroke="#7693B1" '
            f'stroke-width="{rng.uniform(.55, 1.35):.2f}" '
            f'stroke-opacity="{rng.uniform(.045, .12):.4f}"/>'
        )

    for index in range(6):
        y = 384 + index * 61 + rng.uniform(-8, 8)
        bend = rng.uniform(-16, 20)
        out.append(
            f'<path d="M 488 {y+15:.2f} C 635 {y-24-bend:.2f} '
            f'790 {y+28+bend:.2f} 945 {y-10:.2f}" '
            f'clip-path="url(#clip-right-body)" stroke="#B37A5D" '
            f'stroke-width="{rng.uniform(.55, 1.25):.2f}" '
            f'stroke-opacity="{rng.uniform(.04, .105):.4f}"/>'
        )

    out.append("</g>")
    return out


def _counterflow_ribbons(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "counterflow-ribbons"))
    out = ['<g id="d2-counterflow-ribbons" fill="none" stroke-linecap="round">']
    for index in range(5):
        y = 676 + index * 28 + rng.uniform(-5, 5)
        out.append(
            f'<path d="M 155 {y:.2f} C 300 {y-22:.2f} 428 {y+18:.2f} '
            f'532 {y-5:.2f}" stroke="#416B98" stroke-width="{1.4-index*.12:.2f}" '
            f'stroke-opacity="{.11-index*.012:.3f}"/>'
        )
        out.append(
            f'<path d="M 898 {y-18:.2f} C 760 {y+10:.2f} 650 {y-30:.2f} '
            f'526 {y-9:.2f}" stroke="#956044" stroke-width="{1.3-index*.11:.2f}" '
            f'stroke-opacity="{.095-index*.01:.3f}"/>'
        )
    out.append("</g>")
    return out


def base_metadata(seed: str) -> dict[str, Any]:
    return {
        "poster_id": POSTER_ID,
        "schema_version": SCHEMA_VERSION,
        "renderer": {"name": RENDERER_NAME, "version": RENDERER_VERSION},
        "seed": seed,
        "canonical_outputs": {
            "svg_filename": "d2_blues_v1_poster.svg",
            "svg_viewbox": VIEWBOX,
        },
        "visual_contract": {
            "metaphor": "two advected density bodies in pressured counterflow",
            "body_geometry": "asymmetric, tapered, sheared, bottom-heavy",
            "retained_layers": [
                "glow",
                "settling_mist",
                "random_polygons",
                "turbulence",
                "internal_strata",
                "counterflow_ribbons",
                "tactile_void",
            ],
            "warning": "CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM",
        },
        "palette": PALETTE,
    }


def render_svg(seed: str = "d2-blues-v1") -> bytes:
    cfg = BurialConfig()
    left = _advected_body(
        seed, 350, 600, 245, 305, 24, "left-body", -42, 0.25, 0.13, 1, 24
    )
    right = _advected_body(
        seed, 686, 535, 214, 250, 23, "right-body", 48, 0.31, 0.09, -1, 21
    )
    seam = "M 517 338 C 492 430 542 520 508 615 C 480 693 528 760 504 832"
    metadata = json.dumps(
        base_metadata(seed), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" '
        f'viewBox="{VIEWBOX}" role="img" aria-labelledby="title desc">',
        f'<metadata>{metadata.replace("&", "&amp;").replace("<", "&lt;")}</metadata>',
        '<title id="title">D2 — TWO-BODY BLUES</title>',
        '<desc id="desc">Two unequal density bodies press into a heavy settling current. Their contact remains unresolved.</desc>',
        "<defs>",
        '<linearGradient id="body-left" x1="0" y1="0" x2="1" y2=".72">'
        '<stop offset="0" stop-color="#14243A" stop-opacity=".34"/>'
        '<stop offset=".56" stop-color="#315E8E" stop-opacity=".72"/>'
        '<stop offset="1" stop-color="#101A2A" stop-opacity=".16"/>'
        "</linearGradient>",
        '<linearGradient id="body-right" x1="1" y1="0" x2="0" y2=".82">'
        '<stop offset="0" stop-color="#2A2431" stop-opacity=".24"/>'
        '<stop offset=".56" stop-color="#8C5133" stop-opacity=".60"/>'
        '<stop offset="1" stop-color="#31283B" stop-opacity=".22"/>'
        "</linearGradient>",
        f'<clipPath id="clip-left-body"><path d="{left}"/></clipPath>',
        f'<clipPath id="clip-right-body"><path d="{right}"/></clipPath>',
        '<filter id="body-turbulence" x="-30%" y="-30%" width="160%" height="160%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".007 .021" numOctaves="3" '
        'seed="19" result="noise"/>'
        '<feDisplacementMap in="SourceGraphic" in2="noise" scale="29"/>'
        '<feGaussianBlur stdDeviation=".75"/>'
        "</filter>",
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="18 9"/>'
        "</filter>",
        '<filter id="mist" x="-40%" y="-100%" width="180%" height="300%">'
        '<feGaussianBlur stdDeviation="11"/>'
        "</filter>",
        *physical_defs(),
        "</defs>",
        '<rect width="1080" height="1260" fill="#03050A"/>',
        '<g id="d2-artwork">',
        *_polygons(seed),
        *_mist(seed),
        *burial_backdrop_svg(seed, cfg),
        '<g id="d2-density-bodies">',
        f'<path d="{left}" fill="#315E8E" fill-opacity=".16" filter="url(#glow)"/>',
        f'<path id="d2-left-body" d="{left}" fill="url(#body-left)" '
        'filter="url(#body-turbulence)"/>',
        f'<path d="{right}" fill="#A35B2B" fill-opacity=".13" filter="url(#glow)"/>',
        f'<path id="d2-right-body" d="{right}" fill="url(#body-right)" '
        'filter="url(#body-turbulence)"/>',
        "</g>",
        *_internal_strata(seed),
        *_counterflow_ribbons(seed),
        '<g id="d2-contact-seam">',
        f'<path d="{seam}" fill="none" stroke="#315E8E" stroke-width="8" '
        'stroke-opacity=".10" filter="url(#glow)"/>',
        f'<path d="{seam}" fill="none" stroke="#010207" stroke-width="3.2" '
        'stroke-linecap="round"/>',
        "</g>",
        *burial_foreground_svg(seed, cfg),
        *tactile_void_svg(seed, 1080, 1080, 1.0, 2800),
        "</g>",
        '<line x1="90" y1="1100" x2="990" y2="1100" stroke="#737986" '
        'stroke-opacity=".28"/>',
        '<g id="d2-footer" font-family="Arial,Helvetica,sans-serif" text-anchor="middle">',
        '<text x="540" y="1150" fill="#D8D8D5" font-size="28" letter-spacing="5">'
        "TWO-BODY BLUES</text>",
        '<text x="540" y="1194" fill="#737986" font-size="13" letter-spacing="3">'
        "DENSITY · COUNTERFLOW · UNRESOLVED CONTACT</text>",
        '<text x="540" y="1225" fill="#737986" fill-opacity=".66" font-size="10" '
        'letter-spacing="2">CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM</text>',
        "</g>",
        "</svg>",
        "",
    ]
    return "\n".join(svg).encode("utf-8")


def build_metadata(seed: str, svg_bytes: bytes) -> bytes:
    data = base_metadata(seed)
    data["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    data["raster_outputs"] = []
    return canonical_json_bytes(data)


def write_outputs(
    seed: str, svg_path: Path, metadata_path: Path
) -> tuple[Path, Path]:
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
