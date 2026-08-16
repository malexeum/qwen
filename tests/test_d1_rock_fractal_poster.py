from __future__ import annotations

import html
import json
import re
import struct
from pathlib import Path

import pytest

from tools.render_d1_rock_fractal_poster import (
    ART_FIELD_SIZE_PX,
    ARTIFACT_RELATIVE_PATH,
    CANONICAL_HEIGHT_PX,
    CANONICAL_VIEWBOX,
    CANONICAL_WIDTH_PX,
    MIDDLE_DOT,
    PALETTE,
    PREVIEW_HEIGHT_PX,
    PREVIEW_WIDTH_PX,
    SAFE_NODE_X_MAX,
    SAFE_NODE_X_MIN,
    SAFE_NODE_Y_MAX,
    SAFE_NODE_Y_MIN,
    TECHNICAL_FIELD_HEIGHT_PX,
    build_metadata,
    export_png,
    render_canonical,
    seed_hex,
    seed_prefix,
    sha256_prefixed,
    write_canonical_outputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_RELATIVE_PATH


def _external_svg_references(svg_text: str) -> list[str]:
    patterns = (
        r"""(?:href|xlink:href)\s*=\s*["'](?:https?:|//)""",
        r"""url\(\s*["']?(?:https?:|//)""",
        r"""@import\s+(?:url\()?["']?(?:https?:|//)""",
    )
    return [
        match.group(0)
        for pattern in patterns
        for match in re.finditer(pattern, svg_text, flags=re.IGNORECASE)
    ]


def _visible_svg_text(svg_text: str) -> str:
    text_nodes = re.findall(
        r"<text\b[^>]*>(.*?)</text>",
        svg_text,
        flags=re.DOTALL,
    )
    return "\n".join(
        html.unescape(re.sub(r"<[^>]+>", "", node)).strip()
        for node in text_nodes
        if node.strip()
    )


def _group_content(svg_text: str, group_id: str) -> str:
    match = re.search(
        rf'<g id="{re.escape(group_id)}">(.*?)</g>',
        svg_text,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing SVG group: {group_id}"
    return match.group(1)


def _embedded_svg_metadata(svg_text: str) -> dict[str, object]:
    match = re.search(
        r"<metadata>(.*?)</metadata>",
        svg_text,
        flags=re.DOTALL,
    )
    assert match is not None, "canonical SVG must contain metadata"
    return json.loads(html.unescape(match.group(1)))


def _polygon_points(svg_text: str) -> list[tuple[float, float]]:
    polygons = re.findall(r'<polygon points="([^"]+)"', svg_text)
    points: list[tuple[float, float]] = []

    for polygon in polygons:
        for item in polygon.split():
            x_text, y_text = item.split(",", 1)
            points.append((float(x_text), float(y_text)))

    return points


def _png_dimensions(png_path: Path) -> tuple[int, int]:
    header = png_path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert header[12:16] == b"IHDR"
    return struct.unpack(">II", header[16:24])


def test_polaroid_is_deterministic_and_identity_bound(tmp_path):
    first_svg, first_metadata = render_canonical(ARTIFACT_PATH)
    second_svg, second_metadata = render_canonical(ARTIFACT_PATH)

    assert first_svg == second_svg
    assert first_metadata == second_metadata
    assert first_svg.endswith(b"\n")
    assert first_metadata.endswith(b"\n")
    assert b"\r" not in first_svg
    assert b"\r" not in first_metadata

    svg_text = first_svg.decode("utf-8")
    embedded_metadata = _embedded_svg_metadata(svg_text)
    metadata = json.loads(first_metadata.decode("utf-8"))

    assert (
        f'width="{CANONICAL_WIDTH_PX}" height="{CANONICAL_HEIGHT_PX}"'
        in svg_text
    )
    assert f'viewBox="{CANONICAL_VIEWBOX}"' in svg_text
    assert (
        f'<rect width="{ART_FIELD_SIZE_PX}" '
        f'height="{ART_FIELD_SIZE_PX}" '
        f'fill="{PALETTE["background"]}"/>'
    ) in svg_text
    assert (
        f'<rect y="{ART_FIELD_SIZE_PX}" '
        f'width="{CANONICAL_WIDTH_PX}" '
        f'height="{TECHNICAL_FIELD_HEIGHT_PX}" '
        f'fill="{PALETTE["card"]}"/>'
    ) in svg_text

    art_field = _group_content(svg_text, "art-field")
    technical_field = _group_content(svg_text, "technical-field")
    art_text = _visible_svg_text(art_field)
    technical_text = _visible_svg_text(technical_field)

    assert art_text == ""
    assert technical_text.splitlines() == [
        "ROCK.MP3",
        f"d1_rock_v1 {MIDDLE_DOT} seed {seed_prefix(metadata['artifact'])}",
    ]
    assert "ROCK.MP3" not in art_field
    assert "A CANONICAL AUDIO ARTIFACT" not in art_field
    assert "→ D1" not in art_field
    assert "sha256:" not in technical_text
    assert "source:" not in technical_text
    assert "publication:" not in technical_text

    assert '.caption{font-family:Arial,Helvetica,sans-serif;' in svg_text
    assert "font-size:26px;font-weight:400;letter-spacing:1.2px;" in svg_text
    assert '.technical{font-family:Consolas,Menlo,monospace;' in svg_text
    assert "font-size:13px;letter-spacing:0.7px;" in svg_text

    assert (
        '<text x="540.0" y="1152.0" class="caption" '
        'text-anchor="middle">'
    ) in svg_text
    assert (
        '<text x="540.0" y="1191.0" class="technical" '
        'text-anchor="middle">'
    ) in svg_text

    assert "<image" not in svg_text
    assert "data:image" not in svg_text
    assert "<script" not in svg_text
    assert "<foreignObject" not in svg_text
    assert "@font-face" not in svg_text
    assert not _external_svg_references(svg_text)

    assert '<filter id="crystal-glow"' in svg_text
    assert '<radialGradient id="core-glow"' in svg_text
    assert "<polygon " in art_field
    assert "<line " in art_field
    assert '<path class="theta-curve"' in art_field
    assert " A " not in art_field
    assert " C " in art_field
    assert " S " in art_field

    polygon_points = _polygon_points(art_field)
    assert polygon_points
    for x, y in polygon_points:
        assert SAFE_NODE_X_MIN <= x <= SAFE_NODE_X_MAX
        assert SAFE_NODE_Y_MIN <= y <= SAFE_NODE_Y_MAX

    artifact = metadata["artifact"]
    assert artifact["analysis_id"] == "d1_rock_v1"
    assert artifact["schema_version"] == "d1_feature_artifact/v2"
    assert artifact["source_locator_registry_path"] == "tests/audio/Rock.mp3"
    assert artifact["source_title"] == "ROCK.MP3"
    assert artifact["source_byte_size"] == 4_605_149
    assert artifact["canonical_theta_hash"] == "sha256:5e2ac5e7a4c1151d"
    assert artifact["feature_sha256"] == (
        "sha256:814b21fcdf5ae5a1e11172aa2301cd781f2d76446c436e27498902a9cebe81b4"
    )

    central_graphic = embedded_metadata["central_graphic"]
    assert (
        central_graphic["representation"]
        == "deterministic artistic interpretation bound to the "
        "validated D1 identity"
    )
    assert (
        central_graphic["seed_contract"]
        == "sha256(canonical_theta_hash + '|' + feature_sha256)"
    )
    assert central_graphic["seed_sha256"] == seed_hex(artifact)
    assert central_graphic["art_field_px"] == [1080, 1080]

    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(
        first_svg
    )
    assert metadata["raster_outputs"] == []
    assert "svg_sha256" not in embedded_metadata["canonical_outputs"]

    svg_path = tmp_path / "polaroid.svg"
    metadata_path = tmp_path / "polaroid.metadata.json"
    written_svg, written_metadata = write_canonical_outputs(
        artifact_path=ARTIFACT_PATH,
        svg_path=svg_path,
        metadata_path=metadata_path,
    )

    assert written_svg == svg_path
    assert written_metadata == metadata_path
    assert svg_path.read_bytes() == first_svg
    assert metadata_path.read_bytes() == first_metadata


def test_seed_changes_when_identity_hashes_change():
    svg_bytes, metadata_bytes = render_canonical(ARTIFACT_PATH)
    del svg_bytes
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    artifact = metadata["artifact"]

    theta_changed = dict(artifact)
    theta_changed["canonical_theta_hash"] = "sha256:0" * 0 + "sha256:" + "0" * 16
    assert seed_hex(theta_changed) != seed_hex(artifact)

    feature_changed = dict(artifact)
    feature_changed["feature_sha256"] = "sha256:" + "f" * 64
    assert seed_hex(feature_changed) != seed_hex(artifact)


def test_metadata_sha_linkage_matches_svg_bytes():
    svg_bytes, metadata_bytes = render_canonical(ARTIFACT_PATH)
    metadata = json.loads(metadata_bytes.decode("utf-8"))

    rebuilt_metadata = build_metadata(metadata["artifact"], svg_bytes)

    assert rebuilt_metadata == metadata_bytes
    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(
        svg_bytes
    )


def test_export_png_rejects_missing_executable(tmp_path):
    svg_path = tmp_path / "source.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    with pytest.raises(ValueError):
        export_png(
            rsvg_convert=tmp_path / "missing-rsvg-convert.exe",
            svg_path=svg_path,
            png_path=tmp_path / "out.png",
            width=PREVIEW_WIDTH_PX,
            height=PREVIEW_HEIGHT_PX,
        )


def test_png_dimensions_helper_rejects_non_png(tmp_path):
    invalid_png = tmp_path / "invalid.png"
    invalid_png.write_bytes(b"not a PNG")

    with pytest.raises(AssertionError):
        _png_dimensions(invalid_png)


@pytest.mark.parametrize(
    "locator",
    [
        None,
        {},
        {"registry_path": ""},
        {"registry_path": "../Rock.mp3"},
        {"registry_path": "/tests/audio/Rock.mp3"},
        {"registry_path": "tests\\audio\\Rock.mp3"},
        {"registry_path": "tests/audio/.Rock.mp3"},
        {"registry_path": "tests/audio/.."},
        {"registry_path": "tests/audio/Rock?.mp3"},
    ],
)
def test_renderer_fails_closed_for_invalid_source_locator(
    tmp_path,
    locator,
):
    raw = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    raw["source_locator"] = locator
    invalid_artifact = tmp_path / "invalid.json"
    invalid_artifact.write_text(
        json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        render_canonical(invalid_artifact)