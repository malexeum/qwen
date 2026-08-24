from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INVENTORY = Path("corpus/inventory/audio_source_inventory.v1.json")
DEFAULT_CONFIG = Path("configs/d1_perceptual_config.v1.json")
ENTRYPOINT_VERSION = "d1_diagnostic_batch/v1"
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"

try:
    from tools.d1_extract import build_extraction_result
except Exception as exc:  # pragma: no cover - guarded at runtime
    raise RuntimeError(f"cannot import extraction contract: {exc}") from exc


class BatchValidationError(ValueError):
    """Raised when the requested diagnostic batch cannot be validated."""


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


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    slug = slug.strip("._-")
    return slug or "source"


def inventory_document(inventory_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchValidationError(f"cannot read inventory: {inventory_path}") from exc
    if not isinstance(payload, dict):
        raise BatchValidationError("inventory document must be a JSON object")
    if payload.get("schema_version") != "audio_source_inventory/v1":
        raise BatchValidationError("unsupported inventory schema_version")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise BatchValidationError("inventory entries must be a list")
    return payload


def inventory_sha256(path: Path) -> str:
    return sha256_prefixed(path.read_bytes())


def is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError as exc:
        raise BatchValidationError(f"cannot inspect source as raw bytes: {path}") from exc


def _resolve_requested_source(
    *,
    repo_root: Path,
    inventory_path: Path,
    source_name: str,
) -> tuple[str, Path]:
    if not source_name or not source_name.strip():
        raise BatchValidationError("requested source name cannot be empty")
    document = inventory_document(inventory_path)
    matches: list[Path] = []
    for entry in document.get("entries", []):
        if not isinstance(entry, dict):
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str):
            continue
        if Path(path_value).name == source_name:
            matches.append(repo_root / path_value)
    if not matches:
        raise BatchValidationError(f"requested source not found in inventory: {source_name}")
    if len(matches) > 1:
        raise BatchValidationError(
            f"requested source name is ambiguous in inventory: {source_name}"
        )
    source_path = matches[0]
    if not source_path.is_file():
        raise BatchValidationError(f"source file is missing: {source_path}")
    if is_lfs_pointer(source_path):
        raise BatchValidationError(
            f"Git LFS pointer detected for source before extraction: {source_name}"
        )
    return source_name, source_path


def _resolve_requested_sources(
    *,
    repo_root: Path,
    inventory_path: Path,
    requested: list[str],
) -> list[tuple[str, Path]]:
    seen: set[str] = set()
    resolved: list[tuple[str, Path]] = []
    for source_name in requested:
        if source_name in seen:
            raise BatchValidationError(f"duplicate source requested: {source_name}")
        seen.add(source_name)
        resolved.append(_resolve_requested_source(
            repo_root=repo_root,
            inventory_path=inventory_path,
            source_name=source_name,
        ))
    return resolved


def _safe_git_state() -> tuple[str, str]:
    return ("unknown", "unknown")


def _render_svg(
    *,
    source_name: str,
    source_identity: dict[str, Any],
    perceptual: dict[str, Any],
) -> bytes:
    axis_order = list(perceptual.keys())
    values = [float(perceptual[key]) for key in axis_order]
    max_value = max(values) if values else 1.0
    if max_value <= 0:
        max_value = 1.0

    axis_labels = {
        "symmetry_bias": "symmetry_bias",
        "tension": "tension",
        "harmonic_stability": "harmonic_stability",
        "harmonic_change_rate": "harmonic_change_rate",
        "texture_complexity": "texture_complexity",
        "recursion_depth": "recursion_depth",
        "section_complexity": "section_complexity",
        "noise_level": "noise_level",
    }

    bars: list[str] = []
    width = 860
    left = 100
    top = 260
    bar_span = 760
    step = bar_span / len(axis_order)
    for idx, axis_name in enumerate(axis_order):
        value = float(perceptual[axis_name])
        bar_height = 160 * (value / max_value)
        x = left + idx * step + 18
        y = top + 160 - bar_height
        label_y = top + 210
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{(step - 26):.1f}" '
            f'height="{bar_height:.1f}" fill="#46D9E8" opacity="0.9" rx="6"/>'
        )
        bars.append(
            f'<text x="{(x + (step - 26) / 2):.1f}" y="{label_y:.1f}" '
            f'text-anchor="middle" font-size="11" fill="#E9EEF8" '
            f'font-family="Arial, Helvetica, sans-serif">{axis_labels.get(axis_name, axis_name)}</text>'
        )
        bars.append(
            f'<text x="{(x + (step - 26) / 2):.1f}" y="{y - 8:.1f}" '
            f'text-anchor="middle" font-size="11" fill="#F6C85F" '
            f'font-family="monospace">{value:.6f}</text>'
        )

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720">
  <rect width="960" height="720" fill="#070A12"/>
  <text x="480" y="60" text-anchor="middle" font-size="30" fill="#E9EEF8" font-family="Arial, Helvetica, sans-serif" font-weight="700">DIAGNOSTIC LOCAL</text>
  <text x="480" y="95" text-anchor="middle" font-size="16" fill="#9AA8BD" font-family="Arial, Helvetica, sans-serif" letter-spacing="2">PROVISIONAL — NOT CANONICAL</text>
  <rect x="120" y="120" width="720" height="430" fill="none" stroke="#253249" stroke-width="2" rx="12"/>
  <text x="480" y="145" text-anchor="middle" font-size="14" fill="#C75CEB" font-family="Arial, Helvetica, sans-serif" letter-spacing="3">NOT A SPECTROGRAM</text>
  <text x="80" y="180" text-anchor="start" font-size="14" fill="#7CE3A1" font-family="Arial, Helvetica, sans-serif">SOURCE: {source_name}</text>
  <text x="80" y="205" text-anchor="start" font-size="12" fill="#9AA8BD" font-family="monospace">inventory: {source_identity.get('inventory_source_id', 'unknown')}</text>
  <g>
    {' '.join(bars)}
  </g>
  <line x1="80" y1="470" x2="880" y2="470" stroke="#253249" stroke-width="2"/>
  <text x="480" y="510" text-anchor="middle" font-size="13" fill="#9AA8BD" font-family="Arial, Helvetica, sans-serif">Eight-axis perceptual diagnostic map: values are scalar features, not waveform energy or spectrum.</text>
