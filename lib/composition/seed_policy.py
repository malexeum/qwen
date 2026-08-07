"""Seed policy для VisualCompositionPlanner v0.3.

Base seed:
    SHA-256( audio_content_hash | normalize(title) | normalize(artist)
             | duration_ms | style_profile_slug | profile_library_version
             | variation_seed )

Layer seed:
    SHA-256( base_seed | layer_id | canonical_generator_id )

Оба seed — uint64 (первые 8 байт SHA-256 как big-endian unsigned int).
Это обеспечивает детерминизм и область значений пригодную для NumPy.
"""
from __future__ import annotations

import hashlib
import unicodedata


def normalize_text(s: str | None) -> str:
    """NFKC-нормализация + lower + strip. None → пустая строка."""
    if s is None:
        return ""
    normalized = unicodedata.normalize("NFKC", s).lower().strip()
    return normalized


def sha256_to_uint64(text: str) -> int:
    """Первые 8 байт SHA-256(text) → unsigned 64-bit int (big-endian)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big")


def compute_base_seed(
    audio_content_hash: str,
    title: str | None,
    artist: str | None,
    duration_ms: int | None,
    style_profile_slug: str,
    profile_library_version: str,
    variation_seed: int,
) -> int:
    """Детерминированный base seed трека."""
    parts = [
        audio_content_hash,
        normalize_text(title),
        normalize_text(artist),
        str(duration_ms if duration_ms is not None else ""),
        style_profile_slug,
        profile_library_version,
        str(variation_seed),
    ]
    material = "|".join(parts)
    return sha256_to_uint64(material)


def compute_layer_seed(
    base_seed: int,
    layer_id: str,
    canonical_generator_id: str,
) -> int:
    """Детерминированный seed конкретного слоя."""
    material = f"{base_seed}|{layer_id}|{canonical_generator_id}"
    return sha256_to_uint64(material)
