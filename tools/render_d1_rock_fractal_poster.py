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
RENDERER_VERSION = "3"
PUBLICATION_COMMIT = "367a33e53f7be0c7c619c3ab2c8c1a5fc0bdd1c2"

ART_FIELD_SIZE_PX = 1080
TECHNICAL_FIELD_HEIGHT_PX = 180
CANONICAL_WIDTH_PX = ART_FIELD_SIZE_PX
CANONICAL_HEIGHT_PX = ART_FIELD_SIZE_PX + TECHNICAL_FIELD_HEIGHT_PX
CANONICAL_VIEWBOX = (
    f"0 0 {CANONICAL_WIDTH_PX} {CANONICAL_HEIGHT_PX}"
)

PREVIEW_WIDTH_PX = 1080
PREVIEW_HEIGHT_PX = 1260
FINAL_WIDTH_PX = 1528
FINAL_HEIGHT_PX = 1783

ARTIFACT_RELATIVE_PATH = Path("artifacts/d1/features/d1_rock_v1.json")
SVG_FILENAME = "d1_rock_v1_fractal_poster.svg"
METADATA_FILENAME = "d1_rock_v1_fractal_poster.metadata.json"

SAFE_NODE_X_MIN = 108.0
SAFE_NODE_X_MAX = 972.0
SAFE_NODE_Y_MIN = 65.0
SAFE_NODE_Y_MAX = 281.0

PALETTE = {
    "audit_cyan": "#46D9E8",
    "background": "#070A12",
    "card": "#F1EEE7",
    "primary_text": "#1B1D22",
    "rock_magenta": "#C75CEB",
    "secondary_text": "#5B5E66",
    "theta_gold": "#B6811F",
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


def seed_prefix(data: Mapping[str, Any], length: int = 16) -> str:
    if length <= 0:
        raise FractalPosterContractError("seed prefix length must be positive")
    return _seed_bytes(data).hex()[:length]


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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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


def _safe_node_center(
    x: float,
    y: float,
    radius: float,
) -> tuple[float, float]:
    return (
        _clamp(x, SAFE_NODE_X_MIN + radius, SAFE_NODE_X_MAX - radius),
        _clamp(y, SAFE_NODE_Y_MIN + radius, SAFE_NODE_Y_MAX - radius),
    )


def _branch_geometry(seed: bytes) -> list[str]:
    elements: list[str] = []
    palette_cycle = (
        PALETTE["audit_cyan"],
        PALETTE["rock_magenta"],
        PALETTE["theta_gold"],
    )

    root_x = 540.0
    root_y = 610.0
    root_angle = -math.pi / 2.0
    root_length = 228.0 + 20.0 * _seed_fraction(seed, 0)
    branch_angle = 0.34 + 0.24 * _seed_fraction(seed, 1)
    shrink = 0.62 + 0.06 * _seed_fraction(seed, 2)
    max_depth = 5
    stack: list[tuple[float, float, float, float, int, int]] = [
        (root_x, root_y, root_angle, root_length, 0, 0)
    ]

    while stack:
        x1, y1, angle, length, depth, branch_index = stack.pop()
        proposed_x2 = x1 + length * math.cos(angle)
        proposed_y2 = y1 + length * math.sin(angle)

        if depth % 2 == 0:
            node_radius = max(5.5, 18.0 - depth * 2.2)
            x2, y2 = _safe_node_center(
                proposed_x2,
                proposed_y2,
                node_radius,
            )
        else:
            x2 = proposed_x2
            y2 = proposed_y2

        color = palette_cycle[(depth + branch_index) % len(palette_cycle)]
        width = max(1.2, 8.5 - depth * 1.3)
        opacity = max(0.34, 0.94 - depth * 0.11)

        elements.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" '
            f'x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" '
            f'stroke-width="{width:.2f}" stroke-linecap="round" '
            f'opacity="{opacity:.2f}"/>'
        )

        if depth % 2 == 0:
            sides = 5 + int(_seed_fraction(seed, depth + branch_index) * 3)
            rotation = angle + math.pi / 2.0
            polygon = _crystal_polygon(
                x2,
                y2,
                node_radius,
                sides,
                rotation,
            )
            elements.append(
                f'<polygon points="{polygon}" fill="none" stroke="{color}" '
                f'stroke-width="{max(1.0, width * 0.35):.2f}" '
                f'opacity="{min(0.88, opacity + 0.08):.2f}"/>'
            )

        if depth >= max_depth:
            continue

        asymmetry = (
            _seed_fraction(seed, depth * 5 + branch_index) - 0.5
        ) * 0.16
        next_length = length * shrink
        left_angle = angle - branch_angle + asymmetry
        right_angle = angle + branch_angle + asymmetry

        stack.append(
            (
                x2,
                y2,
                right_angle,
                next_length,
                depth + 1,
                branch_index * 2 + 2,
            )
        )
        stack.append(
            (
                x2,
                y2,
                left_angle,
                next_length,
                depth + 1,
                branch_index * 2 + 1,
            )
        )

    return elements


