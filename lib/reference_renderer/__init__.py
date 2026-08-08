"""Reference renderer package — Этап 6.

Единственная точка входа: execute_plan().
PIL используется только здесь, не в lib.composition.
"""
from .execute_plan import execute_plan, RenderResult

__all__ = ["execute_plan", "RenderResult"]
