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
RENDERER_VERSION = "1"
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


def _metadata_dict(data: Mapping[str, Any], svg_sha256: str) -> dict[str, Any]:
    return {
        "artifact": dict(data),
        "canonical_outputs": {
            "svg_filename": SVG_FILENAME,
            "svg_sha256": svg_sha256,
            "svg_viewbox": CANONICAL_VIEWBOX,
        },
        "central_graphic": {
            "label": "CONCEPTUAL TRANSFORMATION MAP",
            "representation": (
                "spectral-rock metaphor transitioning to theta coordinate grid"
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
        "raster_outputs": [],
        "schema_version": POSTER_SCHEMA_VERSION,
    }


def _svg_metadata(data: Mapping[str, Any], svg_sha256: str) -> str:
    encoded = canonical_json_bytes(
        _metadata_dict(data, svg_sha256)
    ).decode("utf-8").rstrip("\n")
    return html.escape(encoded)


def render_svg(data: Mapping[str, Any]) -> bytes:
    source_hash = data["source_content_sha256"]
    theta_hash = data["canonical_theta_hash"]
    feature_hash = data["feature_sha256"]
    source_title = data["source_title"]
    source_size = data["source_byte_size"]
    locator = data["source_locator_registry_path"]

    provisional_metadata = _svg_metadata(data, "sha256:" + "0" * 64)

    spectral_bars = []
    bar_heights = (
        20, 46, 35, 72, 55, 95, 68, 132, 88, 154, 114, 184,
        138, 208, 158, 180, 120, 145, 96, 115, 73, 91, 54,
    )
    for index, height in enumerate(bar_heights):
        x = 250 + index * 25
        y = 500 - height / 2
        color = (
            PALETTE["rock_magenta"]
            if index % 2 == 0
            else PALETTE["audit_cyan"]
        )
        spectral_bars.append(
            f'<rect x="{x}" y="{y:.1f}" width="14" height="{height}" '
            f'fill="{color}" opacity="0.78"/>'
        )

    theta_lines = []
    for offset in range(5):
        x = 675 + offset * 47
        theta_lines.append(
            f'<line x1="{x}" y1="420" x2="{x}" y2="580" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.4" '
            f'opacity="0.85"/>'
        )
    for offset in range(5):
        y = 420 + offset * 40
        theta_lines.append(
            f'<line x1="675" y1="{y}" x2="863" y2="{y}" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.4" '
            f'opacity="0.85"/>'
        )
    for offset in range(4):
        theta_lines.append(
            f'<line x1="{675 + offset * 47}" y1="420" '
            f'x2="{722 + offset * 47}" y2="460" '
            f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.0" '
            f'opacity="0.58"/>'
        )

    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="1080" '
            'height="1080" viewBox="0 0 1080 1080" role="img" '
            'aria-labelledby="poster-title poster-description">',
            f"<metadata>{provisional_metadata}</metadata>",
            "<title id=\"poster-title\">"
            f"{html.escape(source_title)} {RIGHT_ARROW} D1"
            "</title>",
            "<desc id=\"poster-description\">"
            "A conceptual transformation map from a D1 audio artifact "
            "to canonical coordinate provenance. Not a spectrogram."
            "</desc>",
            "<style>",
            (
                ".title{font-family:Arial,Helvetica,sans-serif;"
                "font-size:54px;font-weight:700;letter-spacing:2px;}"
            ),
            (
                ".subtitle{font-family:Arial,Helvetica,sans-serif;"
                "font-size:15px;letter-spacing:3px;}"
            ),
            (
                ".label{font-family:Arial,Helvetica,sans-serif;"
                "font-size:13px;letter-spacing:2px;}"
            ),
            (
                ".body{font-family:Arial,Helvetica,sans-serif;"
                "font-size:16px;letter-spacing:0.5px;}"
            ),
            (
                ".hash{font-family:Consolas,Menlo,monospace;"
                "font-size:16px;}"
            ),
            (
                ".smallhash{font-family:Consolas,Menlo,monospace;"
                "font-size:13px;}"
            ),
            (
                ".manifesto{font-family:Arial,Helvetica,sans-serif;"
                "font-size:18px;font-weight:700;letter-spacing:1.5px;}"
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
                css_class="hash",
                anchor="middle",
            ),
            (
                f'<rect x="351" y="286" width="378" height="94" rx="4" '
                f'fill="none" stroke="{PALETTE["audit_cyan"]}" '
                'stroke-width="1.5"/>'
            ),
            _svg_text(
                540,
                327,
                source_title,
                css_class="body",
                anchor="middle",
            ),
            _svg_text(
                540,
                354,
                f"{source_size:,} B",
                css_class="hash",
                anchor="middle",
            ),
            (
                f'<line x1="540" y1="380" x2="540" y2="407" '
                f'stroke="{PALETTE["audit_cyan"]}" stroke-width="1.5"/>'
            ),
            (
                f'<path d="M532 400 L540 408 L548 400" fill="none" '
                f'stroke="{PALETTE["audit_cyan"]}" stroke-width="1.5"/>'
            ),
            _svg_text(
                540,
                406,
                "EXTRACTION",
                css_class="label",
                anchor="middle",
            ),
            (
                f'<rect x="150" y="420" width="780" height="185" rx="4" '
                f'fill="{PALETTE["background"]}" '
                f'stroke="{PALETTE["border"]}" stroke-width="1.5"/>'
            ),
            _svg_text(
                540,
                450,
                "CONCEPTUAL TRANSFORMATION MAP",
                css_class="label",
                anchor="middle",
            ),
            *spectral_bars,
            (
                f'<line x1="600" y1="500" x2="655" y2="500" '
                f'stroke="{PALETTE["secondary_text"]}" stroke-width="1.4"/>'
            ),
            (
                f'<path d="M647 492 L655 500 L647 508" fill="none" '
                f'stroke="{PALETTE["secondary_text"]}" stroke-width="1.4"/>'
            ),
            *theta_lines,
            _svg_text(
                540,
                581,
                "NOT A SPECTROGRAM",
                css_class="label",
                anchor="middle",
            ),
            (
                f'<line x1="540" y1="605" x2="540" y2="634" '
                f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.5"/>'
            ),
            (
                f'<path d="M532 627 L540 635 L548 627" fill="none" '
                f'stroke="{PALETTE["theta_gold"]}" stroke-width="1.5"/>'
            ),
            _svg_text(
                540,
                664,
                f"CANONICAL {THETA} HASH",
                css_class="label",
                anchor="middle",
            ),
            _svg_text(
                540,
                690,
                theta_hash,
                css_class="hash",
                anchor="middle",
            ),
            _svg_text(
                540,
                737,
                "SEMANTIC FEATURE HASH",
                css_class="label",
                anchor="middle",
            ),
            _svg_text(
                540,
                763,
                _short_hash(feature_hash),
                css_class="hash",
                anchor="middle",
            ),
            (
                f'<rect x="150" y="796" width="780" height="101" rx="4" '
                f'fill="none" stroke="{PALETTE["semantic_green"]}" '
                'stroke-width="1.5"/>'
            ),
            _svg_text(
                180,
                826,
                (
                    f"{data['schema_version']} {MIDDLE_DOT} "
                    f"{data['analysis_id']}"
                ),
                css_class="body",
            ),
            _svg_text(
                180,
                852,
                f"source: {locator}",
                css_class="smallhash",
            ),
            _svg_text(
                180,
                877,
                (
                    "publication: "
                    f"{_short_hash(PUBLICATION_COMMIT, 16, 6)}"
                ),
                css_class="smallhash",
            ),
            _svg_text(
                540,
                934,
                "LOCATION IS AUDITABLE.",
                css_class="manifesto",
                anchor="middle",
            ),
            _svg_text(
                540,
                962,
                "SEMANTICS ARE IMMUTABLE.",
                css_class="manifesto",
                anchor="middle",
            ),
            _svg_text(
                540,
                990,
                "MUSIC BECOMES A COORDINATE.",
                css_class="manifesto",
                anchor="middle",
            ),
            "</svg>",
            "",
        ]
    ).encode("utf-8")

    provisional_hash = sha256_prefixed(svg)
    final_metadata = _svg_metadata(data, provisional_hash)
    return svg.replace(
        provisional_metadata.encode("utf-8"),
        final_metadata.encode("utf-8"),
        1,
    )


def build_metadata(data: Mapping[str, Any], svg_bytes: bytes) -> bytes:
    return canonical_json_bytes(
        _metadata_dict(data, sha256_prefixed(svg_bytes))
    )


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