from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.d1_feature_artifact_io import read_feature_artifact, write_feature_artifact
from lib.d1_feature_artifacts import SCHEMA_V2, build_d1_feature_artifact
from tools.d1_extract import build_extraction_result
from tools.render_rock_visual_identity_v8 import RENDERER_NAME, RENDERER_VERSION, render_v8_svg

DEFAULT_INVENTORY = Path("corpus/inventory/audio_source_inventory.v1.json")
DEFAULT_CONFIG = Path("configs/d1_perceptual_config.v1.json")
DEFAULT_SOURCES = [
    "08. Monkberry Moon Delight.mp3",
    "12 - Sunny Afternoon.mp3",
    "19 - Picture Book.mp3",
    "Road_Trip.mp3",
]
BATCH_MANIFEST_SCHEMA = "rock_visual_identity_v8_batch/v1"


class BatchContractError(ValueError):
    pass


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


def _read_inventory(inventory_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchContractError(f"cannot read inventory: {inventory_path}") from exc
    if not isinstance(payload, dict):
        raise BatchContractError("inventory document must be a JSON object")
    if payload.get("schema_version") != "audio_source_inventory/v1":
        raise BatchContractError("unsupported inventory schema_version")
    if not isinstance(payload.get("entries"), list):
        raise BatchContractError("inventory entries must be a list")
    return payload


def _resolve_source_path(*, repo_root: Path, inventory_path: Path, source_name: str) -> Path:
    inventory = _read_inventory(inventory_path)
    matches: list[Path] = []
    for entry in inventory.get("entries", []):
        if not isinstance(entry, dict):
            continue
        path_text = entry.get("path")
        if not isinstance(path_text, str):
            continue
        candidate = repo_root / path_text
        if Path(path_text).name == source_name or path_text == source_name:
            matches.append(candidate)
    if not matches:
        raise BatchContractError(f"source not found in inventory: {source_name}")
    if len(matches) > 1:
        raise BatchContractError(f"source name is ambiguous: {source_name}")
    result = matches[0]
    if not result.is_file():
        raise BatchContractError(f"source file is missing: {result}")
    return result


def _git_head_sha(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()
    if completed.returncode == 0:
        value = completed.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    return hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()


def _output_guard(output_dir: Path) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise BatchContractError(f"output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise BatchContractError(f"output directory must be empty before batch run: {output_dir}")
        return
    output_dir.mkdir(parents=True, exist_ok=False)


def _source_output_dir(output_dir: Path, source_name: str) -> Path:
    return output_dir / slugify(Path(source_name).stem)


def _build_artifact_for_source(*, repo_root: Path, source_path: Path, inventory_path: Path, config_path: Path, git_sha: str, analysis_id: str = "d1_rock_v1") -> Any:
    result = build_extraction_result(
        repo_root=repo_root,
        source_path=source_path,
        inventory_path=inventory_path,
        config_path=config_path,
    )
    provenance = result["provenance"]
    return build_d1_feature_artifact(
        analysis_id=analysis_id,
        source_identity={
            "kind": "audio_file",
            "inventory_source_id": provenance["inventory_source_id"],
            "content_sha256": provenance["content_sha256"],
            "byte_size": int(provenance["byte_size"]),
            "suffix": ".mp3",
            "adapter_name": "d1_perceptual_extractor",
            "adapter_version": "1.0.0",
            "analysis_config_version": "d1_perceptual_config/v1",
            "decoder_backend": provenance["decoder_capability_backend"],
        },
        perceptual=result["perceptual"],
        git_sha=git_sha,
        schema_version=SCHEMA_V2,
        source_locator={"registry_path": provenance["registry_path"]},
    )


def _source_manifest_entry(*, source_name: str, source_path: Path, output_root: Path, artifact: Any, artifact_path: Path, svg_path: Path, metadata_path: Path, diagnostics_path: Path) -> dict[str, Any]:
    def _sha(path: Path | None) -> str | None:
        if path is None or not path.is_file():
            return None
        return sha256_prefixed(path.read_bytes())

    return {
        "source_name": source_name,
        "registry_path": artifact.source_locator["registry_path"],
        "source_path": str(source_path),
        "output_dir": str(output_root),
        "status": "ok",
        "artifact_path": str(artifact_path),
        "artifact_sha256": _sha(artifact_path),
        "svg_sha256": _sha(svg_path),
        "metadata_sha256": _sha(metadata_path),
        "diagnostics_sha256": _sha(diagnostics_path),
        "renderer": {
            "name": RENDERER_NAME,
            "version": RENDERER_VERSION,
        },
    }


def run_batch(*, repo_root: Path, inventory_path: Path, config_path: Path, output_dir: Path, source_names: list[str]) -> dict[str, Any]:
    if not source_names:
        raise BatchContractError("at least one source must be requested")
    if len(source_names) != 4:
        raise BatchContractError("this batch pipeline requires exactly four sources")

    _output_guard(output_dir)
    git_sha = _git_head_sha(repo_root)
    manifest_entries: list[dict[str, Any]] = []

    for source_name in source_names:
        resolved_source = _resolve_source_path(repo_root=repo_root, inventory_path=inventory_path, source_name=source_name)
        source_root = _source_output_dir(output_dir, source_name)
        source_root.mkdir(parents=True, exist_ok=False)
        artifact = _build_artifact_for_source(
            repo_root=repo_root,
            source_path=resolved_source,
            inventory_path=inventory_path,
            config_path=config_path,
            git_sha=git_sha,
        )
        artifact_path = source_root / "features" / "d1_rock_v1.json"
        svg_path = source_root / "poster.rock_visual_identity_v8.svg"
        metadata_path = source_root / "poster.rock_visual_identity_v8.metadata.json"
        diagnostics_path = source_root / "diagnostics.json"

        write_feature_artifact(source_root, artifact)
        artifact_path = source_root / "features" / "d1_rock_v1.json"
        svg_bytes, metadata = render_v8_svg(artifact_path, seed=source_name)
        svg_path.write_bytes(svg_bytes)
        metadata_path.write_bytes(canonical_json_bytes(metadata))
        diagnostics_path.write_text(json.dumps({"renderer": RENDERER_NAME, "mode": metadata["composition_mode"], "source_name": source_name}, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

        read_feature_artifact(artifact_path)
        manifest_entries.append(
            _source_manifest_entry(
                source_name=source_name,
                source_path=resolved_source,
                output_root=source_root,
                artifact=artifact,
                artifact_path=artifact_path,
                svg_path=svg_path,
                metadata_path=metadata_path,
                diagnostics_path=diagnostics_path,
            )
        )

    manifest = {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(manifest_entries),
        "status": "ok",
        "sources": manifest_entries,
        "renderer": {"name": RENDERER_NAME, "version": RENDERER_VERSION},
    }
    (output_dir / "batch_manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render four canonical D1 feature artifacts via the rock_visual_identity_v8 renderer.")
    parser.add_argument("--inventory", type=Path, required=True, help="Path to the audio source inventory JSON.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to the D1 perceptual config JSON.")
    parser.add_argument("--output", "--output-dir", dest="output", type=Path, required=True, help="Empty batch output directory root.")
    parser.add_argument("--sources", nargs="+", dest="sources", help="Required source basenames to include in the batch.")
    parser.add_argument("--source", dest="source_aliases", action="append", nargs="+", default=[], help="Compatibility alias for repeated source basenames.")
    args = parser.parse_args()

    flat_sources: list[str] = []
    if args.sources:
        flat_sources.extend(args.sources)
    for group in args.source_aliases:
        flat_sources.extend(group)
    if not flat_sources:
        parser.error("--sources SOURCE [SOURCE ...] is required")
    args.sources = flat_sources
    return args


def main() -> int:
    args = parse_args()
    output_dir = args.output
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    run_batch(
        repo_root=REPO_ROOT,
        inventory_path=(REPO_ROOT / args.inventory).resolve(strict=False) if not args.inventory.is_absolute() else args.inventory.resolve(strict=False),
        config_path=(REPO_ROOT / args.config).resolve(strict=False) if not args.config.is_absolute() else args.config.resolve(strict=False),
        output_dir=output_dir.resolve(strict=False),
        source_names=args.sources,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