</svg>
'''
    return svg.encode("utf-8") + b"\n"


def _index_html(entries: list[dict[str, Any]]) -> bytes:
    rows: list[str] = []
    for item in entries:
        rows.append(
            "<tr>"
            f"<td>{item['source_name']}</td>"
            f"<td>{item['json_relative_path']}</td>"
            f"<td>{item['svg_relative_path']}</td>"
            f"<td>{item['sha256_json']}</td>"
            f"<td>{item['sha256_svg']}</td>"
            "</tr>"
        )
    body = "\n".join(rows)
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>D1 Diagnostic Batch</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background: #070A12; color: #E9EEF8; margin: 32px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1200px; }}
    th, td {{ border: 1px solid #253249; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #0f1828; }}
    a {{ color: #46D9E8; }}
  </style>
</head>
<body>
  <h1>DIAGNOSTIC LOCAL</h1>
  <p>PROVISIONAL — NOT CANONICAL</p>
  <table>
    <thead>
      <tr><th>Source</th><th>Parameters JSON</th><th>Poster SVG</th><th>JSON SHA-256</th><th>SVG SHA-256</th></tr>
    </thead>
    <tbody>
      {body}
    </tbody>
  </table>
</body>
</html>
'''
    return html.encode("utf-8") + b"\n"


