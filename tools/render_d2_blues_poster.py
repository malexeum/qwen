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
RENDERER_VERSION = "1.6"
VIEWBOX = "0 0 1080 1260"
PALETTE = {
    "background": "#03050A", "ink": "#D8D8D5", "muted": "#737986",
    "blue": "#315E8E", "ember": "#A35B2B", "violet": "#44374F",
    "blue_note": "#5B4FA8",
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
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _body_specs(seed: str) -> tuple[BodySpec, BodySpec]:
    rng = random.Random(seed_int(seed, "body-proportions-v15"))
    dominance = rng.uniform(1.38, 2.58)
    left_rx = rng.uniform(238, 278)
    left_ry = rng.uniform(300, 348)
    right_ry = rng.uniform(224, 278)
    right_rx = left_rx * left_ry / (dominance * right_ry)
    left = BodySpec(326 + rng.uniform(-18, 14), 600 + rng.uniform(-24, 20), left_rx, left_ry, 30, "left-body-v15")
    right = BodySpec(704 + rng.uniform(-12, 24), 518 + rng.uniform(-30, 24), right_rx, right_ry, 28, "right-body-v15")
    ratio = left.area_proxy / right.area_proxy
    if not 1.35 <= ratio <= 2.65:
        raise AssertionError(f"D2 area ratio outside visual contract: {ratio:.3f}")
    return left, right


def _blob(seed: str, body: BodySpec, salt: str, scale: float = 1.0, roughness: float = 1.0) -> str:
    rng = random.Random(seed_int(seed, salt))
    phases = [rng.uniform(0, math.tau) for _ in range(3)]
    pts: list[tuple[float, float]] = []
    for i in range(body.points):
        a = math.tau * i / body.points
        m = 1 + roughness * (0.052 * math.sin(3*a+phases[0]) + 0.026 * math.sin(5*a+phases[1]) + 0.012 * math.sin(7*a+phases[2]))
        pts.append((body.cx + body.rx*scale*m*math.cos(a), body.cy + body.ry*scale*m*math.sin(a)))
    path = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(body.points):
        p0, p1, p2, p3 = pts[(i-1) % body.points], pts[i], pts[(i+1) % body.points], pts[(i+2) % body.points]
        c1 = (p1[0] + (p2[0]-p0[0])/6, p1[1] + (p2[1]-p0[1])/6)
        c2 = (p2[0] - (p3[0]-p1[0])/6, p2[1] - (p3[1]-p1[1])/6)
        path.append(f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}")
    return " ".join(path) + " Z"


def _smooth_open(points: list[tuple[float, float]]) -> str:
    path = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    last = len(points)-1
    for i in range(last):
        p0, p1, p2, p3 = points[max(0, i-1)], points[i], points[i+1], points[min(last, i+2)]
        c1 = (p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6)
        c2 = (p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6)
        path.append(f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}")
    return " ".join(path)


def _contact_points(seed: str, left: BodySpec, right: BodySpec) -> list[tuple[float, float]]:
    rng = random.Random(seed_int(seed, "contact-corridor-v15"))
    top = max(left.cy-.82*left.ry, right.cy-.86*right.ry)
    bottom = min(left.cy+.82*left.ry, right.cy+.86*right.ry)
    points: list[tuple[float, float]] = []
    for i in range(81):
        y = top + (bottom-top)*i/80
        ln, rn = (y-left.cy)/left.ry, (y-right.cy)/right.ry
        if abs(ln) >= 1 or abs(rn) >= 1:
            continue
        le = left.cx + left.rx*math.sqrt(max(0.0, 1-ln*ln))
        re = right.cx - right.rx*math.sqrt(max(0.0, 1-rn*rn))
        if le-re >= 7:
            points.append(((le+re)/2 + 4*math.sin((y-top)/58+.4) + rng.uniform(-1.2, 1.2), y))
    if len(points) < 7:
        x = (left.cx+left.rx+right.cx-right.rx)/2
        return [(x+3*math.sin(i*.8), top+(bottom-top)*i/8) for i in range(9)]
    return [points[round(i*(len(points)-1)/10)] for i in range(11)]


def _mist(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "mist-v15"))
    out = ['<g id="d2-settling-mist">']
    for _ in range(44):
        out.append(f'<ellipse cx="{rng.uniform(70,1010):.2f}" cy="{rng.uniform(230,925):.2f}" rx="{rng.uniform(18,110):.2f}" ry="{rng.uniform(5,24):.2f}" fill="#8A92A1" fill-opacity="{rng.uniform(.008,.036):.4f}" filter="url(#mist)"/>')
    return out + ['</g>']


