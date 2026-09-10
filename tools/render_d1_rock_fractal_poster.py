from __future__ import annotations
import random

import argparse
import hashlib
import html
import json
import math
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_repo_root_text = str(REPO_ROOT)
if _repo_root_text not in sys.path:
    sys.path.insert(0, _repo_root_text)

from lib.d1_feature_artifact_io import read_feature_artifact

POSTER_ID = "d1_rock_v1_fractal_poster"
POSTER_SCHEMA_VERSION = "d1_fractal_poster_metadata/v1"
RENDERER_NAME = "d1_rock_fractal_poster_renderer"
RENDERER_VERSION = "1"
PUBLICATION_COMMIT = "367a33e53f7be0c7c619c3ab2c8c1a5fc0bdd1c2"

CANONICAL_VIEWBOX = "0 0 1080 1080"
CANONICAL_SIZE_PX = 1080
ARTIFACT_RELATIVE_PATH = Path("artifacts/d1/features/d1_rock_v1.json")

SVG_FILENAME = "d1_rock_v1_fractal_poster.svg"
METADATA_FILENAME = "d1_rock_v1_fractal_poster.metadata.json"

PALETTE = {
    "audit_cyan": "#46D9E8",
    "background": "#070A12",
    "border": "#253249",
    "primary_text": "#E9EEF8",
    "rock_magenta": "#C75CEB",
    "secondary_text": "#9AA8BD",
    "semantic_green": "#7CE3A1",
    "theta_gold": "#F6C85F",
}

RIGHT_ARROW = "\u2192"
MIDDLE_DOT = "\u00b7"

_SVG_TITLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]*\Z")
_HEX_DIGEST_RE = re.compile(r"sha256:([0-9a-f]{16,64})\Z")


