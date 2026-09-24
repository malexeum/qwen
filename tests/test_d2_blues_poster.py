from __future__ import annotations

import json
import re
from pathlib import Path

PALETTE_BLUE_NOTE = "#5B4FA8"

from tools.render_d2_blues_poster import build_metadata, render_svg, sha256_prefixed, write_outputs


def test_blues_poster_is_deterministic_and_layered(tmp_path: Path):
    first = render_svg("fixture")
    assert first == render_svg("fixture")
    assert first.endswith(b"\n")
    text = first.decode("utf-8")
    for group_id in (
        "d2-random-polygons", "d2-settling-mist", "d2-coffin-gravity", "d2-pain-waterfall", "d2-afterimages",
        "d2-burial-backdrop", "d2-density-bodies", "d2-internal-organs",
        "d2-left-internal-organs", "d2-right-internal-organs", "d2-left-tendons",
        "d2-right-tendons", "d2-call-response", "d2-contact-gap", "d2-contact-flows",
        "d2-delayed-embrace-arcs", "d2-counterflow", "d2-blue-note", "d2-aftertone-memory", "d2-burial-foreground",
        "d2-tactile-photographic-void", "d2-footer",
    ):
        assert f'id="{group_id}"' in text
    assert 'viewBox="0 0 1080 1260"' in text
    assert text.index('id="d2-burial-backdrop"') < text.index('id="d2-density-bodies"')
    assert text.index('id="d2-density-bodies"') < text.index('id="d2-contact-gap"')
    assert text.index('id="d2-contact-gap"') < text.index('id="d2-contact-flows"')
    assert text.index('id="d2-contact-flows"') < text.index('id="d2-counterflow"')
    assert text.index('id="d2-counterflow"') < text.index('id="d2-blue-note"')
    assert text.index('id="d2-contact-flows"') < text.index('id="d2-burial-foreground"')
    assert text.index('id="d2-tactile-photographic-void"') < text.index('id="d2-footer"')
    assert 'id="contact-gap-mask"' in text
    assert 'mask="url(#contact-gap-mask)"' in text
    assert 'data-gap="masked-void"' in text
    assert 'stroke-width="2.7"' not in text
    assert 'id="d2-contact-seam"' not in text
    assert 'data-stream="background"' in text
    assert 'data-stream="internal"' in text
    assert 'data-voice="delayed-response"' in text
    assert 'data-mode="attract"' in text
    assert 'data-mode="repel"' in text
    assert 'data-mode="unfinished"' in text
    assert 'data-gesture="beautiful-error"' in text
    assert '<feGaussianBlur stdDeviation="72"/>' in text
    assert PALETTE_BLUE_NOTE in text
    assert "<script" not in text
    assert "<foreignObject" not in text
    assert "<image" not in text
    assert not re.search(r'(?:href|xlink:href)=["\'](?:https?:|//)', text)
    metadata = json.loads(build_metadata("fixture", first))
    assert metadata["renderer"]["version"] == "1.6"
    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(first)
    assert 1.35 <= metadata["body_geometry"]["area_proxy_ratio"] <= 2.65
    assert metadata["visual_contract"]["retained_layers"] == ["glow", "settling_mist", "random_polygons", "turbulence", "tactile_void"]
    assert metadata["visual_contract"]["structural_layers"] == ["coffin_gravity", "pain_waterfall", "afterimages_aab", "internal_organs", "tendons", "call_response", "masked_contact_gap", "contact_flows", "delayed_embrace_arcs", "counterflow", "blue_note", "aftertone_memory"]
    svg_path = tmp_path / "poster.svg"
    metadata_path = tmp_path / "poster.metadata.json"
    write_outputs("fixture", svg_path, metadata_path)
    assert svg_path.read_bytes() == first
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["seed"] == "fixture"


def test_seed_changes_geometry_and_keeps_broad_asymmetry():
    first = render_svg("a")
    second = render_svg("b")
    assert first != second
    for seed, svg in (("a", first), ("b", second)):
        metadata = json.loads(build_metadata(seed, svg))
        assert 1.35 <= metadata["body_geometry"]["area_proxy_ratio"] <= 2.65
