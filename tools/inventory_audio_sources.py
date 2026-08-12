from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a"})
CHUNK_SIZE = 1024 * 1024
SCHEMA_VERSION = "audio_source_inventory/v1"
DEFAULT_AUDIO_ROOT = Path("tests") / "audio"
DEFAULT_OUTPUT_PATH = Path("corpus") / "inventory" / "audio_source_inventory.v1.json"


class InventoryPathError(RuntimeError):
    """Raised when an inventory path resolves outside the repository root."""


def _resolved_repo_root(repo_root: Path) -> Path:
    resolved = repo_root.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {resolved}")
    return resolved


def _relative_input(value: Path, field: str) -> Path:
    if value.is_absolute() or ".." in value.parts:
        raise InventoryPathError(f"{field} must be a repository-relative path: {value}")
    return value


def _require_inside_repo(path: Path, repo_root: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise InventoryPathError(
            f"Path resolves outside repository root: {path} -> {resolved}"
        ) from exc
    return resolved


def _sha256_raw_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _iter_audio_paths(audio_root: Path, repo_root: Path) -> list[Path]:
    discovered: list[Path] = []
    for current_root, directory_names, file_names in os.walk(audio_root, topdown=True, followlinks=False):
        current = Path(current_root)
        _require_inside_repo(current, repo_root)
        retained_directories: list[str] = []
        for directory_name in sorted(directory_names):
            directory_path = current / directory_name
            if directory_path.is_symlink():
                _require_inside_repo(directory_path, repo_root)
                continue
            _require_inside_repo(directory_path, repo_root)
            retained_directories.append(directory_name)
        directory_names[:] = retained_directories
        for file_name in sorted(file_names):
            candidate = current / file_name
            if candidate.suffix.lower() not in AUDIO_SUFFIXES:
                continue
            _require_inside_repo(candidate, repo_root)
            if candidate.is_file():
                discovered.append(candidate)
    return discovered


def build_inventory(repo_root: Path, audio_root: Path = DEFAULT_AUDIO_ROOT) -> dict[str, Any]:
    resolved_repo_root = _resolved_repo_root(repo_root)
    relative_audio_root = _relative_input(audio_root, "audio_root")
    source_root = resolved_repo_root / relative_audio_root
    if not source_root.exists():
        raise FileNotFoundError(f"Audio source directory does not exist: {source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"Audio source root is not a directory: {source_root}")
    _require_inside_repo(source_root, resolved_repo_root)

    entries: list[dict[str, Any]] = []
    for candidate in _iter_audio_paths(source_root, resolved_repo_root):
        resolved_file = _require_inside_repo(candidate, resolved_repo_root)
        relative_path = candidate.relative_to(resolved_repo_root).as_posix()
        entries.append(
            {
                "path": relative_path,
                "byte_size": resolved_file.stat().st_size,
                "sha256": _sha256_raw_bytes(resolved_file),
                "suffix": candidate.suffix.lower(),
            }
        )
    entries.sort(key=lambda entry: entry["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "root": relative_audio_root.as_posix(),
        "entries": entries,
    }


def serialize_inventory(inventory: dict[str, Any]) -> bytes:
    return json.dumps(
        inventory,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"


def write_inventory(
    repo_root: Path,
    audio_root: Path = DEFAULT_AUDIO_ROOT,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    resolved_repo_root = _resolved_repo_root(repo_root)
    relative_output_path = _relative_input(output_path, "output_path")
    destination = resolved_repo_root / relative_output_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = _require_inside_repo(destination.parent, resolved_repo_root)
    resolved_destination = resolved_parent / destination.name
    resolved_destination.write_bytes(
        serialize_inventory(build_inventory(resolved_repo_root, audio_root))
    )
    return resolved_destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a raw-byte external audio inventory.")
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_path = write_inventory(repo_root, args.audio_root, args.output)
    print(output_path.relative_to(repo_root).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
