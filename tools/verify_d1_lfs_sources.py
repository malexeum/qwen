from __future__ import annotations

import hashlib
import sys
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"

EXPECTED_SOURCES: dict[str, tuple[int, str]] = {
    "tests/audio/08. Monkberry Moon Delight.mp3": (
        12974458,
        "9623df517afc73cfcc5d32e4e69e298d7764d5e730eb0fee33acf4aa2224a93d",
    ),
    "tests/audio/12 - Sunny Afternoon.mp3": (
        8628680,
        "8ede453e2c708018c875661f22046dff28d70e8e21b0b8aa19e5e03dbd73c628",
    ),
    "tests/audio/19 - Picture Book.mp3": (
        6230633,
        "c443295a3205b28584adc3ea9c5f13713b14a9b7f1056e4bc4378e19fba5590e",
    ),
    "tests/audio/Road_Trip.mp3": (
        2956826,
        "06e3bfc840cc515d43653a6e4333d20c49135bab9b8127097e3ff3c0ff33c29f",
    ),
}


def sha256_raw_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def is_lfs_pointer(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for relative_name, (expected_size, expected_sha256) in EXPECTED_SOURCES.items():
        path = repo_root / relative_name

        if not path.is_file():
            failures.append(
                f"{relative_name}: missing; "
                f"expected_size={expected_size} expected_sha256={expected_sha256}"
            )
            continue

        if is_lfs_pointer(path):
            failures.append(
                f"{relative_name}: Git LFS pointer was not materialized; "
                f"expected_size={expected_size} expected_sha256={expected_sha256}"
            )
            continue

        actual_size = path.stat().st_size
        actual_sha256 = sha256_raw_bytes(path)

        if actual_size != expected_size or actual_sha256 != expected_sha256:
            failures.append(
                f"{relative_name}: identity mismatch; "
                f"expected_size={expected_size} actual_size={actual_size} "
                f"expected_sha256={expected_sha256} actual_sha256={actual_sha256}"
            )
            continue

        print(
            f"verified {relative_name}: "
            f"size_octets={actual_size} sha256={actual_sha256}"
        )

    if failures:
        print("D1 LFS raw-byte verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
