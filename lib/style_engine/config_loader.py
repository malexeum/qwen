# lib/style_engine/config_loader.py
# v0.3.1 — добавлен GuardrailAction + guardrails в InterpretationProfile

import os
import glob
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import yaml


STYLE_PROFILES_DIR         = os.path.join("configs", "style_profiles")
INTERPRETATION_PROFILES_DIR = os.path.join("configs", "interpretation_profiles")


class StyleProfile:
    def __init__(self, data: Dict[str, Any]):
        self.slug: str             = data["slug"]
        self.music_style: str      = data.get("music_style", "")
        self.visual_mood: str      = data.get("visual_mood", "")
        self.palette: str          = data.get("palette", "default_dark")
        self.contrast: float       = float(data.get("contrast", 0.5))
        self.geometry: str         = data.get("geometry", "")
        self.density: float        = float(data.get("density", 0.5))
        self.motion_intensity: float = float(data.get("motion_intensity", 0.5))
        self.noise_level: float    = float(data.get("noise_level", 0.5))
        self.symmetry_bias: float  = float(data.get("symmetry_bias", 0.5))
        self.complexity_bias: float = float(data.get("complexity_bias", 0.5))
        self.version: str          = data.get("version", "0.3.0")


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
        self.slug: str         = data["slug"]
        self.name: str         = data.get("name", "")
        self.description: str  = data.get("description", "")
        self.axis_weights: Dict[str, float] = {
            k: float(v) for k, v in data.get("axis_weights", {}).items()
        }
        self.mapping_rules: Dict[str, Any] = data.get("mapping_rules", {})
        # guardrails: list of Guardrail objects
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


def _load_yaml_files(directory: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(directory):
        return result
    for path in glob.glob(os.path.join(directory, "*.yaml")):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict) or "slug" not in data:
            continue
        result[data["slug"]] = data
    return result


def load_style_profiles() -> Dict[str, StyleProfile]:
    raw = _load_yaml_files(STYLE_PROFILES_DIR)
    return {slug: StyleProfile(d) for slug, d in raw.items()}


def load_interpretation_profiles() -> Dict[str, InterpretationProfile]:
    raw = _load_yaml_files(INTERPRETATION_PROFILES_DIR)
    return {slug: InterpretationProfile(d) for slug, d in raw.items()}