class FractalPosterContractError(ValueError):
    """Raised when an artifact cannot produce a valid fractal poster."""


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def canonical_json_bytes(data: Any) -> bytes:
    return (
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise FractalPosterContractError(f"{field} must be a non-empty string")
    return value


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FractalPosterContractError(f"{field} must be a positive integer")
    return value


def _display_title_from_locator(locator: Mapping[str, Any] | None) -> str:
    if not isinstance(locator, Mapping) or set(locator) != {"registry_path"}:
        raise FractalPosterContractError(
            "source_locator must contain exactly registry_path"
        )

    registry_path = _require_string(
        locator["registry_path"],
        "source_locator.registry_path",
    )
    if "\\" in registry_path or registry_path.startswith("/"):
        raise FractalPosterContractError(
            "source_locator.registry_path must be a relative POSIX path"
        )

    basename = registry_path.rsplit("/", 1)[-1]
    if (
        basename in {"", ".", ".."}
        or not _SVG_TITLE_RE.fullmatch(basename)
        or basename.startswith(".")
    ):
        raise FractalPosterContractError(
            "source_locator.registry_path has an invalid basename"
        )

    return basename.upper()


def _artifact_display_data(artifact_path: Path) -> dict[str, Any]:
    artifact = read_feature_artifact(artifact_path)

    if artifact.analysis_id != "d1_rock_v1":
        raise FractalPosterContractError(
            "fractal poster renderer accepts only d1_rock_v1"
        )
    if artifact.schema_version != "d1_feature_artifact/v2":
        raise FractalPosterContractError(
            "fractal poster renderer requires d1_feature_artifact/v2"
        )

    source_identity = artifact.source_identity
    source_content_sha256 = _require_string(
        source_identity.get("content_sha256"),
        "source_identity.content_sha256",
    )
    source_byte_size = _require_int(
        source_identity.get("byte_size"),
        "source_identity.byte_size",
    )
    source_title = _display_title_from_locator(artifact.source_locator)

    theta_hash = _require_string(
        artifact.canonical_theta_hash,
        "canonical_theta_hash",
    )
    feature_hash = _require_string(
        artifact.feature_sha256,
        "feature_sha256",
    )
    if not _HEX_DIGEST_RE.fullmatch(theta_hash):
        raise FractalPosterContractError(
            "canonical_theta_hash must be sha256-prefixed hexadecimal"
        )
    if not _HEX_DIGEST_RE.fullmatch(feature_hash):
        raise FractalPosterContractError(
            "feature_sha256 must be sha256-prefixed hexadecimal"
        )

    return {
        "analysis_id": artifact.analysis_id,
        "canonical_theta_hash": theta_hash,
        "feature_sha256": feature_hash,
        "git_sha": _require_string(artifact.git_sha, "git_sha"),
        "schema_version": artifact.schema_version,
        "source_byte_size": source_byte_size,
        "source_content_sha256": source_content_sha256,
        "source_locator_registry_path": artifact.source_locator["registry_path"],
        "source_title": source_title,
    }


def _seed_bytes(data: Mapping[str, Any]) -> bytes:
    material = (
        f"{data['canonical_theta_hash']}|{data['feature_sha256']}"
    ).encode("utf-8")
    return hashlib.sha256(material).digest()


def seed_hex(data: Mapping[str, Any]) -> str:
    return f"sha256:{_seed_bytes(data).hex()}"


def _svg_text(
    x: float,
    y: float,
    text: str,
    *,
    css_class: str,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css_class}" '
        f'text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def _seed_fraction(seed: bytes, index: int) -> float:
    return seed[index % len(seed)] / 255.0


def _point(x: float, y: float) -> str:
    return f"{x:.2f},{y:.2f}"


def _crystal_polygon(
    x: float,
    y: float,
    radius: float,
    sides: int,
    rotation: float,
) -> str:
    points = []
    for index in range(sides):
        angle = rotation + 2.0 * math.pi * index / sides
        points.append(
            _point(
                x + radius * math.cos(angle),
                y + radius * math.sin(angle),
            )
        )
    return " ".join(points)


def build_sacred_mandala(
    cx: float,
    cy: float,
    bridge_params: Mapping[str, Any],
    palette: Mapping[str, str],
    rng: random.Random,
) -> str:
    symmetry = float(bridge_params.get("symmetry", 0.5))
    line_density = float(bridge_params.get("line_density", 0.5))
    drive = float(bridge_params.get("drive", 0.4))
    grain = float(bridge_params.get("grain", 0.5))
    tension = float(bridge_params.get("tension", 0.0))
    mode = str(bridge_params.get("dominant_mode", "structure"))

    col_gold = palette.get("halo_gold", palette.get("theta_gold", "#F6C85F"))
    col_cyan = palette.get("audit_cyan", "#46D9E8")
    col_magenta = palette.get("rock_magenta", "#EA580C")
    col_bg = palette.get("bg_primary", "#0B0F17")

    elements = ['<g id="sacred-mandala-master">']

    # 1. СТУТУ:  (ХЫ  ЫХ Ц)
    if mode == "structure":
        base_r = 150.0 + symmetry * 100.0
        num_strands = int(50 + line_density * 45)
        
        # егкие органические переплетающиеся хорды
        for s in range(num_strands):
            ang1 = rng.uniform(0.0, 2.0 * math.pi)
            span = rng.uniform(1.2, 2.6)
            ang2 = ang1 + span + rng.uniform(-0.15, 0.15)
            
            r_var1 = base_r * rng.uniform(0.35, 1.0)
            r_var2 = base_r * rng.uniform(0.35, 1.0)
            
            x1 = cx + r_var1 * math.cos(ang1)
            y1 = cy + r_var1 * math.sin(ang1)
            x2 = cx + r_var2 * math.cos(ang2)
            y2 = cy + r_var2 * math.sin(ang2)
            
            bend_dist = rng.uniform(-18.0, 18.0)
            mx = (x1 + x2) * 0.5 + bend_dist * math.cos(ang1 + math.pi * 0.5)
            my = (y1 + y2) * 0.5 + bend_dist * math.sin(ang1 + math.pi * 0.5)
            
            str_op = rng.uniform(0.08, 0.22) + line_density * 0.1
            elements.append(
                f'<path d="M {x1:.2f} {y1:.2f} Q {mx:.2f} {my:.2f} {x2:.2f} {y2:.2f}" fill="none" '
                f'stroke="{col_gold}" stroke-width="0.45" stroke-opacity="{str_op:.2f}" />'
            )

    # 2. : УТ
    else:
        elements.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="130.0" fill="{col_bg}" fill-opacity="0.85" filter="url(#core-glow)" />'
        )
        base_r = 150.0 + rng.uniform(40.0, 120.0) + (1.0 - drive) * 60.0
        num_layers = rng.choice([2, 3, 4])
        available_colors = [col_gold, col_magenta, col_cyan]
        rng.shuffle(available_colors)
        base_phase = rng.uniform(0.0, math.pi)

        for l_idx in range(num_layers):
            layer_frac = (l_idx + 1) / num_layers
            r_layer = base_r * (0.35 + 0.65 * layer_frac)
            petal_count = rng.choice([7, 9, 11, 13, 15])
            col_layer = available_colors[l_idx % len(available_colors)]
            fill_op = max(0.05, 0.26 - l_idx * 0.06)
            stroke_op = max(0.40, 0.85 - l_idx * 0.10)
            sw = max(0.6, 1.6 - l_idx * 0.3)
            spread = 0.25 + 0.35 * (1.0 - layer_frac * 0.5)

            for i in range(petal_count):
                ang = (2.0 * math.pi * i / petal_count) + base_phase + (l_idx * 0.22)
                jitter_r = r_layer * rng.uniform(0.94, 1.06)
                w = spread * 0.6
                p0_x = cx + jitter_r * 0.2 * math.cos(ang - w)
                p0_y = cy + jitter_r * 0.2 * math.sin(ang - w)
                p1_x = cx + jitter_r * 0.2 * math.cos(ang + w)
                p1_y = cy + jitter_r * 0.2 * math.sin(ang + w)
                tip_x = cx + jitter_r * math.cos(ang)
                tip_y = cy + jitter_r * math.sin(ang)
                c1_x = cx + jitter_r * 0.65 * math.cos(ang - spread)
                c1_y = cy + jitter_r * 0.65 * math.sin(ang - spread)
                c2_x = cx + jitter_r * 0.65 * math.cos(ang + spread)
                c2_y = cy + jitter_r * 0.65 * math.sin(ang + spread)

                d_petal = (
                    f"M {p0_x:.2f} {p0_y:.2f} "
                    f"C {c1_x:.2f} {c1_y:.2f}, {tip_x:.2f} {tip_y:.2f}, {tip_x:.2f} {tip_y:.2f} "
                    f"C {tip_x:.2f} {tip_y:.2f}, {c2_x:.2f} {c2_y:.2f}, {p1_x:.2f} {p1_y:.2f} Z"
                )
                elements.append(
                    f'<path d="{d_petal}" fill="{col_layer}" fill-opacity="{fill_op:.2f}" '
                    f'stroke="{col_layer}" stroke-width="{sw:.2f}" stroke-opacity="{stroke_op:.2f}" />'
                )

    # 3. СТЩС 
    heart_r = 28.0 + line_density * 8.0
    elements.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{heart_r * 1.4:.2f}" fill="{col_gold}" fill-opacity="0.30" filter="url(#core-glow)" />'
    )
    elements.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{heart_r:.2f}" fill="url(#sacred-heart)" stroke="{col_gold}" stroke-width="1.4" opacity="0.98"/>'
    )
    elements.append('</g>')
    return "".join(elements)


