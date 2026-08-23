from __future__ import annotations

import argparse
import hashlib
import html
import json
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

POSTER_ID = "d1_rock_v1_poster"
POSTER_SCHEMA_VERSION = "d1_poster_metadata/v1"
RENDERER_NAME = "d1_rock_poster_renderer"
RENDERER_VERSION = "2"
PUBLICATION_COMMIT = "367a33e53f7be0c7c619c3ab2c8c1a5fc0bdd1c2"

CANONICAL_VIEWBOX = "0 0 1080 1080"
CANONICAL_SIZE_PX = 1080
ARTIFACT_RELATIVE_PATH = Path("artifacts/d1/features/d1_rock_v1.json")

SVG_FILENAME = "d1_rock_v1_poster.svg"
METADATA_FILENAME = "d1_rock_v1_poster.metadata.json"

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
HORIZONTAL_ELLIPSIS = "\u2026"
THETA = "\u03b8"
MIDDLE_DOT = "\u00b7"
MULTIPLICATION_SIGN = "\u00d7"

_SVG_TITLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]*\Z")


class PosterContractError(ValueError):
    """Raised when an artifact cannot produce a valid D1 Rock poster."""


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
        raise PosterContractError(f"{field} must be a non-empty string")
    return value


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PosterContractError(f"{field} must be a positive integer")
    return value


def _display_title_from_locator(locator: Mapping[str, Any] | None) -> str:
    if not isinstance(locator, Mapping) or set(locator) != {"registry_path"}:
        raise PosterContractError(
            "source_locator must contain exactly registry_path"
        )

    registry_path = _require_string(
        locator["registry_path"],
        "source_locator.registry_path",
    )
    if "\\" in registry_path or registry_path.startswith("/"):
        raise PosterContractError(
            "source_locator.registry_path must be a relative POSIX path"
        )

    basename = registry_path.rsplit("/", 1)[-1]
    if (
        basename in {"", ".", ".."}
        or not _SVG_TITLE_RE.fullmatch(basename)
        or basename.startswith(".")
    ):
        raise PosterContractError(
            "source_locator.registry_path has an invalid basename"
        )

    return basename.upper()


