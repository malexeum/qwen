from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "inventory_audio_sources.py"
REGISTRY_PATH = REPO_ROOT / "corpus" / "inventory" / "audio_source_inventory.v1.json"
SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _load_module():
    spec = importlib.util.spec_from_file_location("inventory_audio_sources", SCRIPT_PATH)
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


def _sandbox_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    audio_root = repo_root / "tests" / "audio"
    audio_root.mkdir(parents=True)
    (audio_root / "zeta.MP3").write_bytes(b"zeta raw bytes")
    (audio_root / "alpha.wav").write_bytes(b"alpha raw bytes")
    return repo_root


def test_audio_source_inventory_is_deterministic_and_raw_byte_based(tmp_path: Path):
    repo_root = _sandbox_repo(tmp_path)
    output = Path("corpus/inventory/audio_source_inventory.v1.json")
    first_path = inventory.write_inventory(repo_root, output_path=output)
    first_bytes = first_path.read_bytes()
    second_path = inventory.write_inventory(repo_root, output_path=output)
    second_bytes = second_path.read_bytes()

    assert first_path == second_path
    assert first_bytes == second_bytes
    assert first_bytes.endswith(b"\n")
    assert b"\r" not in first_bytes

    document = json.loads(first_bytes.decode("utf-8"))
    assert document["schema_version"] == "audio_source_inventory/v1"
    assert document["root"] == "tests/audio"
    assert [entry["path"] for entry in document["entries"]] == [
        "tests/audio/alpha.wav",
        "tests/audio/zeta.MP3",
    ]
    for entry in document["entries"]:
        source_path = repo_root / entry["path"]
        assert entry["byte_size"] == source_path.stat().st_size
        assert entry["sha256"] == _raw_sha256(source_path)
        assert entry["suffix"] == source_path.suffix.lower()


def test_out_of_root_audio_symlink_is_rejected(tmp_path: Path):
    repo_root = _sandbox_repo(tmp_path)
    outside_file = tmp_path / "outside.wav"
    outside_file.write_bytes(b"raw bytes only")
    escaping_link = repo_root / "tests" / "audio" / "escape.wav"
    try:
        escaping_link.symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable on this host: {exc}")
    with pytest.raises(inventory.InventoryPathError):
        inventory.build_inventory(repo_root)


def test_inventory_rejects_absolute_or_traversal_paths(tmp_path: Path):
    repo_root = _sandbox_repo(tmp_path)
    with pytest.raises(inventory.InventoryPathError):
        inventory.build_inventory(repo_root, Path("../audio"))
    with pytest.raises(inventory.InventoryPathError):
        inventory.write_inventory(repo_root, output_path=Path("../inventory.json"))


def test_committed_external_inventory_is_canonical_registry():
    raw_bytes = REGISTRY_PATH.read_bytes()
    assert raw_bytes.endswith(b"\n")
    assert b"\r" not in raw_bytes
    document = json.loads(raw_bytes.decode("utf-8"))
    assert set(document) == {"schema_version", "root", "entries"}
    assert document["schema_version"] == "audio_source_inventory/v1"
    assert document["root"] == "tests/audio"
    assert document["entries"]
    paths = [entry["path"] for entry in document["entries"]]
    assert paths == sorted(paths)
    for entry in document["entries"]:
        assert set(entry) == {"path", "byte_size", "sha256", "suffix"}
        assert entry["path"].startswith("tests/audio/")
        assert Path(entry["path"]).as_posix() == entry["path"]
        assert entry["byte_size"] > 0
        assert SHA256_RE.fullmatch(entry["sha256"])
        assert entry["suffix"] in inventory.AUDIO_SUFFIXES
