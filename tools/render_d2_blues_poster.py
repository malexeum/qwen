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

from tools.blues_d2_physical_layers import BurialConfig, burial_backdrop_svg, burial_foreground_svg, physical_defs, seed_int, tactile_void_svg

POSTER_ID = "d2_blues_v1_poster"
SCHEMA_VERSION = "d2_poster_metadata/v1"
RENDERER_NAME = "d2_blues_two_body_renderer"
RENDERER_VERSION = "1"
VIEWBOX = "0 0 1080 1260"
PALETTE = {"background":"#03050A","ink":"#D8D8D5","muted":"#737986","blue":"#315E8E","ember":"#A35B2B","violet":"#44374F"}


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _blob(seed: str, cx: float, cy: float, rx: float, ry: float, points: int, salt: str) -> str:
    rng = random.Random(seed_int(seed, salt))
    coords = []
    for i in range(points):
        a = 2 * math.pi * i / points
        modulation = 1 + .10 * math.sin(3*a+rng.random()) + .055 * math.sin(7*a+rng.random()*2)
        coords.append((cx + rx*modulation*math.cos(a), cy + ry*modulation*math.sin(a)))
    path = [f"M {coords[0][0]:.2f} {coords[0][1]:.2f}"]
    for i in range(points):
        p0, p1, p2, p3 = coords[(i-1)%points], coords[i], coords[(i+1)%points], coords[(i+2)%points]
        c1 = (p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6)
        c2 = (p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6)
        path.append(f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}")
    return " ".join(path) + " Z"


def _mist(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "mist"))
    out = ['<g id="d2-settling-mist">']
    for _ in range(38):
        x, y = rng.uniform(90, 990), rng.uniform(250, 900)
        out.append(f'<ellipse cx="{x:.2f}" cy="{y:.2f}" rx="{rng.uniform(18,95):.2f}" ry="{rng.uniform(5,22):.2f}" fill="#8A92A1" fill-opacity="{rng.uniform(.008,.035):.4f}" filter="url(#mist)"/>')
    out.append('</g>')
    return out


def _polygons(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "polygons"))
    out = ['<g id="d2-random-polygons">']
    for _ in range(17):
        cx, cy = rng.uniform(80, 1000), rng.uniform(80, 900)
        count = rng.randint(3, 6)
        pts = []
        for i in range(count):
            a = 2*math.pi*i/count + rng.uniform(-.25,.25)
            r = rng.uniform(12, 70)
            pts.append(f"{cx+r*math.cos(a):.2f},{cy+r*math.sin(a):.2f}")
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#687386" stroke-width=".7" stroke-opacity="{rng.uniform(.025,.09):.4f}"/>')
    out.append('</g>')
    return out


def base_metadata(seed: str) -> dict[str, Any]:
    return {"poster_id":POSTER_ID,"schema_version":SCHEMA_VERSION,"renderer":{"name":RENDERER_NAME,"version":RENDERER_VERSION},"seed":seed,"canonical_outputs":{"svg_filename":"d2_blues_v1_poster.svg","svg_viewbox":VIEWBOX},"visual_contract":{"metaphor":"two density bodies in pressured counterflow","retained_layers":["glow","settling_mist","random_polygons","turbulence","tactile_void"],"warning":"CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM"},"palette":PALETTE}


def render_svg(seed: str = "d2-blues-v1") -> bytes:
    cfg = BurialConfig()
    left = _blob(seed, 350, 600, 235, 300, 18, "left-body")
    right = _blob(seed, 690, 535, 205, 245, 17, "right-body")
    seam = "M 517 338 C 492 430 542 520 508 615 C 480 693 528 760 504 832"
    metadata = json.dumps(base_metadata(seed), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}" role="img" aria-labelledby="title desc">',
        f'<metadata>{metadata.replace("&","&amp;").replace("<","&lt;")}</metadata>',
        '<title id="title">D2 — TWO-BODY BLUES</title>',
        '<desc id="desc">Two unequal density bodies press into a heavy settling current. Their contact remains unresolved.</desc>',
        '<defs>',
        '<radialGradient id="body-left"><stop offset="0" stop-color="#315E8E" stop-opacity=".82"/><stop offset=".68" stop-color="#182B43" stop-opacity=".58"/><stop offset="1" stop-color="#080B12" stop-opacity=".08"/></radialGradient>',
        '<radialGradient id="body-right"><stop offset="0" stop-color="#A35B2B" stop-opacity=".68"/><stop offset=".58" stop-color="#44374F" stop-opacity=".50"/><stop offset="1" stop-color="#080B12" stop-opacity=".06"/></radialGradient>',
        '<filter id="body-turbulence" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".008 .019" numOctaves="3" seed="19" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="24"/><feGaussianBlur stdDeviation="2.2"/></filter>',
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>',
        '<filter id="mist" x="-40%" y="-100%" width="180%" height="300%"><feGaussianBlur stdDeviation="11"/></filter>',
        *physical_defs(),
        '</defs>',
        '<rect width="1080" height="1260" fill="#03050A"/>',
        '<g id="d2-artwork">',
        *_polygons(seed),
        *_mist(seed),
        *burial_backdrop_svg(seed, cfg),
        '<g id="d2-density-bodies">',
        f'<path d="{left}" fill="#315E8E" fill-opacity=".18" filter="url(#glow)"/>',
        f'<path id="d2-left-body" d="{left}" fill="url(#body-left)" filter="url(#body-turbulence)"/>',
        f'<path d="{right}" fill="#A35B2B" fill-opacity=".15" filter="url(#glow)"/>',
        f'<path id="d2-right-body" d="{right}" fill="url(#body-right)" filter="url(#body-turbulence)"/>',
        '</g>',
        '<g id="d2-contact-seam">',
        f'<path d="{seam}" fill="none" stroke="#315E8E" stroke-width="8" stroke-opacity=".12" filter="url(#glow)"/>',
        f'<path d="{seam}" fill="none" stroke="#010207" stroke-width="3.2" stroke-linecap="round"/>',
        '</g>',
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
    p = argparse.ArgumentParser(description="Render the canonical D2 two-body Blues SVG and metadata.")
    p.add_argument("--seed", default="d2-blues-v1")
    p.add_argument("--svg-output", type=Path, required=True)
    p.add_argument("--metadata-output", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    write_outputs(a.seed, a.svg_output, a.metadata_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
