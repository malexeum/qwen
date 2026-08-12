from __future__ import annotations

from collections.abc import Mapping

from lib.style_engine.engine import _compute_variation_seed


def compute_render_variation_seed(
    *,
    project_id: str,
    analysis_id: str,
    preset_id: str,
    style_slug: str,
    interpretation_slug: str,
    theta_values: Mapping[str, float],
) -> int:
    """Public adapter for the production StyleEngine render-seed contract.

    The implementation remains owned by ``engine._compute_variation_seed``.
    This adapter deliberately has no independent hash or seed formula.
    """
    return _compute_variation_seed(
        project_id,
        analysis_id,
        preset_id,
        style_slug,
        interpretation_slug,
        dict(theta_values),
    )


__all__ = ["compute_render_variation_seed"]
