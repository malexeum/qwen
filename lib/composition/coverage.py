"""Parameter coverage report для VisualCompositionPlan v0.3.

Доказывает, что каждый активный RenderParams axis использован
хотя бы в одном слое. Мёртвых параметров без отчёта быть не должно.
"""
from __future__ import annotations

from .schema import VisualCompositionPlan

# Обязательные оси RenderParams, которые planner обязан покрыть
REQUIRED_AXES = [
    "symmetry_bias",
    "density_level",
    "noise_level",
    "recursion_depth",
    "motion_intensity",
    "texture_complexity",
    "layout_macro_shape",
]


def build_parameter_coverage(
    plan: VisualCompositionPlan,
    not_applicable: list[dict] | None = None,
    provisional_defaults: list[str] | None = None,
) -> dict:
    """Собирает coverage report из mapping_trace всех слоёв.

    Возвращает структуру соответствующую TZ parameter_coverage/v0.3.
    """
    used: dict[str, list[str]] = {}

    for layer in plan.layers:
        if not layer.enabled:
            continue
        for param_target, source_axis in layer.mapping_trace.items():
            if source_axis not in used:
                used[source_axis] = []
            path = f"{layer.layer_id}.{param_target}"
            if path not in used[source_axis]:
                used[source_axis].append(path)

    na_list = not_applicable or []
    na_axes = {item["parameter"] for item in na_list}
    provisional = provisional_defaults or []

    return {
        "schema_version": "parameter-coverage/v0.3",
        "active_profile": plan.track_identity.style_profile_slug,
        "used": used,
        "not_applicable": na_list,
        "provisional_defaults": provisional,
    }


def validate_coverage(
    coverage: dict,
    required_axes: list[str] | None = None,
) -> list[str]:
    """Возвращает список непокрытых обязательных осей."""
    axes = required_axes or REQUIRED_AXES
    used_axes = set(coverage.get("used", {}).keys())
    na_axes = {item["parameter"] for item in coverage.get("not_applicable", [])}
    covered = used_axes | na_axes
    return [ax for ax in axes if ax not in covered]
