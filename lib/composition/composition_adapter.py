# composition_adapter.py
# Адаптер: преобразует features + perceptual + style_profile
# из существующего pipeline в PlannerInput для composition_planner.py.
#
# Принципы:
# - Берём только устойчивые признаки (Test7 + Test8).
# - brightness, onset_rate_hz, beat_regularity, dynamic_range,
#   silence_rate, spectral_flatness — НЕ передаются в planner.
# - band_energy_6000_nyquist — не используется (зависит от Nyquist частоты,
#   не переносима между разными sample rate).
# - Все значения клипируются в [0, 1] до передачи.

from __future__ import annotations

from typing import Any, Dict, Optional

from composition_planner import PlannerInput


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _safe(d: Dict[str, Any], key: str, default: float = 0.0) -> float:
    """Безопасное извлечение float из словаря."""
    v = d.get(key, default)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def build_planner_input(
    features: Dict[str, Any],
    perceptual: Dict[str, Any],
    style_profile_slug: str = "default",
    macro_shape_hint: Optional[str] = None,
    seed: int = 0,
) -> PlannerInput:
    """Собирает PlannerInput из сырых данных pipeline.

    Args:
        features:          dict из AnalyzeResponse.features (ключи как в api_feature_keys).
        perceptual:        dict из AnalyzeResponse.perceptual / PerceptualLatentDB.
        style_profile_slug: slug из resolve_render_params / derive_style_profile_slug.
        macro_shape_hint:  строка из perceptual["macro_shape_hint"] или явно переданная.
        seed:              целое число для воспроизводимости.

    Returns:
        PlannerInput с нормированными полями.
    """
    # --- устойчивые аудио-признаки ---
    bpm = max(40.0, min(240.0, _safe(features, "bpm", 120.0)))
    energy = _clip(_safe(features, "energy", 0.1))
    repetition_score = _clip(_safe(features, "repetition_score", 0.5))

    band_low = _clip(_safe(features, "band_energy_0_250_hz", 0.33))
    band_mid = _clip(_safe(features, "band_energy_250_2000_hz", 0.33))
    band_high = _clip(_safe(features, "band_energy_2000_6000_hz", 0.10))

    # Нормировка полос: гарантируем, что band_low + band_mid + band_high <= 1
    # (они уже нормированы как доли спектра, но перестрахуемся при граничных значениях)
    total_band = band_low + band_mid + band_high
    if total_band > 1.0:
        band_low /= total_band
        band_mid /= total_band
        band_high /= total_band

    # --- перцептивный слой ---
    perceptual_stability = _clip(_safe(perceptual, "stability", 0.5))
    perceptual_tension = _clip(_safe(perceptual, "tension", 0.5))

    # --- макроформа ---
    if macro_shape_hint is None:
        macro_shape_hint = str(perceptual.get("macro_shape_hint") or "ABA_like")
    if not macro_shape_hint:
        macro_shape_hint = "ABA_like"

    return PlannerInput(
        bpm=bpm,
        energy=energy,
        repetition_score=repetition_score,
        band_low=band_low,
        band_mid=band_mid,
        band_high=band_high,
        style_profile_slug=style_profile_slug,
        macro_shape_hint=macro_shape_hint,
        perceptual_stability=perceptual_stability,
        perceptual_tension=perceptual_tension,
        seed=seed,
    )
