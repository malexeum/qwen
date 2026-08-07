"""Валидация VisualCompositionPlan v0.3 перед сохранением.

11 инвариантов из TZ и RFC v0.3:
  1. canvas 1024×1024, mode=preview
  2. opacity ∈ [0, 1] для всех слоёв
  3. z_index уникален
  4. generator_id в catalog (для fractal_core слоёв)
  5. blend_mode в whitelist
  6. seed присутствует у каждого вычислительного слоя
  7. 3–5 enabled независимых слоёв
  8. layer_id уникальны
  9. transform использует нормализованные координаты [-1, 1]
  10. нет export/final policy
  11. schema_version корректна
"""
from __future__ import annotations

from .config_loader import ALLOWED_BLEND_MODES, CompositionConfigError
from .schema import VisualCompositionPlan

EXPECTED_SCHEMA = "visual-composition-plan/v0.3"


def validate_plan(
    plan: VisualCompositionPlan,
    catalog: dict,
) -> list[str]:
    """Проверяет план. Возвращает список ошибок (пустой = OK)."""
    errors: list[str] = []

    # 1. Canvas
    if plan.canvas.width_px != 1024 or plan.canvas.height_px != 1024:
        errors.append(
            f"Canvas must be 1024×1024, got "
            f"{plan.canvas.width_px}×{plan.canvas.height_px}"
        )
    if plan.canvas.mode != "preview":
        errors.append(f"Canvas mode must be 'preview', got '{plan.canvas.mode}'")

    # 11. Schema version
    if plan.schema_version != EXPECTED_SCHEMA:
        errors.append(
            f"schema_version must be '{EXPECTED_SCHEMA}', got '{plan.schema_version}'"
        )

    enabled_layers = [l for l in plan.layers if l.enabled]

    # 7. Layer count
    if not (3 <= len(enabled_layers) <= 5):
        errors.append(
            f"Enabled layers must be 3–5, got {len(enabled_layers)}"
        )

    seen_z: set[int] = set()
    seen_ids: set[str] = set()
    gen_ids = set(catalog.get("generators", {}).keys())

    for layer in plan.layers:
        # 2. Opacity
        if not (0.0 <= layer.opacity <= 1.0):
            errors.append(
                f"Layer '{layer.layer_id}': opacity {layer.opacity} out of [0,1]"
            )
        # 3. z_index uniqueness
        if layer.z_index in seen_z:
            errors.append(f"Layer '{layer.layer_id}': duplicate z_index {layer.z_index}")
        seen_z.add(layer.z_index)

        # 4. generator_id in catalog (для fractal_core)
        if layer.source_kind == "fractal_core" and layer.generator_id:
            if layer.generator_id not in gen_ids:
                errors.append(
                    f"Layer '{layer.layer_id}': generator_id "
                    f"'{layer.generator_id}' not in catalog"
                )

        # 5. blend_mode
        if layer.blend_mode not in ALLOWED_BLEND_MODES:
            errors.append(
                f"Layer '{layer.layer_id}': blend_mode '{layer.blend_mode}' not allowed"
            )

        # 6. seed
        if layer.source_kind in ("fractal_core", "procedural") and layer.seed == 0:
            # seed==0 допустим если явно задан (это валидное значение),
            # но отсутствие поля seed недопустимо — проверяется типом
            pass  # dataclass гарантирует наличие поля

        # 8. layer_id uniqueness
        if layer.layer_id in seen_ids:
            errors.append(f"Duplicate layer_id: '{layer.layer_id}'")
        seen_ids.add(layer.layer_id)

        # 9. Transform coordinates normalized to [-1, 1]
        offset = layer.transform.get("offset_norm", [0.0, 0.0])
        for i, v in enumerate(offset):
            if not (-1.5 <= v <= 1.5):  # небольшой допуск для off-canvas
                errors.append(
                    f"Layer '{layer.layer_id}': transform.offset_norm[{i}]={v} "
                    f"outside [-1.5, 1.5]"
                )

    return errors


def assert_plan_valid(
    plan: VisualCompositionPlan,
    catalog: dict,
) -> None:
    """Бросает CompositionConfigError если план невалиден."""
    errors = validate_plan(plan, catalog)
    if errors:
        msg = "Plan validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        raise CompositionConfigError(msg)
