"""HarmonyEncoder E2 — детерминированный θ-артефакт трека.

Алгоритм: crossproduct_v1 (детерминированный, без ML).
Входные оси — срез feature_vector из AudioFileAdapter (E1).
Выход: HarmonyTheta ∈ ℝ^8, все θ_i ∈ [0, 1].

AP:
    encoder = HarmonyEncoder()
    theta   = encoder.encode(features)   # features — dict из extract_features()
    theta.values    → list[float] длиной 8
    theta.hash      → str, sha256[:16] округлённого θ
    theta.to_dict() → dict для YAML-артефакта

Интеграция в seed_policy:
    from lib.composition.seed_policy import compute_base_seed
    seed = compute_base_seed(..., harmony_theta_hash=theta.hash)

Mapping-оси harmony_theta_0..7 доступны в профилях генераторов
как источники для секции mapping (регистрация в config_loader.py).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import List

# Порядок осей ЗАФИКСИРОВАН — изменение ломает hash совместимость
HARMONY_AXES: List[str] = [
    "symmetry_bias",          # θ_0 вход
    "tension",                # θ_1 вход
    "harmonic_stability",     # θ_2 вход
    "harmonic_change_rate",   # θ_3 вход
    "texture_complexity",     # θ_4 вход
    "recursion_depth",        # θ_5 вход
    "section_complexity",     # θ_6 вход
    "noise_level",            # θ_7 вход
]

# Имена выходных mapping-осей (θ_0..θ_7)
HARMONY_THETA_AXES: List[str] = [f"harmony_theta_{i}" for i in range(8)]


@dataclass
class HarmonyTheta:
    """Результат HarmonyEncoder — гармоническая сигнатура трека."""
    version: str
    algorithm: str
    source_axes: List[str]
    values: List[float]        # len == 8, каждый ∈ [0, 1]

    @property
    def hash(self) -> str:
        """sha256[:16] от rounded(θ, 3) — стабильный хэш для seed_policy."""
        rounded = [round(v, 3) for v in self.values]
        return hashlib.sha256(
            json.dumps(rounded, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Сериализация в YAML-артефакт трека (поле harmony_theta)."""
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "source_axes": list(self.source_axes),
            "values": [round(v, 6) for v in self.values],
            "hash": self.hash,
        }

    def as_mapping_axes(self) -> dict[str, float]:
        """Возвращает {harmony_theta_0: v0, ..., harmony_theta_7: v7}."""
        return {f"harmony_theta_{i}": v for i, v in enumerate(self.values)}


class HarmonyEncoder:
    """Детерминированный encoder: feature_vector → HarmonyTheta.

    Версия v1 (crossproduct_v1) — без обучаемых весов.
    Все формулы — попарные произведения взаимодополняющих осей:

        θ_0 = symmetry_bias  × (1 − tension)              # гармоническая чистота
        θ_1 = harmonic_stability × harmonic_change_rate    # динамика vs стабильность
        θ_2 = texture_complexity × recursion_depth         # структурная плотность
        θ_3 = tension × (1 − harmonic_stability)           # неразрешённое напряжение
        θ_4 = section_complexity × (1 − noise_level)       # чистый контраст секций
        θ_5 = noise_level × texture_complexity             # тембральный хаос
        θ_6 = harmonic_change_rate × section_complexity    # энтропия развития
        θ_7 = symmetry_bias × harmonic_stability × (1 − tension)  # «кристалличность»
    """

    VERSION   = "1.0"
    ALGORITHM = "crossproduct_v1"

    def encode(self, features: dict) -> HarmonyTheta:
        """Кодирует feature_vector в HarmonyTheta.

        Args:
            features: dict из extract_features() (AudioFileAdapter E1).
                      Должен содержать все 8 осей HARMONY_AXES.
                      Остальные ключи (duration_sec, style, ...) игнорируются.

        Returns:
            HarmonyTheta с values ∈ [0, 1].

        Raises:
            KeyError: если в features отсутствует одна из HARMONY_AXES.
        """
        # Проверка наличия входных осей
        missing = [ax for ax in HARMONY_AXES if ax not in features]
        if missing:
            raise KeyError(
                f"HarmonyEncoder.encode(): missing feature axes: {missing}. "
                f"Required: {HARMONY_AXES}"
            )

        sb  = float(features["symmetry_bias"])
        t   = float(features["tension"])
        hs  = float(features["harmonic_stability"])
        hcr = float(features["harmonic_change_rate"])
        tc  = float(features["texture_complexity"])
        rd  = float(features["recursion_depth"])
        sc  = float(features["section_complexity"])
        nl  = float(features["noise_level"])

        raw = [
            sb  * (1.0 - t),          # θ_0 гармоническая чистота
            hs  * hcr,                # θ_1 динамика vs стабильность
            tc  * rd,                 # θ_2 структурная плотность
            t   * (1.0 - hs),         # θ_3 неразрешённое напряжение
            sc  * (1.0 - nl),         # θ_4 чистый контраст секций
            nl  * tc,                 # θ_5 тембральный хаос
            hcr * sc,                 # θ_6 энтропия развития
            sb  * hs * (1.0 - t),     # θ_7 «кристалличность» трека
        ]

        # clip на случай float-ошибок за пределами [0, 1]
        values = [max(0.0, min(1.0, v)) for v in raw]

        return HarmonyTheta(
            version=self.VERSION,
            algorithm=self.ALGORITHM,
            source_axes=HARMONY_AXES,
            values=values,
        )