def _artifact_display_data(artifact_path: Path) -> dict[str, Any]:
    artifact = read_feature_artifact(artifact_path)

    if artifact.analysis_id != "d1_rock_v1":
        raise PosterContractError("poster renderer accepts only d1_rock_v1")
    if artifact.schema_version != "d1_feature_artifact/v2":
        raise PosterContractError(
            "poster renderer requires d1_feature_artifact/v2"
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

    return {
        "analysis_id": artifact.analysis_id,
        "canonical_theta_hash": _require_string(
            artifact.canonical_theta_hash,
            "canonical_theta_hash",
        ),
        "feature_sha256": _require_string(
            artifact.feature_sha256,
            "feature_sha256",
        ),
        "git_sha": _require_string(artifact.git_sha, "git_sha"),
        "schema_version": artifact.schema_version,
        "source_byte_size": source_byte_size,
        "source_content_sha256": source_content_sha256,
        "source_locator_registry_path": artifact.source_locator["registry_path"],
        "source_title": source_title,
    }


def _short_hash(value: str, prefix: int = 16, suffix: int = 6) -> str:
    if len(value) <= prefix + suffix + 1:
        return value
    return f"{value[:prefix]}{HORIZONTAL_ELLIPSIS}{value[-suffix:]}"


def _svg_text(
    x: float,
    y: float,
    text: str,
    *,
    css_class: str,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" '
        f'class="{css_class}" text-anchor="{anchor}">'
        f"{html.escape(text)}</text>"
    )


def _base_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact": dict(data),
        "canonical_outputs": {
            "svg_filename": SVG_FILENAME,
            "svg_viewbox": CANONICAL_VIEWBOX,
        },
        "central_graphic": {
            "label": "CONCEPTUAL TRANSFORMATION MAP",
            "representation": (
                "enlarged spectral-rock metaphor transitioning to "
                "theta coordinate grid"
            ),
            "scale_note": (
                "central scene enlarged for visual hierarchy; "
                "not a measured spectrum"
            ),
            "warning": "NOT A SPECTROGRAM",
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


def _spectral_bars() -> list[str]:
    bars: list[str] = []
    bar_heights = (
        32, 68, 48, 100, 76, 132, 94, 182, 122, 214, 154, 256,
        192, 286, 216, 250, 168, 202, 134, 162, 102, 126, 76,
    )

    for index, height in enumerate(bar_heights):
        x = 196 + index * 28
        y = 545 - height / 2
        color = (
            PALETTE["rock_magenta"]
            if index % 2 == 0
            else PALETTE["audit_cyan"]
        )
        bars.append(
            f'<rect x="{x}" y="{y:.1f}" width="16" height="{height}" '
            f'fill="{color}" opacity="0.88"/>'
        )

    return bars


def _theta_grid() -> list[str]:
    lines: list[str] = []

    for offset in range(5):
        x = 700 + offset * 48
        lines.append(
            f'<line x1="{x}" y1="430" x2="{x}" y2="660" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.7" '
            'opacity="0.92"/>'
        )

    for offset in range(6):
        y = 430 + offset * 46
        lines.append(
            f'<line x1="700" y1="{y}" x2="892" y2="{y}" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.7" '
            'opacity="0.92"/>'
        )

    for offset in range(4):
        x1 = 700 + offset * 48
        x2 = x1 + 48
        lines.append(
            f'<line x1="{x1}" y1="430" x2="{x2}" y2="476" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.2" '
            'opacity="0.68"/>'
        )
        lines.append(
            f'<line x1="{x1}" y1="476" x2="{x2}" y2="522" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.2" '
            'opacity="0.54"/>'
        )
        lines.append(
            f'<line x1="{x1}" y1="522" x2="{x2}" y2="568" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.2" '
            'opacity="0.42"/>'
        )

    return lines


def render_svg(data: Mapping[str, Any]) -> bytes:
    source_hash = data["source_content_sha256"]
    theta_hash = data["canonical_theta_hash"]
    feature_hash = data["feature_sha256"]
    source_title = data["source_title"]
    source_size = data["source_byte_size"]
    locator = data["source_locator_registry_path"]

    embedded_metadata = _embedded_svg_metadata(data)

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" '
            'height="1080" viewBox="0 0 1080 1080" role="img" '
            'aria-labelledby="poster-title poster-description">',
            f"<metadata>{embedded_metadata}</metadata>",
            "<title id=\"poster-title\">"
            f"{html.escape(source_title)} {RIGHT_ARROW} D1"
            "</title>",
            "<desc id=\"poster-description\">"
            "An audit poster for a D1 audio artifact. The enlarged central "
            "graphic is a conceptual transformation map, not a spectrogram."
            "</desc>",
            "<style>",
            (
                ".title{font-family:Arial,Helvetica,sans-serif;"
                "font-size:54px;font-weight:700;letter-spacing:2px;"
                f"fill:{PALETTE['primary_text']};}}"
            ),
            (
                ".subtitle{font-family:Arial,Helvetica,sans-serif;"
                "font-size:15px;letter-spacing:3px;"
                f"fill:{PALETTE['secondary_text']};}}"
            ),
            (
                ".label{font-family:Arial,Helvetica,sans-serif;"
                "font-size:13px;letter-spacing:2px;"
                f"fill:{PALETTE['secondary_text']};}}"
            ),
            (
                ".label-primary{font-family:Arial,Helvetica,sans-serif;"
                "font-size:13px;letter-spacing:2px;"
                f"fill:{PALETTE['primary_text']};}}"
            ),
            (
                ".body{font-family:Arial,Helvetica,sans-serif;"
                "font-size:16px;letter-spacing:0.5px;"
                f"fill:{PALETTE['primary_text']};}}"
            ),
            (
                ".hash-audit{font-family:Consolas,Menlo,monospace;"
                "font-size:16px;"
                f"fill:{PALETTE['audit_cyan']};}}"
            ),
            (
                ".hash-theta{font-family:Consolas,Menlo,monospace;"
                "font-size:16px;"
                f"fill:{PALETTE['theta_gold']};}}"
            ),
            (
                ".hash-semantic{font-family:Consolas,Menlo,monospace;"
                "font-size:16px;"
                f"fill:{PALETTE['semantic_green']};}}"
            ),
            (
                ".smallhash{font-family:Consolas,Menlo,monospace;"
                "font-size:13px;"
                f"fill:{PALETTE['secondary_text']};}}"
            ),
            (
                ".manifesto{font-family:Arial,Helvetica,sans-serif;"
                "font-size:18px;font-weight:700;letter-spacing:1.5px;"
                f"fill:{PALETTE['primary_text']};}}"
            ),
            "</style>",
            (
                f'<rect width="1080" height="1080" '
                f'fill="{PALETTE["background"]}"/>'
            ),
            (
                f'<rect x="54" y="54" width="972" height="972" fill="none" '
                f'stroke="{PALETTE["border"]}" stroke-width="1.5"/>'
            ),
            _svg_text(
                540,
                137,
                f"{source_title} {RIGHT_ARROW} D1",
                css_class="title",
                anchor="middle",
            ),
            _svg_text(
                540,
                168,
                "FROM PHYSICAL AUDIO TO CANONICAL FORM",
                css_class="subtitle",
                anchor="middle",
            ),
            _svg_text(
                540,
                226,
                "SHA-256 OF AUDIO SOURCE",
                css_class="label",
                anchor="middle",
            ),
            _svg_text(
                540,
                252,
                _short_hash(source_hash),
                css_class="hash-audit",
                anchor="middle",
            ),
            (
                f'<rect x="331" y="278" width="418" height="96" rx="4" '
                f'fill="none" stroke="{PALETTE["audit_cyan"]}" '
                'stroke-width="1.8"/>'
            ),
            _svg_text(
                540,
                312,
                f"SOURCE FILE: {source_title}",
                css_class="body",
                anchor="middle",
            ),
            _svg_text(
                540,
                345,
                f"{source_size:,} BYTES {MIDDLE_DOT} APPROVED INPUT",
                css_class="hash-audit",
                anchor="middle",
            ),
            (
                f'<line x1="540" y1="374" x2="540" y2="397" '
                f'stroke="{PALETTE["audit_cyan"]}" stroke-width="1.8"/>'
            ),
            (
                f'<path d="M532 390 L540 398 L548 390" fill="none" '
                f'stroke="{PALETTE["audit_cyan"]}" stroke-width="1.8"/>'
            ),
            _svg_text(
                540,
                406,
                "EXTRACTION",
                css_class="label",
                anchor="middle",
            ),
            (
                f'<rect x="104" y="420" width="872" height="270" rx="6" '
                f'fill="{PALETTE["background"]}" '
                f'stroke="{PALETTE["border"]}" stroke-width="1.8"/>'
            ),
            _svg_text(
                540,
                452,
                "CONCEPTUAL TRANSFORMATION MAP",
                css_class="label-primary",
                anchor="middle",
            ),
            *_spectral_bars(),
            (
                f'<line x1="636" y1="545" x2="677" y2="545" '
                f'stroke="{PALETTE["secondary_text"]}" stroke-width="1.7"/>'
            ),
            (
                f'<path d="M669 537 L677 545 L669 553" fill="none" '
                f'stroke="{PALETTE["secondary_text"]}" stroke-width="1.7"/>'
            ),
            *_theta_grid(),
            _svg_text(
                540,
                666,
                "NOT A SPECTROGRAM",
                css_class="label",
                anchor="middle",
            ),
            (
                f'<line x1="540" y1="691" x2="540" y2="715" '
                f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.8"/>'
            ),
            (
                f'<path d="M532 708 L540 716 L548 708" fill="none" '
                f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.8"/>'
            ),
            _svg_text(
                540,
                745,
                f"CANONICAL {THETA} HASH",
                css_class="label",
                anchor="middle",
            ),
            _svg_text(
                540,
                771,
                theta_hash,
                css_class="hash-theta",
                anchor="middle",
            ),
            _svg_text(
                540,
                817,
                "SEMANTIC FEATURE HASH",
                css_class="label",
                anchor="middle",
            ),
            _svg_text(
                540,
                843,
                _short_hash(feature_hash),
                css_class="hash-semantic",
                anchor="middle",
            ),
            (
                f'<rect x="150" y="866" width="780" height="76" rx="4" '
                f'fill="none" stroke="{PALETTE["semantic_green"]}" '
                'stroke-width="1.5"/>'
            ),
            _svg_text(
                180,
                894,
                (
                    f"{data['schema_version']} {MIDDLE_DOT} "
                    f"{data['analysis_id']}"
                ),
                css_class="body",
            ),
            _svg_text(
                180,
                918,
                f"source: {locator}",
                css_class="smallhash",
            ),
            _svg_text(
                540,
                976,
                "LOCATION IS AUDITABLE.  SEMANTICS ARE IMMUTABLE.",
                css_class="manifesto",
                anchor="middle",
            ),
            _svg_text(
                540,
                1004,
                "MUSIC BECOMES A COORDINATE.",
                css_class="manifesto",
                anchor="middle",
            ),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render canonical SVG and metadata for the D1 Rock poster."
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