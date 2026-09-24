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
RENDERER_VERSION = "1.2"
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
    for index in range(count):
        p0 = coords[(index - 1) % count]
        p1 = coords[index]
        p2 = coords[(index + 1) % count]
        p3 = coords[(index + 2) % count]
        c1 = (
            p1[0] + (p2[0] - p0[0]) / 6,
            p1[1] + (p2[1] - p0[1]) / 6,
        )
        c2 = (
            p2[0] - (p3[0] - p1[0]) / 6,
            p2[1] - (p3[1] - p1[1]) / 6,
        )
        path.append(
            f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} "
            f"{p2[0]:.2f} {p2[1]:.2f}"
        )
    return " ".join(path) + " Z"


def _signed_power(value: float, exponent: float) -> float:
    return math.copysign(abs(value) ** exponent, value)


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
    contact_dent: float,
    downstream: float,
    settling: float,
) -> str:
    """Build a directional density field with an indented contact flank."""
    rng = random.Random(seed_int(seed, salt))
    phase3 = rng.uniform(0, math.tau)
    phase5 = rng.uniform(0, math.tau)
    phase8 = rng.uniform(0, math.tau)
    coords: list[tuple[float, float]] = []

    for index in range(points):
        angle = math.tau * index / points
        cosine = math.cos(angle)
        sine = math.sin(angle)
        top = max(0.0, -sine)
        bottom = max(0.0, sine)

        # A superelliptic base prevents a soft circular cloud while preserving mass.
        horizontal = _signed_power(cosine, 0.78)
        vertical = _signed_power(sine, 0.94)
        irregularity = (
            1
            + 0.052 * math.sin(3 * angle + phase3)
            + 0.034 * math.sin(5 * angle + phase5)
            + 0.017 * math.sin(8 * angle + phase8)
        )
        horizontal_scale = 1 - top_taper * top + bottom_spread * bottom

        # Contact is a real indentation, not two luminous balls overlapping.
        contact_zone = max(0.0, contact_side * cosine)
        central_contact = math.exp(-((sine + 0.02) / 0.43) ** 2)
        dent = contact_side * contact_dent * contact_zone**1.7 * central_contact

        # The lower mass is dragged away from the seam and settles into the current.
        toe = bottom**2.15
        x = (
            cx
            + rx * irregularity * horizontal_scale * horizontal
            + shear * sine
            + 11 * math.sin(2 * angle + phase5)
            - dent
            + downstream * toe
        )
        y = (
            cy
            + ry * irregularity * vertical
            + 7 * math.sin(angle + phase3)
            + settling * toe
        )
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
        for index in range(count):
            angle = math.tau * index / count + rng.uniform(-0.25, 0.25)
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


def _density_shear_wakes(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "density-shear-wakes"))
    out = ['<g id="d2-density-shear-wakes" fill="none" stroke-linecap="round">']
    for index in range(5):
        offset = index * 31 + rng.uniform(-4, 4)
        out.append(
            f'<path d="M 70 {565+offset:.2f} C 176 {526+offset:.2f} '
            f'324 {548+offset:.2f} 503 {617+offset*.42:.2f}" '
            f'stroke="#315E8E" stroke-width="{27-index*3.6:.2f}" '
            f'stroke-opacity="{.030-index*.0035:.4f}" filter="url(#wake-soft)"/>'
        )
        out.append(
            f'<path d="M 1010 {498+offset:.2f} C 896 {468+offset:.2f} '
            f'760 {496+offset:.2f} 548 {592+offset*.38:.2f}" '
            f'stroke="#A35B2B" stroke-width="{24-index*3.2:.2f}" '
            f'stroke-opacity="{.026-index*.0030:.4f}" filter="url(#wake-soft)"/>'
        )
    out.append("</g>")
    return out


