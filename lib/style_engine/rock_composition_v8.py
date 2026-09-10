from __future__ import annotations

import hashlib
import json
from typing import Any


MODE_TOPOLOGY = {
    "structure": "balanced_axial",
    "material": "asymmetric_organic",
    "gesture": "directional_kinetic",
    "light": "diffuse_resonant",
}


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def resolve_rock_composition_v8(portrait: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profiles = portrait.get("profiles", {})
    pulse = profiles.get("pulse_profile", {})
    form = profiles.get("form_profile", {})
    material = profiles.get("material_profile", {})
    affect = profiles.get("affect_profile", {})
    spatial = profiles.get("spatial_profile", {})
    mode = portrait.get("identity_core", {}).get("dominant_interpretation_mode", "structure")
    mode = mode if mode in MODE_TOPOLOGY else "structure"

    tension = _clamp01(affect.get("tension", 0.5))
    drive = _clamp01(pulse.get("drive", 0.5))
    grain = _clamp01(material.get("grain", 0.5))
    clarity = _clamp01(form.get("structural_clarity", 0.5))
    resonance = _clamp01(spatial.get("resonance", 0.5))
    symmetry = _clamp01(0.72 * clarity + 0.28 * (1.0 - grain)) if mode == "structure" else _clamp01(0.36 * clarity + 0.24 * (1.0 - grain))
    junction_x = 600.0 if mode == "structure" else 430.0 + 340.0 * _clamp01(1.0 - clarity)
    junction_y = 450.0 + (0.5 - resonance) * 180.0
    params = {
        "grammar": "RockCompositionGrammarV8",
        "dominant_mode": mode,
        "topology": MODE_TOPOLOGY[mode],
        "junction": {"x": round(junction_x, 3), "y": round(junction_y, 3)},
        "symmetry": round(symmetry, 6),
        "drive": round(drive, 6),
        "tension": round(tension, 6),
        "grain": round(grain, 6),
        "resonance": round(resonance, 6),
        "line_density": round(0.35 + 0.55 * drive, 6),
        "recursion_depth": int(2 + round(3 * drive)),
        "material_dispersion": round(0.18 + 0.68 * grain, 6),
        "accent_contrast": round(0.18 + 0.72 * tension, 6),
        "palette_id": "structure_contrast" if mode == "structure" else "material_mineral",
        "perceptual": {
            "energy": _clamp01(pulse.get("drive", 0.5)),
            "tension": tension,
            "density": _clamp01(pulse.get("drive", 0.5)),
            "brightness": _clamp01(affect.get("luminosity", 0.5)),
            "stability": _clamp01(affect.get("stability", 0.5)),
            "smoothness": _clamp01(material.get("smoothness", 0.5)),
            "repetition": _clamp01(form.get("return_strength", 0.5)),
            "section_complexity": _clamp01(form.get("contrast", 0.5)),
            "noise_proxy": grain,
            "morphology_guard": _clamp01(1.0 - symmetry),
        },
            "d1_perceptual": {
                "symmetry_bias": symmetry,
                "tension": tension,
                "harmonic_stability": _clamp01(affect.get("stability", 0.5)),
                "harmonic_change_rate": _clamp01(pulse.get("drive", 0.5)),
                "texture_complexity": grain,
                "recursion_depth": _clamp01(pulse.get("drive", 0.5)),
                "section_complexity": _clamp01(form.get("contrast", 0.5)),
                "noise_level": grain,
            },
    }
    trace = [
        {"parameter": "dominant_mode", "value": mode, "source": "identity_core.dominant_interpretation_mode", "reason": f"portrait selected {mode}"},
        {"parameter": "topology", "value": params["topology"], "source": "dominant_mode", "reason": "structure keeps axial balance; material uses asymmetric organic topology"},
        {"parameter": "symmetry", "value": params["symmetry"], "source": "form_profile.structural_clarity + material_profile.grain", "reason": "clarity increases scaffold balance; grain erodes it"},
        {"parameter": "junction", "value": params["junction"], "source": "dominant_mode + form_profile.structural_clarity + spatial_profile.resonance", "reason": "mode selects centered versus displaced center of gravity"},
        {"parameter": "line_density", "value": params["line_density"], "source": "pulse_profile.drive", "reason": "drive controls nested fractal and line density"},
        {"parameter": "recursion_depth", "value": params["recursion_depth"], "source": "pulse_profile.drive", "reason": "higher drive adds deterministic recursive detail"},
        {"parameter": "material_dispersion", "value": params["material_dispersion"], "source": "material_profile.grain", "reason": "grain controls roughness and element dispersion"},
        {"parameter": "accent_contrast", "value": params["accent_contrast"], "source": "affect_profile.tension", "reason": "tension controls contrast and accent drama"},
        {"parameter": "palette_id", "value": params["palette_id"], "source": "dominant_mode", "reason": "palette family follows structural versus material world"},
    ]
    return params, trace


def portrait_hash(portrait: dict[str, Any]) -> str:
    return _hash(portrait)
