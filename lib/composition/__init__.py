"""lib.composition — VisualCompositionPlanner v0.3.

Public API:
    build_visual_composition_plan()
    PerceptualLatent
    RenderParams
    TrackMetadata
    VisualCompositionPlan
    load_composition_config
"""
from .planner import (
    build_visual_composition_plan,
    PerceptualLatent,
    RenderParams,
    TrackMetadata,
)
from .schema import VisualCompositionPlan
from .config_loader import load_composition_config, CompositionConfigError

__all__ = [
    "build_visual_composition_plan",
    "PerceptualLatent",
    "RenderParams",
    "TrackMetadata",
    "VisualCompositionPlan",
    "load_composition_config",
    "CompositionConfigError",
]