def _internal_strata(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "internal-strata"))
    out = ['<g id="d2-internal-strata" fill="none" stroke-linecap="round">']

    for index in range(8):
        y = 420 + index * 50 + rng.uniform(-8, 8)
        bend = rng.uniform(-20, 20)
        out.append(
            f'<path d="M 72 {y+18:.2f} C 214 {y-31+bend:.2f} '
            f'385 {y+27-bend:.2f} 573 {y-12:.2f}" '
            f'clip-path="url(#clip-left-body)" stroke="#7693B1" '
            f'stroke-width="{rng.uniform(.65, 1.55):.2f}" '
            f'stroke-opacity="{rng.uniform(.055, .14):.4f}"/>'
        )

    for index in range(7):
        y = 365 + index * 57 + rng.uniform(-8, 8)
        bend = rng.uniform(-18, 22)
        out.append(
            f'<path d="M 486 {y+18:.2f} C 630 {y-28-bend:.2f} '
            f'810 {y+31+bend:.2f} 970 {y-15:.2f}" '
            f'clip-path="url(#clip-right-body)" stroke="#B37A5D" '
            f'stroke-width="{rng.uniform(.62, 1.48):.2f}" '
            f'stroke-opacity="{rng.uniform(.05, .125):.4f}"/>'
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
            "body_geometry": "advected, indented, sheared, bottom-rooted",
            "retained_layers": [
                "glow",
                "settling_mist",
                "random_polygons",
                "turbulence",
                "density_shear_wakes",
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
        seed,
        350,
        585,
        252,
        326,
        30,
        "left-body-v12",
        -55,
        0.31,
        0.20,
        1,
        52,
        -48,
        30,
    )
    right = _advected_body(
        seed,
        688,
        520,
        224,
        272,
        29,
        "right-body-v12",
        63,
        0.37,
        0.14,
        -1,
        47,
        39,
        22,
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
        '<stop offset="0" stop-color="#14243A" stop-opacity=".32"/>'
        '<stop offset=".56" stop-color="#315E8E" stop-opacity=".70"/>'
        '<stop offset="1" stop-color="#101A2A" stop-opacity=".16"/>'
        "</linearGradient>",
        '<linearGradient id="body-right" x1="1" y1="0" x2="0" y2=".82">'
        '<stop offset="0" stop-color="#2A2431" stop-opacity=".22"/>'
        '<stop offset=".56" stop-color="#8C5133" stop-opacity=".57"/>'
        '<stop offset="1" stop-color="#31283B" stop-opacity=".20"/>'
        "</linearGradient>",
        f'<clipPath id="clip-left-body"><path d="{left}"/></clipPath>',
        f'<clipPath id="clip-right-body"><path d="{right}"/></clipPath>',
        '<filter id="body-turbulence" x="-30%" y="-30%" width="160%" height="160%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".008 .024" numOctaves="3" '
        'seed="19" result="noise"/>'
        '<feDisplacementMap in="SourceGraphic" in2="noise" scale="24"/>'
        '<feGaussianBlur stdDeviation=".32"/>'
        "</filter>",
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="12 5"/>'
        "</filter>",
        '<filter id="wake-soft" x="-30%" y="-100%" width="160%" height="300%">'
        '<feGaussianBlur stdDeviation="16 6"/>'
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
        *_density_shear_wakes(seed),
        '<g id="d2-density-bodies">',
        f'<path d="{left}" fill="#315E8E" fill-opacity=".085" filter="url(#glow)"/>',
        f'<path id="d2-left-body" d="{left}" fill="url(#body-left)" '
        'filter="url(#body-turbulence)"/>',
        f'<path d="{right}" fill="#A35B2B" fill-opacity=".072" filter="url(#glow)"/>',
        f'<path id="d2-right-body" d="{right}" fill="url(#body-right)" '
        'filter="url(#body-turbulence)"/>',
        "</g>",
        *_internal_strata(seed),
        *_counterflow_ribbons(seed),
        '<g id="d2-contact-seam">',
        f'<path d="{seam}" fill="none" stroke="#315E8E" stroke-width="6" '
        'stroke-opacity=".075" filter="url(#glow)"/>',
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
