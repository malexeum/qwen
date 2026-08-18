from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
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
RENDERER_VERSION = "7"
PUBLICATION_COMMIT = "367a33e53f7be0c7c619c3ab2c8c1a5fc0bdd1c2"

ART_FIELD_SIZE_PX = 1080
TECHNICAL_FIELD_HEIGHT_PX = 180
CANONICAL_WIDTH_PX = ART_FIELD_SIZE_PX
CANONICAL_HEIGHT_PX = ART_FIELD_SIZE_PX + TECHNICAL_FIELD_HEIGHT_PX
CANONICAL_VIEWBOX = f"0 0 {CANONICAL_WIDTH_PX} {CANONICAL_HEIGHT_PX}"

PREVIEW_WIDTH_PX = 1080
PREVIEW_HEIGHT_PX = 1260

ARTIFACT_RELATIVE_PATH = Path("artifacts/d1/features/d1_rock_v1.json")
SVG_FILENAME = "d1_rock_v1_fractal_poster.svg"
METADATA_FILENAME = "d1_rock_v1_fractal_poster.metadata.json"

HEXAGON_ORIGIN = (540.0, 360.0)
TRANSITION_ENDPOINT = (540.0, 715.0)

SAFE_NODE_X_MIN = 96.0
SAFE_NODE_X_MAX = 984.0
SAFE_NODE_Y_MIN = 46.0
SAFE_NODE_Y_MAX = 684.0

MATERIALITY_MAX_SHADOW_FIELDS = 3
MATERIALITY_MAX_IMPRINTS = 2
MATERIALITY_OPACITY_MIN = 0.05
MATERIALITY_OPACITY_MAX = 0.12
LYAPUNOV_SECONDARY_LAYER_FRACTION_MAX = 0.10

PALETTE = {
    "audit_cyan": "#46D9E8",
    "background": "#070A12",
    "card": "#11151F",
    "caption": "#E9EEF8",
    "dust": "#7D8798",
    "halo_gold": "#F6C85F",
    "imprint": "#7D8798",
    "rock_magenta": "#C75CEB",
    "shadow": "#303A4D",
    "theta_gold": "#F6C85F",
}

MIDDLE_DOT = "\u00b7"

_SVG_TITLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]*\Z")
_HEX_DIGEST_RE = re.compile(r"sha256:([0-9a-f]{16,64})\Z")


class FractalPosterContractError(ValueError):
    """Raised when an artifact cannot produce a valid fractal poster."""


@dataclass(frozen=True)
class LineGeometry:
    line_id: str
    role: str
    color: str
    start: tuple[float, float]
    end: tuple[float, float]
    width: float
    opacity: float


@dataclass(frozen=True)
class CurveGeometry:
    curve_id: str
    start: tuple[float, float]
    controls: tuple[tuple[float, float], tuple[float, float]]
    end: tuple[float, float]
    color: str
    opacity: float
    width: float
    role: str


@dataclass(frozen=True)
class MaterialityPlacement:
    shadow_centers: tuple[tuple[float, float], ...]
    imprint_centers: tuple[tuple[float, float], ...]
    selected_regions: tuple[str, ...]
    lyapunov_center: tuple[float, float]


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


def seed_prefix(data: Mapping[str, Any], length: int = 16) -> str:
    if length <= 0:
        raise FractalPosterContractError("seed prefix length must be positive")
    return _seed_bytes(data).hex()[:length]


def _seed_fraction(seed: bytes, index: int) -> float:
    return seed[index % len(seed)] / 255.0


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


def _point(x: float, y: float) -> str:
    return f"{x:.2f},{y:.2f}"