def _polygons(seed: str) -> list[str]:
    rng = random.Random(seed_int(seed, "polygons-v15"))
    out = ['<g id="d2-random-polygons">']
    for _ in range(12):
        cx, cy, count = rng.uniform(80,1000), rng.uniform(80,900), rng.randint(3,6)
        pts = []
        for i in range(count):
            a, r = math.tau*i/count+rng.uniform(-.25,.25), rng.uniform(12,70)
            pts.append(f"{cx+r*math.cos(a):.2f},{cy+r*math.sin(a):.2f}")
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#687386" stroke-width=".7" stroke-opacity="{rng.uniform(.02,.07):.4f}"/>')
    return out + ['</g>']


def _afterimages(seed: str, left_path: str, right_path: str) -> list[str]:
    rng = random.Random(seed_int(seed, "afterimage-aab-v15"))
    lx, ly = rng.uniform(-18, -9), rng.uniform(7, 18)
    rx, ry = rng.uniform(8, 17), rng.uniform(-7, 12)
    return ['<g id="d2-afterimages" pointer-events="none" mask="url(#contact-gap-mask)">', f'<path d="{left_path}" transform="translate({lx:.2f} {ly:.2f})" fill="#263F61" fill-opacity=".10" filter="url(#afterimage-blur)"/>', f'<path d="{right_path}" transform="translate({rx:.2f} {ry:.2f})" fill="#8E5635" fill-opacity=".085" filter="url(#afterimage-blur)"/>', '</g>']


def _coffin_gravity(seed: str, contact_x: float) -> list[str]:
    rng = random.Random(seed_int(seed, "coffin-gravity-v15"))
    left, right = 170+rng.uniform(-18,18), 900+rng.uniform(-20,20)
    top, bottom = 744+rng.uniform(-8,10), 1018+rng.uniform(-8,8)
    inset = rng.uniform(48,72)
    path = f"M {left+inset:.2f} {top:.2f} L {right-inset:.2f} {top+5:.2f} L {right:.2f} {bottom-38:.2f} L {right-44:.2f} {bottom:.2f} L {left+42:.2f} {bottom:.2f} L {left:.2f} {bottom-42:.2f} Z"
    return ['<g id="d2-coffin-gravity" pointer-events="none">', f'<path d="{path}" fill="#160D0A" fill-opacity=".14" stroke="#5B463A" stroke-width="2.2" stroke-opacity=".055" filter="url(#coffin-soft)"/>', f'<path d="M {left+inset+42:.2f} {top+8:.2f} L {contact_x-34:.2f} {top+11:.2f}" stroke="#8A725F" stroke-width="1.2" stroke-opacity=".06"/>', '</g>']


def _tendons(seed: str, body: BodySpec, side: str, clip_id: str) -> list[str]:
    rng = random.Random(seed_int(seed, f"{side}-tendons-v15"))
    color, count = ("#94A9BE",3) if side == "left" else ("#D09A72",2)
    out=[f'<g id="d2-{side}-tendons" clip-path="url(#{clip_id})" fill="none" stroke-linecap="round" filter="url(#tendon-blur)">']
    for _ in range(count):
        x1=body.cx+rng.uniform(-.38,-.08)*body.rx; y1=body.cy+rng.uniform(-.35,.30)*body.ry
        x2=body.cx+rng.uniform(.08,.40)*body.rx; y2=body.cy+rng.uniform(-.30,.38)*body.ry
        bend=rng.uniform(-.18,.18)*body.ry
        out.append(f'<path d="M {x1:.2f} {y1:.2f} Q {body.cx+rng.uniform(-25,25):.2f} {(y1+y2)/2+bend:.2f} {x2:.2f} {y2:.2f}" stroke="{color}" stroke-width="{rng.uniform(3.6,6.8):.2f}" stroke-opacity="{rng.uniform(.065,.115):.4f}"/>')
    return out+['</g>']


