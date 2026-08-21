from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from tools.render_d1_rock_poster import (
    ARTIFACT_RELATIVE_PATH,
    CANONICAL_VIEWBOX,
    HORIZONTAL_ELLIPSIS,
    MIDDLE_DOT,
    MULTIPLICATION_SIGN,
    PALETTE,
    PUBLICATION_COMMIT,
    RIGHT_ARROW,
    THETA,
    build_metadata,
    render_canonical,
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
    without_metadata = re.sub(
        r"<metadata>.*?</metadata>",
        "",
        svg_text,
        flags=re.DOTALL,
    )
    without_style = re.sub(
        r"<style>.*?</style>",
        "",
        without_metadata,
        flags=re.DOTALL,
    )
    return re.sub(r"<[^>]+>", " ", without_style)


def _embedded_svg_metadata(svg_text: str) -> dict[str, object]:
    match = re.search(
        r"<metadata>(.*?)</metadata>",
        svg_text,
        flags=re.DOTALL,
    )
    assert match is not None, "canonical SVG must contain metadata"
    return json.loads(html.unescape(match.group(1)))


def test_canonical_poster_is_deterministic_and_artifact_derived(tmp_path):
    first_svg, first_metadata = render_canonical(ARTIFACT_PATH)
    second_svg, second_metadata = render_canonical(ARTIFACT_PATH)

    assert first_svg == second_svg
    assert first_metadata == second_metadata
    assert first_svg.endswith(b"\n")
    assert first_metadata.endswith(b"\n")
    assert b"\r" not in first_svg
    assert b"\r" not in first_metadata

    svg_text = first_svg.decode("utf-8")
    visible_text = _visible_svg_text(svg_text)
    embedded_metadata = _embedded_svg_metadata(svg_text)
    metadata = json.loads(first_metadata.decode("utf-8"))

    assert 'xmlns="http://www.w3.org/2000/svg"' in svg_text
    assert 'viewBox="0 0 1080 1080"' in svg_text
    assert f"ROCK.MP3 {RIGHT_ARROW} D1" in visible_text
    assert "FROM PHYSICAL AUDIO TO CANONICAL FORM" in visible_text
    assert "SOURCE FILE: ROCK.MP3" in visible_text
    assert (
        f"4,605,149 BYTES {MIDDLE_DOT} APPROVED INPUT"
        in visible_text
    )
    assert "CONCEPTUAL TRANSFORMATION MAP" in visible_text
    assert "NOT A SPECTROGRAM" in visible_text
    assert f"CANONICAL {THETA} HASH" in visible_text
    assert HORIZONTAL_ELLIPSIS in visible_text

    assert (
        f".title{{font-family:Arial,Helvetica,sans-serif;"
        f"font-size:54px;font-weight:700;letter-spacing:2px;"
        f"fill:{PALETTE['primary_text']};}}"
    ) in svg_text
    assert (
        f".subtitle{{font-family:Arial,Helvetica,sans-serif;"
        f"font-size:15px;letter-spacing:3px;"
        f"fill:{PALETTE['secondary_text']};}}"
    ) in svg_text
    assert (
        f".hash-audit{{font-family:Consolas,Menlo,monospace;"
        f"font-size:16px;fill:{PALETTE['audit_cyan']};}}"
    ) in svg_text
    assert (
        f".hash-theta{{font-family:Consolas,Menlo,monospace;"
        f"font-size:16px;fill:{PALETTE['theta_gold']};}}"
    ) in svg_text
    assert (
        f".hash-semantic{{font-family:Consolas,Menlo,monospace;"
        f"font-size:16px;fill:{PALETTE['semantic_green']};}}"
    ) in svg_text
    assert (
        f".manifesto{{font-family:Arial,Helvetica,sans-serif;"
        f"font-size:18px;font-weight:700;letter-spacing:1.5px;"
        f"fill:{PALETTE['primary_text']};}}"
    ) in svg_text

    assert '<rect x="104" y="420" width="872" height="270" rx="6"' in svg_text
    assert '<rect x="150" y="420" width="780" height="185" rx="4"' not in svg_text

    artifact = metadata["artifact"]
    assert artifact["analysis_id"] == "d1_rock_v1"
    assert artifact["schema_version"] == "d1_feature_artifact/v2"
    assert artifact["source_locator_registry_path"] == "tests/audio/Rock.mp3"
    assert artifact["source_title"] == "ROCK.MP3"
    assert artifact["source_byte_size"] == 4_605_149
    assert artifact["source_content_sha256"] == (
        "sha256:286b2a46b2eec82d2901625bfc4020547b14a568ca3082a3a5090d8223d27ebc"
    )
    assert artifact["canonical_theta_hash"] == "sha256:5e2ac5e7a4c1151d"
    assert artifact["feature_sha256"] == (
        "sha256:814b21fcdf5ae5a1e11172aa2301cd781f2d76446c436e27498902a9cebe81b4"
    )
    assert artifact["git_sha"] == (
        "cc0be209a69245c52a9a2bd64c48f21954e0b1a7"
    )

    assert embedded_metadata["artifact"] == artifact
    assert embedded_metadata["poster_id"] == metadata["poster_id"]
    assert embedded_metadata["renderer"] == metadata["renderer"]
    assert embedded_metadata["renderer"]["version"] == "2"
    assert (
        embedded_metadata["publication_provenance"]
        == metadata["publication_provenance"]
    )
    assert (
        embedded_metadata["canonical_outputs"]["svg_viewbox"]
        == CANONICAL_VIEWBOX
    )
    assert (
        embedded_metadata["canonical_outputs"]["svg_filename"]
        == "d1_rock_v1_poster.svg"
    )
    assert "svg_sha256" not in embedded_metadata["canonical_outputs"]
    assert "raster_outputs" not in embedded_metadata
    assert (
        embedded_metadata["central_graphic"]["representation"]
        == "enlarged spectral-rock metaphor transitioning to "
        "theta coordinate grid"
    )
    assert (
        embedded_metadata["central_graphic"]["warning"]
        == "NOT A SPECTROGRAM"
    )

    assert metadata["canonical_outputs"]["svg_viewbox"] == CANONICAL_VIEWBOX
    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(
        first_svg
    )
    assert metadata["publication_provenance"]["commit"] == PUBLICATION_COMMIT
    assert metadata["raster_outputs"] == []

    assert not _external_svg_references(svg_text)
    assert "<image" not in svg_text
    assert "data:image" not in svg_text
    assert "@font-face" not in svg_text
    assert "<script" not in svg_text
    assert "<foreignObject" not in svg_text

    forbidden_visible_patterns = (
        r"\bA2\b",
        r"\bA3\b",
        r"\bDPI\b",
        r"\bPRINT\b",
        r"\b4961\b",
        r"\b7016\b",
        r"\b3508\b",
        rf"\b1080{re.escape(MULTIPLICATION_SIGN)}1527\b",
    )
    for pattern in forbidden_visible_patterns:
        assert not re.search(pattern, visible_text, flags=re.IGNORECASE)

    metadata_text = first_metadata.decode("utf-8").lower()
    assert "rsvg-convert" not in metadata_text
    assert "cairosvg" not in metadata_text
    assert "creation_mode" not in metadata_text
    assert "dimensions_px" not in metadata_text

    svg_path = tmp_path / "poster.svg"
    metadata_path = tmp_path / "poster.metadata.json"
    written_svg, written_metadata = write_canonical_outputs(
        artifact_path=ARTIFACT_PATH,
        svg_path=svg_path,
        metadata_path=metadata_path,
    )

    assert written_svg == svg_path
    assert written_metadata == metadata_path
    assert svg_path.read_bytes() == first_svg
    assert metadata_path.read_bytes() == first_metadata


def test_metadata_sha_linkage_matches_svg_bytes():
    svg_bytes, metadata_bytes = render_canonical(ARTIFACT_PATH)
    metadata = json.loads(metadata_bytes.decode("utf-8"))

    rebuilt_metadata = build_metadata(metadata["artifact"], svg_bytes)

    assert rebuilt_metadata == metadata_bytes
    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(
        svg_bytes
    )


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