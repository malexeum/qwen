# composition_planner.py
# Composition Planner v0.1 — детерминированный генератор плана композиции.
#
# Входные данные:
#   PlannerInput — нормированные дескрипторы из composition_adapter.py
# Выходные данные:
#   CompositionPlan — JSON-сериализуемый датакласс со всеми зонами и ограничениями.
#
# Устойчивые признаки (Test7 + Test8):
#   bpm, energy, repetition_score,
#   band_energy_0_250_hz, band_energy_250_2000_hz, band_energy_2000_6000_hz
#
# Все признаки, не прошедшие проверку (brightness, onset_rate_hz, beat_regularity,
# dynamic_range, silence_rate, spectral_flatness), в формулах НЕ используются.

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import List, Optional
import math


# ---------------------------------------------------------------------------
# Контракт входа
# ---------------------------------------------------------------------------

@dataclass
class PlannerInput:
    """Нормированные дескрипторы для планировщика.

    Все значения float должны лежать в [0, 1] за исключением bpm.
    Источник: composition_adapter.py → build_planner_input().
    """
    # --- устойчивые аудио-признаки ---
    bpm: float                     # beats per minute, типично 60–200
    energy: float                  # RMS-энергия, нормированная [0, 1]
    repetition_score: float        # [0, 1], высокое = высокая повторяемость
    band_low: float                # band_energy_0_250_hz   [0, 1]
    band_mid: float                # band_energy_250_2000_hz [0, 1]
    band_high: float               # band_energy_2000_6000_hz [0, 1]

    # --- визуальный контекст из style engine ---
    style_profile_slug: str        # «default», «rock», «ambient», …
    macro_shape_hint: str          # «ABA_like», «linear», «arch», …

    # --- перцептивный слой (опционально, для нюансировки) ---
    perceptual_stability: float = 0.5   # harmonic_stability перцептива [0, 1]
    perceptual_tension: float = 0.5     # tension [0, 1]

    # --- воспроизводимость ---
    seed: int = 0


# ---------------------------------------------------------------------------
# Контракт выхода
# ---------------------------------------------------------------------------

@dataclass
class SpatialZone:
    zone_id: str
    role: str                         # «focal» | «support» | «negative_space"
    center_x: float                   # нормированные [0, 1]
    center_y: float
    radius: float                     # нормированный [0, 1]
    weight: float                     # доля визуальной массы [0, 1]


@dataclass
class MotifSpec:
    count: int
    scale_min: float
    scale_max: float
    orientation_variance_rad: float
    radial_bias: float                # насколько мотивы тяготеют к центру [0, 1]


@dataclass
class CompositionConstraints:
    preserve_negative_space: bool
    allow_edge_clipping: bool
    max_overlap_ratio: float


@dataclass
class CompositionPlan:
    version: str
    seed: int

    # геометрия холста (устанавливается адаптером / endpoint-ом)
    canvas_width_px: int
    canvas_height_px: int

    # макроформа
    archetype: str              # «radial_balance» | «diagonal_tension» | «grid_order» | «organic_flow"
    visual_mass: float          # [0, 1]
    density: float              # [0, 1]
    symmetry: float             # [0, 1]
    negative_space: float       # [0, 1]
    focal_x: float              # нормированные координаты фокусной точки
    focal_y: float

    # зоны
    zones: List[SpatialZone] = field(default_factory=list)

    # мотивы
    motif: Optional[MotifSpec] = None

    # ограничения рендерера
    constraints: Optional[CompositionConstraints] = None

    # провенанс
    planner_version: str = "0.1"
    audio_feature_version: str = "0.4"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Вспомогательные формулы
# ---------------------------------------------------------------------------

def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _map_bpm_norm(bpm: float) -> float:
    """BPM → [0, 1]: 60 bpm → 0.0, 180 bpm → 1.0, клипируется."""
    return _clip((bpm - 60.0) / 120.0)


def _compute_density(energy: float, band_high: float) -> float:
    """Плотность визуальных элементов.

    D = clip(0.20 + 0.65·E + 0.15·B_high, 0.10, 0.90)
    """
    return _clip(0.20 + 0.65 * energy + 0.15 * band_high, 0.10, 0.90)


def _compute_symmetry(repetition_score: float) -> float:
    """Степень симметрии.

    S = clip(0.25 + 0.70·R, 0.20, 0.95)
    """
    return _clip(0.25 + 0.70 * repetition_score, 0.20, 0.95)


def _compute_visual_mass(band_low: float) -> float:
    """Визуальная масса центральной зоны.

    M = clip(0.20 + 0.70·B_low, 0.15, 0.85)
    """
    return _clip(0.20 + 0.70 * band_low, 0.15, 0.85)


def _compute_motif_count(bpm: float, density: float) -> int:
    """Число мотивов.

    N = round(6 + 20·D + 0.05·clip(BPM, 60, 180)), ограничен [8, 36].
    """
    bpm_c = _clip(bpm, 60.0, 180.0)
    n = round(6.0 + 20.0 * density + 0.05 * bpm_c)
    return max(8, min(36, n))


