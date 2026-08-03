"""
Fractal Harmony Engine — core library (v2).
State/Generator/Feature architecture for H -> F(H, theta) nonlinear mapping.
v2: обучаемая проекция HarmonyEncoder (векторизованный градиент) + стохастический член в State.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple
import hashlib

@dataclass
class Harmony:
    spectral_profile: np.ndarray
    freq_ratios: np.ndarray
    rhythmic_period: float
    repetition_coeff: float
    tension: float
    symmetry: float
    density: float
    contrast: float

    def as_vector(self) -> np.ndarray:
        return np.concatenate([
            self.spectral_profile / (np.linalg.norm(self.spectral_profile) + 1e-9),
            self.freq_ratios,
            [self.rhythmic_period, self.repetition_coeff, self.tension,
             self.symmetry, self.density, self.contrast]
        ])

    def stable_hash(self) -> int:
        v = np.round(self.as_vector(), 6).tobytes()
        return int(hashlib.sha256(v).hexdigest()[:8], 16)


class HarmonyEncoder:
    """
    v2: обучаемая линейная+tanh проекция W,b, оптимизированная контрастной функцией потерь
    (within-class distance -> min, between-class distance -> max, с margin).
    Градиент вычисляется аналитически (векторизовано), без сторонних ML-библиотек.
    Fallback: если fit() не вызван, используется детерминированная случайная проекция (как в v1).
    """
    def __init__(self, seed: int = 12345):
        self.rng = np.random.default_rng(seed)
        self.W = None
        self.b = None
        self.trained = False
        self.loss_history = []

    def _ensure_fallback_proj(self, dim_in: int, dim_out: int):
        if self.W is None or self.W.shape != (dim_out, dim_in):
            local_rng = np.random.default_rng(999)
            self.W = local_rng.normal(0, 1, size=(dim_out, dim_in)) / np.sqrt(dim_in)
            self.b = np.zeros(dim_out)

    def encode(self, h: Harmony, dim_out: int = 6) -> np.ndarray:
        v = h.as_vector()
        self._ensure_fallback_proj(len(v), dim_out)
        raw = self.W @ v + self.b
        return np.tanh(raw)

    def fit(self, harmonies_by_class: Dict[str, list], dim_out: int = 6,
            lr: float = 0.1, epochs: int = 400, margin: float = 2.5, seed: int = 0):
        """
        Аналитический (векторизованный) контрастный градиентный спуск.
        L = mean_within(||t_i - t_j||^2) + mean_between(relu(margin - ||t_i - t_j||)^2)
        """
        rng = np.random.default_rng(seed)
        vectors, labels = [], []
        for lbl, hs in harmonies_by_class.items():
            for h in hs:
                vectors.append(h.as_vector())
                labels.append(lbl)
        X = np.array(vectors)
        labels = np.array(labels)
        N, dim_in = X.shape

        same = (labels[:, None] == labels[None, :])
        iu = np.triu_indices(N, k=1)
        same_pairs = same[iu]

        self.W = rng.normal(0, 1, size=(dim_out, dim_in)) / np.sqrt(dim_in)
        self.b = np.zeros(dim_out)

        history = []
        for epoch in range(epochs):
            Z = X @ self.W.T + self.b
            T = np.tanh(Z)
            diff = T[iu[0]] - T[iu[1]]
            dist2 = np.sum(diff ** 2, axis=1)
            dist = np.sqrt(dist2 + 1e-12)

            within_mask = same_pairs
            between_mask = ~same_pairs
            n_within = max(within_mask.sum(), 1)
            n_between = max(between_mask.sum(), 1)

            loss_within = np.sum(dist2[within_mask]) / n_within
            hinge = np.maximum(0.0, margin - dist[between_mask])
            loss_between = np.sum(hinge ** 2) / n_between
            loss = loss_within + loss_between
            history.append(float(loss))

            dL_dT = np.zeros_like(T)
            w_idx = np.where(within_mask)[0]
            if len(w_idx) > 0:
                contrib = 2.0 * diff[w_idx] / n_within
                np.add.at(dL_dT, iu[0][w_idx], contrib)
                np.add.at(dL_dT, iu[1][w_idx], -contrib)
            b_idx = np.where(between_mask)[0]
            if len(b_idx) > 0:
                h_vals = np.maximum(0.0, margin - dist[b_idx])
                active = h_vals > 0
                if active.any():
                    idxa = b_idx[active]
                    coeff = (-2.0 * h_vals[active] / (dist[idxa] + 1e-12) / n_between)[:, None]
                    contrib = coeff * diff[idxa]
                    np.add.at(dL_dT, iu[0][idxa], contrib)
                    np.add.at(dL_dT, iu[1][idxa], -contrib)

            dT_dZ = (1.0 - T ** 2)
            dL_dZ = dL_dT * dT_dZ
            gW = dL_dZ.T @ X
            gb = dL_dZ.sum(axis=0)

            self.W -= lr * gW
            self.b -= lr * gb

        self.trained = True
        self.loss_history = history
        return history

    def variant(self, h: Harmony, noise_scale: float, rng: np.random.Generator) -> Harmony:
        v = h.as_vector()
        noise = rng.normal(0, noise_scale, size=v.shape)
        n_spec = len(h.spectral_profile)
        n_ratio = len(h.freq_ratios)
        vv = v + noise
        return Harmony(
            spectral_profile=np.abs(vv[:n_spec]),
            freq_ratios=np.abs(vv[n_spec:n_spec+n_ratio]),
            rhythmic_period=max(1e-3, vv[n_spec+n_ratio]),
            repetition_coeff=np.clip(vv[n_spec+n_ratio+1], 0, 1),
            tension=np.clip(vv[n_spec+n_ratio+2], 0, 1),
            symmetry=np.clip(vv[n_spec+n_ratio+3], -1, 1),
            density=np.clip(vv[n_spec+n_ratio+4], 0, 1),
            contrast=np.clip(vv[n_spec+n_ratio+5], 0, 1),
        )


@dataclass
class SimState:
    generator_name: str
    theta: np.ndarray
    resolution: Tuple[int, int] = (400, 400)
    domain: Tuple[float, float, float, float] = (-2.0, 2.0, -2.0, 2.0)
    max_iter: int = 200
    escape_radius: float = 4.0
    trap_kind: str = "point"
    seed: int = 0
    stochastic_scale: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    orbit_map: np.ndarray
    visit_density: np.ndarray
    aux: Dict[str, Any] = field(default_factory=dict)
