"""Загрузка и валидация YAML-конфигурации Composition Planner v0.3.

Читает:
  configs/generator_catalog.yaml
  configs/palettes.yaml
  configs/visual_composition_profiles.yaml
  configs/poster_styles.yaml  (опционально)

Возвращает CompositionConfig — единственный объект конфигурации,
используемый во всех остальных модулях пакета.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml")


CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs"

ALLOWED_BLEND_MODES = {
    "normal", "screen", "add", "multiply", "soft_light", "max",
}


class CompositionConfigError(ValueError):
    """Ошибка валидации конфигурационных файлов."""


@dataclass
class CompositionConfig:
    catalog: dict          # generator_catalog.yaml (parsed)
    palettes: dict         # palettes.yaml (parsed)
    profiles: dict         # visual_composition_profiles.yaml (parsed)
    poster_styles: dict    # poster_styles.yaml (parsed, may be empty)
    config_hash: str       # SHA-256 canonical JSON всех загруженных YAML
    profile_library_version: str


def load_composition_config(
    configs_dir: Path | None = None,
) -> CompositionConfig:
    """Загружает, валидирует и возвращает CompositionConfig."""
    root = configs_dir or CONFIGS_DIR

    catalog = _load_yaml(root / "generator_catalog.yaml")
    palettes = _load_yaml(root / "palettes.yaml")
    profiles = _load_yaml(root / "visual_composition_profiles.yaml")
    poster_styles = _load_yaml_optional(root / "poster_styles.yaml")

    _validate_catalog(catalog)
    _validate_palettes(palettes)
    _validate_profiles(profiles, catalog, palettes)

    config_hash = _compute_config_hash(catalog, palettes, profiles, poster_styles)
    profile_lib_ver = profiles.get("profile_library_version", "0.3.0")

    return CompositionConfig(
        catalog=catalog,
        palettes=palettes,
        profiles=profiles,
        poster_styles=poster_styles,
        config_hash=config_hash,
        profile_library_version=profile_lib_ver,
    )


# ─── private helpers ───────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise CompositionConfigError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise CompositionConfigError(f"Expected YAML dict in {path}")
    return data


def _load_yaml_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    return _load_yaml(path)


def _validate_catalog(catalog: dict) -> None:
    required_fields = {"canonical_id", "builder", "family", "roles", "supports"}
    generators = catalog.get("generators", {})
    if not generators:
        raise CompositionConfigError("generator_catalog.yaml: 'generators' is empty")
    # Build reverse-alias index to catch duplicates
    seen_aliases: dict[str, str] = {}
    for gid, spec in generators.items():
        missing = required_fields - set(spec.keys())
        if missing:
            raise CompositionConfigError(
                f"generator_catalog: '{gid}' missing fields: {missing}"
            )
        if spec["canonical_id"] != gid:
            raise CompositionConfigError(
                f"generator_catalog: '{gid}' canonical_id mismatch"
            )
        for alias in spec.get("aliases", []):
            if alias in seen_aliases:
                raise CompositionConfigError(
                    f"Duplicate alias '{alias}' in generators "
                    f"'{seen_aliases[alias]}' and '{gid}'"
                )
            seen_aliases[alias] = gid


def _validate_palettes(palettes: dict) -> None:
    palette_map = palettes.get("palettes", {})
    if not palette_map:
        raise CompositionConfigError("palettes.yaml: 'palettes' is empty")
    for pid, spec in palette_map.items():
        if "background_rgba" not in spec:
            raise CompositionConfigError(
                f"palettes: '{pid}' missing 'background_rgba'"
            )


def _validate_profiles(profiles: dict, catalog: dict, palettes: dict) -> None:
    profile_map = profiles.get("profiles", {})
    if not profile_map:
        raise CompositionConfigError("visual_composition_profiles.yaml: 'profiles' is empty")

    palette_ids = set(palettes.get("palettes", {}).keys())
    generator_ids = set(catalog.get("generators", {}).keys())
    # collect all known aliases
    all_aliases: dict[str, str] = {}
    for gid, spec in catalog.get("generators", {}).items():
        for alias in spec.get("aliases", []):
            all_aliases[alias] = gid
    known_ids = generator_ids | set(all_aliases.keys())

    for slug, profile in profile_map.items():
        identity = profile.get("identity", {})
        pid = identity.get("palette_id")
        if pid and pid not in palette_ids:
            raise CompositionConfigError(
                f"Profile '{slug}': palette_id '{pid}' not found in palettes.yaml"
            )

        for layer in profile.get("layers", []):
            gid = layer.get("generator_id")
            if gid and gid not in known_ids:
                raise CompositionConfigError(
                    f"Profile '{slug}', layer '{layer.get('id')}': "
                    f"unknown generator_id '{gid}'"
                )
            bm = layer.get("blend_mode")
            if bm and bm not in ALLOWED_BLEND_MODES:
                raise CompositionConfigError(
                    f"Profile '{slug}', layer '{layer.get('id')}': "
                    f"blend_mode '{bm}' not allowed"
                )


def _compute_config_hash(*dicts: dict) -> str:
    canonical = json.dumps(list(dicts), ensure_ascii=True, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"