def _solaris_ocean_currents(
    cx: float,
    cy: float,
    bridge_params: Mapping[str, Any],
    palette: Mapping[str, str],
    rng: random.Random,
) -> list[str]:
    """
    агическое нелинейное флюидное пространство кеана Соляриса:
    амильтоново поле линий тока (Streamfunction psi) с сохранением несжимаемости,
    асимметричные вихревые сингулярности разного масштаба,
    невесомые эфирные шлейфы (fill-opacity 0.009..0.022) с глубоким наложением.
    икаких жестких бубликов, полосок или волос.
    """
    elements = ['<g id="solaris-ocean-layer">']

    drive = float(bridge_params.get("drive", 0.4))
    tension = float(bridge_params.get("tension", 0.0))
    line_density = float(bridge_params.get("line_density", 0.5))
    grain = float(bridge_params.get("grain", 0.5))

    col_cyan = palette.get("audit_cyan", "#46D9E8")
    col_magenta = palette.get("rock_magenta", "#EA580C")
    col_gold = palette.get("theta_gold", "#F6C85F")
    palette_pool = [col_cyan, col_magenta, col_gold]

    # СТЫ ХЫ СУСТ (СТ ХСТ  СЫ  )
    # аспределены органично в объеме, создавая богатейший гидродинамический рельеф
    vortex_nodes = [
        {"x": cx + 180.0, "y": cy - 160.0, "gamma": 140.0 + drive * 40.0, "core": 120.0},
        {"x": cx - 220.0, "y": cy + 140.0, "gamma": -110.0 - tension * 35.0, "core": 140.0},
        {"x": cx - 140.0, "y": cy - 230.0, "gamma": 75.0, "core": 95.0},
        {"x": cx + 240.0, "y": cy + 190.0, "gamma": -85.0, "core": 110.0},
        {"x": cx - 40.0,  "y": cy + 320.0, "gamma": 60.0, "core": 130.0},
    ]

    # Скорость несжимаемого течения через градиенты потенциала тока: v = (d_psi/dy, -d_psi/dx)
    def flow_velocity(px: float, py: float, flow_seed: float):
        vx = 0.0
        vy = 0.0

        for vn in vortex_nodes:
            dx = px - vn["x"]
            dy = py - vn["y"]
            r2 = dx * dx + dy * dy + vn["core"] * vn["core"]
            inv_r2 = vn["gamma"] / r2
            # Тангенциальная скорость вихря
            vx += -dy * inv_r2 * 26.0
            vy +=  dx * inv_r2 * 26.0

        # Фоновый анизотропный дрейф океанических глубин
        drift_angle = 0.65 + math.sin(py * 0.003 + flow_seed) * 0.4
        vx += math.cos(drift_angle) * (14.0 + drive * 6.0)
        vy += math.sin(drift_angle) * (8.0 - tension * 4.0)

        # ягкий обтекаемый буфер вокруг светящегося цветка
        dcx, dcy = px - cx, py - cy
        dist_c = math.hypot(dcx, dcy) + 1.0
        if dist_c < 220.0:
            push = math.pow((220.0 - dist_c) / 220.0, 1.4)
            vx += (dcx / dist_c) * push * 32.0
            vy += (dcy / dist_c) * push * 32.0

        return vx, vy

    # Ц ФЫХ ЫХ СС (СЫ ШФЫ)
    num_shrouds = int(22 + line_density * 8)
    steps = 46
    dt = 1.35

    for s_idx in range(num_shrouds):
        # Стартовые позиции распылены по периферии и глубине пространства
        ang = (2.0 * math.pi / num_shrouds) * s_idx + rng.uniform(-0.18, 0.18)
        dist = rng.uniform(320.0, 560.0)
        cur_x = cx + dist * math.cos(ang)
        cur_y = cy + dist * math.sin(ang) * 0.85

        pts_l = []
        pts_r = []
        color = palette_pool[s_idx % len(palette_pool)]
        shroud_seed = s_idx * 0.73

        # нтегрирование траектории и эволюции ширины шлейфа
        for st in range(steps + 1):
            t = st / float(steps)

            vx, vy = flow_velocity(cur_x, cur_y, shroud_seed)
            v_mag = math.hypot(vx, vy) or 1.0
            nx, ny = -vy / v_mag, vx / v_mag

            # лавная, непрерывная дымная толщина (от 20 до 75px)
            # ависит от скорости течения: где поток быстрее — там струя тоньше и острее
            speed_factor = min(2.2, max(0.6, 24.0 / v_mag))
            base_w = (28.0 + grain * 26.0) * math.sin(t * math.pi) * speed_factor

            pts_l.append((cur_x + nx * base_w, cur_y + ny * base_w))
            pts_r.append((cur_x - nx * base_w, cur_y - ny * base_w))

            # Шаг переноса массы
            cur_x += vx * dt
            cur_y += vy * dt

            # редел холста
            if math.hypot(cur_x - cx, cur_y - cy) > 680.0:
                break

        if len(pts_l) > 5:
            path_cmds = [f"M {pts_l[0][0]:.2f} {pts_l[0][1]:.2f}"]
            for p in pts_l[1:]:
                path_cmds.append(f"L {p[0]:.2f} {p[1]:.2f}")
            for p in reversed(pts_r):
                path_cmds.append(f"L {p[0]:.2f} {p[1]:.2f}")
            path_cmds.append("Z")

            veil_d = " ".join(path_cmds)

            # ТШ, С СТЦСТ: 0.011..0.024
            # ри наложении десятков слоев дает глубокое, шелковое объемное свечение без плотных полос
            alpha = (0.012 + grain * 0.010) * (1.15 if s_idx % 2 == 0 else 0.85)

            elements.append(
                f'<path d="{veil_d}" fill="{color}" fill-opacity="{alpha:.4f}" '
                f'stroke="none" />'
            )

    elements.append('</g>')
    return elements


