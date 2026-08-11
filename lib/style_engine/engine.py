from __future__ import annotations

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

_THETA_DEFAULT = 0.5  # нейтральное значение при отсутствии оси в perceptual

# ---------------------------------------------------------------------------
# Таблица алиасов slug-ов (применяется ДО проверки реестра)
# ---------------------------------------------------------------------------
# E3-C:
#   - jazz удалён как алиас: jazz — самостоятельный canonical профиль
#   - cinematic удалён: dangling alias (soundtrack не существует)
#   - blues/blues_jazz → blues_jazz сохранены
#   - electro/techno/electronic_music → electronic сохранены
#   - Каждый destination обязан присутствовать в реестре; иначе → ValidationError
_STYLE_ALIASES: Dict[str, str] = {
    "blues":            "blues_jazz",
    "blues_jazz":       "blues_jazz",   # идемпотентный
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
    """
    Raised when a theta axis is missing or an unsupported key is found
    and strict validation is enabled.
    """


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MappingTraceEntry:
    """Одна запись трассировки: какой параметр, из какого источника, финальное значение."""
    param: str
    source: str       # имя оси-источника или 'formula' / 'base' / 'guardrail'
    raw: float        # значение до clamp
    final: float      # значение после clamp01
    stage: str        # 'base' | 'perceptual' | 'user' | 'guardrail'


@dataclass
class RenderParams:
    style_profile_slug: str
    interpretation_profile_slug: str
    preset_id: str

    # Классические визуальные оси
    symmetry_bias: float
    recursion_depth: float
    density_level: float
    noise_level: float
    motion_intensity: float
    texture_complexity: float

    # E3: гармонические θ-оси (8 штук, range [0, 1])
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

    # Трассировка (не сериализуется в JSON-ответ, только для отладки)
    mapping_trace: List[MappingTraceEntry] = field(default_factory=list, compare=False, repr=False)


# ---------------------------------------------------------------------------
# Вспомогательные функции
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

    spectral_flatness в E1 лежит в диапазоне ~[0, 0.05].
    log10(x + eps) отображает этот диапазон примерно в [-6, -1.3],
    затем линейно нормируется в [0, 1].

    scale: ожидаемый практический максимум spectral_flatness.
    При raw >= scale → 1.0; при raw ≈ 0 → 0.0.
    """
    if raw is None:
        return 0.0
    raw = max(0.0, float(raw))
    log_val   = math.log10(raw + eps)
    log_min   = math.log10(eps)            # ~-6.0
    log_max   = math.log10(scale + eps)    # ~-1.3 при scale=0.05
    if log_max <= log_min:
        return 0.0
    normalized = (log_val - log_min) / (log_max - log_min)
    return _clamp01(normalized)


def _prepare_noise_proxy(perceptual: Dict[str, Any]) -> float:
    """
    Вычисляет noise_proxy — нормализованный proxy тембрального шума.

    Источник: perceptual["noise_proxy"] (если уже вычислен upstream)
      или perceptual["spectral_flatness"] через log-нормировку.

    Контракт E3-C:
      - noise_proxy — единственный входной сигнал шума для formula noise_level
      - density и tension не участвуют в target noise_level
      - harmony_theta_5 — дополнительный модификатор тембрального хаоса
    """
    # Приоритет 1: уже нормированный proxy, переданный upstream (E1-bridge)
    if "noise_proxy" in perceptual and perceptual["noise_proxy"] is not None:
        return _clamp01(float(perceptual["noise_proxy"]))
    # Приоритет 2: raw spectral_flatness → log-нормировка
    sf = perceptual.get("spectral_flatness", None)
    if sf is not None:
        return _log_normalize(float(sf))
    # Fallback: нейтральное значение
    return 0.5


def compute_theta_hash(theta: Mapping[str, float], strict: bool = True) -> str:
    """
    Canonical named θ-hash — публичная функция (CB-1 contract).

    Алгоритм (ТЗ §2.2):
      1. Извлекаем ровно 8 именованных осей из THETA_AXES.
      2. Округляем каждое значение до 6 десятичных знаков.
      3. Сериализуем в canonical JSON (sort_keys=True, compact separators).
      4. SHA-256 → первые 16 hex-символов.

    Гарантии:
      - input dict в любом порядке → одинаковый hash.
      - перестановка значений между осями → другой hash.
      - изменение любой оси на ±0.000001 → другой hash.

    strict=True (default):
      - missing axis → ValidationError с именем оси.
      - unsupported key → ValidationError с именем ключа.
    strict=False:
      - missing axis подставляет _THETA_DEFAULT; лишние ключи игнорируются.

    Float precision policy: round(float(v), 6) — ровно 6 знаков после запятой.
    """
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


# Keep private alias for internal callers (backward compat)
def _compute_theta_hash(theta_values: Dict[str, float]) -> str:
    """Internal alias → compute_theta_hash(strict=False) for legacy callers."""
    return compute_theta_hash(theta_values, strict=False)


def _compute_variation_seed(
    project_id: str,
    analysis_id: str,
    preset_id: str,
    style_slug: str,
    interp_slug: str,
    theta_values: Dict[str, float],
) -> int:
    """
    SHA-256-based variation seed.

    CB-1: theta contribution uses same canonical JSON scheme as compute_theta_hash
    so that seed и hash are derived from identical serialisation — prevents
    divergence between hash contract and seed contract.
    """
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
    """
    Нормализует slug стиля.

    Порядок:
      1. Применяет таблицу алиасов _STYLE_ALIASES (ДО проверки реестра).
         Если alias destination отсутствует в реестре — бросает ValidationError.
         Это предотвращает dangling aliases.
      2. Если slug уже в реестре — возвращает как есть.
      3. Иначе возвращает оригинальный slug (engine выбросит ValueError).

    E3-C контракт:
      - jazz НЕ является алиасом blues_jazz; jazz — canonical профиль.
      - cinematic НЕ является алиасом soundtrack (soundtrack отсутствует в реестре).
    """
    slug = (style_profile_slug or "default").strip()
    slug_lower = slug.lower()

    # Шаг 1: применяем алиасы (приоритет выше реестра)
    canonical = _STYLE_ALIASES.get(slug_lower)
    if canonical is not None:
        # Dangling alias guard: destination обязан существовать в реестре
        if canonical not in style_registry:
            available = sorted(style_registry.keys())
            raise ValidationError(
                f"dangling_alias: '{slug}' → '{canonical}' "
                f"but '{canonical}' not in style registry. "
                f"Available canonical profiles: {available}"
            )
        return canonical

    # Шаг 2: slug уже в реестре — возвращаем как есть
    if slug in style_registry:
        return slug

    # Шаг 3: неизвестный slug — возвращаем как есть, engine выбросит ValueError
    return slug


def _derive_palette_id(base_palette: str, brightness: float) -> str:
    """
    Legacy-логика выбора палитры: suffix _bright/_dark относительно базового palette.
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
    Отражает риск потери музыкальной идентичности при слишком гладкой морфологии.
    """
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    tension = _safe_float(perceptual.get("tension", 0.0))
    repetition = _safe_float(perceptual.get("repetition", 0.0))
    stability = _safe_float(perceptual.get("stability", 0.0))
    w1, w2, w3, w4 = 0.5, 0.4, 0.3, 0.3
    value = w1 * section_complexity + w2 * tension - w3 * repetition - w4 * stability
    return _clamp01(value)


def _extract_theta_axes(
    perceptual: Dict[str, Any],
    strict: bool = True,
) -> Dict[str, float]:
    """
    Извлекает harmony_theta_0..7 из perceptual.

    strict=True (production): если ось объявлена в THETA_AXES но отсутствует
    в perceptual — молча подставляет _THETA_DEFAULT (нейтрально).
    Если значение присутствует но не конвертируется в float — бросает ValueError.
    """
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
    """
    E3: заменяет silent-zero на явную ошибку.
    Бросает ValueError если source не найден в axes.
    """
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
    Главный визуальный resolver в declarative-режиме.

    perceptual: dict с осями (energy, tension, density, brightness, stability,
      smoothness, repetition, section_complexity, macro_shape_hint) +
      E3: harmony_theta_0..7 +
      E3-C: noise_proxy (log-нормированная spectral_flatness, [0,1]).

    user_preset: dict со слайдерами (complexity, symmetry, density, noise, motion).

    strict_theta=True: неизвестный mapping source → ValueError вместо silent-zero.

    Логика:
      1) Base layer из StyleProfile.
      2) Perceptual layer из InterpretationProfile.mapping_rules.
      3) User layer из UserPreset.
      4) Guardrails из InterpretationProfile.guardrails.
    """

    trace: List[MappingTraceEntry] = []

    def _trace(param: str, source: str, raw: float, final: float, stage: str) -> None:
        trace.append(MappingTraceEntry(param=param, source=source, raw=raw, final=final, stage=stage))

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

    style_profile = style_registry[normalized_style_slug]
    interp_profile = interp_registry[interpretation_profile_slug]

    # -----------------------------------------------------------------------
    # 1. Base layer (StyleProfile)
    # -----------------------------------------------------------------------
    base_symmetry  = _clamp01(_safe_float(getattr(style_profile, "symmetry_bias",   0.5), 0.5))
    base_recursion = _clamp01(_safe_float(getattr(style_profile, "complexity_bias", 0.5), 0.5))
    base_density   = _clamp01(_safe_float(getattr(style_profile, "density",         0.5), 0.5))
    base_noise     = _clamp01(_safe_float(getattr(style_profile, "noise_level",     0.5), 0.5))
    base_motion    = _clamp01(_safe_float(getattr(style_profile, "motion_intensity", 0.5), 0.5))
    base_texture   = base_recursion
    base_stochastic = 0.25
    base_palette   = (getattr(style_profile, "palette", "default_dark") or "default_dark").strip()

    for pname, pval in [
        ("symmetry_bias",    base_symmetry),
        ("recursion_depth",  base_recursion),
        ("density_level",    base_density),
        ("noise_level",      base_noise),
        ("motion_intensity", base_motion),
        ("texture_complexity", base_texture),
    ]:
        _trace(pname, "style_profile", pval, pval, "base")

    # -----------------------------------------------------------------------
    # Perceptual axes (классические)
    # -----------------------------------------------------------------------
    energy             = _safe_float(perceptual.get("energy",           0.0))
    tension            = _safe_float(perceptual.get("tension",          0.0))
    density_axis       = _safe_float(perceptual.get("density",          0.0))
    brightness         = _safe_float(perceptual.get("brightness",       0.0))
    stability          = _safe_float(perceptual.get("stability",        0.0))
    smoothness         = _safe_float(perceptual.get("smoothness",       0.0))
    repetition         = _safe_float(perceptual.get("repetition",       0.0))
    section_complexity = _safe_float(perceptual.get("section_complexity", 0.0))
    macro_shape_hint   = perceptual.get("macro_shape_hint", "unknown") or "unknown"

    # E3-C: noise_proxy — log-нормированная spectral_flatness, независимая ось шума.
    # НЕ является density; density — плотность событий/текстуры, не тембральная шумность.
    noise_proxy = _prepare_noise_proxy(perceptual)

    # E3: извлекаем θ-оси
    theta_values = _extract_theta_axes(perceptual, strict=strict_theta)

    morphology_guard = _compute_morphology_guard(perceptual)

    # Полный axes-словарь: классика + noise_proxy + θ + derived
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
        # E3-C: шумовой proxy (log-norm spectral_flatness)
        "noise_proxy":        noise_proxy,
        # E3: theta axes
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
        _trace(name, expr or "base", raw_val, final, "perceptual")
        return final

    symmetry_bias      = _eval_param("symmetry_bias",     base_symmetry)
    recursion_depth    = _eval_param("recursion_depth",   base_recursion)
    density_level      = _eval_param("density_level",     base_density)
    noise_level        = _eval_param("noise_level",       base_noise)
    motion_intensity   = _eval_param("motion_intensity",  base_motion)
    texture_complexity = _eval_param("texture_complexity", base_texture)

    # layout_macro_shape via rules
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

    # Palette
    palette_id    = _derive_palette_id(base_palette, brightness)
    stochastic_term = _clamp01(base_stochastic)

    # -----------------------------------------------------------------------
    # 3. User layer (UserPreset biases, ±0.25 диапазон влияния)
    # -----------------------------------------------------------------------
    preset_complexity = _safe_float(user_preset.get("complexity", 0.5), 0.5)
    preset_symmetry   = _safe_float(user_preset.get("symmetry",   0.5), 0.5)
    preset_density    = _safe_float(user_preset.get("density",    0.5), 0.5)
    preset_noise      = _safe_float(user_preset.get("noise",      0.5), 0.5)
    preset_motion     = _safe_float(user_preset.get("motion",     0.5), 0.5)

    def _apply_preset(cur: float, preset_val: float, name: str) -> float:
        raw = cur + (preset_val - 0.5) * 0.5
        final = _clamp01(raw)
        _trace(name, f"user_preset:{name}", raw, final, "user")
        return final

    symmetry_bias      = _apply_preset(symmetry_bias,      preset_symmetry,   "symmetry_bias")
    recursion_depth    = _apply_preset(recursion_depth,    preset_complexity, "recursion_depth")
    density_level      = _apply_preset(density_level,      preset_density,    "density_level")
    noise_level        = _apply_preset(noise_level,        preset_noise,      "noise_level")
    motion_intensity   = _apply_preset(motion_intensity,   preset_motion,     "motion_intensity")

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
            _trace(param_name, f"guardrail:{gr.when}", val, val, "guardrail")

    symmetry_bias      = _mutable["symmetry_bias"]
    recursion_depth    = _mutable["recursion_depth"]
    density_level      = _mutable["density_level"]
    noise_level        = _mutable["noise_level"]
    motion_intensity   = _mutable["motion_intensity"]
    texture_complexity = _mutable["texture_complexity"]

    # -----------------------------------------------------------------------
    # Variation seed (CB-1: canonical JSON theta payload)
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