def _deformed_arc_segment(
    *,
    cx: float,
    cy: float,
    radius: float,
    start_angle: float,
    end_angle: float,
    bend: float,
) -> str:
    x1 = cx + radius * math.cos(start_angle)
    y1 = cy + radius * math.sin(start_angle)
    x2 = cx + radius * math.cos(end_angle)
    y2 = cy + radius * math.sin(end_angle)

    midpoint = (start_angle + end_angle) / 2.0
    control_radius = radius + bend
    c1_angle = start_angle + (end_angle - start_angle) * 0.33
    c2_angle = start_angle + (end_angle - start_angle) * 0.67

    c1x = cx + control_radius * math.cos(c1_angle)
    c1y = cy + control_radius * math.sin(c1_angle)
    c2x = cx + control_radius * math.cos(c2_angle)
    c2y = cy + control_radius * math.sin(c2_angle)

    midpoint_x = cx + (radius + bend * 0.45) * math.cos(midpoint)
    midpoint_y = cy + (radius + bend * 0.45) * math.sin(midpoint)

    return (
        f"M {x1:.2f} {y1:.2f} "
        f"C {c1x:.2f} {c1y:.2f}, {midpoint_x:.2f} {midpoint_y:.2f}, "
        f"{c2x:.2f} {c2y:.2f} "
        f"S {x2:.2f} {y2:.2f}, {x2:.2f} {y2:.2f}"
    )


def _theta_curves(seed: bytes) -> list[str]:
    curves: list[str] = []
    cx = 518.0
    cy = 575.0
    count = 6 + int(_seed_fraction(seed, 7) * 2)
    base_radius = 104.0 + 16.0 * _seed_fraction(seed, 8)

    for index in range(count):
        radius = base_radius + index * (
            35.0 + 9.0 * _seed_fraction(seed, 9 + index)
        )
        start_angle = (
            -1.62
            + index * 0.13
            + (_seed_fraction(seed, 16 + index) - 0.5) * 0.24
        )
        total_span = 1.02 + _seed_fraction(seed, 23 + index) * 0.72
        gap_fraction = 0.08 + _seed_fraction(seed, 30 + index) * 0.13
        split_angle = start_angle + total_span * (
            0.42 + (_seed_fraction(seed, 37 + index) - 0.5) * 0.16
        )
        gap = total_span * gap_fraction
        bend = (
            _seed_fraction(seed, 44 + index) - 0.5
        ) * (17.0 + index * 3.0)
        color = (
            PALETTE["audit_cyan"]
            if index < 3
            else PALETTE["theta_gold"]
        )
        opacity = 0.28 + index * 0.075
        width = 1.15 + index * 0.13

        first_segment = _deformed_arc_segment(
            cx=cx,
            cy=cy,
            radius=radius,
            start_angle=start_angle,
            end_angle=split_angle - gap / 2.0,
            bend=bend,
        )
        second_segment = _deformed_arc_segment(
            cx=cx,
            cy=cy,
            radius=radius,
            start_angle=split_angle + gap / 2.0,
            end_angle=start_angle + total_span,
            bend=-bend * 0.72,
        )

        curves.append(
            f'<path class="theta-curve" d="{first_segment}" fill="none" '
            f'stroke="{color}" stroke-width="{width:.2f}" '
            f'stroke-linecap="round" opacity="{opacity:.2f}"/>'
        )
        curves.append(
            f'<path class="theta-curve" d="{second_segment}" fill="none" '
            f'stroke="{color}" stroke-width="{width:.2f}" '
            f'stroke-linecap="round" opacity="{opacity:.2f}"/>'
        )

    return curves


