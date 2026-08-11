from __future__ import annotations

import ast
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from lib.style_engine.config_loader import (
    InterpretationProfile,
    StyleProfile,
    load_interpretation_profiles,
    load_style_profiles,
)
from lib.style_engine.engine_evaluator import _safe_eval_bool, _safe_eval_expr

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

THETA_AXES: Tuple[str, ...] = (
    "harmony_theta_0",  # гармоническая чистота
    "harmony_theta_1",  # стабильность × смена
    "harmony_theta_2",  # структурная плотность
    "harmony_theta_3",  # неразрешённое напряжение
    "harmony_theta_4",  # чистый контраст секций
    "harmony_theta_5",  # тембральный хаос
    "harmony_theta_6",  # энтропия развития
    "harmony_theta_7",  # кристалличность
)

# Perceptual (audio-derived) axes — не θ, не служебные.
# Используются в _extract_formula_axes для канонического порядка source_axes.
PERCEPTUAL_AXES: Tuple[str, ...] = (
    "energy",
    "tension",
    "density",
    "brightness",
    "stability",
    "smoothness",
    "repetition",
    "section_complexity",
    "noise_proxy",
    "morphology_guard",
)

# Служебные имена — не попадают в source_axes
_NON_SOURCE_NAMES = frozenset({"base", "macro_shape_hint"})

_THETA_DEFAULT = 0.5

# ---------------------------------------------------------------------------
# Таблица алиасов slug-ов
# ---------------------------------------------------------------------------
_STYLE_ALIASES: Dict[str, str] = {
    "blues":            "blues_jazz",
    "blues_jazz":       "blues_jazz",
    "techno":           "electronic",
    "electro":          "electronic",
    "electronic_music": "electronic",
    "space":            "ambient",
    "mixed":            "default",
}


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MappingTraceEntry:
    """
    Одна запись трассировки.

    CB-3.1-A1: расширена полями θ-провенанса и генераторного слоя.

      param         — имя визуального параметра
      source        — формула-строка или описание источника
      raw           — значение до clamp01
      final         — значение после clamp01
      stage         — 'base' | 'perceptual' | 'user' | 'guardrail'

      source_axes   — канонический список осей из формулы (AST-based, без 'base')
      formula       — точная formula-строка из YAML (None если stage≠perceptual)
      input_values  — снимок значений source_axes на момент вычисления
      layer_id      — 'interpretation' для StyleEngine; реальный layer при composition
      generator_id  — None до Step B; реальный generator_id при composition render
    """
    param: str
    source: str
    raw: float
    final: float
    stage: str

    source_axes: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    input_values: Dict[str, float] = field(default_factory=dict)

    layer_id: Optional[str] = None
    generator_id: Optional[str] = None


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
    texture_complexity: float

    harmony_theta_0: float = _THETA_DEFAULT
    harmony_theta_1: float = _THETA_DEFAULT
    harmony_theta_2: float = _THETA_DEFAULT
    harmony_theta_3: float = _THETA_DEFAULT
    harmony_theta_4: float = _THETA_DEFAULT
    harmony_theta_5: float = _THETA_DEFAULT
    harmony_theta_6: float = _THETA_DEFAULT
    harmony_theta_7: float = _THETA_DEFAULT

    palette_id: str = "default_dark"
    stochastic_term: float = 0.25
    layout_macro_shape: str = "ABA_like"

    variation_seed: int = 0

    mapping_trace: List[MappingTraceEntry] = field(default_factory=list, compare=False, repr=False)


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _log_normalize(raw: float, eps: float = 1e-6, scale: float = 0.05) -> float:
    """
    Log-нормировка spectral_flatness → noise_proxy ∈ [0, 1].
    """
    raw = max(0.0, float(raw))
    log_val = math.log10(raw + eps)
    log_min = math.log10(eps)
    log_max = math.log10(scale + eps)
    if log_max <= log_min:
        return 0.0
    return _clamp01((log_val - log_min) / (log_max - log_min))


def _prepare_noise_proxy(perceptual: Dict[str, Any]) -> float:
    """
    Tri-state noise_proxy контракт (E3-C):

      noise_proxy key present & not None  → use directly (clamp01)
      spectral_flatness present & not None → _log_normalize(sf)
      neither present                      → 0.5  (unknown/neutral fallback)

    Важно: «нет данных» ≠ «идеально чистый сигнал».
    spectral_flatness=0.0 даёт ~0.0 (чистый тон), а отсутствие
    любого поля — нейтральный 0.5.
    """
    noise_proxy = perceptual.get("noise_proxy")
    if noise_proxy is not None:
        return _clamp01(float(noise_proxy))

    sf = perceptual.get("spectral_flatness")
    if sf is not None:
        return _log_normalize(float(sf))

    return 0.5


