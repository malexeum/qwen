"""PlanLoader — загрузка и валидация plan.json."""
from __future__ import annotations

import json
from pathlib import Path


class PlanLoadError(Exception):
    pass


# Принимаемые префиксы schema_version
_SUPPORTED_SCHEMAS = (
    "visual-composition-plan/v0.3",   # planner v0.3 (current)
    "composition-plan/v0.3",          # legacy
)


def load_plan(plan_path: str | Path) -> dict:
    """Load plan.json, validate schema_version and required fields."""
    path = Path(plan_path)
    if not path.exists():
        raise PlanLoadError(f"plan.json not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlanLoadError(f"Invalid JSON in {path}: {e}") from e

    if "plan_id" not in data:
        raise PlanLoadError("plan.json missing 'plan_id'")

    schema = data.get("schema_version", "")
    if not any(schema.startswith(s) for s in _SUPPORTED_SCHEMAS):
        raise PlanLoadError(
            f"Unsupported schema_version: '{schema}'. "
            f"Supported: {_SUPPORTED_SCHEMAS}"
        )

    if "layers" not in data or not isinstance(data["layers"], list):
        raise PlanLoadError("plan.json missing 'layers' list")
    if "canvas" not in data:
        raise PlanLoadError("plan.json missing 'canvas'")
    return data