def _branch_geometry(
    seed: bytes,
    bridge_params: Mapping[str, Any] | None = None,
) -> list[str]:
    elements: list[str] = []
    palette_cycle = (
        PALETTE.get("rock_magenta", "#EA580C"),
        PALETTE.get("audit_cyan", "#46D9E8"),
        PALETTE.get("theta_gold", "#F6C85F"),
    )

    bp = bridge_params or {}
    junction = bp.get("junction") if isinstance(bp.get("junction"), Mapping) else {}
    cx = float(junction.get("x", 540.0))
    cy = float(junction.get("y", 540.0))
    drive = float(bp.get("drive", 0.4))
    line_density = float(bp.get("line_density", 0.5))
    grain = float(bp.get("grain", 0.5))
    tension = float(bp.get("tension", 0.0))

    seed_int = int.from_bytes(seed[:8], "big")
    rng = random.Random(seed_int)

    # 0. лубокое космическое пятно
    elements.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="450" fill="url(#space-ambient)" />'
    )
    elements.extend(_solaris_ocean_currents(cx, cy, bp, PALETTE, rng))

    # 1. ЦЫ С: 3 Ы Т (Х 6 ЩУЦ!)
    # асовый ствол идет преимущественно вниз (гравитация рока), два боковых крыла расходятся влево-вверх и вправо
    main_stems = [
        {"base_phi": math.pi * 0.5 + rng.choice([-0.28, 0.28]), "weight": 1.4, "len": 390.0 + drive * 150.0}, # ощный ствол вниз
        {"base_phi": math.pi * 1.05 + rng.uniform(-0.25, 0.15), "weight": 1.0, "len": 320.0 + drive * 120.0}, # евое крыло
        {"base_phi": -math.pi * 0.08 + rng.uniform(-0.15, 0.25), "weight": 1.1, "len": 340.0 + drive * 130.0}, # равое крыло
    ]

    # сли высокий драйв трека — может пробиться 4-й тонкий побег наверх
    if drive > 0.65 or rng.random() < 0.25:
        main_stems.append({"base_phi": -math.pi * 0.5 + rng.uniform(-0.3, 0.3), "weight": 0.7, "len": 260.0})

    bud_points = []

    def to_smooth_svg(points):
        if len(points) < 2:
            return ""
        d = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
        for i in range(1, len(points)):
            d.append(f"L {points[i][0]:.2f} {points[i][1]:.2f}")
        return " ".join(d)

    # 2. С СТ Ы (СТ СЦЫ)
    for stem_idx, stem in enumerate(main_stems):
        phi = stem["base_phi"]
        total_len = stem["len"]
        col_wood = palette_cycle[stem_idx % len(palette_cycle)]
        col_vine = palette_cycle[(stem_idx + 1) % len(palette_cycle)]

        steps = 55
        spine_pts = []
        vine_pts = []

        # узыкальные случайные узлы роста (индивидуальные для каждой ветки!)
        growth_nodes = sorted([rng.uniform(0.15, 0.90) for _ in range(rng.randint(3, 5))])

        for s in range(steps + 1):
            t = s / float(steps)
            dist = total_len * t

            # стественный прогиб под весом (гравитация)
            grav_drop = (1.2 - drive * 0.4) * 110.0 * (t ** 1.7) if math.sin(phi) > -0.2 else -20.0 * (t**1.4)

            # лавный свивающийся изгиб основного древесного ствола
            wood_bend = math.sin(t * math.pi * 2.2 + stem_idx * 1.5) * (42.0 + tension * 28.0) * math.sin(t * math.pi * 0.95)

            px = cx + dist * math.cos(phi) - wood_bend * math.sin(phi)
            py = cy + dist * math.sin(phi) + wood_bend * math.cos(phi) + grav_drop
            spine_pts.append((px, py))

            #  Щ Т ( СУС,  У Т):
            # на прижимается к стволу в узлах роста и отходит свободной дугой между ними
            nearest_node_dist = min([abs(t - node) for node in growth_nodes])
            loop_amplitude = (18.0 + grain * 16.0) * math.sin(nearest_node_dist * math.pi * 3.5) * math.sin(t * math.pi)

            nx = -math.sin(phi)
            ny = math.cos(phi)
            vx = px + nx * loop_amplitude
            vy = py + ny * loop_amplitude
            vine_pts.append((vx, vy))

            if s == steps:
                bud_points.append((px, py, 5.0 + line_density * 2.0))

        # трисовка основного гибкого ствола
        elements.append(
            f'<path d="{to_smooth_svg(spine_pts)}" fill="none" stroke="{col_wood}" '
            f'stroke-width="{2.0 * stem["weight"]:.2f}" stroke-opacity="0.92" stroke-linecap="round" stroke-linejoin="round" />'
        )
        # трисовка обвивающей живой лозы
        elements.append(
            f'<path d="{to_smooth_svg(vine_pts)}" fill="none" stroke="{col_vine}" '
            f'stroke-width="{1.2 * stem["weight"]:.2f}" stroke-opacity="0.80" stroke-linecap="round" stroke-linejoin="round" />'
        )

        # 3. Т УСЫ  Ы Т  У СТ
        for node_t in growth_nodes:
            node_idx = int(node_t * steps)
            if node_idx < len(spine_pts):
                nx, ny = spine_pts[node_idx]
                shoot_angle = phi + rng.choice([-1.0, 1.0]) * rng.uniform(0.6, 1.3)
                shoot_len = rng.uniform(70.0, 160.0)

                sh_pts = []
                for ss in range(18):
                    st = ss / 17.0
                    curve = math.sin(st * math.pi * 1.6) * 14.0
                    sx = nx + shoot_len * st * math.cos(shoot_angle) - curve * math.sin(shoot_angle)
                    sy = ny + shoot_len * st * math.sin(shoot_angle) + curve * math.cos(shoot_angle) + 40.0 * (st ** 1.6)
                    sh_pts.append((sx, sy))
                    if ss == 17:
                        bud_points.append((sx, sy, 3.2 + line_density * 1.5))

                elements.append(
                    f'<path d="{to_smooth_svg(sh_pts)}" fill="none" stroke="{col_wood}" '
                    f'stroke-width="0.85" stroke-opacity="0.75" stroke-linecap="round" />'
                )

    # 4. СТЩС ТЫ СЫ
    col_gold = PALETTE.get("theta_gold", "#F6C85F")
    for bx, by, br in bud_points:
        elements.append(
            f'<circle cx="{bx:.2f}" cy="{by:.2f}" r="{br*2.2:.2f}" fill="{col_gold}" fill-opacity="0.22" filter="url(#core-glow)" />'
        )
        elements.append(
            f'<circle cx="{bx:.2f}" cy="{by:.2f}" r="{br:.2f}" fill="{col_gold}" fill-opacity="0.95" />'
        )

    # 5.  Х С
    elements.append(build_sacred_mandala(cx, cy, bp, PALETTE, rng))
    return elements