def _extract_formula_axes(
    formula: str,
    allowed_axes: Tuple[str, ...],
) -> List[str]:
    """
    CB-3.1-A1: AST-based извлечение осей из формулы.

    Правила:
    - Используется ast.walk, а не substring-поиск.
    - 'base' и другие служебные имена (_NON_SOURCE_NAMES) исключаются.
    - Порядок результата — канонический: сначала PERCEPTUAL_AXES,
      потом THETA_AXES (в порядке их определения), а не порядок set.
    - Если formula не парсится — возвращает [].
    """
    if not formula:
        return []
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError:
        return []

    names_in_formula: set[str] = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    # Убираем служебные
    names_in_formula -= _NON_SOURCE_NAMES

    # Канонический порядок по allowed_axes
    allowed_set = set(allowed_axes)
    return [
        axis for axis in allowed_axes
        if axis in names_in_formula and axis in allowed_set
    ]


def _snapshot_input_values(
    axis_names: List[str],
    axes: Dict[str, Any],
) -> Dict[str, float]:
    """
    CB-3.1-A1: снимок числовых значений перечисленных осей.
    Нечисловые значения (macro_shape_hint и т.п.) пропускаются.
    """
    result: Dict[str, float] = {}
    for name in axis_names:
        val = axes.get(name)
        if val is not None:
            try:
                result[name] = round(float(val), 6)
            except (TypeError, ValueError):
                pass
    return result


# Полный канонический список осей для _extract_formula_axes
_ALL_FORMULA_AXES: Tuple[str, ...] = PERCEPTUAL_AXES + THETA_AXES