def _pain_waterfall(seed: str, left: BodySpec, right: BodySpec, contact_x: float) -> list[str]:
    rng = random.Random(seed_int(seed, "pain-waterfall-v16"))
    out = ['<g id="d2-pain-waterfall" fill="none" stroke-linecap="round" pointer-events="none">']
    colors = ("#354B67", "#6B4B49", "#4B4662")
    for i in range(8):
        x, y0, y1, drift = rng.uniform(120,960), rng.uniform(170,310), rng.uniform(820,1010), rng.uniform(-42,42)
        out.append(f'<path data-stream="background" d="M {x:.2f} {y0:.2f} C {x+drift*.25:.2f} {y0+190:.2f} {x-drift*.35:.2f} {y1-190:.2f} {x+drift:.2f} {y1:.2f}" stroke="{colors[i%3]}" stroke-width="{rng.uniform(5,15):.2f}" stroke-opacity="{rng.uniform(.018,.052):.4f}" filter="url(#waterfall-blur)"/>')
    for body, clip_id, color in ((left,"clip-left-body","#6F8DAE"),(right,"clip-right-body","#B17655")):
        for _ in range(2):
            x = body.cx+rng.uniform(-.28,.28)*body.rx; y0=body.cy-rng.uniform(.45,.68)*body.ry; y1=body.cy+rng.uniform(.48,.72)*body.ry
            out.append(f'<path data-stream="internal" d="M {x:.2f} {y0:.2f} C {x+rng.uniform(-24,24):.2f} {body.cy-.18*body.ry:.2f} {x+rng.uniform(-28,28):.2f} {body.cy+.22*body.ry:.2f} {x+rng.uniform(-18,18):.2f} {y1:.2f}" clip-path="url(#{clip_id})" stroke="{color}" stroke-width="{rng.uniform(7,13):.2f}" stroke-opacity="{rng.uniform(.035,.065):.4f}" filter="url(#waterfall-blur)"/>')
    x=contact_x+rng.uniform(-4,4)
    out.append(f'<path data-stream="blue-note-fall" d="M {x-10:.2f} 278 C {x-2:.2f} 454 {x+8:.2f} 584 {x-4:.2f} 710 C {x-9:.2f} 756 {x+31:.2f} 783 {x+20:.2f} 850" stroke="#5B4FA8" stroke-width="6" stroke-opacity=".070" filter="url(#waterfall-blur)"/>')
    return out+['</g>']