def _star_field(seed: bytes) -> list[str]:
    stars: list[str] = []

    for index in range(56):
        x = 72.0 + _seed_fraction(seed, index * 3) * 936.0
        y = 90.0 + _seed_fraction(seed, index * 3 + 1) * 880.0
        radius = 0.55 + _seed_fraction(seed, index * 3 + 2) * 1.7
        color = (
            PALETTE["audit_cyan"]
            if index % 3 == 0
            else "#C8D1DF"
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
            "art_field_px": [
                ART_FIELD_SIZE_PX,
                ART_FIELD_SIZE_PX,
            ],
            "composition": {
                "branch_lines": (
                    "seed-derived branch network with a central cyan "
                    "transformation axis and one transition node"
                ),
                "node_safe_zone": {
                    "x_max": SAFE_NODE_X_MAX,
                    "x_min": SAFE_NODE_X_MIN,
                    "y_max": SAFE_NODE_Y_MAX,
                    "y_min": SAFE_NODE_Y_MIN,
                },
                "theta_curves": (
                    "seed-derived deformed broken Bezier curves; "
                    "artistic, not measured waveforms"
                ),
            },
            "representation": (
                "deterministic artistic interpretation bound to the "
                "validated D1 identity"
            ),
            "scientific_claim": (
                "artistic interpretation; not a spectrogram, measured "
                "fractal property, or scientific visualization of the track"
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


def _embedded_svg_metadata(data: Mapping[str, Any]) -> str:
    encoded = canonical_json_bytes(
        _base_metadata(data)
    ).decode("utf-8").rstrip("\n")
    return html.escape(encoded)


def render_svg(data: Mapping[str, Any]) -> bytes:
    source_title = data["source_title"]
    seed = _seed_bytes(data)
    seed_label = (
        f"{data['analysis_id']} {MIDDLE_DOT} seed {seed_prefix(data)}"
    )
    embedded_metadata = _embedded_svg_metadata(data)

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" '
            'height="1260" viewBox="0 0 1080 1260" role="img" '
            'aria-labelledby="poster-title poster-description">',
            f"<metadata>{embedded_metadata}</metadata>",
            "<title id=\"poster-title\">"
            f"{html.escape(source_title)} D1 polaroid poster"
            "</title>",
            "<desc id=\"poster-description\">"
            "A deterministic artistic interpretation bound to a validated "
            "D1 identity. The square art field contains only a crystalline "
            "wave composition; the lower technical field contains the "
            "source filename and a short seed prefix."
            "</desc>",
            "<defs>",
            (
                '<filter id="crystal-glow" x="-80%" y="-80%" '
                'width="260%" height="260%">'
            ),
            '<feGaussianBlur stdDeviation="5" result="blur"/>',
            '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/>'
            "</feMerge>",
            "</filter>",
            (
                '<radialGradient id="core-glow" cx="50%" cy="50%" r="50%">'
            ),
            f'<stop offset="0%" stop-color="{PALETTE["rock_magenta"]}" '
            'stop-opacity="0.34"/>',
            f'<stop offset="45%" stop-color="{PALETTE["audit_cyan"]}" '
            'stop-opacity="0.12"/>',
            f'<stop offset="100%" stop-color="{PALETTE["background"]}" '
            'stop-opacity="0"/>',
            "</radialGradient>",
            "</defs>",
            "<style>",
            (
                ".caption{font-family:Arial,Helvetica,sans-serif;"
                "font-size:26px;font-weight:400;letter-spacing:1.2px;"
                f"fill:{PALETTE['primary_text']};}}"
            ),
            (
                ".technical{font-family:Consolas,Menlo,monospace;"
                "font-size:13px;letter-spacing:0.7px;"
                f"fill:{PALETTE['theta_gold']};}}"
            ),
            "</style>",
            (
                f'<rect width="{CANONICAL_WIDTH_PX}" '
                f'height="{CANONICAL_HEIGHT_PX}" '
                f'fill="{PALETTE["card"]}"/>'
            ),
            '<g id="art-field">',
            (
                f'<rect width="{ART_FIELD_SIZE_PX}" '
                f'height="{ART_FIELD_SIZE_PX}" '
                f'fill="{PALETTE["background"]}"/>'
            ),
            *_star_field(seed),
            '<circle cx="518" cy="575" r="440" fill="url(#core-glow)"/>',
            '<g filter="url(#crystal-glow)">',
            *_theta_curves(seed),
            *_branch_geometry(seed),
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
                540,
                1152,
                source_title,
                css_class="caption",
                anchor="middle",
            ),
            _svg_text(
                540,
                1191,
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
    metadata = _base_metadata(data)
    metadata["canonical_outputs"]["svg_sha256"] = sha256_prefixed(svg_bytes)
    metadata["raster_outputs"] = []
    return canonical_json_bytes(metadata)


def render_canonical(artifact_path: Path) -> tuple[bytes, bytes]:
    data = _artifact_display_data(artifact_path)
    svg_bytes = render_svg(data)
    metadata_bytes = build_metadata(data, svg_bytes)
    return svg_bytes, metadata_bytes


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
        description="Render canonical SVG and metadata for a D1 polaroid poster."
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
    parser.add_argument(
        "--png-output",
        type=Path,
        help="Optional explicit local PNG output path.",
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