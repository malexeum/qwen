"""
lib/style_engine/generator_runtime.py

Step B: GeneratorRuntime — чистый adapter/runtime boundary.

  StyleEngine (engine.py)  ──►  GeneratorRuntime  ──►  lib.generators (backend)

Правила:
  - lib/generators.py не трогать, не копировать, не переопределять.
  - generator_stack в RenderResult — журнал ФАКТИЧЕСКИ вызванных builders,
    не декларация из YAML.
  - На этапе A1 generator_id был None в MappingTraceEntry;
    здесь он заполняется при рендере.

Зависимости:
  lib.core        → SimState, RunResult
  lib.generators  → julia_orbit_trap, orbit_ifs_multi_trap,
                     duffing_lyapunov_map, chaotic_scattering_basins
  lib.style_engine.engine → RenderParams, MappingTraceEntry
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any

from lib.core import SimState, RunResult
import lib.generators as generator_backend
from lib.style_engine.engine import RenderParams


# ---------------------------------------------------------------------------
# Реестр builders: имя → callable(SimState) -> RunResult
# Только то, что реально экспортирует lib/generators.py.
# ---------------------------------------------------------------------------
_BUILDER_REGISTRY: dict[str, Any] = {
    "julia_orbit_trap":         generator_backend.julia_orbit_trap,
    "orbit_ifs_multi_trap":     generator_backend.orbit_ifs_multi_trap,
    "duffing_lyapunov_map":     generator_backend.duffing_lyapunov_map,
    "chaotic_scattering_basins": generator_backend.chaotic_scattering_basins,
}

# Порядок θ-осей как требует lib.generators (8 осей → numpy float array)
_THETA_ORDER: tuple[str, ...] = (
    "harmony_theta_0",
    "harmony_theta_1",
    "harmony_theta_2",
    "harmony_theta_3",
    "harmony_theta_4",
    "harmony_theta_5",
    "harmony_theta_6",
    "harmony_theta_7",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ResolvedGeneratorLayer:
    """
    Один разрешённый слой: bridge между StyleEngine и конкретным builder.

    Контракт (из спецификации):
      layer_id        — уникальный ID слоя в composition
      generator_id    — совпадает с builder (для трассировки)
      builder         — имя функции в _BUILDER_REGISTRY
      palette_id      — ID палитры (может быть None)
      resolved_mapping — финальные float-параметры после StyleEngine
      source_axes     — θ-оси, участвовавшие в маппинге этого слоя
    """
    layer_id: str
    generator_id: str
    builder: str
    palette_id: str | None
    resolved_mapping: dict[str, float | int]
    source_axes: list[str]


@dataclass
class RenderResult:
    """
    Результат рендера одного или нескольких слоёв.

    orbit_map       — финальная карта (H×W float32), смешение всех слоёв
    visit_density   — карта посещаемости последнего слоя
    generator_stack — ЖУРНАЛ фактически вызванных builders (не декларация!)
    layer_results   — сырые RunResult по каждому слою (для отладки)
    aux             — дополнительные поля от builders
    """
    orbit_map: np.ndarray
    visit_density: np.ndarray
    generator_stack: list[str]          # фактический порядок вызовов
    layer_results: list[RunResult] = field(default_factory=list, repr=False)
    aux: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# GeneratorRuntime
# ---------------------------------------------------------------------------

class GeneratorRuntime:
    """
    Adapter: StyleEngine RenderParams + composition_profile  →  lib.generators call.

    Использование:
        runtime = GeneratorRuntime()
        layers  = runtime.resolve_stack(profile_slug, render_params, composition_profile)
        result  = runtime.render(layers, seed, width, height)
        # result.generator_stack содержит фактически вызванные builders
    """

    # Разрешение по умолчанию (можно переопределить)
    DEFAULT_RESOLUTION: tuple[int, int] = (256, 256)
    DEFAULT_DOMAIN: tuple[float, float, float, float] = (-2.0, 2.0, -2.0, 2.0)
    DEFAULT_MAX_ITER: int = 200
    DEFAULT_ESCAPE_RADIUS: float = 4.0

    def resolve_stack(
        self,
        profile_slug: str,
        render_params: RenderParams,
        composition_profile: dict,
    ) -> list[ResolvedGeneratorLayer]:
        """
        Строит список ResolvedGeneratorLayer из composition_profile YAML-словаря.

        Ожидаемый формат composition_profile:
            layers:
              - id: "layer_0"
                builder: "julia_orbit_trap"
                palette_id: "default_dark"
                weight: 1.0          # для смешения при render (опционально)

        RenderParams используется для заполнения resolved_mapping и source_axes.
        """
        layers_cfg: list[dict] = (
            composition_profile.get("layers", []) if composition_profile else []
        )

        # Собираем θ-snapshot из render_params
        theta_snapshot: dict[str, float] = {
            ax: float(getattr(render_params, ax, 0.5))
            for ax in _THETA_ORDER
        }

        # Собираем перцептивный snapshot из trace (все perceptual-записи)
        perceptual_snapshot: dict[str, float] = {}
        for entry in render_params.mapping_trace:
            if entry.stage == "perceptual":
                perceptual_snapshot[entry.param] = entry.final
                for ax, val in entry.input_values.items():
                    perceptual_snapshot.setdefault(ax, val)

        resolved_layers: list[ResolvedGeneratorLayer] = []

        for i, layer_cfg in enumerate(layers_cfg):
            layer_id    = str(layer_cfg.get("id", f"layer_{i}"))
            builder     = str(layer_cfg.get("builder", "julia_orbit_trap"))
            palette_id  = layer_cfg.get("palette_id") or render_params.palette_id

            if builder not in _BUILDER_REGISTRY:
                raise ValueError(
                    f"GeneratorRuntime.resolve_stack: unknown builder '{builder}'. "
                    f"Available: {sorted(_BUILDER_REGISTRY.keys())}"
                )

            # resolved_mapping: финальные значения из StyleEngine + theta
            resolved_mapping: dict[str, float | int] = {
                "symmetry_bias":      render_params.symmetry_bias,
                "recursion_depth":    render_params.recursion_depth,
                "density_level":      render_params.density_level,
                "noise_level":        render_params.noise_level,
                "motion_intensity":   render_params.motion_intensity,
                "texture_complexity": render_params.texture_complexity,
                **theta_snapshot,
            }

            # source_axes: все θ-оси, упоминавшиеся в trace для этого слоя
            layer_source_axes: list[str] = []
            seen: set[str] = set()
            for entry in render_params.mapping_trace:
                if entry.stage == "perceptual":
                    for ax in (entry.source_axes or []):
                        if ax not in seen:
                            layer_source_axes.append(ax)
                            seen.add(ax)

            resolved_layers.append(ResolvedGeneratorLayer(
                layer_id=layer_id,
                generator_id=builder,   # generator_id = builder name
                builder=builder,
                palette_id=palette_id,
                resolved_mapping=resolved_mapping,
                source_axes=layer_source_axes,
            ))

        return resolved_layers

    def render(
        self,
        layers: list[ResolvedGeneratorLayer],
        seed: int,
        width: int,
        height: int,
        domain: tuple[float, float, float, float] | None = None,
        max_iter: int | None = None,
        escape_radius: float | None = None,
        stochastic_scale: float = 0.0,
    ) -> RenderResult:
        """
        Вызывает lib.generators для каждого ResolvedGeneratorLayer.

        ВАЖНО: generator_stack формируется ТОЛЬКО по фактически вызванным builders.
        Порядок записей = порядок реального исполнения.
        """
        if not layers:
            empty = np.zeros((height, width), dtype=np.float32)
            return RenderResult(
                orbit_map=empty,
                visit_density=empty,
                generator_stack=[],
            )

        resolution = (width, height)
        domain_use = domain or self.DEFAULT_DOMAIN
        max_iter_use = max_iter or self.DEFAULT_MAX_ITER
        esc_use = escape_radius or self.DEFAULT_ESCAPE_RADIUS

        layer_results: list[RunResult] = []
        generator_stack: list[str] = []          # журнал фактического исполнения

        for layer in layers:
            builder_fn = _BUILDER_REGISTRY[layer.builder]

            # Строим theta-вектор в каноническом порядке для lib.generators
            theta_arr = np.array([
                float(layer.resolved_mapping.get(ax, 0.5))
                for ax in _THETA_ORDER
            ], dtype=np.float64)

            # stochastic_scale из noise_level (0→0.0, 1→0.05 — мягкий маппинг)
            noise_lv = float(layer.resolved_mapping.get("noise_level", 0.0))
            s_scale = stochastic_scale if stochastic_scale > 0.0 else noise_lv * 0.05

            state = SimState(
                generator_name=layer.builder,
                theta=theta_arr,
                resolution=resolution,
                domain=domain_use,
                max_iter=max_iter_use,
                escape_radius=esc_use,
                seed=seed,
                stochastic_scale=s_scale,
                extra={},
            )

            # --- фактический вызов backend ---
            result: RunResult = builder_fn(state)

            # Записываем в журнал ПОСЛЕ успешного вызова
            generator_stack.append(layer.builder)
            layer_results.append(result)

        # Смешение слоёв: равновесное среднее orbit_map
        maps = [r.orbit_map for r in layer_results]
        if len(maps) == 1:
            combined = maps[0].astype(np.float32)
        else:
            stacked = np.stack([m.astype(np.float32) for m in maps], axis=0)
            combined = stacked.mean(axis=0)

        # Нормировка [0, 1]
        mn, mx = combined.min(), combined.max()
        if mx > mn:
            combined = (combined - mn) / (mx - mn)

        last_visit = layer_results[-1].visit_density.astype(np.float32)

        return RenderResult(
            orbit_map=combined,
            visit_density=last_visit,
            generator_stack=generator_stack,
            layer_results=layer_results,
            aux={"n_layers": len(layers)},
        )
