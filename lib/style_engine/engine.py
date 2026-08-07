from typing import Dict, Any, Tuple
from dataclasses import dataclass

from lib.style_engine.config_loader import (
    StyleProfile,
    InterpretationProfile,
    load_style_profiles,
    load_interpretation_profiles,
)
from lib.style_engine.engine_evaluator import _safe_eval_expr, _safe_eval_bool


@dataclass
class RenderParams:
    style_profile_slug: str
    interpretation_profile_slug: str
    preset_id: str

    symmetry_bias: float
    recursion_depth: float
    density_level: float
    noise_level: float
    motion_intensity: float

    palette_id: str
    stochastic_term: float
    layout_macro_shape: str
    texture_complexity: float

    variation_seed: int


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _compute_variation_seed(
    project_id: str,
    analysis_id: str,
    preset_id: str,
    style_slug: str,
    interp_slug: str,
) -> int:
    base = hash((project_id, analysis_id, preset_id, style_slug, interp_slug))
    return base & 0xFFFFFFFF


def _normalize_style_slug(style_profile_slug: str, style_registry: Dict[str, StyleProfile]) -> str:
    slug = (style_profile_slug or "default").strip()
    if slug in style_registry:
        return slug

    aliases = {
        "jazz": "blues_jazz",
        "blues": "blues_jazz",
        "classical": "soundtrack",
        "cinematic": "soundtrack",
        "techno": "electronic",
        "electro": "electronic",
        "electronic_music": "electronic",
        "space": "ambient",
        "pop": "rock",
        "mixed": "default",
    }

    mapped = aliases.get(slug.lower())
    if mapped and mapped in style_registry:
        return mapped

    return slug


def _derive_palette_id(base_palette: str, brightness: float) -> str:
    """
    Legacy-логика выбора палитры: suffix _bright/_dark относительно базового palette.
    Совместима с текущим StyleProfile, где palette — строка вида 'sepia_dark', 'neon_dark'.
    """
    base_palette = (base_palette or "default_dark").strip()
    if brightness > 0.60:
        return f"{base_palette}_bright"
    if brightness < 0.30:
        return f"{base_palette}_dark"
    return base_palette


def _compute_morphology_guard(perceptual: Dict[str, float]) -> float:
    """
    Derived axis: morphology_guard.

    Концептуально отражает риск потери музыкальной идентичности при слишком
    гладкой морфологии для структурно сложных треков.
    """
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    tension = _safe_float(perceptual.get("tension", 0.0))
    repetition = _safe_float(perceptual.get("repetition", 0.0))
    stability = _safe_float(perceptual.get("stability", 0.0))

    # Простая линейная формула; веса можно позже вынести в конфиг.
    w1, w2, w3, w4 = 0.5, 0.4, 0.3, 0.3
    value = (
        w1 * section_complexity
        + w2 * tension
        - w3 * repetition
        - w4 * stability
    )
    return _clamp01(value)


