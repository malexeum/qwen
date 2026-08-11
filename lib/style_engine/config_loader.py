# lib/style_engine/config_loader.py
# v0.3.2 — CB-3.1-A0/A1 corrective
#
# BUGFIX: config dirs are now resolved relative to THIS FILE (__file__),
# not relative to CWD. Previously, pytest run from D:\WORK\AVCoder loaded
# root-level configs/ (old schema, base: 0.25, missing theta axes) instead
# of canonical lib/style_engine/configs/.
#
# Layout:
#   lib/style_engine/config_loader.py   <- THIS file, parents[0] = lib/style_engine
#   lib/style_engine/configs/           <- canonical config root
#     interpretation_profiles/
#     style_profiles/

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ---------------------------------------------------------------------------
# Path resolution — anchored to THIS file, CWD-independent
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent          # lib/style_engine/
_CONFIG_ROOT = _THIS_DIR / "configs"                 # lib/style_engine/configs/

INTERPRETATION_PROFILES_DIR: Path = _CONFIG_ROOT / "interpretation_profiles"
STYLE_PROFILES_DIR: Path           = _CONFIG_ROOT / "style_profiles"

# Legacy str aliases kept for any callers that did os.path.join with these.
# Use the Path objects above for all new code.
INTERPRETATION_PROFILES_DIR_STR: str = str(INTERPRETATION_PROFILES_DIR)
STYLE_PROFILES_DIR_STR: str          = str(STYLE_PROFILES_DIR)


# ---------------------------------------------------------------------------
# Profile dataclasses
# ---------------------------------------------------------------------------

class StyleProfile:
    def __init__(self, data: Dict[str, Any]):
        self.slug: str              = data["slug"]
        self.music_style: str       = data.get("music_style", "")
        self.visual_mood: str       = data.get("visual_mood", "")
        self.palette: str           = data.get("palette", "default_dark")
        self.contrast: float        = float(data.get("contrast", 0.5))
        self.geometry: str          = data.get("geometry", "")
        self.density: float         = float(data.get("density", 0.5))
        self.motion_intensity: float = float(data.get("motion_intensity", 0.5))
        self.noise_level: float     = float(data.get("noise_level", 0.5))
        self.symmetry_bias: float   = float(data.get("symmetry_bias", 0.5))
        self.complexity_bias: float = float(data.get("complexity_bias", 0.5))
        self.version: str           = data.get("version", "0.3.0")


@dataclass
class GuardrailAction:
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass
class Guardrail:
    when: str
    actions: Dict[str, GuardrailAction] = field(default_factory=dict)


class InterpretationProfile:
    def __init__(self, data: Dict[str, Any]):
        self.slug: str          = data["slug"]
        self.name: str          = data.get("name", "")
        self.description: str   = data.get("description", "")
        self.axis_weights: Dict[str, float] = {
            k: float(v) for k, v in data.get("axis_weights", {}).items()
        }
        self.mapping_rules: Dict[str, Any] = data.get("mapping_rules", {})
        self.guardrails: List[Guardrail] = []
        for gr_raw in data.get("guardrails", []):
            when = str(gr_raw.get("when", ""))
            actions_raw = gr_raw.get("actions", {})
            actions: Dict[str, GuardrailAction] = {}
            for param, act in actions_raw.items():
                actions[param] = GuardrailAction(
                    min=float(act["min"]) if "min" in act else None,
                    max=float(act["max"]) if "max" in act else None,
                )
            self.guardrails.append(Guardrail(when=when, actions=actions))
        # Provenance: record which file was loaded and its SHA-256
        self._source_path: Optional[str] = data.get("_source_path")
        self._source_sha256: Optional[str] = data.get("_source_sha256")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_yaml_files(directory: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load all *.yaml files from *directory*.
    Injects _source_path and _source_sha256 into each dict for provenance.
    Returns empty dict (no KeyError) if directory does not exist.
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.yaml")):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict) or "slug" not in data:
            continue
        data["_source_path"] = str(path)
        data["_source_sha256"] = _sha256_file(path)
        result[data["slug"]] = data
    return result


def load_style_profiles() -> Dict[str, StyleProfile]:
    raw = _load_yaml_files(STYLE_PROFILES_DIR)
    return {slug: StyleProfile(d) for slug, d in raw.items()}


def load_interpretation_profiles() -> Dict[str, InterpretationProfile]:
    raw = _load_yaml_files(INTERPRETATION_PROFILES_DIR)
    return {slug: InterpretationProfile(d) for slug, d in raw.items()}