def _gravitational_dripping(
    seed: bytes,
    bridge_params: Mapping[str, Any] | None = None,
) -> list[str]:
    bp = bridge_params or {}
    junction = bp.get("junction") if isinstance(bp.get("junction"), Mapping) else {}
    cx = float(junction.get("x", 540.0))
    cy = float(junction.get("y", 540.0))
    grain = float(bp.get("grain", 0.5))
    drive = float(bp.get("drive", 0.4))
    tension = float(bp.get("tension", 0.0))

    col_gold = PALETTE.get("theta_gold", "#F6C85F")
    col_cyan = PALETTE.get("audit_cyan", "#46D9E8")
    col_magenta = PALETTE.get("rock_magenta", "#C75CEB")
    drip_colors = [col_gold, col_magenta, col_cyan]

    seed_int = int.from_bytes(seed[4:12], "big")
    rng = random.Random(seed_int)

    elements = ['<g id="gravitational-dripping-spatter">']

    # 1. Струйки туши
    num_trails = int(3 + grain * 4)
    for _ in range(num_trails):
        start_x = cx + rng.uniform(-130.0, 130.0)
        start_y = cy + rng.uniform(50.0, 200.0)
        trail_len = rng.uniform(40.0, 140.0) + drive * 60.0
        c_trail = rng.choice(drip_colors)
        w_trail = rng.uniform(0.35, 0.70)
        op_trail = rng.uniform(0.12, 0.28)

        ctrl_x = start_x + rng.uniform(-5.0, 5.0)
        end_x = start_x + rng.uniform(-10.0, 10.0)
        end_y = start_y + trail_len

        elements.append(
            f'<path d="M {start_x:.2f} {start_y:.2f} Q {ctrl_x:.2f} {start_y + trail_len*0.5:.2f} {end_x:.2f} {end_y:.2f}" '
            f'fill="none" stroke="{c_trail}" stroke-width="{w_trail:.2f}" stroke-opacity="{op_trail:.3f}" stroke-linecap="round" />'
        )
        r_drop = rng.uniform(1.2, 2.4)
        elements.append(
            f'<ellipse cx="{end_x:.2f}" cy="{end_y + r_drop:.2f}" rx="{r_drop*0.8:.2f}" ry="{r_drop*1.3:.2f}" '
            f'fill="{c_trail}" fill-opacity="{op_trail * 1.4:.3f}" />'
        )

    # 2. икрокапли и взвесь
    num_drips = int(14 + grain * 20 + drive * 12)
    for _ in range(num_drips):
        spread_x = rng.gauss(0.0, 100.0 + tension * 35.0)
        drop_x = cx + spread_x
        drop_y = cy + rng.uniform(80.0, 480.0)
        c_spatter = rng.choice(drip_colors)
        rx = rng.uniform(0.6, 1.7)
        ry = rx * rng.uniform(1.2, 2.2)
        op_spatter = rng.uniform(0.10, 0.40)
        elements.append(
            f'<ellipse cx="{drop_x:.2f}" cy="{drop_y:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'fill="{c_spatter}" fill-opacity="{op_spatter:.3f}" />'
        )

    elements.append("</g>")
    return elements


