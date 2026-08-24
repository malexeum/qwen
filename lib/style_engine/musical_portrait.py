from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class MusicalPortrait:
    pulse_regularity: float = 0.5
    pulse_urgency: float = 0.5
    pulse_impact: float = 0.5
    gesture_continuity: float = 0.5
    gesture_angularity: float = 0.5
    gesture_propulsion: float = 0.5
    form_complexity: float = 0.5
    form_recurrence: float = 0.5
    form_contrast: float = 0.5
    form_climax_position: float = 0.5
    material_roughness: float = 0.5
    material_brightness: float = 0.5
    material_density: float = 0.5
    material_sustain: float = 0.5
    affect_tension: float = 0.5
    affect_stability: float = 0.5
    affect_openness: float = 0.5

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if isinstance(value, bool):
                raise ValueError(f"{name} must be numeric and bounded 0..1")
            value = float(value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0.0, 1.0]")

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def resolve_mode(portrait: MusicalPortrait) -> str:
    score = {
        "recursive_grove": (
            portrait.form_complexity * 0.30
            + portrait.form_recurrence * 0.30
            + portrait.gesture_continuity * 0.20
            + portrait.affect_stability * 0.20
        ),
        "fragmented_signal": (
            portrait.affect_tension * 0.35
            + portrait.material_roughness * 0.30
            + portrait.gesture_angularity * 0.20
            + portrait.form_contrast * 0.15
        ),
        "kinetic_break": (
            portrait.gesture_angularity * 0.30
            + portrait.affect_tension * 0.25
            + portrait.form_complexity * 0.25
            + portrait.material_brightness * 0.20
        ),
        "monolithic": (
            portrait.form_recurrence * 0.30
            + portrait.affect_stability * 0.30
            + portrait.pulse_regularity * 0.20
            + portrait.material_sustain * 0.20
        ),
        "open_horizon": (
            portrait.affect_openness * 0.35
            + portrait.gesture_continuity * 0.30
            + portrait.form_contrast * 0.20
            + portrait.material_brightness * 0.15
        ),
    }
    return max(score.items(), key=lambda item: item[1])[0]


def resolve_macro_params(portrait: MusicalPortrait, mode: str) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "junction": _clamp01(portrait.form_climax_position * 0.8 + portrait.affect_tension * 0.2),
        "flow_angle": _clamp01(portrait.gesture_propulsion * 0.7 + portrait.gesture_angularity * 0.3),
        "competing_centers": int(round(1 + portrait.form_complexity * 4)),
        "branch_count": int(round(4 + portrait.form_complexity * 8)),
        "recursion_levels": int(round(2 + portrait.form_recurrence * 4)),
        "global_symmetry": _clamp01(0.5 + (portrait.affect_stability - 0.5) * 0.7),
        "line_continuity": _clamp01(0.5 + (portrait.gesture_continuity - 0.5) * 0.8),
        "density": _clamp01(0.4 + portrait.material_density * 0.6),
        "materiality": _clamp01(0.35 + portrait.material_roughness * 0.65),
        "palette_usage_ratio": _clamp01(0.25 + portrait.material_brightness * 0.5),
    }
    if mode == "recursive_grove":
        mapping["junction"] = _clamp01(0.25 + portrait.form_recurrence * 0.45)
        mapping["branch_count"] = int(round(7 + portrait.form_complexity * 8))
        mapping["recursion_levels"] = int(round(3 + portrait.form_complexity * 5))
        mapping["global_symmetry"] = _clamp01(0.55 + portrait.affect_stability * 0.35)
    elif mode == "fragmented_signal":
        mapping["flow_angle"] = _clamp01(0.45 + portrait.gesture_angularity * 0.55)
        mapping["global_symmetry"] = _clamp01(0.2 + (1.0 - portrait.affect_stability) * 0.6)
        mapping["line_continuity"] = _clamp01(0.2 + (1.0 - portrait.gesture_continuity) * 0.6)
    elif mode == "kinetic_break":
        mapping["junction"] = _clamp01(0.45 + portrait.affect_tension * 0.4)
        mapping["branch_count"] = int(round(6 + portrait.gesture_angularity * 7))
        mapping["density"] = _clamp01(0.5 + portrait.material_density * 0.5)
    elif mode == "open_horizon":
        mapping["junction"] = _clamp01(0.2 + portrait.affect_openness * 0.5)
        mapping["flow_angle"] = _clamp01(0.1 + portrait.affect_openness * 0.4)
        mapping["line_continuity"] = _clamp01(0.5 + portrait.gesture_continuity * 0.4)
    elif mode == "monolithic":
        mapping["global_symmetry"] = _clamp01(0.55 + portrait.affect_stability * 0.35)
        mapping["recursion_levels"] = int(round(2 + portrait.form_recurrence * 3))
    return mapping