def _delayed_embrace_arcs(seed: str, left: BodySpec, right: BodySpec, points: list[tuple[float,float]]) -> list[str]:
    rng=random.Random(seed_int(seed,"delayed-embrace-arcs-v16")); x,y=points[len(points)//2]; lag=rng.uniform(14,25)
    return ['<g id="d2-delayed-embrace-arcs" fill="none" stroke-linecap="round" pointer-events="none" filter="url(#embrace-blur)">',
        f'<path data-voice="call" d="M {left.cx-left.rx*.52:.2f} {left.cy-left.ry*.08:.2f} C {left.cx-left.rx*.08:.2f} {left.cy-left.ry*.34:.2f} {x-70:.2f} {y-78:.2f} {x-10:.2f} {y-18:.2f}" stroke="#7895B5" stroke-width="9" stroke-opacity=".070"/>',
        f'<path data-voice="delayed-response" d="M {right.cx+right.rx*.48:.2f} {right.cy+right.ry*.12+lag:.2f} C {right.cx+right.rx*.06:.2f} {right.cy+right.ry*.34+lag:.2f} {x+68:.2f} {y+76+lag:.2f} {x+11:.2f} {y+20+lag:.2f}" stroke="#B77951" stroke-width="8" stroke-opacity=".066"/>',
        f'<path data-voice="almost-embrace" d="M {x-86:.2f} {y+42:.2f} Q {x:.2f} {y-38:.2f} {x+82:.2f} {y+46:.2f}" stroke="#75647D" stroke-width="5" stroke-opacity=".058"/>','</g>']


def _aftertone_memory(seed: str, right: BodySpec) -> list[str]:
    rng=random.Random(seed_int(seed,"aftertone-memory-v15")); out=['<g id="d2-aftertone-memory" fill="none" stroke-linecap="round" filter="url(#memory-blur)">']
    for i in range(3):
        y=660+i*48+rng.uniform(-10,10); x1=right.cx+right.rx*.45+rng.uniform(-5,16); x2=rng.uniform(930,1035)
        out.append(f'<path d="M {x1:.2f} {y:.2f} C {x1+70:.2f} {y+rng.uniform(-8,10):.2f} {x2-80:.2f} {y+rng.uniform(8,22):.2f} {x2:.2f} {y+rng.uniform(14,30):.2f}" stroke="#8A91A0" stroke-width="{rng.uniform(2,4):.2f}" stroke-opacity="{rng.uniform(.018,.034):.4f}"/>')
    return out+['</g>']


def _organs(seed: str, body: BodySpec, side: str, clip_id: str) -> list[str]:
    rng = random.Random(seed_int(seed, f"{side}-organs-v15"))
    colors = ("#536F92", "#263F61", "#111E33", "#5B4FA8") if side == "left" else ("#91552F", "#684054", "#2A2333", "#5B4FA8")
    out = [f'<g id="d2-{side}-internal-organs" clip-path="url(#{clip_id})">']
    for i in range(7 if side == "left" else 5):
        organ = BodySpec(body.cx+rng.uniform(-.34,.34)*body.rx, body.cy+rng.uniform(-.38,.38)*body.ry, body.rx*rng.uniform(.12,.34), body.ry*rng.uniform(.08,.25), 18, f"{side}-organ-{i}")
        path = _blob(seed, organ, organ.salt, roughness=.62)
        out.append(f'<path d="{path}" fill="{colors[i%4]}" fill-opacity="{rng.uniform(.080,.165):.4f}" filter="url(#{"organ-deep" if i%2 else "organ-soft"})"/>')
    for i in range(2 if side == "left" else 1):
        cavity = BodySpec(body.cx+rng.uniform(-.25,.25)*body.rx, body.cy+rng.uniform(-.25,.25)*body.ry, body.rx*rng.uniform(.08,.16), body.ry*rng.uniform(.07,.14), 16, f"{side}-cavity-{i}")
        out.append(f'<path d="{_blob(seed,cavity,cavity.salt,roughness=.5)}" fill="#010207" fill-opacity="{rng.uniform(.12,.21):.4f}" filter="url(#organ-deep)"/>')
    return out + ['</g>']


def _call_response(left: BodySpec, right: BodySpec) -> list[str]:
    return ['<g id="d2-call-response" fill="none" stroke-linecap="round" filter="url(#organ-soft)">', f'<path d="M {left.cx-left.rx*.58:.2f} {left.cy-left.ry*.20:.2f} Q {left.cx:.2f} {left.cy-left.ry*.38:.2f} {left.cx+left.rx*.52:.2f} {left.cy-left.ry*.10:.2f}" stroke="#7691AE" stroke-width="7" stroke-opacity=".065" clip-path="url(#clip-left-body)"/>', f'<path d="M {right.cx-right.rx*.55:.2f} {right.cy+right.ry*.14:.2f} Q {right.cx:.2f} {right.cy+right.ry*.34:.2f} {right.cx+right.rx*.48:.2f} {right.cy+right.ry*.08:.2f}" stroke="#B77951" stroke-width="7" stroke-opacity=".07" clip-path="url(#clip-right-body)"/>', '</g>']


def _contact_flows(seed: str, points: list[tuple[float, float]]) -> list[str]:
    rng=random.Random(seed_int(seed,"contact-flows-v15")); out=['<g id="d2-contact-flows" fill="none" stroke-linecap="round">']
    for fraction,mode in ((.24,"attract"),(.50,"repel"),(.72,"unfinished")):
        x,y=points[round(fraction*(len(points)-1))]; span,rise=rng.uniform(52,88),rng.uniform(-18,18)
        if mode=="attract":
            path=f"M {x-span:.2f} {y+rise:.2f} C {x-span*.34:.2f} {y-rise:.2f} {x+span*.30:.2f} {y+rise:.2f} {x+span:.2f} {y-rise*.45:.2f}"
            out.append(f'<path data-mode="attract" d="{path}" stroke="url(#flow-lr)" stroke-width="8" stroke-opacity=".13" filter="url(#flow-glow)"/>')
        elif mode=="repel":
            for direction,color in ((-1,"#557DA9"),(1,"#9B6549")):
                path=f"M {x:.2f} {y:.2f} C {x+direction*18:.2f} {y+rise:.2f} {x+direction*span*.55:.2f} {y-rise:.2f} {x+direction*span:.2f} {y+rise*.65:.2f}"
                out.append(f'<path data-mode="repel" d="{path}" stroke="{color}" stroke-width="6" stroke-opacity=".105" filter="url(#flow-glow)"/>')
        else:
            path=f"M {x-span*.92:.2f} {y+rise:.2f} C {x-span*.48:.2f} {y-rise*.8:.2f} {x-span*.20:.2f} {y+rise*.4:.2f} {x-7:.2f} {y-4:.2f}"
            out.append(f'<path data-mode="unfinished" d="{path}" stroke="#78647D" stroke-width="7" stroke-opacity=".12" filter="url(#flow-glow)"/>')
    return out+['</g>']


def _counterflow(seed: str, left: BodySpec, right: BodySpec) -> list[str]:
    rng = random.Random(seed_int(seed, "counterflow-bands-v15"))
    out = ['<g id="d2-counterflow" fill="none" stroke-linecap="round" filter="url(#counterflow-blur)">']
    for body, color, direction in ((left,"#315E8E",1),(right,"#8C4E2B",-1)):
        for band in range(3):
            y = body.cy+(band-1)*body.ry*.24+rng.uniform(-12,12)
            out.append(f'<path d="M {body.cx-direction*body.rx*.62:.2f} {y:.2f} C {body.cx-body.rx*.16:.2f} {y+rng.uniform(-42,42):.2f} {body.cx+body.rx*.18:.2f} {y+rng.uniform(-42,42):.2f} {body.cx+direction*body.rx*.60:.2f} {y+rng.uniform(-10,10):.2f}" stroke="{color}" stroke-width="{rng.uniform(12,24):.2f}" stroke-opacity="{rng.uniform(.022,.052):.4f}"/>')
    return out + ['</g>']


def _blue_note(points: list[tuple[float, float]]) -> list[str]:
    x,y=points[round(.66*(len(points)-1))]
    path=f"M {x-100:.2f} {y+20:.2f} C {x-58:.2f} {y-16:.2f} {x-23:.2f} {y+14:.2f} {x-5:.2f} {y-1:.2f} L {x+8:.2f} {y+17:.2f} C {x+29:.2f} {y-21:.2f} {x+54:.2f} {y-25:.2f} {x+78:.2f} {y+4:.2f}"
    return ['<g id="d2-blue-note">',f'<path data-gesture="beautiful-error" d="{path}" fill="none" stroke="#5B4FA8" stroke-width="8" stroke-opacity=".13" stroke-linecap="round" stroke-linejoin="round" filter="url(#flow-glow)"/>',f'<ellipse cx="{x+8:.2f}" cy="{y+17:.2f}" rx="19" ry="9" fill="#5B4FA8" fill-opacity=".11" filter="url(#organ-soft)"/>','</g>']


def base_metadata(seed: str) -> dict[str, Any]:
    left, right = _body_specs(seed)
    return {"poster_id": POSTER_ID, "schema_version": SCHEMA_VERSION, "renderer": {"name": RENDERER_NAME, "version": RENDERER_VERSION}, "seed": seed, "canonical_outputs": {"svg_filename": "d2_blues_v1_poster.svg", "svg_viewbox": VIEWBOX}, "body_geometry": {"left": vars(left), "right": vars(right), "area_proxy_ratio": left.area_proxy/right.area_proxy}, "visual_contract": {"metaphor": "two unequal smoky bodies perform an A-A-B exchange inside the almost invisible coffin of time", "retained_layers": ["glow","settling_mist","random_polygons","turbulence","tactile_void"], "structural_layers": ["coffin_gravity","pain_waterfall","afterimages_aab","internal_organs","tendons","call_response","masked_contact_gap","contact_flows","delayed_embrace_arcs","counterflow","blue_note","aftertone_memory"], "warning": "CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM"}, "palette": PALETTE}


def render_svg(seed: str = "d2-blues-v1") -> bytes:
    left, right = _body_specs(seed)
    left_path, right_path = _blob(seed,left,left.salt), _blob(seed,right,right.salt)
    points = _contact_points(seed,left,right)
    seam, contact_x = _smooth_open(points), sum(x for x,_ in points)/len(points)
    cfg = BurialConfig(left_x=left.cx,right_x=right.cx,contact_x=contact_x,left_sink=72,right_sink=42,left_sigma=max(190,left.rx*.82),right_sigma=max(130,right.rx*.88),contact_ridge=21,foreground_opacity=.38,sediment_count=210)
    metadata = json.dumps(base_metadata(seed),sort_keys=True,separators=(",",":"),ensure_ascii=False).replace("&","&amp;").replace("<","&lt;")
    svg = ['<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="{VIEWBOX}" role="img" aria-labelledby="title desc">', f'<metadata>{metadata}</metadata>', '<title id="title">D2 — TWO-BODY BLUES</title>', '<desc id="desc">Two unequal smoky densities exchange pressure around an unresolved contact.</desc>', '<defs>', '<radialGradient id="body-left"><stop offset="0" stop-color="#315E8E" stop-opacity=".80"/><stop offset=".6" stop-color="#182B43" stop-opacity=".56"/><stop offset="1" stop-color="#080B12" stop-opacity=".04"/></radialGradient>', '<radialGradient id="body-right"><stop offset="0" stop-color="#A35B2B" stop-opacity=".66"/><stop offset=".58" stop-color="#44374F" stop-opacity=".48"/><stop offset="1" stop-color="#080B12" stop-opacity=".04"/></radialGradient>', '<linearGradient id="flow-lr"><stop offset="0" stop-color="#315E8E" stop-opacity="0"/><stop offset=".5" stop-color="#5B4FA8"/><stop offset="1" stop-color="#A35B2B" stop-opacity="0"/></linearGradient>', f'<clipPath id="clip-left-body"><path d="{left_path}"/></clipPath>', f'<clipPath id="clip-right-body"><path d="{right_path}"/></clipPath>', f'<mask id="contact-gap-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1080" height="1080"><rect width="1080" height="1080" fill="white"/><path d="{seam}" fill="none" stroke="black" stroke-width="15" stroke-linecap="round" filter="url(#gap-mask-soft)"/></mask>', '<filter id="glow" x="-55%" y="-55%" width="210%" height="210%"><feGaussianBlur stdDeviation="72"/></filter>', '<filter id="smoke-body" x="-55%" y="-55%" width="210%" height="210%"><feTurbulence type="fractalNoise" baseFrequency=".005 .012" numOctaves="3" seed="19" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="18" result="d"/><feGaussianBlur in="d" stdDeviation="22"/></filter>', '<filter id="mist" x="-40%" y="-100%" width="180%" height="300%"><feGaussianBlur stdDeviation="11"/></filter>', '<filter id="organ-soft" x="-60%" y="-80%" width="220%" height="260%"><feGaussianBlur stdDeviation="12"/></filter>', '<filter id="organ-deep" x="-70%" y="-90%" width="240%" height="280%"><feGaussianBlur stdDeviation="21"/></filter>', '<filter id="flow-glow" x="-70%" y="-150%" width="240%" height="400%"><feGaussianBlur stdDeviation="12"/></filter>', '<filter id="counterflow-blur" x="-40%" y="-80%" width="180%" height="260%"><feGaussianBlur stdDeviation="18"/></filter>', '<filter id="afterimage-blur"><feGaussianBlur stdDeviation="34"/></filter>', '<filter id="tendon-blur"><feGaussianBlur stdDeviation="8"/></filter>', '<filter id="memory-blur"><feGaussianBlur stdDeviation="10"/></filter>', '<filter id="coffin-soft"><feGaussianBlur stdDeviation="3"/></filter>', '<filter id="gap-mask-soft"><feGaussianBlur stdDeviation="3.2"/></filter>', '<filter id="waterfall-blur"><feGaussianBlur stdDeviation="13"/></filter>', '<filter id="embrace-blur"><feGaussianBlur stdDeviation="10"/></filter>', *physical_defs(), '</defs>', '<rect width="1080" height="1260" fill="#03050A"/>', '<g id="d2-artwork">', *_polygons(seed), *_mist(seed), *_coffin_gravity(seed,contact_x), *burial_backdrop_svg(seed,cfg), *_pain_waterfall(seed,left,right,contact_x), *_afterimages(seed,left_path,right_path), '<g id="d2-density-bodies" mask="url(#contact-gap-mask)">', f'<path d="{left_path}" fill="#315E8E" fill-opacity=".27" filter="url(#glow)"/>', f'<path id="d2-left-body" d="{left_path}" fill="url(#body-left)" fill-opacity=".50" filter="url(#smoke-body)"/>', f'<path d="{right_path}" fill="#A35B2B" fill-opacity=".23" filter="url(#glow)"/>', f'<path id="d2-right-body" d="{right_path}" fill="url(#body-right)" fill-opacity=".50" filter="url(#smoke-body)"/>', '<g id="d2-internal-organs">', *_organs(seed,left,"left","clip-left-body"), *_organs(seed,right,"right","clip-right-body"), *_tendons(seed,left,"left","clip-left-body"), *_tendons(seed,right,"right","clip-right-body"), '</g>', *_call_response(left,right), '</g>', '<g id="d2-contact-gap" data-gap="masked-void" pointer-events="none">', f'<path d="{seam}" fill="none" stroke="#8490A2" stroke-width="3" stroke-opacity=".035" stroke-linecap="round" filter="url(#flow-glow)"/>', '</g>', *_contact_flows(seed,points), *_delayed_embrace_arcs(seed,left,right,points), *_counterflow(seed,left,right), *_blue_note(points), *_aftertone_memory(seed,right), *burial_foreground_svg(seed,cfg), *tactile_void_svg(seed,1080,1080,.42,760), '</g>', '<g id="d2-footer"><rect y="1080" width="1080" height="180" fill="#03050A"/><line x1="84" x2="996" y1="1100" y2="1100" stroke="#737986" stroke-opacity=".26"/><text x="540" y="1150" text-anchor="middle" fill="#D8D8D5" font-family="Arial,sans-serif" font-size="27" letter-spacing="8">TWO-BODY BLUES</text><text x="540" y="1193" text-anchor="middle" fill="#737986" font-family="Arial,sans-serif" font-size="11" letter-spacing="4">DENSITY · COUNTERFLOW · UNRESOLVED CONTACT</text><text x="540" y="1225" text-anchor="middle" fill="#4A505A" font-family="Arial,sans-serif" font-size="9" letter-spacing="2">CONCEPTUAL VISUALIZATION — NOT A SPECTROGRAM</text></g>', '</svg>']
    return ("\n".join(svg)+"\n").encode("utf-8")


def build_metadata(seed: str, svg_bytes: bytes) -> bytes:
    data = base_metadata(seed)
    data["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    return canonical_json_bytes(data)


def write_outputs(seed: str, svg_path: Path, metadata_path: Path) -> tuple[Path, Path]:
    svg = render_svg(seed)
    svg_path.parent.mkdir(parents=True,exist_ok=True)
    metadata_path.parent.mkdir(parents=True,exist_ok=True)
    svg_path.write_bytes(svg)
    metadata_path.write_bytes(build_metadata(seed,svg))
    return svg_path, metadata_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render the canonical D2 two-body Blues SVG and metadata.")
    p.add_argument("--seed",default="d2-blues-v1")
    p.add_argument("--svg-output",type=Path,default=Path("artifacts/d2/posters/d2_blues_v1_poster.svg"))
    p.add_argument("--metadata-output",type=Path,default=Path("artifacts/d2/posters/d2_blues_v1_poster.metadata.json"))
    return p.parse_args()


def main() -> int:
    a = parse_args()
    write_outputs(a.seed,a.svg_output,a.metadata_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