def _paper_canvas_texture(seed: bytes) -> list[str]:
    """
    атериальная фактура офортного листа / холста:
    микроволокна и зернистая взвесь туши, убирающая цифровой пластик.
    """
    elements = ['<g id="canvas-paper-texture" pointer-events="none">']
    seed_int = int.from_bytes(seed[12:20], "big")
    rng = random.Random(seed_int)

    # 1. икроволокна бумаги (короткие штрихи)
    for _ in range(160):
        x = rng.uniform(40.0, 1040.0)
        y = rng.uniform(40.0, 1040.0)
        length = rng.uniform(2.5, 7.0)
        angle = rng.uniform(0, math.pi)
        dx = length * math.cos(angle)
        dy = length * math.sin(angle)
        op = rng.uniform(0.04, 0.12)
        col = "#E9EEF8" if rng.random() > 0.4 else "#F6C85F"
        elements.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+dx:.1f}" y2="{y+dy:.1f}" '
            f'stroke="{col}" stroke-width="0.6" stroke-opacity="{op:.3f}" stroke-linecap="round"/>'
        )

    # 2. ернистые микропоры полотна (точки)
    for _ in range(350):
        px = rng.uniform(30.0, 1050.0)
        py = rng.uniform(30.0, 1050.0)
        r = rng.uniform(0.4, 0.9)
        op = rng.uniform(0.05, 0.16)
        elements.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.2f}" fill="#E9EEF8" fill-opacity="{op:.3f}"/>'
        )

    elements.append('</g>')
    return elements


def _bold_dripping(
    seed: bytes,
    bridge_params: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    равитационный дриппинг: струи и капли жидкой туши, стекающие вниз.
    """
    bp = bridge_params or {}
    junction = bp.get("junction") if isinstance(bp.get("junction"), Mapping) else {}
    cx = float(junction.get("x", 540.0))
    cy = float(junction.get("y", 540.0))
    drive = float(bp.get("drive", 0.4))
    grain = float(bp.get("grain", 0.5))

    col_gold = PALETTE.get("theta_gold", "#F6C85F")
    col_cyan = PALETTE.get("audit_cyan", "#46D9E8")
    col_magenta = PALETTE.get("rock_magenta", "#C75CEB")
    colors = [col_gold, col_magenta, col_cyan, col_gold]

    seed_int = int.from_bytes(seed[2:10], "big")
    rng = random.Random(seed_int)

    elements = ['<g id="gravitational-ink-dripping">']

    # 1. аметные вертикальные потеки туши со свисающими каплями
    num_trails = int(5 + grain * 4)
    for i in range(num_trails):
        # сточник потеков: нижняя часть цветка и начало стебля
        ox = cx + rng.uniform(-110.0, 110.0)
        oy = cy + rng.uniform(70.0, 220.0)
        d_len = rng.uniform(50.0, 170.0) + drive * 80.0
        c_ink = colors[i % len(colors)]
        w_trail = rng.uniform(1.0, 1.8)
        op_trail = rng.uniform(0.40, 0.75)

        ctrl_x = ox + rng.uniform(-6.0, 6.0)
        end_x = ox + rng.uniform(-10.0, 10.0)
        end_y = oy + d_len

        # Струя туши
        elements.append(
            f'<path d="M {ox:.2f} {oy:.2f} Q {ctrl_x:.2f} {oy + d_len*0.5:.2f} {end_x:.2f} {end_y:.2f}" '
            f'fill="none" stroke="{c_ink}" stroke-width="{w_trail:.2f}" stroke-opacity="{op_trail:.3f}" stroke-linecap="round"/>'
        )

        # апля туши на конце потека
        r_drop = rng.uniform(2.2, 4.0)
        elements.append(
            f'<ellipse cx="{end_x:.2f}" cy="{end_y + r_drop*0.8:.2f}" rx="{r_drop*0.85:.2f}" ry="{r_drop*1.3:.2f}" '
            f'fill="{c_ink}" fill-opacity="{min(0.95, op_trail + 0.2):.3f}"/>'
        )

    # 2. адающие капли и брызги в свободном падении
    num_spatters = int(24 + grain * 25)
    for _ in range(num_spatters):
        sp_x = cx + rng.gauss(0.0, 95.0)
        # етят вниз к низу арт-поля (Y от 120 до 480 ниже центра)
        sp_y = cy + rng.uniform(110.0, 480.0)
        c_drop = rng.choice(colors)
        rx = rng.uniform(1.0, 2.5)
        ry = rx * rng.uniform(1.3, 2.2) # вытянуты по вертикали гравитацией
        op = rng.uniform(0.35, 0.80)

        elements.append(
            f'<ellipse cx="{sp_x:.2f}" cy="{sp_y:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'fill="{c_drop}" fill-opacity="{op:.3f}"/>'
        )

    elements.append('</g>')
    return elements


def _theta_arcs(
    seed: bytes,
    bridge_params: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    лагородные эфирные дуги йнштейна на дальней периферии:
    - ынесены дальше от цветка/гнезда (r: 320..520).
    - инии толще (1.5..2.1px), но прозрачнее (0.10..0.18) — эффект мягкого оптоволокна/неона.
    - ольшая часть дуги растворена в темноте (крутое затухание краев sin^2).
    """
    arcs: list[str] = ['<g id="gravitational-peripheral-flashes">']
    bp = bridge_params or {}
    junction = bp.get("junction") if isinstance(bp.get("junction"), Mapping) else {}
    cx = float(junction.get("x", 540.0))
    cy = float(junction.get("y", 540.0))
    resonance = float(bp.get("resonance", 0.3))
    tension = float(bp.get("tension", 0.0))
    drive = float(bp.get("drive", 0.4))

    col_cyan = PALETTE.get("audit_cyan", "#46D9E8")
    col_gold = PALETTE.get("theta_gold", "#F6C85F")
    colors = [col_cyan, col_gold, col_cyan]

    seed_int = int.from_bytes(seed[8:16], "big")
    rng = random.Random(seed_int)

    # 3 внешних световых серпа: вынесены на дальнюю периферию (320..520)
    arc_configs = [
        {"r": 330.0 + resonance * 35.0, "span": 0.90 * math.pi, "phi0": 0.45 + tension * 0.6, "w": 2.05, "op": 0.16},
        {"r": 420.0 + drive * 45.0,     "span": 0.75 * math.pi, "phi0": math.pi * 1.05 - tension * 0.4, "w": 1.75, "op": 0.13},
        {"r": 510.0 + resonance * 50.0, "span": 0.65 * math.pi, "phi0": -0.60 + drive * 0.7, "w": 1.50, "op": 0.10},
    ]

    for idx, cfg in enumerate(arc_configs):
        color = colors[idx % len(colors)]
        r_base = cfg["r"]
        phi0 = cfg["phi0"]
        span = cfg["span"]
        sw = cfg["w"]
        base_op = cfg["op"]

        steps = 40
        pts = []
        alphas = []

        fx = cx + math.cos(phi0) * 45.0
        fy = cy + math.sin(phi0) * 35.0

        for s in range(steps + 1):
            t = s / float(steps)
            phi = (phi0 - span * 0.5) + t * span

            # лавная гравитационная волна
            r_curr = r_base * (1.0 + 0.07 * math.sin(phi * 2.0 + tension) + 0.03 * math.cos(phi * 3.0))

            # Ш СТ СТ: крутое затухание краев (sin^2)
            edge_fade = math.pow(math.sin(t * math.pi), 2.0)
            cur_alpha = base_op * edge_fade

            px = fx + r_curr * math.cos(phi)
            py = fy + (r_curr * 0.86) * math.sin(phi)

            pts.append((px, py))
            alphas.append(cur_alpha)

        mean_alpha = sum(alphas) / max(1, len(alphas))
        if len(pts) > 3 and mean_alpha > 0.01:
            d_chunks = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
            for pt in pts[1:]:
                d_chunks.append(f"L {pt[0]:.2f} {pt[1]:.2f}")
            path_d = " ".join(d_chunks)

            arcs.append(
                f'<path d="{path_d}" fill="none" stroke="{color}" '
                f'stroke-width="{sw:.2f}" stroke-opacity="{mean_alpha:.3f}" '
                f'stroke-linecap="round" />'
            )

    arcs.append('</g>')
    return arcs


def _star_field(seed: bytes) -> list[str]:
    stars: list[str] = []

    for index in range(56):
        x = 72.0 + _seed_fraction(seed, index * 3) * 936.0
        y = 180.0 + _seed_fraction(seed, index * 3 + 1) * 690.0
        radius = 0.55 + _seed_fraction(seed, index * 3 + 2) * 1.7
        color = (
            PALETTE["audit_cyan"]
            if index % 3 == 0
            else PALETTE["secondary_text"]
        )
        opacity = 0.14 + _seed_fraction(seed, index + 11) * 0.42
        stars.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
            f'fill="{color}" opacity="{opacity:.2f}"/>'
        )

    return stars


