from __future__ import annotations

import json
import re
from pathlib import Path

from tools.render_d2_blues_poster import (
    RENDERER_VERSION,
    build_metadata,
    render_svg,
    sha256_prefixed,
    write_outputs,
)


def test_blues_poster_is_deterministic_and_layered(tmp_path: Path):
    first = render_svg("fixture")
    second = render_svg("fixture")
    assert first == second
    assert first.endswith(b"\n")
    text = first.decode("utf-8")
    for group_id in (
        "d2-random-polygons",
        "d2-settling-mist",
        "d2-burial-backdrop",
        "d2-density-bodies",
        "d2-internal-strata",
        "d2-counterflow-ribbons",
        "d2-contact-seam",
        "d2-burial-foreground",
        "d2-tactile-photographic-void",
        "d2-footer",
    ):
        assert f'id="{group_id}"' in text
    assert 'viewBox="0 0 1080 1260"' in text
    assert text.index('id="d2-burial-backdrop"') < text.index('id="d2-density-bodies"')
    assert text.index('id="d2-density-bodies"') < text.index('id="d2-internal-strata"')
    assert text.index('id="d2-internal-strata"') < text.index('id="d2-contact-seam"')
    assert text.index('id="d2-density-bodies"') < text.index('id="d2-burial-foreground"')
    assert text.index('id="d2-tactile-photographic-void"') < text.index('id="d2-footer"')
    assert "<script" not in text
    assert "<foreignObject" not in text
    assert "<image" not in text
    assert not re.search(r'(?:href|xlink:href)=["\'](?:https?:|//)', text)

    metadata = json.loads(build_metadata("fixture", first))
    assert metadata["renderer"]["version"] == RENDERER_VERSION == "1.1"
    assert metadata["canonical_outputs"]["svg_sha256"] == sha256_prefixed(first)
    assert metadata["visual_contract"]["body_geometry"] == "asymmetric, tapered, sheared, bottom-heavy"
    assert metadata["visual_contract"]["retained_layers"] == [
        "glow",
        "settling_mist",
        "random_polygons",
        "turbulence",
        "internal_strata",
        "counterflow_ribbons",
        "tactile_void",
    ]

    svg_path = tmp_path / "poster.svg"
    metadata_path = tmp_path / "poster.metadata.json"
    write_outputs("fixture", svg_path, metadata_path)
    assert svg_path.read_bytes() == first
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["seed"] == "fixture"


def test_seed_changes_geometry():
    assert render_svg("a") != render_svg("b")
