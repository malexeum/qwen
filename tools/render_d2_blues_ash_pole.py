from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RENDERER_VERSION = "1.0"
VIEWBOX = "0 0 1080 1260"
POSTER_ID = "d2_blues_ash_pole"


@dataclass(frozen=True)
class DryBody:
    cx: float
    cy: float
    rx: float
    ry: float
    lean: float
    salt: str


def _seed(seed: str, salt: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{salt}".encode()).digest()[:8], "big")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _bodies(seed: str) -> tuple[DryBody, DryBody]:
    rng = random.Random(_seed(seed, "dry-bodies"))
    heavy = DryBody(382+rng.uniform(-18, 12), 615+rng.uniform(-12, 18), rng.uniform(142, 172), rng.uniform(292, 338), rng.uniform(-34, -14), "heavy")
    answer = DryBody(665+rng.uniform(-10, 20), 575+rng.uniform(-18, 20), rng.uniform(84, 112), rng.uniform(230, 278), rng.uniform(10, 30), "answer")
    return heavy, answer


def _dry_path(seed: str, body: DryBody, salt: str, scale: float = 1.0) -> str:
    rng = random.Random(_seed(seed, salt))
    n = 26
    pts: list[tuple[float, float]] = []
    p1, p2, p3 = (rng.uniform(0, math.tau) for _ in range(3))
    for i in range(n):
        a = math.tau*i/n
        y0 = math.sin(a)
        taper = .80 + .20*(1-abs(y0))
        pulse = 1 + .045*math.sin(3*a+p1) + .024*math.sin(5*a+p2) + .012*math.sin(9*a+p3)
        x = body.cx + body.lean*y0 + body.rx*scale*taper*pulse*math.cos(a)
        y = body.cy + body.ry*scale*pulse*y0
        pts.append((x, y))
    chunks = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(n):
        p0, p, q, p3v = pts[(i-1)%n], pts[i], pts[(i+1)%n], pts[(i+2)%n]
        c1 = (p[0]+(q[0]-p0[0])/6, p[1]+(q[1]-p0[1])/6)
        c2 = (q[0]-(p3v[0]-p[0])/6, q[1]-(p3v[1]-p[1])/6)
        chunks.append(f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {q[0]:.2f} {q[1]:.2f}")
    return " ".join(chunks)+" Z"


def _wash(seed: str) -> list[str]:
    rng = random.Random(_seed(seed, "paper-wash"))
    out = ['<g id="ash-paper-memory" filter="url(#wash-blur)">']
    for _ in range(28):
        out.append(f'<ellipse cx="{rng.uniform(20,1060):.2f}" cy="{rng.uniform(20,1030):.2f}" rx="{rng.uniform(30,180):.2f}" ry="{rng.uniform(5,35):.2f}" fill="{rng.choice(["#81786A","#A8987E","#59606A"])}" fill-opacity="{rng.uniform(.008,.025):.4f}"/>')
    return out+['</g>']


def _scratches(seed: str, body: DryBody, clip: str, side: str) -> list[str]:
    rng = random.Random(_seed(seed, f"{side}-scratches"))
    color = "#C4B89E" if side == "heavy" else "#E0C99B"
    out = [f'<g id="ash-{side}-scratches" clip-path="url(#{clip})" fill="none" stroke-linecap="round">']
    count = 9 if side == "heavy" else 6
    for _ in range(count):
        x = body.cx+rng.uniform(-.55,.55)*body.rx
        y1 = body.cy+rng.uniform(-.62,.35)*body.ry
        y2 = y1+rng.uniform(38,125)
        out.append(f'<path d="M {x:.2f} {y1:.2f} Q {x+rng.uniform(-18,18):.2f} {(y1+y2)/2:.2f} {x+rng.uniform(-9,9):.2f} {y2:.2f}" stroke="{color}" stroke-width="{rng.uniform(.7,2.2):.2f}" stroke-opacity="{rng.uniform(.08,.22):.4f}"/>')
    return out+['</g>']


def _stains(seed: str, body: DryBody, clip: str, side: str) -> list[str]:
    rng = random.Random(_seed(seed, f"{side}-stains"))
    palette = ["#17191B", "#41362F", "#6E3D2D"] if side == "heavy" else ["#9B6038", "#B98A50", "#6A4435"]
    out = [f'<g id="ash-{side}-organs" clip-path="url(#{clip})" filter="url(#stain-blur)">']
    for _ in range(5 if side == "heavy" else 3):
        out.append(f'<ellipse cx="{body.cx+rng.uniform(-.30,.30)*body.rx:.2f}" cy="{body.cy+rng.uniform(-.42,.42)*body.ry:.2f}" rx="{rng.uniform(.10,.25)*body.rx:.2f}" ry="{rng.uniform(.05,.15)*body.ry:.2f}" transform="rotate({rng.uniform(-28,28):.2f} {body.cx:.2f} {body.cy:.2f})" fill="{rng.choice(palette)}" fill-opacity="{rng.uniform(.08,.19):.4f}"/>')
    return out+['</g>']


def _exchange(seed: str, heavy: DryBody, answer: DryBody) -> list[str]:
    rng = random.Random(_seed(seed, "dry-exchange"))
    gap = (heavy.cx+heavy.rx*.74+answer.cx-answer.rx*.82)/2
    out = ['<g id="ash-call-response" fill="none" stroke-linecap="round">']
    ys = [470, 570, 680]
    for i, y in enumerate(ys):
        y += rng.uniform(-14,14)
        if i == 0:
            d = f"M {gap-88:.2f} {y:.2f} C {gap-42:.2f} {y-16:.2f} {gap+24:.2f} {y+21:.2f} {gap+76:.2f} {y-5:.2f}"
            out.append(f'<path data-phrase="call" d="{d}" stroke="#6D4938" stroke-width="4" stroke-opacity=".34" filter="url(#thread-soft)"/>')
        elif i == 1:
            d = f"M {gap+70:.2f} {y:.2f} C {gap+31:.2f} {y+19:.2f} {gap-18:.2f} {y-14:.2f} {gap-58:.2f} {y+8:.2f}"
            out.append(f'<path data-phrase="response" d="{d}" stroke="#28384D" stroke-width="3" stroke-opacity=".28" filter="url(#thread-soft)"/>')
        else:
            d = f"M {gap-74:.2f} {y:.2f} C {gap-40:.2f} {y-9:.2f} {gap-10:.2f} {y+17:.2f} {gap+8:.2f} {y+4:.2f}"
            out.append(f'<path data-phrase="unanswered" d="{d}" stroke="#704F4C" stroke-width="3.5" stroke-opacity=".30" filter="url(#thread-soft)"/>')
    out.append(f'<path id="ash-blue-note" data-gesture="wrong-weight" d="M {gap-54:.2f} 744 C {gap-18:.2f} 718 {gap+5:.2f} 756 {gap+23:.2f} 733 L {gap+39:.2f} 758" stroke="#2457C5" stroke-width="5" stroke-opacity=".72"/>')
    return out+['</g>']


def _floor(seed: str) -> list[str]:
    rng = random.Random(_seed(seed, "threshold"))
    top = 868+rng.uniform(-8,8)
    return ['<g id="ash-coffin-threshold">', f'<path d="M 122 {top:.2f} L 914 {top+4:.2f} L 972 1018 L 88 1018 Z" fill="#403A32" fill-opacity=".055" stroke="#413A31" stroke-opacity=".12" stroke-width="1.5"/>', f'<path d="M 190 {top+24:.2f} L 852 {top+27:.2f}" stroke="#151719" stroke-opacity=".13" stroke-width="2"/>', '</g>']


def metadata(seed: str, svg: bytes | None = None) -> dict[str, Any]:
    heavy, answer = _bodies(seed)
    data: dict[str, Any] = {"poster_id": POSTER_ID, "schema_version": "d2_poster_metadata/v1", "renderer": {"name": "d2_blues_ash_pole_renderer", "version": RENDERER_VERSION}, "seed": seed, "pole": "ash_daylight", "body_geometry": {"heavy": vars(heavy), "answer": vars(answer), "area_proxy_ratio": heavy.rx*heavy.ry/(answer.rx*answer.ry)}, "visual_contract": {"metaphor": "Blues after the smoke clears: two dry residues negotiate across expensive daylight", "aab": ["charcoal_statement", "delayed_erasure", "cobalt_unresolved_answer"], "negative_space_target": "55-68%", "blue_note": "single cobalt wrong-weight gesture"}}
    if svg is not None:
        data["svg_sha256"] = _sha(svg)
    return data


def render_svg(seed: str = "d2-blues-ash-v1") -> bytes:
    heavy, answer = _bodies(seed)
    hp, ap = _dry_path(seed, heavy, "heavy-path"), _dry_path(seed, answer, "answer-path")
    embedded = json.dumps(metadata(seed), sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace("&", "&amp;").replace("<", "&lt;")
    svg = ['<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}" role="img" aria-labelledby="title desc">', f'<metadata>{embedded}</metadata>', '<title id="title">D2 — ASH-DAYLIGHT BLUES</title>', '<desc id="desc">The opposite pole of smoky blues: dry daylight, erased bodies, and one unresolved cobalt gesture.</desc>', '<defs>', f'<clipPath id="clip-heavy"><path d="{hp}"/></clipPath>', f'<clipPath id="clip-answer"><path d="{ap}"/></clipPath>', '<linearGradient id="paper" x2="0" y2="1"><stop stop-color="#DED7C8"/><stop offset=".58" stop-color="#D2C8B6"/><stop offset="1" stop-color="#BEB19A"/></linearGradient>', '<linearGradient id="heavy-ink" x2="1" y2="1"><stop stop-color="#101417" stop-opacity=".90"/><stop offset=".62" stop-color="#302B28" stop-opacity=".72"/><stop offset="1" stop-color="#76503C" stop-opacity=".24"/></linearGradient>', '<linearGradient id="answer-ink" x2="0" y2="1"><stop stop-color="#8A4A2C" stop-opacity=".18"/><stop offset=".45" stop-color="#A86639" stop-opacity=".70"/><stop offset="1" stop-color="#3A2924" stop-opacity=".48"/></linearGradient>', '<filter id="wash-blur"><feGaussianBlur stdDeviation="16"/></filter>', '<filter id="dry-edge" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".018 .045" numOctaves="2" seed="31" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="10" result="d"/><feGaussianBlur in="d" stdDeviation="2.8"/></filter>', '<filter id="ghost-blur"><feGaussianBlur stdDeviation="13"/></filter>', '<filter id="stain-blur"><feGaussianBlur stdDeviation="9"/></filter>', '<filter id="thread-soft"><feGaussianBlur stdDeviation="2.5"/></filter>', '</defs>', '<rect width="1080" height="1260" fill="url(#paper)"/>', '<g id="ash-artwork">', *_wash(seed), *_floor(seed), '<g id="ash-afterimages">', f'<path d="{hp}" transform="translate(-21 13)" fill="none" stroke="#332F2B" stroke-width="7" stroke-opacity=".075" filter="url(#ghost-blur)"/>', f'<path d="{ap}" transform="translate(15 -9)" fill="none" stroke="#8A542F" stroke-width="6" stroke-opacity=".09" filter="url(#ghost-blur)"/>', '</g>', '<g id="ash-dry-bodies">', f'<path id="ash-heavy-body" d="{hp}" fill="url(#heavy-ink)" filter="url(#dry-edge)"/>', f'<path id="ash-answer-body" d="{ap}" fill="url(#answer-ink)" filter="url(#dry-edge)"/>', *_stains(seed, heavy, "clip-heavy", "heavy"), *_stains(seed, answer, "clip-answer", "answer"), *_scratches(seed, heavy, "clip-heavy", "heavy"), *_scratches(seed, answer, "clip-answer", "answer"), '</g>', '<g id="ash-erasure">', f'<path d="M {heavy.cx+heavy.rx*.22:.2f} 330 C {heavy.cx+heavy.rx*.58:.2f} 510 {heavy.cx+heavy.rx*.28:.2f} 705 {heavy.cx+heavy.rx*.52:.2f} 880" fill="none" stroke="#D7CEBE" stroke-width="34" stroke-opacity=".22" filter="url(#ghost-blur)"/>', '</g>', *_exchange(seed, heavy, answer), '</g>', '<g id="ash-footer"><rect y="1080" width="1080" height="180" fill="#C9BEAB"/><line x1="84" x2="996" y1="1100" y2="1100" stroke="#3D3A35" stroke-opacity=".18"/><text x="540" y="1150" text-anchor="middle" fill="#26282A" font-family="Arial,sans-serif" font-size="25" letter-spacing="7">ASH-DAYLIGHT BLUES</text><text x="540" y="1193" text-anchor="middle" fill="#5B554C" font-family="Arial,sans-serif" font-size="10" letter-spacing="4">ERASURE · DELAY · ONE WRONG WEIGHT</text><text x="540" y="1225" text-anchor="middle" fill="#736B60" font-family="Arial,sans-serif" font-size="9" letter-spacing="2">CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM</text></g>', '</svg>']
    return ("\n".join(svg)+"\n").encode()


def write_outputs(seed: str, svg_path: Path, metadata_path: Path) -> tuple[Path, Path]:
    svg = render_svg(seed)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg)
    metadata_path.write_bytes(_canonical(metadata(seed, svg)))
    return svg_path, metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the dry, high-key opposite pole of D2 Blues.")
    parser.add_argument("--seed", default="d2-blues-ash-v1")
    parser.add_argument("--svg-output", type=Path, default=Path("artifacts/d2/posters/d2_blues_ash_pole.svg"))
    parser.add_argument("--metadata-output", type=Path, default=Path("artifacts/d2/posters/d2_blues_ash_pole.metadata.json"))
    args = parser.parse_args()
    write_outputs(args.seed, args.svg_output, args.metadata_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
