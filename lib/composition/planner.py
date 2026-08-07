"""VisualCompositionPlanner v0.3 — главная точка сборки плана.

Входы:
  PerceptualLatent  — перцептивные оси из StyleEngine
  RenderParams      — нормированные параметры из style resolver
  TrackMetadata     — идентичность трека

Выход:
  VisualCompositionPlan v0.3 (dataclass) + артефакты на диске

NB: этот модуль ЗАПРЕЩЕНО импортировать PIL, matplotlib, fractal generators.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonicalize import build_alias_index, canonicalize_generator_id
from .config_loader import CompositionConfig, CompositionConfigError, load_composition_config
from .coverage import build_parameter_coverage, validate_coverage
from .schema import CanvasSpec, LayerSpec, TrackIdentity, VisualCompositionPlan
from .seed_policy import compute_base_seed, compute_layer_seed
from .storage import plan_id_from_plan, save_plan_artifacts
from .validation import assert_plan_valid

from .mappings.julia import build_julia_state
from .mappings.ifs import build_ifs_state
from .mappings.duffing import build_duffing_state
from .mappings.scattering import build_scattering_state
from .mappings.procedural import (
    build_orbital_field_spec,
    build_colored_noise_spec,
    build_symmetry_snowflake_spec,
)

PLANNER_VERSION = "0.3.0"

# Dispatch table: canonical_generator_id → builder function
_BUILDERS: dict[str, Any] = {
    "julia_orbit_trap": build_julia_state,
    "orbit_ifs_multi_trap": build_ifs_state,
    "duffing_lyapunov": build_duffing_state,
    "chaotic_scattering_basins": build_scattering_state,
    "orbital_field": build_orbital_field_spec,
    "colored_noise_field": build_colored_noise_spec,
    "symmetry_snowflake": build_symmetry_snowflake_spec,
}


@dataclass
class PerceptualLatent:
    energy: float = 0.5
    tension: float = 0.5
    repetition: float = 0.5
    tempo: float = 0.5                   # нормированный [0,1]
    section_complexity: float = 0.5
    silence_rate: float = 0.2
    harmonic_stability: float = 0.5
    harmonic_change_rate: float = 0.5
    spectral_flatness: float = 0.5
    high_frequency_energy: float = 0.5


@dataclass
class RenderParams:
    style_profile_slug: str
    symmetry_bias: float = 0.5
    density_level: float = 0.5
    noise_level: float = 0.1
    recursion_depth: float = 0.5
    motion_intensity: float = 0.5
    texture_complexity: float = 0.5
    layout_macro_shape: str = "center"
    palette_id: str = "neutral_noir"
    visual_style_slug: str = "fullcolor"
    variation_seed: int = 0


@dataclass
class TrackMetadata:
    audio_content_hash: str
    title: str | None = None
    artist: str | None = None
    duration_ms: int | None = None


# ─── public API ────────────────────────────────────────────────────────────

def build_visual_composition_plan(
    *,
    perceptual: PerceptualLatent,
    render_params: RenderParams,
    track_metadata: TrackMetadata,
    variation_seed: int = 0,
    config: CompositionConfig | None = None,
    configs_dir: Path | None = None,
    storage_root: Path | None = None,
    save_artifacts: bool = True,
) -> VisualCompositionPlan:
    """Детерминированно строит VisualCompositionPlan v0.3.

    Не вызывает фрактальные генераторы, не создаёт PNG.
    """
    cfg = config or load_composition_config(configs_dir)
    alias_index = build_alias_index(cfg.catalog)

    slug = render_params.style_profile_slug
    profile_map = cfg.profiles.get("profiles", {})
    if slug not in profile_map:
        raise CompositionConfigError(
            f"Unknown style_profile_slug: '{slug}'. "
            f"Available: {sorted(profile_map.keys())}"
        )
    profile = profile_map[slug]

    # ── Seeds ──────────────────────────────────────────────────────────────
    base_seed = compute_base_seed(
        audio_content_hash=track_metadata.audio_content_hash,
        title=track_metadata.title,
        artist=track_metadata.artist,
        duration_ms=track_metadata.duration_ms,
        style_profile_slug=slug,
        profile_library_version=cfg.profile_library_version,
        variation_seed=variation_seed,
    )

    # ── Track identity ─────────────────────────────────────────────────────
    identity = TrackIdentity(
        audio_content_hash=track_metadata.audio_content_hash,
        canonical_title=track_metadata.title,
        canonical_artist=track_metadata.artist,
        duration_ms=track_metadata.duration_ms,
        style_profile_slug=slug,
        base_seed=base_seed,
        variation_seed=variation_seed,
    )

    # ── Visual identity ────────────────────────────────────────────────────
    profile_identity = profile.get("identity", {})
    palette_id = (
        render_params.palette_id
        or profile_identity.get("palette_id")
        or "neutral_noir"
    )
    visual_identity = {
        "palette_id": palette_id,
        "macro_archetype": profile_identity.get("macro_archetype", "quiet_field"),
        "postprocess_style_slug": render_params.visual_style_slug
        or profile_identity.get("postprocess_style_slug", "fullcolor"),
    }

    # ── Layers ─────────────────────────────────────────────────────────────
    layer_specs: list[LayerSpec] = []
    layer_yaml_list = profile.get("layers", [])

    for layer_cfg in layer_yaml_list:
        layer_id = layer_cfg["id"]
        role = layer_cfg["role"]
        source_kind = layer_cfg.get("source_kind", "fractal_core")

        # enabled_if evaluation
        enabled = _eval_enabled(layer_cfg, perceptual, render_params)
        if not enabled:
            # включаем disabled слой в план (enabled=False), не вызываем builder
            layer_specs.append(
                LayerSpec(
                    layer_id=layer_id,
                    role=role,
                    enabled=False,
                    z_index=layer_cfg.get("z_index", 99),
                    source_kind=source_kind,
                    generator_id=layer_cfg.get("generator_id"),
                    generator_version=None,
                    seed=0,
                    computation_resolution_px=(0, 0),
                    sim_state=None,
                    palette_id=layer_cfg.get("palette_id"),
                    opacity=layer_cfg.get("opacity", 0.0),
                    blend_mode=layer_cfg.get("blend_mode", "normal"),
                    transform={},
                )
            )
            continue

        # Canonicalize generator ID
        raw_gen_id = layer_cfg.get("generator_id")
        if source_kind == "procedural_mask":
            canonical_gen_id = None
        elif raw_gen_id:
            canonical_gen_id = canonicalize_generator_id(
                raw_gen_id, cfg.catalog, alias_index
            )
        else:
            raise CompositionConfigError(
                f"Layer '{layer_id}': missing generator_id"
            )

        # Layer seed
        layer_seed = compute_layer_seed(
            base_seed=base_seed,
            layer_id=layer_id,
            canonical_generator_id=canonical_gen_id or "procedural_mask",
        )

        # Computation resolution
        frac = layer_cfg.get("computation_resolution_fraction", 1.0)
        res_px = max(128, min(1024, round(1024 * frac)))
        resolution_px = (res_px, res_px)

        # Layer-level palette
        layer_palette = layer_cfg.get("palette_id") or palette_id

        # Rotation from motion_intensity and profile range
        rot_range = layer_cfg.get(
            "rotation_range_deg",
            {"range": [-30.0, 30.0]}
        )
        if isinstance(rot_range, dict):
            r_min, r_max = rot_range.get("min", -30.0), rot_range.get("max", 30.0)
        elif isinstance(rot_range, list) and len(rot_range) == 2:
            r_min, r_max = rot_range
        else:
            r_min, r_max = -30.0, 30.0
        rotation_deg = r_min + render_params.motion_intensity * (r_max - r_min)

        # Build state using dispatch table
        built: dict | None = None
        if source_kind == "procedural_mask":
            built = _build_procedural_mask(layer_cfg, perceptual, render_params)
        elif canonical_gen_id and canonical_gen_id in _BUILDERS:
            builder_fn = _BUILDERS[canonical_gen_id]
            built = _call_builder(
                builder_fn=builder_fn,
                layer_id=layer_id,
                seed=layer_seed,
                resolution_px=resolution_px,
                perceptual=perceptual,
                render_params=render_params,
                rotation_deg=rotation_deg,
            )
        else:
            raise CompositionConfigError(
                f"No builder for canonical_id='{canonical_gen_id}'"
            )

        layer_specs.append(
            LayerSpec(
                layer_id=layer_id,
                role=role,
                enabled=True,
                z_index=layer_cfg.get("z_index", 99),
                source_kind=source_kind,
                generator_id=canonical_gen_id,
                generator_version=built["sim_state"].get("generator_version")
                if built["sim_state"] else None,
                seed=layer_seed,
                computation_resolution_px=resolution_px,
                sim_state=built["sim_state"],
                palette_id=layer_palette,
                opacity=layer_cfg.get("opacity", 1.0),
                blend_mode=layer_cfg.get("blend_mode", "normal"),
                transform=built["transform"],
                mapping_trace=built.get("mapping_trace", {}),
            )
        )

    # ── Composition meta ───────────────────────────────────────────────────
    comp_cfg = profile.get("composition", {})
    negative_space = comp_cfg.get("negative_space", {})

    composition = {
        "coordinate_system": "normalized_canvas",
        "negative_space": {
            "coverage_range": negative_space.get("coverage_range", [0.08, 0.58]),
            "coverage_source": negative_space.get("coverage_source", "silence_rate"),
        },
    }

    postprocess = {
        "style_slug": visual_identity["postprocess_style_slug"],
    }

    # ── Assemble plan ──────────────────────────────────────────────────────
    plan = VisualCompositionPlan(
        schema_version="visual-composition-plan/v0.3",
        plan_id="",  # will be set deterministically below
        planner_version=PLANNER_VERSION,
        profile_library_version=cfg.profile_library_version,
        config_hash=cfg.config_hash,
        track_identity=identity,
        canvas=CanvasSpec(),
        visual_identity=visual_identity,
        layers=layer_specs,
        composition=composition,
        postprocess=postprocess,
        parameter_coverage={},
        validation={},
    )

    # Deterministic plan_id
    plan.plan_id = plan_id_from_plan(plan)

    # ── Validate ───────────────────────────────────────────────────────────
    assert_plan_valid(plan, cfg.catalog)

    # ── Coverage ───────────────────────────────────────────────────────────
    coverage = build_parameter_coverage(plan)
    uncovered = validate_coverage(coverage)
    if uncovered:
        # Записываем как предупреждение — не блокируем план,
        # но сигнализируем о неполноте coverage
        coverage["warnings"] = [
            f"Axis '{ax}' has no coverage entry" for ax in uncovered
        ]
    plan.parameter_coverage = coverage

    # ── Save ───────────────────────────────────────────────────────────────
    diagnostics = {
        "planner_version": PLANNER_VERSION,
        "config_hash": cfg.config_hash,
        "loaded_files": [
            "generator_catalog.yaml",
            "palettes.yaml",
            "visual_composition_profiles.yaml",
        ],
        "profile_slug": slug,
        "enabled_layers": [
            l.layer_id for l in plan.layers if l.enabled
        ],
        "warnings": coverage.get("warnings", []),
        "provisional_defaults": [],
    }

    if save_artifacts:
        save_plan_artifacts(
            plan=plan,
            coverage=coverage,
            diagnostics=diagnostics,
            storage_root=storage_root,
        )

    return plan


# ─── private helpers ────────────────────────────────────────────────────────

def _eval_enabled(
    layer_cfg: dict,
    perceptual: PerceptualLatent,
    render_params: RenderParams,
) -> bool:
    """Вычисляет enabled / enabled_if по ограниченному DSL."""
    if "enabled" in layer_cfg and not layer_cfg.get("enabled", True):
        return False
    if "enabled_if" not in layer_cfg:
        return True

    conditions = layer_cfg["enabled_if"]
    # Поддерживаем: all: [...] | any: [...] | одиночный dict
    if "all" in conditions:
        return all(_eval_condition(c, perceptual, render_params) for c in conditions["all"])
    if "any" in conditions:
        return any(_eval_condition(c, perceptual, render_params) for c in conditions["any"])
    if isinstance(conditions, dict) and "source" in conditions:
        return _eval_condition(conditions, perceptual, render_params)
    return True  # неизвестный формат → включаем


_OPERATORS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
}


def _eval_condition(
    cond: dict,
    perceptual: PerceptualLatent,
    render_params: RenderParams,
) -> bool:
    source = cond["source"]
    op = cond["operator"]
    value = float(cond["value"])
    actual = _get_axis(source, perceptual, render_params)
    fn = _OPERATORS.get(op)
    if fn is None:
        raise CompositionConfigError(f"Unknown enabled_if operator: '{op}'")
    return fn(actual, value)


def _get_axis(
    name: str,
    perceptual: PerceptualLatent,
    render_params: RenderParams,
) -> float:
    """Ищет ось сначала в PerceptualLatent, потом в RenderParams."""
    if hasattr(perceptual, name):
        return float(getattr(perceptual, name))
    if hasattr(render_params, name):
        return float(getattr(render_params, name))
    raise CompositionConfigError(
        f"enabled_if: unknown source axis '{name}'"
    )


def _build_procedural_mask(
    layer_cfg: dict,
    perceptual: PerceptualLatent,
    render_params: RenderParams,
) -> dict:
    mapping = layer_cfg.get("mapping", {})
    coverage_val = _get_axis(
        mapping.get("coverage", "silence_rate"), perceptual, render_params
    )
    edge_softness = perceptual.tension
    return {
        "sim_state": {
            "generator_name": "procedural_mask",
            "coverage": round(float(coverage_val), 4),
            "direction": render_params.layout_macro_shape,
            "edge_softness": round(edge_softness, 4),
        },
        "transform": {"offset_norm": [0.0, 0.0], "scale_xy": [1.0, 1.0], "rotation_deg": 0.0},
        "mapping_trace": {
            "coverage": mapping.get("coverage", "silence_rate"),
            "direction": "layout_macro_shape",
            "edge_softness": "tension",
        },
    }


def _call_builder(
    builder_fn,
    layer_id: str,
    seed: int,
    resolution_px: tuple[int, int],
    perceptual: PerceptualLatent,
    render_params: RenderParams,
    rotation_deg: float,
) -> dict:
    """Вызывает builder с набором общих kwargs, игнорируя лишние через **kw."""
    import inspect
    sig = inspect.signature(builder_fn)
    params = set(sig.parameters.keys())

    kwargs: dict = {
        "layer_id": layer_id,
        "seed": seed,
        "resolution_px": resolution_px,
        "rotation_deg": rotation_deg,
    }

    # Перцептивные оси
    for ax in [
        "energy", "tension", "repetition", "tempo",
        "section_complexity", "silence_rate",
        "harmonic_stability", "harmonic_change_rate",
        "spectral_flatness", "high_frequency_energy",
    ]:
        if ax in params:
            kwargs[ax] = getattr(perceptual, ax)

    # RenderParams оси
    for ax in [
        "symmetry_bias", "density_level", "noise_level",
        "recursion_depth", "motion_intensity", "texture_complexity",
    ]:
        if ax in params:
            kwargs[ax] = getattr(render_params, ax)

    return builder_fn(**kwargs)
