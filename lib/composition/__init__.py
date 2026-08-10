"""lib.composition — VisualCompositionPlanner v0.3.

Public API:
    build_visual_composition_plan()
    PerceptualLatent
    RenderParams
    TrackMetadata
    VisualCompositionPlan
    load_composition_config
    HarmonyEncoder          (E2)
    HarmonyTheta            (E2)
    HarmonyThetaArtifact    (E2)
    HARMONY_AXES            (E2)
    HARMONY_THETA_AXES      (E2)
"""
from .planner import (
    build_visual_composition_plan,
    PerceptualLatent,
    RenderParams,
    TrackMetadata,
)
from .schema import VisualCompositionPlan, HarmonyThetaArtifact
from .config_loader import (
    load_composition_config,
    CompositionConfigError,
    VALID_HARMONY_THETA_AXES,
)
from .harmony_encoder import (
    HarmonyEncoder,
    HarmonyTheta,
    HARMONY_AXES,
    HARMONY_THETA_AXES,
)

__all__ = [
    # planner
    "build_visual_composition_plan",
    "PerceptualLatent",
    "RenderParams",
    "TrackMetadata",
    # schema
    "VisualCompositionPlan",
    "HarmonyThetaArtifact",
    # config
    "load_composition_config",
    "CompositionConfigError",
    "VALID_HARMONY_THETA_AXES",
    # E2
    "HarmonyEncoder",
    "HarmonyTheta",
    "HARMONY_AXES",
    "HARMONY_THETA_AXES",
]