def _base_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact": dict(data),
        "canonical_outputs": {
            "svg_filename": SVG_FILENAME,
            "svg_viewbox": CANONICAL_VIEWBOX,
        },
        "central_graphic": {
            "representation": "deterministic artistic crystalline wave",
            "scientific_claim": (
                "artistic interpretation; not a spectrogram or measured "
                "fractal property"
            ),
            "seed_contract": (
                "sha256(canonical_theta_hash + '|' + feature_sha256)"
            ),
            "seed_sha256": seed_hex(data),
        },
        "palette": PALETTE,
        "poster_id": POSTER_ID,
        "publication_provenance": {"commit": PUBLICATION_COMMIT},
        "renderer": {
            "name": RENDERER_NAME,
            "version": RENDERER_VERSION,
        },
        "schema_version": POSTER_SCHEMA_VERSION,
    }


def _embedded_svg_metadata(data: Mapping[str, Any]) -> str:
    encoded = canonical_json_bytes(
        _base_metadata(data)
    ).decode("utf-8").rstrip("\n")
    return html.escape(encoded)


def render_svg(data: Mapping[str, Any]) -> bytes:
    source_title = data.get("source_title", "UNTITLED")
    theta_short = data.get("canonical_theta_hash", "").removeprefix("sha256:")[:16]
    seed_short = data.get("central_graphic", {}).get("seed_sha256", "").removeprefix("sha256:")[:16]
    if not seed_short and "canonical_theta_hash" in data:
        seed_short = data["canonical_theta_hash"].removeprefix("sha256:")[:16]
    
    seed = _seed_bytes(data)
    raw_bridge_params = data.get("bridge_params", {})
    bridge_params = raw_bridge_params if isinstance(raw_bridge_params, Mapping) else {}
    raw_junction = bridge_params.get("junction", {})
    junction = raw_junction if isinstance(raw_junction, Mapping) else {}

    junction_x = float(junction.get("x", 540.0))
    junction_y = float(junction.get("y", 540.0))
    topology = str(bridge_params.get("topology", "balanced_axial"))
    mode = str(bridge_params.get("dominant_mode", "structure"))
    embedded_metadata = _embedded_svg_metadata(data)

    clean_title = html.escape(source_title).upper()
    footer_id = f"d1_rock_v1 · seed {seed_short}" if seed_short else "d1_rock_v1"

    return chr(10).join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1260" viewBox="0 0 1080 1260" role="img">',
            f"<metadata>{embedded_metadata}</metadata>",
            "<defs>",
                        '<radialGradient id="space-ambient" cx="50%" cy="50%" r="50%">',
            '<stop offset="0%" stop-color="#C75CEB" stop-opacity="0.18"/>',
            '<stop offset="45%" stop-color="#46D9E8" stop-opacity="0.06"/>',
            '<stop offset="100%" stop-color="#0E131F" stop-opacity="0"/>',
            '</radialGradient>',
            '<filter id="crystal-glow" x="-20%" y="-20%" width="140%" height="140%">',
            '<feGaussianBlur stdDeviation="4" result="blur"/>',
            '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
            "</filter>",
            '<radialGradient id="sacred-heart" cx="50%" cy="50%" r="50%">',
            '<stop offset="0%" stop-color="#FEF3C7" stop-opacity="1"/>',
            '<stop offset="60%" stop-color="#F6C85F" stop-opacity="0.85"/>',
            '<stop offset="100%" stop-color="#EA580C" stop-opacity="0.2"/>',
            '</radialGradient>',
            '<filter id="core-glow" x="-40%" y="-40%" width="180%" height="180%">',
            '<feGaussianBlur stdDeviation="12" result="glow"/>',
            '<feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>',
            "</filter>",
            '<filter id="analog-paper-grain" x="0%" y="0%" width="100%" height="100%">',
            '<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" result="noise"/>',
            '<feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.045 0"/>',
            '</filter>',
            '</defs>',
            "<style>",
            ".title{font-family:'Segoe UI',Arial,sans-serif;font-size:28px;font-weight:700;letter-spacing:4px;fill:#E9EEF8;text-anchor:middle;}",
            ".hash{font-family:Consolas,Menlo,monospace;font-size:15px;letter-spacing:2px;fill:#7D8798;text-anchor:middle;}",
            "</style>",
            # 1. Фон квадратного арт-поля (1080x1080)
            f'<rect width="1080" height="1080" fill="{PALETTE["background"]}"/>',
            '<rect width="1080" height="1080" fill="#FFFFFF" opacity="0.035" filter="url(#analog-paper-grain)" pointer-events="none"/>',
            # 2. вездное/текстурное поле
            *_star_field(seed),
            # Фактура бумаги и офортного холста
            *_paper_canvas_texture(seed),
            # 3. рафика в координатах junction
            '<g id="d1-geometry" filter="url(#crystal-glow)">',
            *_theta_arcs(seed, bridge_params),
            *_branch_geometry(seed, bridge_params),
            *_bold_dripping(seed, bridge_params),
            *_gravitational_dripping(seed, bridge_params),
            "</g>",
            # 4. Тонкая разделительная черта под артом
            f'<line x1="0" y1="1080" x2="1080" y2="1080" stroke="{PALETTE.get("card", PALETTE.get("background", "#14100E"))}" stroke-width="2"/>',
            # 5. ижняя плашка паспорта (1080x180)
            f'<rect y="1080" width="1080" height="180" fill="{PALETTE.get("card", PALETTE.get("background", "#14100E"))}"/>',
            # 6. Только название трека и хэш снизу по центру
            f'<text x="540" y="1150" class="title">{clean_title}</text>',
            f'<text x="540" y="1195" class="hash">{footer_id}</text>',
            "</svg>",
        ]
    ).encode("utf-8")


