# lib/style_engine/config_loader.py

import os
import glob
import yaml
from typing import Dict, Any


STYLE_PROFILES_DIR = os.path.join("configs", "style_profiles")
INTERPRETATION_PROFILES_DIR = os.path.join("configs", "interpretation_profiles")


class StyleProfile:
    def __init__(self, data: Dict[str, Any]):
        self.slug: str = data["slug"]
        self.music_style: str = data.get("music_style", "")
        self.visual_mood: str = data.get("visual_mood", "")
        self.palette: str = data.get("palette", "")
        self.contrast: float = float(data.get("contrast", 0.5))
        self.geometry: str = data.get("geometry", "")
        self.density: float = float(data.get("density", 0.5))
        self.motion_intensity: float = float(data.get("motion_intensity", 0.5))
        self.noise_level: float = float(data.get("noise_level", 0.5))
        self.symmetry_bias: float = float(data.get("symmetry_bias", 0.5))
        self.complexity_bias: float = float(data.get("complexity_bias", 0.5))
        self.version: str = data.get("version", "0.2.1")


class InterpretationProfile:
    def __init__(self, data: Dict[str, Any]):
        self.slug: str = data["slug"]
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        # axis_weights: dict[str, float]
        self.axis_weights: Dict[str, float] = {
            k: float(v) for k, v in data.get("axis_weights", {}).items()
        }
        # mapping_rules: arbitrary config, но мы ожидаем ключи типа "symmetry_bias" etc.
        self.mapping_rules: Dict[str, Any] = data.get("mapping_rules", {})


def _load_yaml_files(directory: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(directory):
        return result

    pattern = os.path.join(directory, "*.yaml")
    for path in glob.glob(pattern):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or "slug" not in data:
            continue
        slug = data["slug"]
        result[slug] = data
    return result


def load_style_profiles() -> Dict[str, StyleProfile]:
    raw = _load_yaml_files(STYLE_PROFILES_DIR)
    profiles: Dict[str, StyleProfile] = {}
    for slug, data in raw.items():
        profiles[slug] = StyleProfile(data)
    return profiles


def load_interpretation_profiles() -> Dict[str, InterpretationProfile]:
    raw = _load_yaml_files(INTERPRETATION_PROFILES_DIR)
    profiles: Dict[str, InterpretationProfile] = {}
    for slug, data in raw.items():
        profiles[slug] = InterpretationProfile(data)
    return profiles