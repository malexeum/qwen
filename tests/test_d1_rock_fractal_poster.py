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
    HEXAGON_ORIGIN,
    LYAPUNOV_SECONDARY_LAYER_FRACTION_MAX,
    MATERIALITY_MAX_IMPRINTS,
    MATERIALITY_MAX_SHADOW_FIELDS,
    MATERIALITY_OPACITY_MAX,
    MATERIALITY_OPACITY_MIN,
    MIDDLE_DOT,
    PALETTE,
    PREVIEW_HEIGHT_PX,
    PREVIEW_WIDTH_PX,
    SAFE_NODE_X_MAX,
    SAFE_NODE_X_MIN,
    SAFE_NODE_Y_MAX,
    SAFE_NODE_Y_MIN,
    TECHNICAL_FIELD_HEIGHT_PX,
    TRANSITION_ENDPOINT,
    _incoming_branch_geometry,
    _materiality_placement,
    _seed_bytes,
    _theta_geometry,
    build_metadata,
    build_preview_diagnostics,
    export_png,
    render_canonical,
    seed_hex,
    seed_prefix,
    sha256_prefixed,
    write_canonical_outputs,
    write_preview_diagnostics,
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
    opening = f'<g id="{group_id}">'
    start = svg_text.find(opening)
    assert start >= 0, f"missing SVG group: {group_id}"

    content_start = start + len(opening)
    depth = 1
    token_re = re.compile(r"</?g(?:\s[^>]*)?>")

    for match in token_re.finditer(svg_text, content_start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return svg_text[content_start:match.start()]
        elif not token.endswith("/>"):
            depth += 1

    raise AssertionError(f"unclosed SVG group: {group_id}")


def _embedded_svg_metadata(svg_text: str) -> dict[str, object]:
    match = re.search(
        r"<metadata>(.*?)</metadata>",
        svg_text,
        flags=re.DOTALL,
    )
    assert match is not None, "canonical SVG must contain metadata"
    return json.loads(html.unescape(match.group(1)))


def _polygon_points(svg_text: str) -> list[tuple[float, float]]:
    polygons = re.findall(r'<polygon[^>]*points="([^"]+)"', svg_text)
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


def _svg_data_float(element: str, name: str) -> float:
    match = re.search(rf'{re.escape(name)}="([^"]+)"', element)
    assert match is not None, f"missing SVG attribute: {name}"
    return float(match.group(1))


def _svg_data_text(element: str, name: str) -> str:
    match = re.search(rf'{re.escape(name)}="([^"]+)"', element)
    assert match is not None, f"missing SVG attribute: {name}"
    return match.group(1)


def _svg_elements_with_class(svg_text: str, css_class: str) -> list[str]:
    return re.findall(
        rf'<(?:path|line|polygon|circle)\b[^>]*\bclass="{re.escape(css_class)}"[^>]*>',
        svg_text,
        flags=re.DOTALL,
    )


def _artifact_data() -> dict[str, object]:
    _, metadata_bytes = render_canonical(ARTIFACT_PATH)
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    return metadata["artifact"]


def test_polaroid_is_deterministic_identity_bound_and_isolated(tmp_path):
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

    assert _visible_svg_text(art_field) == ""
    assert _visible_svg_text(technical_field).splitlines() == [
        "ROCK.MP3",
        f"d1_rock_v1 {MIDDLE_DOT} seed {seed_prefix(metadata['artifact'])}",
    ]

    assert "ROCK.MP3" not in art_field
    assert "A CANONICAL AUDIO ARTIFACT" not in art_field
    assert "sha256:" not in technical_field
    assert "source:" not in technical_field
    assert "publication:" not in technical_field

    assert '.caption{font-family:Arial,Helvetica,sans-serif;' in svg_text
    assert "font-size:26px;font-weight:400;letter-spacing:3px;" in svg_text
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
    assert '<radialGradient id="junction-glow"' in svg_text

    artifact = metadata["artifact"]
    assert artifact["analysis_id"] == "d1_rock_v1"
    assert artifact["schema_version"] == "d1_feature_artifact/v2"
    assert artifact["source_locator_registry_path"] == "tests/audio/Rock.mp3"
    assert artifact["source_title"] == "ROCK.MP3"

    central_graphic = embedded_metadata["central_graphic"]
    assert (
        central_graphic["representation"]
        == "deterministic artistic interpretation bound to the "
        "validated D1 identity"
    )
    assert central_graphic["seed_sha256"] == seed_hex(artifact)
    assert central_graphic["art_field_px"] == [1080, 1080]

    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(
        first_svg
    )
    assert metadata["raster_outputs"] == []
    assert "svg_sha256" not in embedded_metadata["canonical_outputs"]

    svg_path = tmp_path / "preview.svg"
    metadata_path = tmp_path / "preview.metadata.json"
    written_svg, written_metadata = write_canonical_outputs(
        artifact_path=ARTIFACT_PATH,
        svg_path=svg_path,
        metadata_path=metadata_path,
    )

    assert written_svg == svg_path
    assert written_metadata == metadata_path
    assert svg_path.read_bytes() == first_svg
    assert metadata_path.read_bytes() == first_metadata


def test_hexagon_is_literal_junction_and_primary_origin():
    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")

    hexagon = re.search(
        r'<polygon id="junction-hexagon"[^>]*>',
        art_field,
        flags=re.DOTALL,
    )
    assert hexagon is not None
    assert _svg_data_text(hexagon.group(0), "data-role") == "actual-junction"
    assert _svg_data_float(hexagon.group(0), "data-x") == HEXAGON_ORIGIN[0]
    assert _svg_data_float(hexagon.group(0), "data-y") == HEXAGON_ORIGIN[1]

    incoming = [
        line
        for line in _svg_elements_with_class(art_field, "branch-line")
        if _svg_data_text(line, "data-role") == "incoming-junction"
    ]

    assert len(incoming) >= 3

    incoming_colors = {_svg_data_text(line, "stroke") for line in incoming}
    assert PALETTE["audit_cyan"] in incoming_colors
    assert PALETTE["theta_gold"] in incoming_colors
    assert PALETTE["rock_magenta"] in incoming_colors

    for line in incoming:
        assert _svg_data_float(line, "data-end-x") == HEXAGON_ORIGIN[0]
        assert _svg_data_float(line, "data-end-y") == HEXAGON_ORIGIN[1]
        assert _svg_data_float(line, "data-start-y") >= 45.0

    assert art_field.count('class="resonance-halo"') == 2
    assert "hexagon-origin" not in art_field


def test_upper_tree_is_visible_de_mechanised_and_nodes_are_safe():
    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")

    lines = _svg_elements_with_class(art_field, "branch-line")
    upper_tree = [
        line
        for line in lines
        if _svg_data_text(line, "data-role") == "incoming-tree"
    ]
    offshoots = [
        line
        for line in lines
        if _svg_data_text(line, "data-role") == "secondary-offshoot"
    ]

    assert len(upper_tree) == 15
    assert len(offshoots) == 2
    assert all(
        _svg_data_float(line, "data-start-y") >= 28.0
        for line in upper_tree
    )
    assert all(
        _svg_data_float(line, "data-end-y") >= 94.0
        for line in upper_tree
    )

    total_length = 0.0
    visible_length = 0.0

    for line in lines:
        x1 = _svg_data_float(line, "x1")
        y1 = _svg_data_float(line, "y1")
        x2 = _svg_data_float(line, "x2")
        y2 = _svg_data_float(line, "y2")
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        total_length += length
        if (
            0.0 <= x1 <= ART_FIELD_SIZE_PX
            and 0.0 <= y1 <= ART_FIELD_SIZE_PX
            and 0.0 <= x2 <= ART_FIELD_SIZE_PX
            and 0.0 <= y2 <= ART_FIELD_SIZE_PX
        ):
            visible_length += length

    assert total_length > 0.0
    assert visible_length / total_length >= 0.92

    complete_nodes = _svg_elements_with_class(art_field, "branch-node")
    incomplete_nodes = re.findall(
        r'<path class="branch-node incomplete-node"[^>]*>',
        art_field,
        flags=re.DOTALL,
    )
    total_non_junction_nodes = len(complete_nodes) + len(incomplete_nodes)

    assert len(complete_nodes) == 10
    assert len(incomplete_nodes) == 2
    assert total_non_junction_nodes == 12
    assert 0.15 <= len(incomplete_nodes) / total_non_junction_nodes <= 0.20

    for x, y in _polygon_points(art_field):
        assert SAFE_NODE_X_MIN <= x <= SAFE_NODE_X_MAX
        assert SAFE_NODE_Y_MIN <= y <= SAFE_NODE_Y_MAX


def test_theta_field_starts_at_junction_and_is_not_uniform_petal():
    artifact = _artifact_data()
    curves = _theta_geometry(_seed_bytes(artifact))

    assert 5 <= len(curves) <= 7
    assert all(curve.start == HEXAGON_ORIGIN for curve in curves)

    far_right_lower = [
        curve
        for curve in curves
        if curve.end[0] >= 860.0 and curve.end[1] >= 650.0
    ]
    assert len(far_right_lower) <= 2

    assert len({curve.role for curve in curves}) == len(curves)
    assert any(curve.end[0] < 800.0 for curve in curves)
    assert any(curve.end[1] < 560.0 for curve in curves)
    assert any(curve.end[1] > 620.0 for curve in curves)

    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")
    svg_curves = _svg_elements_with_class(art_field, "theta-curve")

    assert len(svg_curves) == len(curves)

    for curve in svg_curves:
        assert _svg_data_float(curve, "data-start-x") == HEXAGON_ORIGIN[0]
        assert _svg_data_float(curve, "data-start-y") == HEXAGON_ORIGIN[1]


def test_trunk_is_layered_aftertrace_and_endpoint_has_no_halo():
    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")

    core = re.search(r'<path id="trunk-core"[^>]*>', art_field)
    haze = re.search(r'<path id="trunk-haze"[^>]*>', art_field)
    ghost = re.search(r'<path id="trunk-ghost"[^>]*>', art_field)

    assert core is not None
    assert haze is not None
    assert ghost is not None

    core_text = core.group(0)
    haze_text = haze.group(0)
    ghost_text = ghost.group(0)

    assert (
        _svg_data_text(core_text, "data-role")
        == "energetic-aftertrace-core"
    )
    assert (
        _svg_data_text(haze_text, "data-role")
        == "energetic-aftertrace-haze"
    )
    assert (
        _svg_data_text(ghost_text, "data-role")
        == "energetic-aftertrace-ghost"
    )

    for element in (core_text, haze_text):
        assert _svg_data_float(element, "data-start-x") == HEXAGON_ORIGIN[0]
        assert _svg_data_float(element, "data-start-y") == HEXAGON_ORIGIN[1]
        assert _svg_data_float(element, "data-end-x") == TRANSITION_ENDPOINT[0]
        assert _svg_data_float(element, "data-end-y") == TRANSITION_ENDPOINT[1]

    assert 3.0 <= _svg_data_float(core_text, "stroke-width") <= 5.0
    assert 0.60 <= _svg_data_float(core_text, "opacity") <= 0.75

    assert 16.0 <= _svg_data_float(haze_text, "stroke-width") <= 30.0
    assert 0.08 <= _svg_data_float(haze_text, "opacity") <= 0.18

    assert 0.03 <= _svg_data_float(ghost_text, "opacity") <= 0.06
    assert TRANSITION_ENDPOINT[1] >= 690.0
    assert TRANSITION_ENDPOINT[1] <= 730.0

    endpoint_x, endpoint_y = TRANSITION_ENDPOINT
    assert f'cx="{endpoint_x:.2f}" cy="{endpoint_y:.2f}"' not in art_field


def test_materiality_is_deterministic_visible_and_anchor_derived():
    artifact = _artifact_data()
    seed = _seed_bytes(artifact)
    first = _materiality_placement(seed)
    second = _materiality_placement(seed)

    assert first == second
    assert len(first.shadow_centers) == MATERIALITY_MAX_SHADOW_FIELDS
    assert len(first.imprint_centers) == MATERIALITY_MAX_IMPRINTS
    assert len(first.selected_regions) == 5

    for x, y in first.shadow_centers + first.imprint_centers:
        assert 165.0 <= x <= 860.0
        assert 285.0 <= y <= 860.0
        assert (
            (x - HEXAGON_ORIGIN[0]) ** 2
            + (y - HEXAGON_ORIGIN[1]) ** 2
        ) ** 0.5 >= 150.0

    assert MATERIALITY_OPACITY_MIN == 0.05
    assert MATERIALITY_OPACITY_MAX == 0.12

    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")

    clouds = _svg_elements_with_class(art_field, "shadow-density")
    imprints = _svg_elements_with_class(art_field, "paper-imprint")

    assert len(clouds) == MATERIALITY_MAX_SHADOW_FIELDS
    assert len(imprints) == MATERIALITY_MAX_IMPRINTS

    cloud_opacities = [_svg_data_float(cloud, "opacity") for cloud in clouds]
    assert all(
        MATERIALITY_OPACITY_MIN <= opacity <= MATERIALITY_OPACITY_MAX
        for opacity in cloud_opacities
    )

    assert all(
        _svg_data_float(cloud, "data-area") >= 34_000.0
        for cloud in clouds
    )

    imprint_opacities = [
        _svg_data_float(imprint, "opacity")
        for imprint in imprints
    ]
    assert all(0.06 <= opacity <= 0.10 for opacity in imprint_opacities)


def test_lyapunov_event_is_topologically_legible_and_capped():
    svg_bytes, _ = render_canonical(ARTIFACT_PATH)
    art_field = _group_content(svg_bytes.decode("utf-8"), "art-field")

    haze = re.search(r'<path id="lyapunov-haze"[^>]*>', art_field)
    stable = re.search(r'<path id="lyapunov-stable"[^>]*>', art_field)
    split_a = re.search(r'<path id="lyapunov-split-a"[^>]*>', art_field)
    split_b = re.search(r'<path id="lyapunov-split-b"[^>]*>', art_field)

    assert haze is not None
    assert stable is not None
    assert split_a is not None
    assert split_b is not None

    haze_text = haze.group(0)
    stable_text = stable.group(0)
    split_a_text = split_a.group(0)
    split_b_text = split_b.group(0)

    assert (
        _svg_data_text(haze_text, "data-role")
        == "split-drift-return-fade-haze"
    )
    assert all(
        _svg_data_text(element, "data-role")
        == "split-drift-return-fade"
        for element in (stable_text, split_a_text, split_b_text)
    )

    assert 12.0 <= _svg_data_float(haze_text, "stroke-width") <= 18.0
    assert 0.02 <= _svg_data_float(haze_text, "opacity") <= 0.04

    assert 2.0 <= _svg_data_float(stable_text, "stroke-width") <= 4.0
    assert 2.0 <= _svg_data_float(split_a_text, "stroke-width") <= 4.0
    assert 2.0 <= _svg_data_float(split_b_text, "stroke-width") <= 4.0

    assert 0.05 <= _svg_data_float(stable_text, "opacity") <= 0.08
    assert 0.05 <= _svg_data_float(split_a_text, "opacity") <= 0.08
    assert 0.05 <= _svg_data_float(split_b_text, "opacity") <= 0.08

    separation = _svg_data_float(split_a_text, "data-separation")
    assert 20.0 <= separation <= 35.0
    assert _svg_data_float(split_b_text, "data-separation") == separation

    artifact = _artifact_data()
    diagnostics = json.loads(build_preview_diagnostics(artifact).decode("utf-8"))
    event = diagnostics["lyapunov_event"]

    assert event["layer"] == "materiality"
    assert event["topology"] == "split-drift-return-fade"
    assert event["branch_separation_px"] == separation
    assert event["opacity_range"] == [0.065, 0.078]
    assert (
        event["secondary_layer_fraction"]
        == LYAPUNOV_SECONDARY_LAYER_FRACTION_MAX
    )
    assert event["secondary_layer_fraction"] <= 0.10


def test_diagnostics_are_geometry_linked_and_deterministic(tmp_path):
    artifact = _artifact_data()

    first = build_preview_diagnostics(artifact)
    second = build_preview_diagnostics(artifact)

    assert first == second
    assert first.endswith(b"\n")

    diagnostics = json.loads(first.decode("utf-8"))
    assert diagnostics["junction"]["x"] == HEXAGON_ORIGIN[0]
    assert diagnostics["junction"]["y"] == HEXAGON_ORIGIN[1]

    endpoints = diagnostics["incoming_branch_endpoints"]
    assert len(endpoints) >= 3
    assert {
        endpoint["color"]
        for endpoint in endpoints
    } >= {
        PALETTE["audit_cyan"],
        PALETTE["theta_gold"],
        PALETTE["rock_magenta"],
    }

    assert all(
        endpoint["x2"] == HEXAGON_ORIGIN[0]
        and endpoint["y2"] == HEXAGON_ORIGIN[1]
        for endpoint in endpoints
    )

    branch_network = diagnostics["branch_network"]
    assert branch_network["visible_branch_segments"] >= 20
    assert branch_network["incomplete_node_count"] == 2

    curve_starts = diagnostics["theta_curve_starts"]
    assert 5 <= len(curve_starts) <= 7
    assert all(
        start["x"] == HEXAGON_ORIGIN[0]
        and start["y"] == HEXAGON_ORIGIN[1]
        for start in curve_starts
    )

    trunk = diagnostics["trunk"]
    assert trunk["start"] == [HEXAGON_ORIGIN[0], HEXAGON_ORIGIN[1]]
    assert trunk["end"] == [
        TRANSITION_ENDPOINT[0],
        TRANSITION_ENDPOINT[1],
    ]
    assert trunk["endpoint_halo"] is False
    assert trunk["core"] == {"opacity": 0.68, "width_px": 4.4}
    assert trunk["haze"] == {"opacity": 0.13, "width_px": 20.0}
    assert trunk["ghost"] == {"opacity": 0.045, "width_px": 7.0}

    diagnostics_path = tmp_path / "preview.diagnostics.json"
    written = write_preview_diagnostics(
        artifact_path=ARTIFACT_PATH,
        diagnostics_path=diagnostics_path,
    )

    assert written == diagnostics_path
    assert diagnostics_path.read_bytes() == first


def test_seed_changes_when_identity_hashes_change():
    artifact = _artifact_data()

    theta_changed = dict(artifact)
    theta_changed["canonical_theta_hash"] = "sha256:" + "0" * 16
    assert seed_hex(theta_changed) != seed_hex(artifact)

    feature_changed = dict(artifact)
    feature_changed["feature_sha256"] = "sha256:" + "f" * 64
    assert seed_hex(feature_changed) != seed_hex(artifact)


def test_metadata_sha_linkage_matches_svg_bytes():
    svg_bytes, metadata_bytes = render_canonical(ARTIFACT_PATH)
    metadata = json.loads(metadata_bytes.decode("utf-8"))

    assert build_metadata(metadata["artifact"], svg_bytes) == metadata_bytes
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