def resolve_render_params(
    project_id: str,
    analysis_id: str,
    perceptual: Dict[str, float],
    style_profile_slug: str,
    interpretation_profile_slug: str,
    user_preset: Dict[str, float],
) -> Tuple[RenderParams, StyleProfile, InterpretationProfile]:
    """
    Главный визуальный resolver в declarative-режиме.

    - perceptual: dict с осями (energy, tension, density, brightness, stability,
      smoothness, repetition, section_complexity, macro_shape_hint).
    - user_preset: dict со слайдерами (complexity, symmetry, density, noise, motion).

    Логика:
    1) Base layer из StyleProfile (плоские поля).
    2) Perceptual layer из InterpretationProfile.mapping_rules.
    3) User layer из UserPreset.
    4) Guardrails из InterpretationProfile.guardrails.
    """

    style_registry = load_style_profiles()
    interp_registry = load_interpretation_profiles()

    normalized_style_slug = _normalize_style_slug(style_profile_slug, style_registry)
    if normalized_style_slug not in style_registry:
        raise ValueError(f"unknown_style_profile: {style_profile_slug}")
    if interpretation_profile_slug not in interp_registry:
        raise ValueError(f"unknown_interpretation_profile: {interpretation_profile_slug}")

    style_profile = style_registry[normalized_style_slug]
    interp_profile = interp_registry[interpretation_profile_slug]

    # --- 1. Base layer (StyleProfile: текущие поля) ---
    base_symmetry = _clamp01(_safe_float(getattr(style_profile, "symmetry_bias", 0.5), 0.5))
    base_recursion = _clamp01(_safe_float(getattr(style_profile, "complexity_bias", 0.5), 0.5))
    base_density = _clamp01(_safe_float(getattr(style_profile, "density", 0.5), 0.5))
    base_noise = _clamp01(_safe_float(getattr(style_profile, "noise_level", 0.5), 0.5))
    base_motion = _clamp01(_safe_float(getattr(style_profile, "motion_intensity", 0.5), 0.5))
    # Если отдельного texture_complexity нет — используем complexity_bias.
    base_texture = base_recursion

    base_stochastic = 0.25  # можно позже вынести в конфиг
    base_palette = (getattr(style_profile, "palette", "default_dark") or "default_dark").strip()

    # --- Perceptual axes ---
    energy = _safe_float(perceptual.get("energy", 0.0))
    tension = _safe_float(perceptual.get("tension", 0.0))
    density_axis = _safe_float(perceptual.get("density", 0.0))
    brightness = _safe_float(perceptual.get("brightness", 0.0))
    stability = _safe_float(perceptual.get("stability", 0.0))
    smoothness = _safe_float(perceptual.get("smoothness", 0.0))
    repetition = _safe_float(perceptual.get("repetition", 0.0))
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    macro_shape_hint = perceptual.get("macro_shape_hint", "unknown") or "unknown"

    morphology_guard = _compute_morphology_guard(perceptual)

    axes = {
        "energy": energy,
        "tension": tension,
        "density": density_axis,
        "brightness": brightness,
        "stability": stability,
        "smoothness": smoothness,
        "repetition": repetition,
        "section_complexity": section_complexity,
        "macro_shape_hint": macro_shape_hint,
        "morphology_guard": morphology_guard,
    }

    # --- 2. Perceptual layer via mapping_rules ---
    mr = interp_profile.mapping_rules or {}

    def _eval_param(name: str, base_default: float) -> float:
        rule_raw = mr.get(name, {})
        rule = rule_raw if isinstance(rule_raw, dict) else {}
        base = float(rule.get("base", base_default))
        expr = str(rule.get("formula", "")) if "formula" in rule else ""
        value = _safe_eval_expr(expr, {"base": base, **axes})
        return _clamp01(value)

    symmetry_bias = _eval_param("symmetry_bias", base_symmetry)
    recursion_depth = _eval_param("recursion_depth", base_recursion)
    density_level = _eval_param("density_level", base_density)
    noise_level = _eval_param("noise_level", base_noise)
    motion_intensity = _eval_param("motion_intensity", base_motion)
    texture_complexity = _eval_param("texture_complexity", base_texture)

    # layout_macro_shape via rules
    layout_cfg = mr.get("layout_macro_shape", {})
    layout_rules = layout_cfg.get("rules", []) if isinstance(layout_cfg, dict) else []
    layout_macro_shape = "unknown"
    for rule in layout_rules:
        when_expr = str(rule.get("when", ""))
        value = str(rule.get("value", ""))
        if when_expr and value and _safe_eval_bool(when_expr, axes):
            layout_macro_shape = value
            break
    if layout_macro_shape == "unknown":
        layout_macro_shape = "ABA_like"

    # --- Palette ---
    palette_id = _derive_palette_id(base_palette, brightness)
    stochastic_term = _clamp01(base_stochastic)

    # --- 3. User layer (UserPreset biases) ---
    preset_complexity = _safe_float(user_preset.get("complexity", 0.5), 0.5)
    preset_symmetry = _safe_float(user_preset.get("symmetry", 0.5), 0.5)
    preset_density = _safe_float(user_preset.get("density", 0.5), 0.5)
    preset_noise = _safe_float(user_preset.get("noise", 0.5), 0.5)
    preset_motion = _safe_float(user_preset.get("motion", 0.5), 0.5)

    # Диапазон влияния оставляем как ±0.25; позже можно вынести в конфиг.
    symmetry_bias = _clamp01(symmetry_bias + (preset_symmetry - 0.5) * 0.5)
    recursion_depth = _clamp01(recursion_depth + (preset_complexity - 0.5) * 0.5)
    density_level = _clamp01(density_level + (preset_density - 0.5) * 0.5)
    noise_level = _clamp01(noise_level + (preset_noise - 0.5) * 0.5)
    motion_intensity = _clamp01(motion_intensity + (preset_motion - 0.5) * 0.5)

    # --- 4. Guardrails ---
    guard_vars = axes.copy()
    guard_vars.update(
        {
            "symmetry_bias": symmetry_bias,
            "recursion_depth": recursion_depth,
            "density_level": density_level,
            "noise_level": noise_level,
            "motion_intensity": motion_intensity,
            "texture_complexity": texture_complexity,
        }
    )

    for gr in getattr(interp_profile, "guardrails", []):
        if not gr.when:
            continue
        if not _safe_eval_bool(gr.when, guard_vars):
            continue
        for param_name, action in gr.actions.items():
            if param_name == "symmetry_bias":
                val = symmetry_bias
            elif param_name == "recursion_depth":
                val = recursion_depth
            elif param_name == "density_level":
                val = density_level
            elif param_name == "noise_level":
                val = noise_level
            elif param_name == "motion_intensity":
                val = motion_intensity
            elif param_name == "texture_complexity":
                val = texture_complexity
            else:
                continue

            if action.min is not None:
                val = max(val, action.min)
            if action.max is not None:
                val = min(val, action.max)

            val = _clamp01(val)

            if param_name == "symmetry_bias":
                symmetry_bias = val
            elif param_name == "recursion_depth":
                recursion_depth = val
            elif param_name == "density_level":
                density_level = val
            elif param_name == "noise_level":
                noise_level = val
            elif param_name == "motion_intensity":
                motion_intensity = val
            elif param_name == "texture_complexity":
                texture_complexity = val

    # variation_seed
    preset_id = str(user_preset.get("id", "preset"))
    variation_seed = _compute_variation_seed(
        project_id,
        analysis_id,
        preset_id,
        normalized_style_slug,
        interpretation_profile_slug,
    )

    render_params = RenderParams(
        style_profile_slug=style_profile.slug,
        interpretation_profile_slug=interp_profile.slug,
        preset_id=preset_id,
        symmetry_bias=symmetry_bias,
        recursion_depth=recursion_depth,
        density_level=density_level,
        noise_level=noise_level,
        motion_intensity=motion_intensity,
        palette_id=palette_id,
        stochastic_term=stochastic_term,
        layout_macro_shape=layout_macro_shape,
        texture_complexity=texture_complexity,
        variation_seed=variation_seed,
    )

    return render_params, style_profile, interp_profile