"""Канонизация generator ID для VisualCompositionPlanner v0.3.

Каждый alias в generator_catalog.yaml → canonical_id.
Неизвестный ID/alias вызывает CompositionConfigError — никакого fallback.
"""
from __future__ import annotations

from .config_loader import CompositionConfigError


def build_alias_index(catalog: dict) -> dict[str, str]:
    """Строит словарь alias → canonical_id из generator_catalog."""
    index: dict[str, str] = {}
    for canonical_id, spec in catalog.get("generators", {}).items():
        index[canonical_id] = canonical_id  # сам себе alias
        for alias in spec.get("aliases", []):
            index[alias] = canonical_id
    return index


def canonicalize_generator_id(
    requested_id: str,
    catalog: dict,
    alias_index: dict[str, str] | None = None,
) -> str:
    """Возвращает canonical_id или кидает CompositionConfigError."""
    idx = alias_index if alias_index is not None else build_alias_index(catalog)
    if requested_id not in idx:
        known = sorted(idx.keys())
        raise CompositionConfigError(
            f"Unknown generator id or alias: '{requested_id}'. "
            f"Known: {known}"
        )
    return idx[requested_id]


def get_generator_spec(canonical_id: str, catalog: dict) -> dict:
    """Возвращает spec генератора по canonical_id."""
    generators = catalog.get("generators", {})
    if canonical_id not in generators:
        raise CompositionConfigError(
            f"Generator '{canonical_id}' not in catalog"
        )
    return generators[canonical_id]
