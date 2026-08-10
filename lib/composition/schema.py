"""VisualCompositionPlan v0.3 — dataclass schema.

Единственный источник правды между Python reference renderer и Java renderer.
Не импортировать PIL, matplotlib, fractal generators.

E2: добавлен HarmonyThetaArtifact — поле harmony_theta в TrackIdentity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class HarmonyThetaArtifact:
    """Гармоническая сигнатура трека θ ∈ ℝ^8 (E2).

    Сериализуется в track_artifact.yaml рядом с feature_vector.
    Формат соответствует HarmonyTheta.to_dict().
    """
    version: str
    algorithm: str
    source_axes: list[str]
    values: list[float]         # len == 8, каждый ∈ [0, 1]
    hash: str                   # sha256[:16] для seed_policy


@dataclass
class TrackIdentity:
    audio_content_hash: str
    canonical_title: str | None
    canonical_artist: str | None
    duration_ms: int | None
    style_profile_slug: str
    base_seed: int
    variation_seed: int
    harmony_theta: HarmonyThetaArtifact | None = None   # E2: опционально


@dataclass
class CanvasSpec:
    width_px: int = 1024
    height_px: int = 1024
    color_space: str = "sRGB"
    background_rgba: list[int] = field(default_factory=lambda: [7, 9, 18, 255])
    mode: str = "preview"


@dataclass
class LayerSpec:
    layer_id: str
    role: str
    enabled: bool
    z_index: int
    source_kind: str                      # "fractal_core" | "procedural"
    generator_id: str | None
    generator_version: str | None
    seed: int
    computation_resolution_px: tuple[int, int]
    sim_state: dict | None                # JSON-serialisable SimState
    palette_id: str | None
    opacity: float
    blend_mode: str
    transform: dict
    mask: dict | None = None
    parameter_coverage: dict = field(default_factory=dict)
    mapping_trace: dict = field(default_factory=dict)


@dataclass
class VisualCompositionPlan:
    schema_version: str
    plan_id: str
    planner_version: str
    profile_library_version: str
    config_hash: str
    track_identity: TrackIdentity
    canvas: CanvasSpec
    visual_identity: dict
    layers: list[LayerSpec]
    composition: dict
    postprocess: dict
    parameter_coverage: dict
    validation: dict

    def to_dict(self) -> dict:
        return _clean(asdict(self))

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _clean(obj: Any) -> Any:
    """Рекурсивно убирает None-значения и конвертирует tuple→list."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, (list, tuple)):
        return [_clean(i) for i in obj]
    return obj
