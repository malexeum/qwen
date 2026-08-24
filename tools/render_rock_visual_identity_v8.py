from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from lib.d1_feature_artifact_io import read_feature_artifact
from lib.d1_feature_artifacts import SCHEMA_V2

RENDERER_NAME = "rock_visual_identity_v8"
RENDERER_VERSION = "v8.0.0"
MODE_ORDER = ("monolithic", "kinetic_break", "recursive_grove", "fragmented_signal")


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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _derive_mode_and_macro(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    f = payload
    tension = float(f["tension"])
    harmonic_stability = float(f["harmonic_stability"])
    harmonic_change_rate = float(f["harmonic_change_rate"])
    texture_complexity = float(f["texture_complexity"])
    recursion_depth = float(f["recursion_depth"])
    section_complexity = float(f["section_complexity"])
    noise_level = float(f["noise_level"])
    symmetry_bias = float(f["symmetry_bias"])

    if recursion_depth > 0.66 and harmonic_stability > 0.58:
        mode = "recursive_grove"
    elif tension > 0.62 or noise_level > 0.60:
        mode = "fragmented_signal"
    elif harmonic_change_rate > 0.58 and texture_complexity > 0.52:
        mode = "kinetic_break"
    else:
        mode = "monolithic"

    traced = {
        "tension": tension,
        "harmonic_stability": harmonic_stability,
        "harmonic_change_rate": harmonic_change_rate,
        "texture_complexity": texture_complexity,
        "recursion_depth": recursion_depth,
        "section_complexity": section_complexity,
        "noise_level": noise_level,
        "symmetry_bias": symmetry_bias,
    }

    if mode == "monolithic":
        junction_x = 290.0 + symmetry_bias * 260.0
        junction_y = 320.0 + (1.0 - harmonic_stability) * 120.0
        primary_angle = 18.0 + tension * 28.0
        visual_masses = 2 + int(section_complexity * 2)
        branch_count = 7 + int(texture_complexity * 5)
        recursion_levels = 2 + int(recursion_depth * 3)
        symmetry = 0.74 + symmetry_bias * 0.18
        line_continuity = 0.72 + harmonic_stability * 0.18
        density = 0.56 + texture_complexity * 0.3
        materiality = 0.35 + noise_level * 0.34
        palette_ratio = 0.28 + symmetry_bias * 0.32
    elif mode == "kinetic_break":
        junction_x = 340.0 + harmonic_change_rate * 240.0
        junction_y = 260.0 + (1.0 - tension) * 160.0
        primary_angle = 34.0 + harmonic_change_rate * 38.0
        visual_masses = 3 + int(texture_complexity * 3)
        branch_count = 9 + int(harmonic_change_rate * 7)
        recursion_levels = 2 + int(recursion_depth * 4)
        symmetry = 0.52 + (1.0 - symmetry_bias) * 0.2
        line_continuity = 0.48 + harmonic_stability * 0.24
        density = 0.64 + texture_complexity * 0.24
        materiality = 0.42 + noise_level * 0.3
        palette_ratio = 0.36 + harmonic_change_rate * 0.25
    elif mode == "recursive_grove":
        junction_x = 240.0 + recursion_depth * 280.0
        junction_y = 340.0 + (1.0 - symmetry_bias) * 150.0
        primary_angle = 12.0 + symmetry_bias * 26.0
        visual_masses = 4 + int(recursion_depth * 3)
        branch_count = 11 + int(recursion_depth * 8)
        recursion_levels = 3 + int(recursion_depth * 5)
        symmetry = 0.65 + symmetry_bias * 0.22
        line_continuity = 0.80 + harmonic_stability * 0.12
        density = 0.68 + texture_complexity * 0.2
        materiality = 0.52 + (1.0 - harmonic_stability) * 0.26
        palette_ratio = 0.44 + recursion_depth * 0.26
    else:
        junction_x = 260.0 + (1.0 - symmetry_bias) * 240.0
        junction_y = 300.0 + noise_level * 170.0
        primary_angle = 60.0 + tension * 34.0
        visual_masses = 4 + int(noise_level * 4)
        branch_count = 13 + int(noise_level * 9)
        recursion_levels = 2 + int(section_complexity * 4)
        symmetry = 0.33 + (1.0 - symmetry_bias) * 0.45
        line_continuity = 0.32 + harmonic_stability * 0.22
        density = 0.72 + noise_level * 0.18
        materiality = 0.58 + noise_level * 0.2
        palette_ratio = 0.30 + texture_complexity * 0.3

    macro = {
        "composition_mode": mode,
        "global_junction_x": round(junction_x, 2),
        "global_junction_y": round(junction_y, 2),
        "primary_flow_angle_deg": round(primary_angle, 2),
        "visual_masses": int(visual_masses),
        "branch_count": int(branch_count),
        "recursion_levels": int(recursion_levels),
        "symmetry": round(_clamp01(symmetry), 6),
        "line_continuity": round(_clamp01(line_continuity), 6),
        "density": round(_clamp01(density), 6),
        "materiality": round(_clamp01(materiality), 6),
        "palette_usage_ratio": round(_clamp01(palette_ratio), 6),
    }
    trace = [
        "mode_selected_from_semantic_payload",
        "score_order = [tension, harmonic_stability, harmonic_change_rate, texture_complexity, recursion_depth, section_complexity, noise_level, symmetry_bias]",
        f"mode={mode}",
        f"macro_junction=({macro['global_junction_x']},{macro['global_junction_y']})",
        f"branch_count={macro['branch_count']}",
        f"recursion_levels={macro['recursion_levels']}",
    ]
    return mode, macro, trace


def _select_seed(seed: str | None, artifact_hash: str) -> int:
    if seed is None:
        return int(artifact_hash[-8:], 16) % 100000
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 100000


def _artifacts_from_path(artifact_path: Path) -> tuple[Any, dict[str, Any]]:
    artifact = read_feature_artifact(artifact_path)
    if artifact.schema_version != SCHEMA_V2:
        raise ValueError("rock_visual_identity_v8 requires d1_feature_artifact/v2")
    semantic = artifact.semantic_payload()
    source_identity = artifact.source_identity
    return artifact, {
        "analysis_id": artifact.analysis_id,
        "feature_sha256": artifact.feature_sha256,
        "canonical_theta_hash": artifact.canonical_theta_hash,
        "source_locator_registry_path": artifact.source_locator["registry_path"],
        "source_title": artifact.source_locator["registry_path"].rsplit("/", 1)[-1].upper(),
        "content_sha256": source_identity["content_sha256"],
        "byte_size": source_identity["byte_size"],
        "semantic_payload": semantic,
    }


def render_v8_svg(artifact_path: Path, *, seed: str | None = None) -> tuple[bytes, dict[str, Any]]:
    artifact, display = _artifacts_from_path(artifact_path)
    mode, macro, trace = _derive_mode_and_macro(display["semantic_payload"])
    artifact_bytes = artifact_path.read_bytes()
    seed_value = _select_seed(seed, display["feature_sha256"])
    rng = seed_value % 997

    cx = macro["global_junction_x"]
    cy = macro["global_junction_y"]
    angle = math.radians(macro["primary_flow_angle_deg"])
    endpoint_x = cx + math.cos(angle) * (300.0 + macro["density"] * 260.0)
    endpoint_y = cy + math.sin(angle) * (260.0 + macro["density"] * 180.0)
    branch_count = macro["branch_count"]
    masses = macro["visual_masses"]
    palette = [
        ("#0f172a", "#60a5fa"),
        ("#111827", "#f59e0b"),
        ("#1f2937", "#f472b6"),
        ("#0b1120", "#34d399"),
    ]
    palette_index = seed_value % len(palette)
    bg, accent = palette[palette_index]

    radius = 28.0 + macro["density"] * 18.0
    lines: list[str] = []
    for i in range(branch_count):
        offset = (i / max(1, branch_count)) * 2.0 * math.pi + (rng / 1000.0)
        x = cx + math.cos(offset + angle) * (40.0 + i * 12.0)
        y = cy + math.sin(offset + angle) * (20.0 + i * 12.0)
        lines.append(
            f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="{accent}" stroke-width="{(1.4 + macro["line_continuity"] * 2.4):.2f}" opacity="{(0.34 + macro["density"] * 0.46):.2f}" />'
        )

    masses_svg: list[str] = []
    for idx in range(masses):
        mx = cx + (idx - (masses - 1) / 2.0) * (48.0 + macro["symmetry"] * 70.0)
        my = cy + math.sin(idx + angle) * (70.0 + macro["materiality"] * 80.0)
        masses_svg.append(
            f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="{radius + idx * 8.0}" fill="none" stroke="{accent}" stroke-width="{(1.0 + macro["density"] * 2.2):.2f}" opacity="{(0.18 + (idx + 1) / (masses + 1) * 0.42):.2f}" />'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <defs>
    <radialGradient id="bg" cx="50%" cy="40%" r="75%">
      <stop offset="0%" stop-color="{bg}"/>
      <stop offset="100%" stop-color="#020817"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="900" fill="url(#bg)"/>
  <g>
    <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{(48.0 + macro['materiality'] * 54.0):.2f}" fill="none" stroke="{accent}" stroke-width="{(3.0 + macro['density'] * 3.0):.2f}" opacity="0.9"/>
    <line x1="{cx:.2f}" y1="{cy:.2f}" x2="{endpoint_x:.2f}" y2="{endpoint_y:.2f}" stroke="{accent}" stroke-width="{(3.6 + macro['line_continuity'] * 4.0):.2f}" opacity="0.9"/>
    {' '.join(lines)}
    {' '.join(masses_svg)}
  </g>
  <g id="caption">
    <text x="600" y="96" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="34" fill="#e2e8f0" letter-spacing="4">ROCK VISUAL IDENTITY V8</text>
    <text x="600" y="128" text-anchor="middle" font-family="Consolas, monospace" font-size="18" fill="#cbd5e1" letter-spacing="2">{mode.upper()} · {display['source_title']}</text>
    <text x="600" y="840" text-anchor="middle" font-family="Consolas, monospace" font-size="16" fill="#cbd5e1">composition_mode={mode} · seed={seed_value}</text>
  </g>
</svg>
'''.encode("utf-8") + b"\n"

    metadata = {
        "artifact": {
            "analysis_id": display["analysis_id"],
            "feature_sha256": display["feature_sha256"],
            "canonical_theta_hash": display["canonical_theta_hash"],
            "source_locator_registry_path": display["source_locator_registry_path"],
            "source_title": display["source_title"],
            "schema_version": "d1_feature_artifact/v2",
        },
        "composition_mode": mode,
        "mode_selection": {
            "method": "deterministic_from_semantic_payload",
            "mode_order": list(MODE_ORDER),
            "selected_mode": mode,
            "selection_features": {
                "tension": display["semantic_payload"]["tension"],
                "harmonic_stability": display["semantic_payload"]["harmonic_stability"],
                "harmonic_change_rate": display["semantic_payload"]["harmonic_change_rate"],
                "texture_complexity": display["semantic_payload"]["texture_complexity"],
                "recursion_depth": display["semantic_payload"]["recursion_depth"],
                "section_complexity": display["semantic_payload"]["section_complexity"],
                "noise_level": display["semantic_payload"]["noise_level"],
                "symmetry_bias": display["semantic_payload"]["symmetry_bias"],
            },
        },
        "macro_mapping_trace": trace,
        "resolved_visual_parameters": macro,
        "renderer": {
            "name": RENDERER_NAME,
            "version": RENDERER_VERSION,
        },
        "input_artifact_hashes": {
            "feature_sha256": display["feature_sha256"],
            "artifact_sha256": sha256_prefixed(artifact_bytes),
            "source_content_sha256": display["content_sha256"],
        },
        "seed": seed_value,
    }
    return svg, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a v8 macro-composition poster from a canonical D1 feature artifact.")
    parser.add_argument("--artifact", type=Path, required=True, help="Validated d1_feature_artifact/v2 JSON path.")
    parser.add_argument("--svg-output", type=Path, required=True, help="Target output SVG path.")
    parser.add_argument("--metadata-output", type=Path, required=True, help="Target output metadata JSON path.")
    parser.add_argument("--seed", type=str, default=None, help="Optional bounded seed for micro-variation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    svg, metadata = render_v8_svg(args.artifact, seed=args.seed)
    args.svg_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.svg_output.write_bytes(svg)
    args.metadata_output.write_bytes(canonical_json_bytes(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