def compute_theta_hash(theta: Mapping[str, float], strict: bool = True) -> str:
    if strict:
        known = set(THETA_AXES)
        for key in theta:
            if key not in known:
                raise ValidationError(
                    f"theta_hash: unsupported axis key '{key}'. "
                    f"Allowed axes: {list(THETA_AXES)}"
                )
        for axis in THETA_AXES:
            if axis not in theta:
                raise ValidationError(
                    f"theta_hash: missing required axis '{axis}'."
                )
    payload = {
        axis: round(float(theta[axis]) if axis in theta else _THETA_DEFAULT, 6)
        for axis in THETA_AXES
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _compute_theta_hash(theta_values: Dict[str, float]) -> str:
    return compute_theta_hash(theta_values, strict=False)


def _compute_variation_seed(
    project_id: str,
    analysis_id: str,
    preset_id: str,
    style_slug: str,
    interp_slug: str,
    theta_values: Dict[str, float],
) -> int:
    theta_payload = {
        axis: round(float(theta_values.get(axis, _THETA_DEFAULT)), 6)
        for axis in THETA_AXES
    }
    theta_canonical = json.dumps(
        theta_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    raw = f"{project_id}|{analysis_id}|{preset_id}|{style_slug}|{interp_slug}|{theta_canonical}"
    digest = hashlib.sha256(raw.encode()).digest()
    return int.from_bytes(digest[:4], "big")


def _normalize_style_slug(
    style_profile_slug: str,
    style_registry: Dict[str, StyleProfile],
) -> str:
    slug = (style_profile_slug or "default").strip()
    slug_lower = slug.lower()
    canonical = _STYLE_ALIASES.get(slug_lower)
    if canonical is not None:
        if canonical not in style_registry:
            available = sorted(style_registry.keys())
            raise ValidationError(
                f"dangling_alias: '{slug}' → '{canonical}' "
                f"but '{canonical}' not in style registry. "
                f"Available canonical profiles: {available}"
            )
        return canonical
    if slug in style_registry:
        return slug
    return slug


def _derive_palette_id(base_palette: str, brightness: float) -> str:
    base_palette = (base_palette or "default_dark").strip()
    if brightness > 0.60:
        return f"{base_palette}_bright"
    if brightness < 0.30:
        return f"{base_palette}_dark"
    return base_palette


def _compute_morphology_guard(perceptual: Dict[str, float]) -> float:
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    tension            = _safe_float(perceptual.get("tension", 0.0))
    repetition         = _safe_float(perceptual.get("repetition", 0.0))
    stability          = _safe_float(perceptual.get("stability", 0.0))
    value = 0.5 * section_complexity + 0.4 * tension - 0.3 * repetition - 0.3 * stability
    return _clamp01(value)


def _extract_theta_axes(
    perceptual: Dict[str, Any],
    strict: bool = True,
) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for axis in THETA_AXES:
        raw = perceptual.get(axis, None)
        if raw is None:
            result[axis] = _THETA_DEFAULT
        else:
            try:
                val = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"harmony_theta_parse_error: axis='{axis}' value={raw!r}"
                ) from exc
            result[axis] = _clamp01(val)
    return result


def _validate_mapping_source(
    source: str,
    axes: Dict[str, Any],
    param_name: str,
    layer_id: str = "",
) -> None:
    if source not in axes:
        ctx = f" (layer={layer_id})" if layer_id else ""
        raise ValueError(
            f"unknown_mapping_source: param='{param_name}', "
            f"source='{source}'{ctx} not in axes. "
            f"Available: {sorted(axes.keys())}"
        )


# ---------------------------------------------------------------------------
# Основной resolver
# ---------------------------------------------------------------------------

def resolve_render_params(
    project_id: str,
    analysis_id: str,
    perceptual: Dict[str, Any],
    style_profile_slug: str,
    interpretation_profile_slug: str,
    user_preset: Dict[str, float],
    strict_theta: bool = True,
) -> Tuple[RenderParams, StyleProfile, InterpretationProfile]:
    """
    Главный визуальный resolver.

    CB-3.1-A1: каждый MappingTraceEntry несёт полный θ-провенанс:
      source_axes (AST-based), formula, input_values,
      layer_id='interpretation', generator_id=None.
    """

    trace: List[MappingTraceEntry] = []

    def _trace_base(param: str, val: float) -> None:
        trace.append(MappingTraceEntry(
            param=param,
            source="style_profile",
            raw=val,
            final=val,
            stage="base",
            source_axes=[],
            formula=None,
            input_values={},
            layer_id="interpretation",
            generator_id=None,
        ))

    def _trace_formula(
        param: str,
        formula_str: str,
        raw: float,
        final: float,
        axes: Dict[str, Any],
    ) -> None:
        """
        CB-3.1-A1: stage=perceptual с полным θ-провенансом.
        source_axes извлекается через AST, 'base' исключён.
        """
        used_axes = _extract_formula_axes(formula_str, _ALL_FORMULA_AXES) if formula_str else []
        snap = _snapshot_input_values(used_axes, axes)
        trace.append(MappingTraceEntry(
            param=param,
            source=formula_str or "base",
            raw=raw,
            final=final,
            stage="perceptual",
            source_axes=used_axes,
            formula=formula_str if formula_str else None,
            input_values=snap,
            layer_id="interpretation",
            generator_id=None,
        ))

    def _trace_user(param: str, raw: float, final: float, preset_key: str) -> None:
        trace.append(MappingTraceEntry(
            param=param,
            source=f"user_preset:{preset_key}",
            raw=raw,
            final=final,
            stage="user",
            source_axes=[],
            formula=None,
            input_values={},
            layer_id="interpretation",
            generator_id=None,
        ))

    def _trace_guardrail(param: str, val: float, when_expr: str) -> None:
        trace.append(MappingTraceEntry(
            param=param,
            source=f"guardrail:{when_expr}",
            raw=val,
            final=val,
            stage="guardrail",
            source_axes=[],
            formula=None,
            input_values={},
            layer_id="interpretation",
            generator_id=None,
        ))

    # -----------------------------------------------------------------------
    # Загрузка реестров
    # -----------------------------------------------------------------------
    style_registry = load_style_profiles()
    interp_registry = load_interpretation_profiles()

    normalized_style_slug = _normalize_style_slug(style_profile_slug, style_registry)
    if normalized_style_slug not in style_registry:
        raise ValueError(f"unknown_style_profile: {style_profile_slug!r}")
    if interpretation_profile_slug not in interp_registry:
        raise ValueError(f"unknown_interpretation_profile: {interpretation_profile_slug!r}")

    style_profile  = style_registry[normalized_style_slug]
    interp_profile = interp_registry[interpretation_profile_slug]

    # -----------------------------------------------------------------------
    # 1. Base layer (StyleProfile)
    # -----------------------------------------------------------------------
    base_symmetry   = _clamp01(_safe_float(getattr(style_profile, "symmetry_bias",    0.5), 0.5))
    base_recursion  = _clamp01(_safe_float(getattr(style_profile, "complexity_bias",  0.5), 0.5))
    base_density    = _clamp01(_safe_float(getattr(style_profile, "density",          0.5), 0.5))
    base_noise      = _clamp01(_safe_float(getattr(style_profile, "noise_level",      0.5), 0.5))
    base_motion     = _clamp01(_safe_float(getattr(style_profile, "motion_intensity", 0.5), 0.5))
    base_texture    = base_recursion
    base_stochastic = 0.25
    base_palette    = (getattr(style_profile, "palette", "default_dark") or "default_dark").strip()

    for pname, pval in [
        ("symmetry_bias",      base_symmetry),
        ("recursion_depth",    base_recursion),
        ("density_level",      base_density),
        ("noise_level",        base_noise),
        ("motion_intensity",   base_motion),
        ("texture_complexity", base_texture),
    ]:
        _trace_base(pname, pval)

    # -----------------------------------------------------------------------
    # Perceptual axes
    # -----------------------------------------------------------------------
    energy             = _safe_float(perceptual.get("energy",             0.0))
    tension            = _safe_float(perceptual.get("tension",            0.0))
    density_axis       = _safe_float(perceptual.get("density",            0.0))
    brightness         = _safe_float(perceptual.get("brightness",         0.0))
    stability          = _safe_float(perceptual.get("stability",          0.0))
    smoothness         = _safe_float(perceptual.get("smoothness",         0.0))
    repetition         = _safe_float(perceptual.get("repetition",         0.0))
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    macro_shape_hint   = perceptual.get("macro_shape_hint", "unknown") or "unknown"

    noise_proxy      = _prepare_noise_proxy(perceptual)
    theta_values     = _extract_theta_axes(perceptual, strict=strict_theta)
    morphology_guard = _compute_morphology_guard(perceptual)

    axes: Dict[str, Any] = {
        "energy":             energy,
        "tension":            tension,
        "density":            density_axis,
        "brightness":         brightness,
        "stability":          stability,
        "smoothness":         smoothness,
        "repetition":         repetition,
        "section_complexity": section_complexity,
        "macro_shape_hint":   macro_shape_hint,
        "morphology_guard":   morphology_guard,
        "noise_proxy":        noise_proxy,
        **theta_values,
    }

    # -----------------------------------------------------------------------
    # 2. Perceptual layer via mapping_rules
    # -----------------------------------------------------------------------
    mr = interp_profile.mapping_rules or {}

    def _eval_param(name: str, base_default: float) -> float:
        rule_raw = mr.get(name, {})
        rule = rule_raw if isinstance(rule_raw, dict) else {}
        base = float(rule.get("base", base_default))
        expr = str(rule.get("formula", "")) if "formula" in rule else ""
        if expr:
            raw_val = _safe_eval_expr(expr, {"base": base, **axes})
        else:
            raw_val = base
        final = _clamp01(raw_val)
        _trace_formula(name, expr, raw_val, final, {"base": base, **axes})
        return final

    symmetry_bias      = _eval_param("symmetry_bias",      base_symmetry)
    recursion_depth    = _eval_param("recursion_depth",    base_recursion)
    density_level      = _eval_param("density_level",      base_density)
    noise_level        = _eval_param("noise_level",        base_noise)
    motion_intensity   = _eval_param("motion_intensity",   base_motion)
    texture_complexity = _eval_param("texture_complexity", base_texture)

    # layout_macro_shape
    layout_cfg   = mr.get("layout_macro_shape", {})
    layout_rules = layout_cfg.get("rules", []) if isinstance(layout_cfg, dict) else []
    layout_macro_shape = "unknown"
    for rule in layout_rules:
        when_expr = str(rule.get("when", ""))
        value_str = str(rule.get("value", ""))
        if when_expr and value_str and _safe_eval_bool(when_expr, axes):
            layout_macro_shape = value_str
            break
    if layout_macro_shape == "unknown":
        layout_macro_shape = "ABA_like"

    palette_id      = _derive_palette_id(base_palette, brightness)
    stochastic_term = _clamp01(base_stochastic)

    # -----------------------------------------------------------------------
    # 3. User layer
    # -----------------------------------------------------------------------
    preset_complexity = _safe_float(user_preset.get("complexity", 0.5), 0.5)
    preset_symmetry   = _safe_float(user_preset.get("symmetry",   0.5), 0.5)
    preset_density    = _safe_float(user_preset.get("density",    0.5), 0.5)
    preset_noise      = _safe_float(user_preset.get("noise",      0.5), 0.5)
    preset_motion     = _safe_float(user_preset.get("motion",     0.5), 0.5)

    def _apply_preset(cur: float, preset_val: float, name: str, preset_key: str) -> float:
        raw = cur + (preset_val - 0.5) * 0.5
        final = _clamp01(raw)
        _trace_user(name, raw, final, preset_key)
        return final

    symmetry_bias   = _apply_preset(symmetry_bias,   preset_symmetry,   "symmetry_bias",   "symmetry")
    recursion_depth = _apply_preset(recursion_depth, preset_complexity, "recursion_depth", "complexity")
    density_level   = _apply_preset(density_level,   preset_density,    "density_level",   "density")
    noise_level     = _apply_preset(noise_level,     preset_noise,      "noise_level",     "noise")
    motion_intensity = _apply_preset(motion_intensity, preset_motion,   "motion_intensity", "motion")

    # -----------------------------------------------------------------------
    # 4. Guardrails
    # -----------------------------------------------------------------------
    guard_vars = axes.copy()
    guard_vars.update({
        "symmetry_bias":      symmetry_bias,
        "recursion_depth":    recursion_depth,
        "density_level":      density_level,
        "noise_level":        noise_level,
        "motion_intensity":   motion_intensity,
        "texture_complexity": texture_complexity,
    })

    _mutable = {
        "symmetry_bias":      symmetry_bias,
        "recursion_depth":    recursion_depth,
        "density_level":      density_level,
        "noise_level":        noise_level,
        "motion_intensity":   motion_intensity,
        "texture_complexity": texture_complexity,
    }

    for gr in getattr(interp_profile, "guardrails", []):
        if not gr.when:
            continue
        if not _safe_eval_bool(gr.when, guard_vars):
            continue
        for param_name, action in gr.actions.items():
            if param_name not in _mutable:
                continue
            val = _mutable[param_name]
            if action.min is not None:
                val = max(val, action.min)
            if action.max is not None:
                val = min(val, action.max)
            val = _clamp01(val)
            _mutable[param_name] = val
            _trace_guardrail(param_name, val, gr.when)

    symmetry_bias      = _mutable["symmetry_bias"]
    recursion_depth    = _mutable["recursion_depth"]
    density_level      = _mutable["density_level"]
    noise_level        = _mutable["noise_level"]
    motion_intensity   = _mutable["motion_intensity"]
    texture_complexity = _mutable["texture_complexity"]

    # -----------------------------------------------------------------------
    # Variation seed
    # -----------------------------------------------------------------------
    preset_id = str(user_preset.get("id", "preset"))
    variation_seed = _compute_variation_seed(
        project_id,
        analysis_id,
        preset_id,
        normalized_style_slug,
        interpretation_profile_slug,
        theta_values,
    )

    # -----------------------------------------------------------------------
    # Сборка RenderParams
    # -----------------------------------------------------------------------
    render_params = RenderParams(
        style_profile_slug=style_profile.slug,
        interpretation_profile_slug=interp_profile.slug,
        preset_id=preset_id,
        symmetry_bias=symmetry_bias,
        recursion_depth=recursion_depth,
        density_level=density_level,
        noise_level=noise_level,
        motion_intensity=motion_intensity,
        texture_complexity=texture_complexity,
        harmony_theta_0=theta_values["harmony_theta_0"],
        harmony_theta_1=theta_values["harmony_theta_1"],
        harmony_theta_2=theta_values["harmony_theta_2"],
        harmony_theta_3=theta_values["harmony_theta_3"],
        harmony_theta_4=theta_values["harmony_theta_4"],
        harmony_theta_5=theta_values["harmony_theta_5"],
        harmony_theta_6=theta_values["harmony_theta_6"],
        harmony_theta_7=theta_values["harmony_theta_7"],
        palette_id=palette_id,
        stochastic_term=stochastic_term,
        layout_macro_shape=layout_macro_shape,
        variation_seed=variation_seed,
        mapping_trace=trace,
    )

    return render_params, style_profile, interp_profile
