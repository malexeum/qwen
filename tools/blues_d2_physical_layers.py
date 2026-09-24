from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
from collections.abc import Sequence


@dataclass(frozen=True)
class BurialConfig:
    width: int = 1080
    art_height: int = 1080
    surface_y: float = 770.0
    left_x: float = 340.0
    right_x: float = 655.0
    contact_x: float = 510.0
    left_sink: float = 56.0
    right_sink: float = 46.0
    left_sigma: float = 190.0
    right_sigma: float = 170.0
    contact_ridge: float = 25.0
    ridge_sigma: float = 78.0
    darkness: float = 0.94
    foreground_opacity: float = 0.42
    sediment_count: int = 260


def seed_int(seed: bytes | str | int, salt: str) -> int:
    raw = seed if isinstance(seed, bytes) else str(seed).encode("utf-8")
    digest = hashlib.sha256(raw + b"\0" + salt.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _surface_y(x: float, cfg: BurialConfig) -> float:
    left = cfg.left_sink * math.exp(-((x - cfg.left_x) ** 2) / (2 * cfg.left_sigma**2))
    right = cfg.right_sink * math.exp(-((x - cfg.right_x) ** 2) / (2 * cfg.right_sigma**2))
    ridge = cfg.contact_ridge * math.exp(-((x - cfg.contact_x) ** 2) / (2 * cfg.ridge_sigma**2))
    current = 5 * math.sin(x / 155 + 0.35) + 2.5 * math.sin(x / 71 - 0.8)
    return cfg.surface_y + left + right - ridge + current


def _surface(cfg: BurialConfig, offset: float = 0, step: int = 12) -> list[tuple[float, float]]:
    return [(float(min(x, cfg.width)), _surface_y(float(min(x, cfg.width)), cfg) + offset) for x in range(0, cfg.width + step, step)]


def _open_path(points: Sequence[tuple[float, float]]) -> str:
    head, *tail = points
    return " ".join([f"M {head[0]:.2f} {head[1]:.2f}", *(f"L {x:.2f} {y:.2f}" for x, y in tail)])


def _bottom_path(points: Sequence[tuple[float, float]], cfg: BurialConfig) -> str:
    return f'{_open_path(points)} L {cfg.width} {cfg.art_height} L 0 {cfg.art_height} Z'


def physical_defs() -> list[str]:
    return [
        '<linearGradient id="d2-burial-back" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#101726" stop-opacity=".42"/>',
        '<stop offset=".24" stop-color="#090D17" stop-opacity=".82"/>',
        '<stop offset=".62" stop-color="#04060C" stop-opacity=".97"/>',
        '<stop offset="1" stop-color="#010207"/>',
        '</linearGradient>',
        '<linearGradient id="d2-burial-front" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#111827" stop-opacity=".02"/>',
        '<stop offset=".16" stop-color="#080C15" stop-opacity=".22"/>',
        '<stop offset=".58" stop-color="#03050A" stop-opacity=".58"/>',
        '<stop offset="1" stop-color="#010207" stop-opacity=".92"/>',
        '</linearGradient>',
        '<filter id="d2-burial-soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="22"/></filter>',
        '<filter id="d2-sediment-soft" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="5"/></filter>',
    ]


def burial_backdrop_svg(seed: bytes | str | int, cfg: BurialConfig | None = None) -> list[str]:
    cfg = cfg or BurialConfig()
    rng = random.Random(seed_int(seed, "burial-backdrop"))
    elements = ['<g id="d2-burial-backdrop">']
    elements.append(f'<path d="{_bottom_path(_surface(cfg), cfg)}" fill="url(#d2-burial-back)" fill-opacity="{cfg.darkness:.3f}"/>')
    for index, depth in enumerate((22, 48, 82, 124, 172)):
        decay = max(.25, 1 - index * .14)
        points = []
        for x in range(0, cfg.width + 13, 13):
            xx = float(min(x, cfg.width))
            local = cfg.surface_y + decay * (_surface_y(xx, cfg) - cfg.surface_y)
            wave = 3.2 * math.sin(xx / (92 + index * 17) + index * .73) + 1.5 * math.sin(xx / 43 - index * .37)
            points.append((xx, local + depth + wave))
        elements.append(f'<path d="{_open_path(points)}" fill="none" stroke="#293247" stroke-width="{1.15-index*.1:.2f}" stroke-opacity="{.13-index*.015:.3f}"/>')
    for _ in range(9):
        x = rng.uniform(90, cfg.width - 90)
        y = rng.uniform(_surface_y(x, cfg) + 28, cfg.art_height - 40)
        elements.append(f'<ellipse cx="{x:.2f}" cy="{y:.2f}" rx="{rng.uniform(42,125):.2f}" ry="{rng.uniform(14,42):.2f}" fill="#263148" fill-opacity="{rng.uniform(.025,.075):.4f}" filter="url(#d2-sediment-soft)"/>')
    elements.append('</g>')
    return elements


def burial_foreground_svg(seed: bytes | str | int, cfg: BurialConfig | None = None) -> list[str]:
    cfg = cfg or BurialConfig()
    rng = random.Random(seed_int(seed, "burial-foreground"))
    elements = ['<g id="d2-burial-foreground">']
    elements.append(f'<path d="{_bottom_path(_surface(cfg, 18), cfg)}" fill="url(#d2-burial-front)" fill-opacity="{cfg.foreground_opacity:.3f}"/>')
    for _ in range(cfg.sediment_count):
        x = rng.uniform(18, cfg.width - 18)
        sy = _surface_y(x, cfg) + 12
        available = max(1, cfg.art_height - sy - 8)
        depth = rng.random() ** .58 * available
        y = sy + depth
        radius = rng.uniform(.35, 1.15) * (.75 + .45 * depth / available)
        opacity = rng.uniform(.018, .070)
        color = rng.choice(("#A6ADBA", "#667085", "#41495A", "#171D29"))
        elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity="{opacity:.4f}"/>')
    elements.append('</g>')
    return elements


def tactile_void_svg(seed: bytes | str | int, width: int = 1080, height: int = 1080, strength: float = 1.0, grain_count: int = 2800) -> list[str]:
    rng = random.Random(seed_int(seed, "tactile-void"))
    strength = max(0, min(2, strength))
    elements = ['<g id="d2-tactile-photographic-void" pointer-events="none" shape-rendering="crispEdges">']
    for _ in range(grain_count):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        upper = 1 + .28 * max(0, 1 - y / (height * .72))
        opacity = rng.uniform(.012, .052) * strength * upper
        color = rng.choice(("#D8D8D5", "#AEB2B8", "#777D88")) if rng.random() > .38 else rng.choice(("#010208", "#05070C", "#0B0D12"))
        size = rng.uniform(.28, .92)
        elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{size:.2f}" height="{size:.2f}" fill="{color}" fill-opacity="{opacity:.4f}"/>')
    for _ in range(42):
        x, y, length = rng.uniform(30, width - 30), rng.uniform(20, height - 20), rng.uniform(3, 17)
        angle = rng.gauss(0, .14)
        elements.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x+math.cos(angle)*length:.2f}" y2="{y+math.sin(angle)*length:.2f}" stroke="#C9C8C4" stroke-width=".45" stroke-opacity="{rng.uniform(.012,.035)*strength:.4f}"/>')
    elements.append('</g>')
    return elements