def _build_batch(
    *,
    repo_root: Path,
    inventory_path: Path,
    config_path: Path,
    source_names: list[str],
    output_dir: Path,
    mode: str,
) -> dict[str, Any]:
    inventory = inventory_document(inventory_path)
    inventory_hash = inventory_sha256(inventory_path)
    resolved = _resolve_requested_sources(
        repo_root=repo_root,
        inventory_path=inventory_path,
        requested=source_names,
    )

    stage_dir = output_dir.parent / f".{output_dir.name}.staging.{uuid.uuid4().hex[:8]}"
    stage_dir.mkdir(parents=True, exist_ok=False)

    try:
        file_records: list[dict[str, Any]] = []
        source_records: list[dict[str, Any]] = []

        for source_name, source_path in resolved:
            extraction = build_extraction_result(
                repo_root=repo_root,
                source_path=source_path,
                inventory_path=inventory_path,
                config_path=config_path,
            )
            source_identity = dict(extraction["provenance"])
            source_records.append(source_identity)
            slug = slugify(Path(source_name).stem)
            source_dir = stage_dir / slug
            source_dir.mkdir(parents=True, exist_ok=False)

            visual_mapping = {
                "axes": list(extraction["perceptual"].keys()),
                "values": dict(extraction["perceptual"]),
                "layout": {
                    "title": "DIAGNOSTIC LOCAL",
                    "subtitle": "PROVISIONAL — NOT CANONICAL",
                    "warning": "NOT A SPECTROGRAM",
                    "visual_mode": "eight_axis_scalar_bar_map",
                },
            }

            poster_svg_bytes = _render_svg(
                source_name=source_name,
                source_identity=source_identity,
                perceptual=extraction["perceptual"],
            )
            poster_rel = Path(slug) / f"poster.diagnostic_local.svg"
            poster_path = stage_dir / poster_rel
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            poster_path.write_bytes(poster_svg_bytes)

            param_obj: dict[str, Any] = {
                "schema_version": "d1_diagnostic_parameters/v1",
                "status": "diagnostic_local",
                "provisional": True,
                "canonical": False,
                "ci_verified": False,
                "source_identity": source_identity,
                "extraction_result": extraction,
                "visual_mapping": visual_mapping,
                "poster_svg_sha256": sha256_prefixed(poster_svg_bytes),
                "poster_svg_relative_path": poster_rel.as_posix(),
            }
            param_rel = Path(slug) / "parameters.diagnostic_local.json"
            param_path = stage_dir / param_rel
            param_path.parent.mkdir(parents=True, exist_ok=True)
            param_path.write_bytes(canonical_json_bytes(param_obj))

            file_records.append(
                {
                    "source_name": source_name,
                    "json_relative_path": param_rel.as_posix(),
                    "svg_relative_path": poster_rel.as_posix(),
                    "sha256_json": sha256_prefixed(param_path.read_bytes()),
                    "sha256_svg": sha256_prefixed(poster_path.read_bytes()),
                }
            )

        index_bytes = _index_html(file_records)
        index_rel = Path("index.html")
        (stage_dir / index_rel).write_bytes(index_bytes)

        final_files: list[dict[str, Any]] = []
        for item in file_records:
            json_path = stage_dir / item["json_relative_path"]
            svg_path = stage_dir / item["svg_relative_path"]
            final_files.append(
                {
                    "path": item["json_relative_path"],
                    "sha256": sha256_prefixed(json_path.read_bytes()),
                    "kind": "json",
                }
            )
            final_files.append(
                {
                    "path": item["svg_relative_path"],
                    "sha256": sha256_prefixed(svg_path.read_bytes()),
                    "kind": "svg",
                }
            )
        final_files.append(
            {
                "path": index_rel.as_posix(),
                "sha256": sha256_prefixed((stage_dir / index_rel).read_bytes()),
                "kind": "index",
            }
        )

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        repo_commit, repo_dirty = _safe_git_state()

        manifest = {
            "schema_version": "d1_diagnostic_batch_manifest/v1",
            "mode": mode,
            "status": "provisional",
            "canonical": False,
            "ci_verified": False,
            "inventory_path": str(Path(inventory_path).as_posix()),
            "inventory_sha256": inventory_hash,
            "requested_source_names": source_names,
            "source_identities": source_records,
            "files": final_files,
            "entrypoint_version": ENTRYPOINT_VERSION,
            "generated_at_utc": generated_at,
            "repository_commit": repo_commit,
            "repository_dirty": repo_dirty,
        }
        manifest_bytes = canonical_json_bytes(manifest)
        manifest_path = stage_dir / "batch_manifest.json"
        manifest_path.write_bytes(manifest_bytes)

        return {
            "stage_dir": stage_dir,
            "manifest": manifest,
            "file_records": file_records,
        }
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a provisional local D1 extraction diagnostic batch.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root used to resolve inventory and source paths.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="Repository-relative or absolute path to the audio inventory.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Repository-relative or absolute path to the approved extraction config.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="Requested source basenames from the inventory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory to receive the completed diagnostic batch.",
    )
    parser.add_argument(
        "--mode",
        choices=["diagnostic_local"],
        default="diagnostic_local",
        help="Diagnostic batch mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve(strict=False)
    inventory_path = args.inventory
    if not inventory_path.is_absolute():
        inventory_path = (repo_root / inventory_path).resolve(strict=False)
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve(strict=False)
    output_dir = args.output
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve(strict=False)

    if output_dir.exists() and output_dir.is_dir() and any(output_dir.iterdir()):
        raise BatchValidationError(f"refusing to overwrite non-empty output directory: {output_dir}")
    if output_dir.exists() and output_dir.is_file():
        raise BatchValidationError(f"output path is a file, not a directory: {output_dir}")

    batch = _build_batch(
        repo_root=repo_root,
        inventory_path=inventory_path,
        config_path=config_path,
        source_names=args.sources,
        output_dir=output_dir,
        mode=args.mode,
    )
    stage_dir = batch["stage_dir"]
    try:
        if output_dir.exists():
            raise BatchValidationError(f"output path already exists during rename: {output_dir}")
        stage_dir.rename(output_dir)
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BatchValidationError as exc:
        print(f"Batch validation error: {exc}", file=sys.stderr)
        raise SystemExit(1)