def build_metadata(data: Mapping[str, Any], svg_bytes: bytes) -> bytes:
    metadata = _base_metadata(data)
    metadata["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    metadata["raster_outputs"] = []
    return canonical_json_bytes(metadata)


def render_canonical(
    artifact_path: Path,
    bridge_params: Mapping[str, Any] | None = None,
) -> tuple[bytes, bytes]:
    data = _artifact_display_data(artifact_path)
    if bridge_params is not None:
        if isinstance(data, dict):
            data["bridge_params"] = dict(bridge_params)
    svg_bytes = render_svg(data)
    metadata_bytes = build_metadata(data, svg_bytes)
    return svg_bytes, metadata_bytes


def write_canonical_outputs(
    *,
    artifact_path: Path,
    svg_path: Path,
    metadata_path: Path,
    bridge_params: Mapping[str, Any] | None = None,
) -> tuple[Path, Path]:
    svg_bytes, metadata_bytes = render_canonical(artifact_path, bridge_params=bridge_params)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg_bytes)
    metadata_path.write_bytes(metadata_bytes)
    return svg_path, metadata_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render canonical SVG and metadata for a D1 fractal poster."
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="Validated d1_rock_v1 feature artifact JSON.",
    )
    parser.add_argument(
        "--svg-output",
        type=Path,
        required=True,
        help="Explicit output path for the canonical SVG.",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        required=True,
        help="Explicit output path for canonical poster metadata JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_canonical_outputs(
        artifact_path=args.artifact,
        svg_path=args.svg_output,
        metadata_path=args.metadata_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())