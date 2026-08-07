"""Сохранение артефактов VisualCompositionPlan v0.3.

Все артефакты одного reference-preview лежат в:
  D:\\WORK\\AVCoder\\storage\\poster_runs\\{plan_id}\\

Создаёт папку и пишет:
  visual_composition_plan.json
  parameter_coverage.json
  planner_diagnostics.json

PNG создаётся не здесь — только в reference_renderer.execute_plan.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schema import VisualCompositionPlan

DEFAULT_STORAGE = Path(r"D:\WORK\AVCoder\storage\poster_runs")


def save_plan_artifacts(
    plan: VisualCompositionPlan,
    coverage: dict,
    diagnostics: dict,
    storage_root: Path | None = None,
) -> Path:
    """Сохраняет JSON-артефакты в {storage_root}/{plan_id}/.

    Возвращает путь к созданной папке.
    """
    root = storage_root or DEFAULT_STORAGE
    plan_dir = root / plan.plan_id
    plan_dir.mkdir(parents=True, exist_ok=True)

    plan_json = plan.to_json()
    coverage_json = json.dumps(coverage, ensure_ascii=False, indent=2)
    diagnostics_json = json.dumps(diagnostics, ensure_ascii=False, indent=2)

    (plan_dir / "visual_composition_plan.json").write_text(
        plan_json, encoding="utf-8"
    )
    (plan_dir / "parameter_coverage.json").write_text(
        coverage_json, encoding="utf-8"
    )
    (plan_dir / "planner_diagnostics.json").write_text(
        diagnostics_json, encoding="utf-8"
    )

    return plan_dir


def plan_id_from_plan(plan: VisualCompositionPlan) -> str:
    """Детерминированный plan_id: SHA-256 canonical JSON без plan_id поля."""
    d = plan.to_dict()
    d.pop("plan_id", None)
    canonical = json.dumps(d, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