def _distance(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def _crystal_polygon(
    x: float,
    y: float,
    radius: float,
    sides: int,
    rotation: float,
) -> str:
    return " ".join(
        _point(
            x + radius * math.cos(rotation + 2.0 * math.pi * index / sides),
            y + radius * math.sin(rotation + 2.0 * math.pi * index / sides),
        )
        for index in range(sides)
    )


def _hexagon_geometry() -> str:
    x, y = HEXAGON_ORIGIN
    return (
        f'<polygon id="junction-hexagon" data-role="actual-junction" '
        f'data-x="{x:.2f}" data-y="{y:.2f}" points="'
        f'{_crystal_polygon(x, y, 31.0, 6, math.pi / 6.0)}" '
        f'fill="#0B1520" stroke="{PALETTE["halo_gold"]}" '
        'stroke-width="2.40" opacity="0.98"/>'
    )


def _incoming_branch_geometry(seed: bytes) -> list[LineGeometry]:
    junction = HEXAGON_ORIGIN
    trunks = (
        (
            "incoming-cyan",
            PALETTE["audit_cyan"],
            (333.0, 118.0),
            5.15,
            0.90,
        ),
        (
            "incoming-gold",
            PALETTE["theta_gold"],
            (616.0, 94.0),
            4.80,
            0.88,
        ),
        (
            "incoming-magenta",
            PALETTE["rock_magenta"],
            (792.0, 206.0),
            3.70,
            0.78,
        ),
    )

    geometry: list[LineGeometry] = [
        LineGeometry(
            line_id=line_id,
            role="incoming-junction",
            color=color,
            start=start,
            end=junction,
            width=width,
            opacity=opacity,
        )
        for line_id, color, start, width, opacity in trunks
    ]

    branch_specs = (
        (
            (333.0, 118.0),
            PALETTE["audit_cyan"],
            (
                (184.0, 74.0),
                (239.0, 196.0),
                (304.0, 42.0),
                (420.0, 72.0),
                (445.0, 180.0),
            ),
        ),
        (
            (616.0, 94.0),
            PALETTE["theta_gold"],
            (
                (509.0, 48.0),
                (566.0, 202.0),
                (681.0, 44.0),
                (743.0, 146.0),
                (594.0, 252.0),
            ),
        ),
        (
            (792.0, 206.0),
            PALETTE["rock_magenta"],
            (
                (863.0, 78.0),
                (929.0, 160.0),
                (900.0, 278.0),
                (730.0, 282.0),
                (812.0, 330.0),
            ),
        ),
    )

    branch_index = 0
    for anchor, color, endpoints in branch_specs:
        for depth, endpoint in enumerate(endpoints):
            shift = (
                _seed_fraction(seed, 24 + branch_index) - 0.5
            ) * 16.0
            start = (
                endpoint[0] + shift,
                max(28.0, endpoint[1] - shift * 0.42),
            )
            geometry.append(
                LineGeometry(
                    line_id=f"upper-branch-{branch_index}",
                    role="incoming-tree",
                    color=color,
                    start=start,
                    end=anchor,
                    width=max(1.15, 2.85 - depth * 0.27),
                    opacity=max(0.38, 0.69 - depth * 0.055),
                )
            )
            branch_index += 1

    geometry.extend(
        [
            LineGeometry(
                line_id="offshoot-cyan",
                role="secondary-offshoot",
                color=PALETTE["audit_cyan"],
                start=(260.0, 142.0),
                end=(333.0, 118.0),
                width=1.55,
                opacity=0.42,
            ),
            LineGeometry(
                line_id="offshoot-gold",
                role="secondary-offshoot",
                color=PALETTE["theta_gold"],
                start=(668.0, 186.0),
                end=(616.0, 94.0),
                width=1.45,
                opacity=0.40,
            ),
        ]
    )

    return geometry


def _line_svg(line: LineGeometry) -> str:
    return (
        f'<line id="{line.line_id}" class="branch-line" '
        f'data-role="{line.role}" '
        f'data-start-x="{line.start[0]:.2f}" data-start-y="{line.start[1]:.2f}" '
        f'data-end-x="{line.end[0]:.2f}" data-end-y="{line.end[1]:.2f}" '
        f'x1="{line.start[0]:.2f}" y1="{line.start[1]:.2f}" '
        f'x2="{line.end[0]:.2f}" y2="{line.end[1]:.2f}" '
        f'stroke="{line.color}" stroke-width="{line.width:.2f}" '
        f'stroke-linecap="round" opacity="{line.opacity:.2f}"/>'
    )


def _upper_nodes(seed: bytes) -> list[str]:
    nodes: list[str] = []
    node_centers = (
        (184.0, 74.0),
        (239.0, 196.0),
        (304.0, 42.0),
        (420.0, 72.0),
        (445.0, 180.0),
        (509.0, 48.0),
        (566.0, 202.0),
        (681.0, 44.0),
        (743.0, 146.0),
        (594.0, 252.0),
        (863.0, 78.0),
        (929.0, 160.0),
    )
    incomplete_indices = {2, 7}

    for index, (x, y) in enumerate(node_centers):
        radius = 6.0 + 3.5 * _seed_fraction(seed, 90 + index)
        x = min(max(x, SAFE_NODE_X_MIN + radius), SAFE_NODE_X_MAX - radius)
        y = min(max(y, SAFE_NODE_Y_MIN + radius), SAFE_NODE_Y_MAX - radius)
        color = (
            PALETTE["audit_cyan"]
            if index % 3 == 0
            else PALETTE["theta_gold"]
            if index % 3 == 1
            else PALETTE["rock_magenta"]
        )

        if index in incomplete_indices:
            nodes.append(
                f'<path class="branch-node incomplete-node" '
                f'data-role="incomplete-upper-node" '
                f'd="M {x - radius:.2f} {y + radius * 0.25:.2f} '
                f'L {x:.2f} {y - radius:.2f} '
                f'L {x + radius:.2f} {y + radius * 0.18:.2f}" '
                f'fill="none" stroke="{color}" stroke-width="1.25" '
                'stroke-linecap="round" stroke-linejoin="round" '
                'opacity="0.56"/>'
            )
            continue

        nodes.append(
            f'<polygon class="branch-node" data-role="upper-node" points="'
            f'{_crystal_polygon(x, y, radius, 6, math.pi / 6.0)}" '
            f'fill="none" stroke="{color}" stroke-width="1.25" '
            'opacity="0.61"/>'
        )

    return nodes


def _theta_geometry(seed: bytes) -> list[CurveGeometry]:
    x, y = HEXAGON_ORIGIN
    specifications = (
        (
            (650.0, 392.0),
            (710.0, 462.0),
            (770.0, 500.0),
            PALETTE["audit_cyan"],
            0.44,
            2.05,
            "early-fade",
        ),
        (
            (637.0, 438.0),
            (720.0, 454.0),
            (808.0, 566.0),
            PALETTE["theta_gold"],
            0.52,
            2.15,
            "turning-trace",
        ),
        (
            (606.0, 476.0),
            (692.0, 560.0),
            (744.0, 654.0),
            PALETTE["audit_cyan"],
            0.38,
            1.65,
            "downward-fade",
        ),
        (
            (665.0, 346.0),
            (757.0, 415.0),
            (875.0, 460.0),
            PALETTE["theta_gold"],
            0.45,
            1.85,
            "long-right",
        ),
        (
            (636.0, 514.0),
            (754.0, 612.0),
            (926.0, 732.0),
            PALETTE["theta_gold"],
            0.40,
            1.70,
            "far-right-lower",
        ),
        (
            (588.0, 412.0),
            (662.0, 505.0),
            (702.0, 580.0),
            PALETTE["rock_magenta"],
            0.30,
            1.45,
            "broken-return",
        ),
    )

    curves: list[CurveGeometry] = []
    for index, (
        control_1,
        control_2,
        end,
        color,
        opacity,
        width,
        role,
    ) in enumerate(specifications):
        jitter = (_seed_fraction(seed, 120 + index) - 0.5) * 18.0
        curves.append(
            CurveGeometry(
                curve_id=f"theta-{index}",
                start=(x, y),
                controls=(
                    (control_1[0], control_1[1] + jitter),
                    (control_2[0], control_2[1] - jitter * 0.55),
                ),
                end=(end[0], end[1] + jitter * 0.35),
                color=color,
                opacity=opacity,
                width=width,
                role=role,
            )
        )

    return curves


def _curve_svg(curve: CurveGeometry) -> str:
    control_1, control_2 = curve.controls
    return (
        f'<path id="{curve.curve_id}" class="theta-curve" '
        f'data-role="{curve.role}" data-start-x="{curve.start[0]:.2f}" '
        f'data-start-y="{curve.start[1]:.2f}" '
        f'data-end-x="{curve.end[0]:.2f}" data-end-y="{curve.end[1]:.2f}" '
        f'd="M {curve.start[0]:.2f} {curve.start[1]:.2f} '
        f'C {control_1[0]:.2f} {control_1[1]:.2f}, '
        f'{control_2[0]:.2f} {control_2[1]:.2f}, '
        f'{curve.end[0]:.2f} {curve.end[1]:.2f}" fill="none" '
        f'stroke="{curve.color}" stroke-width="{curve.width:.2f}" '
        f'stroke-linecap="round" opacity="{curve.opacity:.2f}"/>'
    )


def _transition_trace() -> list[str]:
    start_x, start_y = HEXAGON_ORIGIN
    end_x, end_y = TRANSITION_ENDPOINT
    path = (
        f"M {start_x:.2f} {start_y + 31.0:.2f} "
        f"C {start_x - 6.0:.2f} {start_y + 142.0:.2f}, "
        f"{end_x + 8.0:.2f} {end_y - 102.0:.2f}, "
        f"{end_x:.2f} {end_y:.2f}"
    )

    return [
        (
            f'<path id="trunk-haze" data-role="energetic-aftertrace-haze" '
            f'data-start-x="{start_x:.2f}" data-start-y="{start_y:.2f}" '
            f'data-end-x="{end_x:.2f}" data-end-y="{end_y:.2f}" '
            f'd="{path}" fill="none" stroke="{PALETTE["audit_cyan"]}" '
            'stroke-width="20.0" stroke-linecap="round" opacity="0.13"/>'
        ),
        (
            f'<path id="trunk-ghost" data-role="energetic-aftertrace-ghost" '
            f'data-start-x="{start_x:.2f}" data-start-y="{start_y:.2f}" '
            f'data-end-x="{end_x + 7.0:.2f}" data-end-y="{end_y - 6.0:.2f}" '
            f'd="M {start_x + 5.0:.2f} {start_y + 35.0:.2f} '
            f'C {start_x + 9.0:.2f} {start_y + 155.0:.2f}, '
            f'{end_x + 18.0:.2f} {end_y - 110.0:.2f}, '
            f'{end_x + 7.0:.2f} {end_y - 6.0:.2f}" fill="none" '
            f'stroke="{PALETTE["rock_magenta"]}" stroke-width="7.0" '
            'stroke-linecap="round" opacity="0.045"/>'
        ),
        (
            f'<path id="trunk-core" data-role="energetic-aftertrace-core" '
            f'data-start-x="{start_x:.2f}" data-start-y="{start_y:.2f}" '
            f'data-end-x="{end_x:.2f}" data-end-y="{end_y:.2f}" '
            f'd="{path}" fill="none" stroke="{PALETTE["audit_cyan"]}" '
            'stroke-width="4.4" stroke-linecap="round" opacity="0.68"/>'
        ),
    ]


def _resonance_halo() -> list[str]:
    x, y = HEXAGON_ORIGIN
    return [
        (
            f'<circle class="resonance-halo" cx="{x:.2f}" cy="{y:.2f}" '
            f'r="71.0" fill="none" stroke="{PALETTE["audit_cyan"]}" '
            'stroke-width="1.60" opacity="0.17"/>'
        ),
        (
            f'<circle class="resonance-halo" cx="{x:.2f}" cy="{y:.2f}" '
            f'r="45.0" fill="none" stroke="{PALETTE["halo_gold"]}" '
            'stroke-width="1.45" opacity="0.24"/>'
        ),
    ]


def _star_field(seed: bytes) -> list[str]:
    stars: list[str] = []
    for index in range(24):
        x = 72.0 + _seed_fraction(seed, index * 3) * 936.0
        y = 90.0 + _seed_fraction(seed, index * 3 + 1) * 846.0
        if _distance((x, y), HEXAGON_ORIGIN) < 102.0:
            continue
        if x < 430.0 and 260.0 < y < 810.0:
            continue
        radius = 0.40 + _seed_fraction(seed, index * 3 + 2) * 1.25
        opacity = 0.08 + _seed_fraction(seed, 180 + index) * 0.22
        color = PALETTE["audit_cyan"] if index % 4 == 0 else "#BAC4D2"
        stars.append(
            f'<circle class="star" cx="{x:.2f}" cy="{y:.2f}" '
            f'r="{radius:.2f}" fill="{color}" opacity="{opacity:.2f}"/>'
        )
    return stars


def _occupancy(x: float, y: float) -> float:
    def gaussian(
        center: tuple[float, float],
        sigma_x: float,
        sigma_y: float,
        weight: float,
    ) -> float:
        dx = (x - center[0]) / sigma_x
        dy = (y - center[1]) / sigma_y
        return weight * math.exp(-0.5 * (dx * dx + dy * dy))

    return min(
        1.0,
        gaussian((540.0, 190.0), 275.0, 168.0, 0.80)
        + gaussian(HEXAGON_ORIGIN, 84.0, 84.0, 1.00)
        + gaussian((742.0, 520.0), 258.0, 218.0, 0.69)
        + gaussian((540.0, 535.0), 78.0, 196.0, 0.52),
    )


def _materiality_safe(x: float, y: float) -> bool:
    if not 165.0 <= x <= 860.0 or not 285.0 <= y <= 860.0:
        return False
    if _distance((x, y), HEXAGON_ORIGIN) < 150.0:
        return False
    if abs(x - 540.0) < 108.0 and 320.0 <= y <= 760.0:
        return False
    return True


def _materiality_score(
    x: float,
    y: float,
    seed: bytes,
    index: int,
) -> float:
    if not _materiality_safe(x, y):
        return -1.0

    quiet = (1.0 - _occupancy(x, y)) ** 1.45
    visual_mass = (642.0, 385.0)
    dx = visual_mass[0] - x
    dy = y - visual_mass[1]
    counterweight = (
        max(0.0, dx / 560.0) * 0.61
        + max(0.0, dy / 620.0) * 0.21
        + min(1.0, math.hypot(dx, dy) / 770.0) * 0.18
    )
    spread_penalty = 0.09 if x < 235.0 else 0.0
    jitter = (_seed_fraction(seed, index) - 0.5) * 0.045
    return quiet * counterweight - spread_penalty + jitter


def _materiality_placement(seed: bytes) -> MaterialityPlacement:
    candidates: list[tuple[float, float, float]] = []

    for y in range(300, 850, 43):
        for x in range(185, 825, 47):
            x_jitter = (
                _seed_fraction(seed, x + y) - 0.5
            ) * 19.0
            y_jitter = (
                _seed_fraction(seed, x * 3 + y) - 0.5
            ) * 17.0
            candidate_x = x + x_jitter
            candidate_y = y + y_jitter
            candidates.append(
                (
                    _materiality_score(
                        candidate_x,
                        candidate_y,
                        seed,
                        x * 11 + y,
                    ),
                    candidate_x,
                    candidate_y,
                )
            )

    candidates.sort(reverse=True)
    selected: list[tuple[float, float]] = []

    for _, x, y in candidates:
        if all(_distance((x, y), center) > 180.0 for center in selected):
            selected.append((x, y))
        if len(selected) == 5:
            break

    if len(selected) != 5:
        raise FractalPosterContractError(
            "materiality field could not place deterministic quiet anchors"
        )

    return MaterialityPlacement(
        shadow_centers=tuple(selected[:3]),
        imprint_centers=tuple(selected[3:5]),
        selected_regions=tuple(
            f"quiet-counterweight-{index + 1}@{x:.1f},{y:.1f}"
            for index, (x, y) in enumerate(selected)
        ),
        lyapunov_center=selected[3],
    )


def _cloud_path(
    x: float,
    y: float,
    width: float,
    height: float,
    seed: bytes,
    index: int,
) -> str:
    a = (_seed_fraction(seed, 205 + index) - 0.5) * 42.0
    b = (_seed_fraction(seed, 214 + index) - 0.5) * 38.0
    return (
        f"M {x - width * 0.58:.2f} {y + height * 0.08:.2f} "
        f"C {x - width * 0.42:.2f} {y - height * 0.62 + a:.2f}, "
        f"{x - width * 0.04:.2f} {y - height * 0.52:.2f}, "
        f"{x + width * 0.22:.2f} {y - height * 0.25 + b:.2f} "
        f"C {x + width * 0.57:.2f} {y - height * 0.04:.2f}, "
        f"{x + width * 0.50:.2f} {y + height * 0.48:.2f}, "
        f"{x + width * 0.10:.2f} {y + height * 0.56:.2f} "
        f"C {x - width * 0.28:.2f} {y + height * 0.64:.2f}, "
        f"{x - width * 0.61:.2f} {y + height * 0.35:.2f}, "
        f"{x - width * 0.58:.2f} {y + height * 0.08:.2f} Z"
    )


def _materiality_geometry(
    seed: bytes,
    placement: MaterialityPlacement,
) -> list[str]:
    elements: list[str] = [
        '<g id="space-materiality" data-role="anchor-derived-materiality">'
    ]

    cloud_opacities = (0.076, 0.094, 0.110)
    for index, (x, y) in enumerate(placement.shadow_centers):
        width = 214.0 + 42.0 * _seed_fraction(seed, 236 + index)
        height = 162.0 + 34.0 * _seed_fraction(seed, 243 + index)
        opacity = cloud_opacities[index]
        elements.append(
            f'<path class="shadow-density" data-role="cloud-density" '
            f'data-center-x="{x:.2f}" data-center-y="{y:.2f}" '
            f'data-area="{width * height:.2f}" '
            f'd="{_cloud_path(x, y, width, height, seed, index)}" '
            f'fill="{PALETTE["shadow"]}" opacity="{opacity:.3f}"/>'
        )

    for index, (x, y) in enumerate(placement.imprint_centers):
        opacity = 0.078 if index == 0 else 0.091
        drift = (_seed_fraction(seed, 250 + index) - 0.5) * 30.0
        elements.append(
            f'<path class="paper-imprint" data-role="fragmented-imprint" '
            f'data-center-x="{x:.2f}" data-center-y="{y:.2f}" '
            f'd="M {x - 126.0:.2f} {y + 42.0:.2f} '
            f'C {x - 96.0:.2f} {y - 66.0:.2f}, '
            f'{x - 33.0:.2f} {y - 46.0 + drift:.2f}, '
            f'{x - 12.0:.2f} {y + 16.0:.2f} '
            f'M {x + 20.0:.2f} {y + 25.0:.2f} '
            f'C {x + 62.0:.2f} {y + 84.0 - drift:.2f}, '
            f'{x + 118.0:.2f} {y + 70.0:.2f}, '
            f'{x + 150.0:.2f} {y - 20.0:.2f}" fill="none" '
            f'stroke="{PALETTE["imprint"]}" stroke-width="13.0" '
            f'stroke-linecap="round" opacity="{opacity:.3f}"/>'
        )

    ly_x, ly_y = placement.lyapunov_center
    separation = 28.0
    elements.extend(
        [
            (
                f'<path id="lyapunov-haze" data-role="split-drift-return-fade-haze" '
                f'data-center-x="{ly_x:.2f}" data-center-y="{ly_y:.2f}" '
                f'data-separation="{separation:.2f}" '
                f'd="M {ly_x - 132.0:.2f} {ly_y + 20.0:.2f} '
                f'C {ly_x - 72.0:.2f} {ly_y - 24.0:.2f}, '
                f'{ly_x - 26.0:.2f} {ly_y - 8.0:.2f}, '
                f'{ly_x:.2f} {ly_y:.2f} '
                f'C {ly_x + 48.0:.2f} {ly_y - separation:.2f}, '
                f'{ly_x + 96.0:.2f} {ly_y - separation * 0.72:.2f}, '
                f'{ly_x + 124.0:.2f} {ly_y - 7.0:.2f}" fill="none" '
                f'stroke="{PALETTE["imprint"]}" stroke-width="15.0" '
                'stroke-linecap="round" opacity="0.025"/>'
            ),
            (
                f'<path id="lyapunov-stable" data-role="split-drift-return-fade" '
                f'data-center-x="{ly_x:.2f}" data-center-y="{ly_y:.2f}" '
                f'd="M {ly_x - 132.0:.2f} {ly_y + 20.0:.2f} '
                f'C {ly_x - 72.0:.2f} {ly_y - 24.0:.2f}, '
                f'{ly_x - 26.0:.2f} {ly_y - 8.0:.2f}, '
                f'{ly_x:.2f} {ly_y:.2f}" fill="none" '
                f'stroke="{PALETTE["imprint"]}" stroke-width="3.4" '
                'stroke-linecap="round" opacity="0.078"/>'
            ),
            (
                f'<path id="lyapunov-split-a" data-role="split-drift-return-fade" '
                f'data-separation="{separation:.2f}" '
                f'd="M {ly_x:.2f} {ly_y:.2f} '
                f'C {ly_x + 35.0:.2f} {ly_y - separation:.2f}, '
                f'{ly_x + 82.0:.2f} {ly_y - separation * 0.90:.2f}, '
                f'{ly_x + 122.0:.2f} {ly_y - 10.0:.2f}" fill="none" '
                f'stroke="{PALETTE["imprint"]}" stroke-width="3.2" '
                'stroke-linecap="round" opacity="0.074"/>'
            ),
            (
                f'<path id="lyapunov-split-b" data-role="split-drift-return-fade" '
                f'data-separation="{separation:.2f}" '
                f'd="M {ly_x:.2f} {ly_y:.2f} '
                f'C {ly_x + 36.0:.2f} {ly_y + separation:.2f}, '
                f'{ly_x + 78.0:.2f} {ly_y + separation * 0.72:.2f}, '
                f'{ly_x + 102.0:.2f} {ly_y + 8.0:.2f} '
                f'C {ly_x + 116.0:.2f} {ly_y - 8.0:.2f}, '
                f'{ly_x + 132.0:.2f} {ly_y + 6.0:.2f}, '
                f'{ly_x + 148.0:.2f} {ly_y + 20.0:.2f}" fill="none" '
                f'stroke="{PALETTE["imprint"]}" stroke-width="2.8" '
                'stroke-linecap="round" opacity="0.065"/>'
            ),
        ]
    )

    elements.append("</g>")
    return elements


def _base_metadata(
    data: Mapping[str, Any],
    placement: MaterialityPlacement,
) -> dict[str, Any]:
    return {
        "artifact": dict(data),
        "canonical_outputs": {
            "svg_filename": SVG_FILENAME,
            "svg_viewbox": CANONICAL_VIEWBOX,
        },
        "central_graphic": {
            "art_field_px": [ART_FIELD_SIZE_PX, ART_FIELD_SIZE_PX],
            "composition": {
                "actual_junction": {
                    "role": "literal visible branch junction and field origin",
                    "x": HEXAGON_ORIGIN[0],
                    "y": HEXAGON_ORIGIN[1],
                },
                "branch_lines": (
                    "seed-derived incoming crystalline branch network; "
                    "visible branches terminate at the junction hexagon"
                ),
                "transition_endpoint": {
                    "role": "dissolving energetic after-trace endpoint; "
                    "not field origin",
                    "x": TRANSITION_ENDPOINT[0],
                    "y": TRANSITION_ENDPOINT[1],
                },
                "theta_curves": (
                    "seed-derived asymmetric broken Bezier trajectories "
                    "originating at the literal junction hexagon"
                ),
            },
            "lyapunov_accent": {
                "claim": (
                    "subtle artistic controlled-instability accent; "
                    "not measured dynamics"
                ),
                "enabled": True,
                "secondary_layer_fraction_max": LYAPUNOV_SECONDARY_LAYER_FRACTION_MAX,
                "topology": "split-drift-return-fade",
            },
            "materiality_layer": {
                "contract": (
                    "deterministic quiet-counterweight placement of cloud-like "
                    "shadow density and fragmented paper-imprint traces"
                ),
                "opacity_range": [
                    MATERIALITY_OPACITY_MIN,
                    MATERIALITY_OPACITY_MAX,
                ],
                "placement_regions": list(placement.selected_regions),
            },
            "representation": (
                "deterministic artistic interpretation bound to the "
                "validated D1 identity"
            ),
            "scientific_claim": (
                "artistic interpretation; not an audio spectrogram, measured "
                "fractal property, Lyapunov measurement, or scientific "
                "visualization of the track"
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
        "technical_field_px": [
            CANONICAL_WIDTH_PX,
            TECHNICAL_FIELD_HEIGHT_PX,
        ],
    }


def _embedded_svg_metadata(
    data: Mapping[str, Any],
    placement: MaterialityPlacement,
) -> str:
    return html.escape(
        canonical_json_bytes(
            _base_metadata(data, placement)
        ).decode("utf-8").rstrip("\n")
    )


def render_svg(data: Mapping[str, Any]) -> bytes:
    source_title = data["source_title"]
    seed = _seed_bytes(data)
    branches = _incoming_branch_geometry(seed)
    curves = _theta_geometry(seed)
    placement = _materiality_placement(seed)
    seed_label = (
        f"{data['analysis_id']} {MIDDLE_DOT} seed {seed_prefix(data)}"
    )

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" '
            'height="1260" viewBox="0 0 1080 1260" role="img" '
            'aria-labelledby="poster-title poster-description">',
            f"<metadata>{_embedded_svg_metadata(data, placement)}</metadata>",
            "<title id=\"poster-title\">"
            f"{html.escape(source_title)} Polaroid Poster MVP preview"
            "</title>",
            "<desc id=\"poster-description\">"
            "A deterministic artistic interpretation bound to a validated "
            "D1 identity. The junction hexagon is the literal branch "
            "termination and origin of a dispersed resonant field."
            "</desc>",
            "<defs>",
            (
                '<filter id="crystal-glow" x="-80%" y="-80%" '
                'width="260%" height="260%">'
            ),
            '<feGaussianBlur stdDeviation="4.2" result="blur"/>',
            '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/>'
            "</feMerge>",
            "</filter>",
            (
                '<radialGradient id="junction-glow" cx="50%" cy="50%" r="50%">'
            ),
            f'<stop offset="0%" stop-color="{PALETTE["audit_cyan"]}" '
            'stop-opacity="0.21"/>',
            f'<stop offset="42%" stop-color="{PALETTE["halo_gold"]}" '
            'stop-opacity="0.10"/>',
            f'<stop offset="100%" stop-color="{PALETTE["background"]}" '
            'stop-opacity="0"/>',
            "</radialGradient>",
            "</defs>",
            "<style>",
            (
                ".caption{font-family:Arial,Helvetica,sans-serif;"
                "font-size:26px;font-weight:400;letter-spacing:3px;"
                f"fill:{PALETTE['caption']};}}"
            ),
            (
                ".technical{font-family:Consolas,Menlo,monospace;"
                "font-size:13px;letter-spacing:0.7px;"
                f"fill:{PALETTE['theta_gold']};}}"
            ),
            "</style>",
            (
                f'<rect width="{CANONICAL_WIDTH_PX}" '
                f'height="{CANONICAL_HEIGHT_PX}" fill="{PALETTE["card"]}"/>'
            ),
            '<g id="art-field">',
            (
                f'<rect width="{ART_FIELD_SIZE_PX}" '
                f'height="{ART_FIELD_SIZE_PX}" '
                f'fill="{PALETTE["background"]}"/>'
            ),
            *_materiality_geometry(seed, placement),
            *_star_field(seed),
            (
                f'<circle cx="{HEXAGON_ORIGIN[0]:.2f}" '
                f'cy="{HEXAGON_ORIGIN[1]:.2f}" r="142.0" '
                'fill="url(#junction-glow)"/>'
            ),
            '<g filter="url(#crystal-glow)">',
            *_resonance_halo(),
            *(_line_svg(line) for line in branches),
            *_upper_nodes(seed),
            *(_curve_svg(curve) for curve in curves),
            *_transition_trace(),
            _hexagon_geometry(),
            "</g>",
            "</g>",
            '<g id="technical-field">',
            (
                f'<rect y="{ART_FIELD_SIZE_PX}" '
                f'width="{CANONICAL_WIDTH_PX}" '
                f'height="{TECHNICAL_FIELD_HEIGHT_PX}" '
                f'fill="{PALETTE["card"]}"/>'
            ),
            _svg_text(
                540.0,
                1152.0,
                source_title,
                css_class="caption",
                anchor="middle",
            ),
            _svg_text(
                540.0,
                1191.0,
                seed_label,
                css_class="technical",
                anchor="middle",
            ),
            "</g>",
            "</svg>",
            "",
        ]
    ).encode("utf-8")


def build_metadata(data: Mapping[str, Any], svg_bytes: bytes) -> bytes:
    placement = _materiality_placement(_seed_bytes(data))
    metadata = _base_metadata(data, placement)
    metadata["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    metadata["raster_outputs"] = []
    return canonical_json_bytes(metadata)


def render_canonical(artifact_path: Path) -> tuple[bytes, bytes]:
    data = _artifact_display_data(artifact_path)
    svg_bytes = render_svg(data)
    metadata_bytes = build_metadata(data, svg_bytes)
    return svg_bytes, metadata_bytes


def build_preview_diagnostics(data: Mapping[str, Any]) -> bytes:
    seed = _seed_bytes(data)
    branches = _incoming_branch_geometry(seed)
    curves = _theta_geometry(seed)
    placement = _materiality_placement(seed)

    diagnostics = {
        "branch_network": {
            "incomplete_node_count": 2,
            "visible_branch_segments": len(branches),
        },
        "junction": {
            "role": "literal visible branch junction and field origin",
            "x": HEXAGON_ORIGIN[0],
            "y": HEXAGON_ORIGIN[1],
        },
        "incoming_branch_endpoints": [
            {
                "color": line.color,
                "id": line.line_id,
                "x1": line.start[0],
                "x2": line.end[0],
                "y1": line.start[1],
                "y2": line.end[1],
            }
            for line in branches
            if line.role == "incoming-junction"
        ],
        "lyapunov_event": {
            "branch_separation_px": 28.0,
            "center": [
                placement.lyapunov_center[0],
                placement.lyapunov_center[1],
            ],
            "layer": "materiality",
            "opacity_range": [0.065, 0.078],
            "secondary_layer_fraction": LYAPUNOV_SECONDARY_LAYER_FRACTION_MAX,
            "topology": "split-drift-return-fade",
        },
        "materiality": {
            "paper_imprints": {
                "count": len(placement.imprint_centers),
                "opacity_range": [0.078, 0.091],
            },
            "placement_regions": list(placement.selected_regions),
            "shadow_density": {
                "count": len(placement.shadow_centers),
                "opacity_range": [0.076, 0.110],
            },
        },
        "theta_curve_starts": [
            {
                "id": curve.curve_id,
                "index": index,
                "x": curve.start[0],
                "y": curve.start[1],
            }
            for index, curve in enumerate(curves)
        ],
        "trunk": {
            "core": {"opacity": 0.68, "width_px": 4.4},
            "end": [TRANSITION_ENDPOINT[0], TRANSITION_ENDPOINT[1]],
            "endpoint_halo": False,
            "ghost": {"opacity": 0.045, "width_px": 7.0},
            "haze": {"opacity": 0.13, "width_px": 20.0},
            "start": [HEXAGON_ORIGIN[0], HEXAGON_ORIGIN[1]],
        },
    }
    return canonical_json_bytes(diagnostics)


def write_canonical_outputs(
    *,
    artifact_path: Path,
    svg_path: Path,
    metadata_path: Path,
) -> tuple[Path, Path]:
    svg_bytes, metadata_bytes = render_canonical(artifact_path)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg_bytes)
    metadata_path.write_bytes(metadata_bytes)
    return svg_path, metadata_path


def write_preview_diagnostics(
    *,
    artifact_path: Path,
    diagnostics_path: Path,
) -> Path:
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_bytes(
        build_preview_diagnostics(_artifact_display_data(artifact_path))
    )
    return diagnostics_path


def export_png(
    *,
    rsvg_convert: Path,
    svg_path: Path,
    png_path: Path,
    width: int,
    height: int,
) -> Path:
    if not rsvg_convert.is_file():
        raise FractalPosterContractError(
            f"rsvg-convert executable does not exist: {rsvg_convert}"
        )
    if not svg_path.is_file():
        raise FractalPosterContractError(f"SVG input does not exist: {svg_path}")
    if width <= 0 or height <= 0:
        raise FractalPosterContractError("PNG dimensions must be positive")

    png_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(rsvg_convert),
        "--format=png",
        "--width",
        str(width),
        "--height",
        str(height),
        "--output",
        str(png_path),
        str(svg_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise FractalPosterContractError(
            "cannot execute rsvg-convert"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise FractalPosterContractError(
            f"rsvg-convert failed: {stderr or exc.returncode}"
        ) from exc

    if not png_path.is_file() or png_path.stat().st_size <= 0:
        raise FractalPosterContractError(
            "rsvg-convert did not create a non-empty PNG"
        )

    return png_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a temporary refined D1 Polaroid poster preview."
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
        help="Explicit temporary SVG output path.",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        required=True,
        help="Explicit temporary sidecar metadata output path.",
    )
    parser.add_argument(
        "--diagnostics-output",
        type=Path,
        help="Optional temporary geometry diagnostics JSON output path.",
    )
    parser.add_argument(
        "--png-output",
        type=Path,
        help="Optional explicit local temporary PNG output path.",
    )
    parser.add_argument(
        "--rsvg-convert",
        type=Path,
        help="Explicit path to local rsvg-convert executable.",
    )
    parser.add_argument(
        "--png-width",
        type=int,
        help="PNG width; requires --png-output and --rsvg-convert.",
    )
    parser.add_argument(
        "--png-height",
        type=int,
        help="PNG height; requires --png-output and --rsvg-convert.",
    )
    return parser.parse_args()

def main() -> int:
    args = parse_args()

    png_arguments = (
        args.png_output,
        args.rsvg_convert,
        args.png_width,
        args.png_height,
    )
    if any(value is not None for value in png_arguments) and not all(
        value is not None for value in png_arguments
    ):
        raise FractalPosterContractError(
            "PNG export requires --png-output, --rsvg-convert, "
            "--png-width, and --png-height together"
        )

    write_canonical_outputs(
        artifact_path=args.artifact,
        svg_path=args.svg_output,
        metadata_path=args.metadata_output,
    )

    if args.diagnostics_output is not None:
        write_preview_diagnostics(
            artifact_path=args.artifact,
            diagnostics_path=args.diagnostics_output,
        )

    if args.png_output is not None:
        export_png(
            rsvg_convert=args.rsvg_convert,
            svg_path=args.svg_output,
            png_path=args.png_output,
            width=args.png_width,
            height=args.png_height,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())