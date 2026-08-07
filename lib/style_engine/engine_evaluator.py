# lib/style_engine/engine_evaluator.py

from typing import Dict, Any
import ast

ALLOWED_NAMES = {
    "base",
    "energy",
    "tension",
    "density",
    "brightness",
    "stability",
    "smoothness",
    "repetition",
    "section_complexity",
    "macro_shape_hint",
    "morphology_guard",
}

ALLOWED_NODES = (
    "Expression",
    "BinOp",
    "UnaryOp",
    "Name",
    "Load",
    "Constant",
    "BoolOp",
    "Compare",
    "And",
    "Or",
    "Eq",
    "NotEq",
    "Lt",
    "LtE",
    "Gt",
    "GtE",
)


def _safe_eval_expr(expr: str, local_vars: Dict[str, Any]) -> float:
    """
    Evaluate a simple arithmetic expression over PerceptualLatent axes.

    Supports +, -, *, /, parentheses, using allowed variable names only.
    Returns float; on error falls back to base.
    """
    if not expr:
        return float(local_vars.get("base", 0.0))
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        return float(local_vars.get("base", 0.0))

    class Checker(ast.NodeVisitor):
        def visit_Name(self, n: ast.Name):
            if n.id not in ALLOWED_NAMES:
                raise ValueError(f"Forbidden name: {n.id}")

        def generic_visit(self, n):
            if type(n).__name__ not in ALLOWED_NODES:
                raise ValueError(f"Forbidden node: {type(n).__name__}")
            super().generic_visit(n)

    try:
        Checker().visit(node)
        code_obj = compile(node, "<expr>", "eval")
        return float(eval(code_obj, {"__builtins__": {}}, local_vars))
    except Exception:
        return float(local_vars.get("base", 0.0))


def _safe_eval_bool(expr: str, local_vars: Dict[str, Any]) -> bool:
    """
    Evaluate a simple boolean expression used in guardrails `when`.

    Supports logical operations (and, or) and comparisons over axes.
    Returns bool; on error returns False.
    """
    if not expr:
        return False
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False

    class Checker(ast.NodeVisitor):
        def visit_Name(self, n: ast.Name):
            if n.id not in ALLOWED_NAMES:
                raise ValueError(f"Forbidden name: {n.id}")

        def generic_visit(self, n):
            if type(n).__name__ not in ALLOWED_NODES:
                raise ValueError(f"Forbidden node: {type(n).__name__}")
            super().generic_visit(n)

    try:
        Checker().visit(node)
        code_obj = compile(node, "<bool_expr>", "eval")
        return bool(eval(code_obj, {"__builtins__": {}}, local_vars))
    except Exception:
        return False