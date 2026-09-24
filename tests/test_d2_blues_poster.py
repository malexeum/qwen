from __future__ import annotations
import json
from pathlib import Path
from tools.render_d2_blues_poster import (
    build_metadata, render_svg, sha256_prefixed, write_outputs, base_metadata
)

PALETTE_BLUE_NOTE = "#5B4FA8"


def test_blues_poster_renders_and_is_deterministic():
    svg = render_svg("d2-blues-v1")
    assert isinstance(svg, bytes)
    assert svg == render_svg("d2-blues-v1")
    assert len(svg) > 10_000
    assert b"<script" not in svg
    assert b"<foreignObject" not in svg


def test_required_layers_present():
    svg = render_svg("d2-blues-v1")
    for gid in [
        "d2-coffin-gravity",
        "d2-pain-waterfall",
        "d2-afterimages",
        "d2-density-bodies",
        "d2-internal-organs",
        "d2-contact-flows",
        "d2-counterflow",
        "d2-blue-note",
        "d2-graphite-dust",
        "d2-footer",
    ]:
        assert f'id="{gid}"'.encode() in svg, f"missing layer: {gid}"


def test_bodies_are_smoky():
    svg = render_svg("d2-blues-v1")
    assert b'stdDeviation="72"' in svg
    assert PALETTE_BLUE_NOTE.encode() in svg
    assert b"smoke-body" in svg
    assert b"feTurbulence" in svg


def test_seed_changes_geometry():
    assert render_svg("alpha") != render_svg("beta")


def test_metadata_contract():
    svg = render_svg("d2-blues-v1")
    sha = sha256_prefixed(svg)
    meta_bytes = build_metadata("d2-blues-v1", svg)
    meta = json.loads(meta_bytes)
    assert meta["renderer"]["version"] == "1.7"
    assert meta["body_geometry"]["area_proxy_ratio"] >= 1.35
    assert meta["body_geometry"]["area_proxy_ratio"] <= 2.65
    assert meta["canonical_outputs"]["svg_sha256"] == sha
    assert "pain_waterfall" in meta["visual_contract"]["structural_layers"]


def test_write_outputs(tmp_path: Path):
    svg_p  = tmp_path / "poster.svg"
    meta_p = tmp_path / "poster.metadata.json"
    write_outputs("d2-blues-v1", svg_p, meta_p)
    assert svg_p.exists()
    assert meta_p.exists()
    meta = json.loads(meta_p.read_bytes())
    assert meta["seed"] == "d2-blues-v1"