def _choose_archetype(
    symmetry: float,
    density: float,
    band_mid: float,
    macro_shape_hint: str,
    tension: float,
) -> str:
    """Выбор архетипа композиции по параметрам.

    Приоритет: macro_shape_hint > алгоритмическое решение.
    """
    hint_map = {
        "ABA_like": "radial_balance",
        "arch": "radial_balance",
        "linear": "diagonal_tension",
        "stochastic": "organic_flow",
    }
    if macro_shape_hint in hint_map:
        return hint_map[macro_shape_hint]

    # алгоритмический путь
    if symmetry > 0.70 and density < 0.55:
        return "radial_balance"
    if tension > 0.65 and density > 0.60:
        return "diagonal_tension"
    if band_mid > 0.60 and symmetry > 0.55:
        return "grid_order"
    return "organic_flow"


def _focal_point(archetype: str, tension: float) -> tuple[float, float]:
    """Нормированные координаты фокусной точки."""
    if archetype == "radial_balance":
        return (0.50, 0.44)       # чуть выше центра — классическое золотое деление по Y
    if archetype == "diagonal_tension":
        x = _clip(0.30 + 0.40 * tension)
        return (x, 1.0 - x)      # по диагонали
    if archetype == "grid_order":
        return (0.50, 0.50)
    # organic_flow
    return (0.45, 0.50)


def _normalize_zone_weights(zones: list) -> list:
    """Нормирует веса зон так, чтобы их сумма была строго равна 1.0.

    Применяет пропорциональное масштабирование. При нулевой сумме
    распределяет веса равномерно.
    """
    total = sum(z.weight for z in zones)
    if total <= 0.0:
        for z in zones:
            z.weight = round(1.0 / len(zones), 4)
    else:
        for z in zones:
            z.weight = round(z.weight / total, 4)
        # корректируем остаток на последнюю зону, чтобы избежать float-дрейфа
        diff = round(1.0 - sum(z.weight for z in zones), 4)
        zones[-1].weight = round(zones[-1].weight + diff, 4)
    return zones


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def build_composition_plan(
    inp: PlannerInput,
    canvas_width_px: int = 2048,
    canvas_height_px: int = 2048,
) -> CompositionPlan:
    """Детерминированно строит CompositionPlan из PlannerInput.

    Нет случайности: один и тот же inp всегда даёт один и тот же план.
    Seed хранится в плане для возможного использования renderer-ом.
    """
    density = _compute_density(inp.energy, inp.band_high)
    symmetry = _compute_symmetry(inp.repetition_score)
    visual_mass = _compute_visual_mass(inp.band_low)
    negative_space = _clip(1.0 - density - 0.10, 0.10, 0.70)

    archetype = _choose_archetype(
        symmetry=symmetry,
        density=density,
        band_mid=inp.band_mid,
        macro_shape_hint=inp.macro_shape_hint,
        tension=inp.perceptual_tension,
    )

    fx, fy = _focal_point(archetype, inp.perceptual_tension)

    # -------- зоны --------
    core_radius = _clip(0.10 + 0.12 * visual_mass, 0.08, 0.25)
    field_radius = _clip(0.30 + 0.15 * density, 0.28, 0.50)

    core_weight = _clip(visual_mass * 0.55, 0.15, 0.60)
    field_weight = _clip(density * 0.45, 0.15, 0.55)
    margin_weight = _clip(1.0 - core_weight - field_weight, 0.05, 0.50)

    zones = [
        SpatialZone(
            zone_id="core",
            role="focal",
            center_x=fx,
            center_y=fy,
            radius=core_radius,
            weight=round(core_weight, 4),
        ),
        SpatialZone(
            zone_id="field",
            role="support",
            center_x=0.50,
            center_y=0.50,
            radius=field_radius,
            weight=round(field_weight, 4),
        ),
        SpatialZone(
            zone_id="margin",
            role="negative_space",
            center_x=0.50,
            center_y=0.50,
            radius=1.0,
            weight=round(margin_weight, 4),
        ),
    ]

    # Нормируем веса зон: гарантируем sum(weights) == 1.0
    zones = _normalize_zone_weights(zones)

    # -------- мотивы --------
    n_motifs = _compute_motif_count(inp.bpm, density)
    bpm_norm = _map_bpm_norm(inp.bpm)

    scale_min = _clip(0.02 + 0.04 * (1.0 - density), 0.015, 0.08)
    scale_max = _clip(scale_min * 3.5 + 0.04 * visual_mass, scale_min + 0.01, 0.30)

    # ориентационная вариация: быстрые треки → больше хаоса
    orient_var = _clip(0.10 + 1.20 * bpm_norm + 0.30 * inp.perceptual_tension)
    orient_var_rad = orient_var * math.pi

    radial_bias = _clip(symmetry * 0.90)

    motif = MotifSpec(
        count=n_motifs,
        scale_min=round(scale_min, 4),
        scale_max=round(scale_max, 4),
        orientation_variance_rad=round(orient_var_rad, 4),
        radial_bias=round(radial_bias, 4),
    )

    # -------- ограничения --------
    constraints = CompositionConstraints(
        preserve_negative_space=(negative_space > 0.20),
        allow_edge_clipping=(archetype == "diagonal_tension"),
        max_overlap_ratio=round(_clip(0.05 + 0.20 * density, 0.05, 0.35), 4),
    )

    return CompositionPlan(
        version="0.1",
        seed=inp.seed,
        canvas_width_px=canvas_width_px,
        canvas_height_px=canvas_height_px,
        archetype=archetype,
        visual_mass=round(visual_mass, 4),
        density=round(density, 4),
        symmetry=round(symmetry, 4),
        negative_space=round(negative_space, 4),
        focal_x=round(fx, 4),
        focal_y=round(fy, 4),
        zones=zones,
        motif=motif,
        constraints=constraints,
    )
