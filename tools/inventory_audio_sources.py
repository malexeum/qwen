from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a"})
CHUNK_SIZE = 1024 * 1024

SCHEMA_VERSION = "audio_source_inventory/v1"
INVENTORY_ROOT = Path("tests") / "audio"
OUTPUT_PATH = Path("reports") / "audio_source_inventory.json"


class InventoryPathError(RuntimeError):
    """Raised when an inventory path resolves outside the repository root."""


def _resolved_repo_root(repo_root: Path) -> Path:
    """Return the existing, resolved repository root directory."""
    resolved = repo_root.resolve(strict=True)

    if not resolved.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {resolved}")

    return resolved


def _require_inside_repo(path: Path, repo_root: Path) -> Path:
    """
    Resolve an existing path and ensure it remains inside repository root.

    This rejects symlinks resolving outside the repository.
    """
    resolved = path.resolve(strict=True)

    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise InventoryPathError(
            f"Path resolves outside repository root: {path} -> {resolved}"
        ) from exc

    return resolved


def _sha256_raw_bytes(path: Path) -> str:
    """Compute a SHA-256 digest from exact raw bytes using streaming chunks."""
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)

    return f"sha256:{digest.hexdigest()}"


def _iter_audio_paths(audio_root: Path, repo_root: Path) -> list[Path]:
    """
    Find recognized audio files recursively without following directory symlinks.

    File symlinks are allowed only when their resolved target stays within
    the repository root. Directory symlinks are checked but not traversed.
    """
    discovered: list[Path] = []

    for current_root, directory_names, file_names in os.walk(
        audio_root,
        topdown=True,
        followlinks=False,
    ):
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

            if not candidate.is_file():
                continue

            discovered.append(candidate)

    return discovered


def build_inventory(repo_root: Path) -> dict[str, Any]:
    """Build the deterministic inventory document for tests/audio."""
    resolved_repo_root = _resolved_repo_root(repo_root)
    audio_root = resolved_repo_root / INVENTORY_ROOT

    if not audio_root.exists():
        raise FileNotFoundError(f"Audio source directory does not exist: {audio_root}")

    if not audio_root.is_dir():
        raise NotADirectoryError(f"Audio source root is not a directory: {audio_root}")

    _require_inside_repo(audio_root, resolved_repo_root)

    entries: list[dict[str, Any]] = []

    for candidate in _iter_audio_paths(audio_root, resolved_repo_root):
        resolved_file = _require_inside_repo(candidate, resolved_repo_root)
        relative_path = candidate.relative_to(resolved_repo_root).as_posix()

        relative_parts = Path(relative_path).parts
        if Path(relative_path).is_absolute() or ".." in relative_parts:
            raise InventoryPathError(
                f"Invalid repository-relative path: {relative_path}"
            )

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
        "root": INVENTORY_ROOT.as_posix(),
        "entries": entries,
    }


def serialize_inventory(inventory: dict[str, Any]) -> bytes:
    """
    Serialize canonical UTF-8 JSON with exactly one terminal LF.

    Binary output avoids Windows text-mode conversion of LF to CRLF.
    """
    payload = json.dumps(
        inventory,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return payload.encode("utf-8") + b"\n"


def write_inventory(repo_root: Path) -> Path:
    """Write reports/audio_source_inventory.json and return its full path."""
    resolved_repo_root = _resolved_repo_root(repo_root)

    output_path = resolved_repo_root / OUTPUT_PATH
    output_parent = output_path.parent

    # reports/ may not exist on first invocation.
    output_parent.mkdir(parents=True, exist_ok=True)

    # Now strict resolution works, and also checks for a symlink escape.
    resolved_output_parent = _require_inside_repo(
        output_parent,
        resolved_repo_root,
    )
    resolved_output_path = resolved_output_parent / output_path.name

    serialized = serialize_inventory(build_inventory(resolved_repo_root))
    resolved_output_path.write_bytes(serialized)

    return resolved_output_path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = write_inventory(repo_root)

    # Intentionally prints only a path; never emits source hashes.
    print(output_path.relative_to(repo_root).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())