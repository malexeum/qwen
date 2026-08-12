from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "inventory_audio_sources.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_audio_sources",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory = _load_module()


def _raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)

    return f"sha256:{digest.hexdigest()}"


def test_audio_source_inventory_is_deterministic_and_raw_byte_based():
    output_path = inventory.write_inventory(REPO_ROOT)
    first_bytes = output_path.read_bytes()

    output_path = inventory.write_inventory(REPO_ROOT)
    second_bytes = output_path.read_bytes()

    assert first_bytes == second_bytes
    assert first_bytes.endswith(b"\n")
    assert b"\r" not in first_bytes

    document = json.loads(first_bytes.decode("utf-8"))

    assert set(document) == {"schema_version", "root", "entries"}
    assert document["schema_version"] == "audio_source_inventory/v1"
    assert document["root"] == "tests/audio"

    entries = document["entries"]
    assert [entry["path"] for entry in entries] == sorted(
        entry["path"] for entry in entries
    )

    resolved_repo_root = REPO_ROOT.resolve()

    for entry in entries:
        assert set(entry) == {"path", "byte_size", "sha256", "suffix"}

        relative_path = Path(entry["path"])
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        assert relative_path.as_posix() == entry["path"]

        source_path = REPO_ROOT / relative_path
        resolved_source_path = source_path.resolve(strict=True)

        try:
            resolved_source_path.relative_to(resolved_repo_root)
        except ValueError as exc:
            raise AssertionError(
                f"Inventory path escapes repository root: {entry['path']}"
            ) from exc

        assert entry["byte_size"] == resolved_source_path.stat().st_size
        assert entry["sha256"] == _raw_sha256(resolved_source_path)
        assert entry["suffix"] == source_path.suffix.lower()


def test_out_of_root_audio_symlink_is_rejected(tmp_path: Path):
    outside_file = tmp_path / "outside.wav"
    outside_file.write_bytes(b"raw bytes only")

    sandbox_repo = tmp_path / "repo"
    sandbox_audio_root = sandbox_repo / "tests" / "audio"
    sandbox_audio_root.mkdir(parents=True)

    escaping_link = sandbox_audio_root / "escape.wav"

    try:
        escaping_link.symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable on this host: {exc}")

    with pytest.raises(inventory.InventoryPathError):
        inventory.build_inventory(sandbox_repo)