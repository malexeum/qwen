# ТЗ: Reference Renderer — Подфаза C1

**Статус:** следует после Generator Contract Lock (B1 ✅)
**Объект работы:** `lib/renderer/` + `lib/renderer/test_renderer.py`
**Вход:** `plan.json` (выход `CompositionPlanner`)
**Выход:** `preview_<plan_id>.png` 1024×1024 sRGB
**Версия:** C1.0

---

## 1. Цель

Reference renderer — это единственный Python-исполнитель плана. Его задача —
доказать, что `VisualCompositionPlan` превращается в наблюдаемое изображение
без амбиций художественного постпроцессинга.

Renderer **не является** production-рендером.
Он является эталоном, по которому позже будет выверен заказчик.

---

## 2. Архитектура

```
plan.json
    ↓
PlanLoader          — загрузка и валидация plan.json
    ↓
LayerExecutor       — для каждого enabled слоя:
    ├─ FractalLayerRunner   — вызывает generators.py (julia/ifs/duffing/scattering)
    └─ ProceduralLayerRunner — реализует orbital_field, colored_noise_field, symmetry_snowflake
    ↓
    ← возвращает numpy array [H, W, 4] в sRGB
    ↓
PaletteMapper       — применяет palette_id к orbit_map/visit_density
    ↓
BlendCompositor     — накладывает слои в порядке z_index через blend_mode
    ↓
SilenceMaskApplicator — накладывает silence_mask последним
    ↓
PNGExporter         — сохраняет PNG 1024×1024
```

---

## 3. Модули

| Модуль | Назначение |
|---|---|
| `lib/renderer/__init__.py` | Пакет |
| `lib/renderer/plan_loader.py` | Загрузка plan.json, проверка версии schema, валидация plan_id |
| `lib/renderer/fractal_runner.py` | Вызов `fractal_core.generators.*` через `SimState`, получение `RunResult` |
| `lib/renderer/procedural_runner.py` | Реализация orbital_field, colored_noise_field, symmetry_snowflake |
| `lib/renderer/theta_builder.py` | Преобразование `layer.params` из plan.json в `theta: list[float]` для `SimState` |
| `lib/renderer/palette_mapper.py` | Применение цветовой палитры к orbit_map → RGBA [H, W, 4] |
| `lib/renderer/blend_compositor.py` | Наложение слоёв в порядке z_index, реализация blend_mode |
| `lib/renderer/silence_mask.py` | Генерация и наложение silence_mask по coverage/direction/edge_softness |
| `lib/renderer/png_exporter.py` | Сохранение PNG, запись метаданных plan_id/profile/palette |
| `lib/renderer/reference_renderer.py` | Высокоуровневая точка входа: `render(plan_path) -> Path` |
| `lib/renderer/test_renderer.py` | Unit-тесты renderer |

---

## 4. Тета-модель theta_builder

`plan.json` хранит уже готовые числовые значения параметров (`layer.params`).
`theta_builder` преобразует их в позиционный вектор `theta: list[float]`,
принимаемый `SimState`.

### Порядок theta по генераторам

#### `julia_orbit_trap`
```
theta[0] = c_real
theta[1] = c_imag
theta[2] = exponent_p
theta[3] = trap_radius
# theta[4] = trap_center_real (0.0 if absent)
# theta[5] = trap_center_imag (0.0 if absent)
```
`SimState.max_iter` ← `max_iter`
`SimState.stochastic_scale` ← `stochastic_scale`
`SimState.domain` ← `[-domain_zoom, domain_zoom, -domain_zoom, domain_zoom]`

#### `orbit_ifs_multi_trap`
```
# theta не используется напрямую
```
`SimState.extra["n_points"]` ← `n_points`
`SimState.extra["map_diversity"]` ← `map_diversity`
`SimState.extra["attractor_spread"]` ← `attractor_spread`
`SimState.extra["n_iter"]` ← на `SimState.max_iter`
`SimState.stochastic_scale` ← `stochastic_scale`

#### `duffing_lyapunov`
```
theta[0] = damping           # delta параметризация: (param - 0.1) / 0.25
theta[1] = nonlinear_stiffness  # beta
theta[2] = forcing           # gamma0
theta[3] = forcing_frequency    # omega0
```
`SimState.extra["n_steps"]` ← `n_steps`
`SimState.stochastic_scale` ← `stochastic_scale`
`SimState.domain` ← варьируется через `gamma_window`/`omega_window`

#### `chaotic_scattering_basins`
```
theta[0] = scatterer_radius   # radius = 0.15 + 0.05*th0, параметризация: (param - 0.15) / 0.05
theta[1] = center_phase_offset # сдвиг фазы центров
theta[2] = center_radius       # r = 0.7 + 0.2*th2, параметризация: (param - 0.7) / 0.2
theta[3] = initial_velocity_x  # vx0 = 0.02 * (1 + 0.5*th3)
theta[4] = initial_velocity_y  # vy0 = 0.015 * (1 + 0.5*th4)
```
`SimState.max_iter` ← `max_steps`
`SimState.stochastic_scale` ← `stochastic_scale`

---

## 5. Procedural runners

Три процедурных генератора не имеют SimState. Каждый
возвращает `np.ndarray [H, W]` float32 в `[0, 1]` (аналог orbit_map)
для палитры и композиции.

### `orbital_field`

```python
def run_orbital_field(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params keys: flow_speed, orbit_radius, line_count,
                 amplitude, angular_break, rotation_deg
    """
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), dtype=np.float32)
    n = int(np.clip(params["line_count"] * 120 + 40, 40, 200))
    for _ in range(n):
        x0 = rng.uniform(-1.0, 1.0)
        y0 = rng.uniform(-1.0, 1.0)
        angle = rng.uniform(0, 2 * np.pi)
        for step in range(int(params["flow_speed"] * 400 + 100)):
            r = np.sqrt(x0 ** 2 + y0 ** 2) + 1e-9
            dr = -params["amplitude"] * 0.02
            dtheta = (params["angular_break"] * 0.5 + 0.5) / r
            x0 += dr * np.cos(angle) - dtheta * np.sin(angle)
            y0 += dr * np.sin(angle) + dtheta * np.cos(angle)
            ix = int((x0 + 1.0) / 2.0 * (W - 1))
            iy = int((y0 + 1.0) / 2.0 * (H - 1))
            if 0 <= ix < W and 0 <= iy < H:
                canvas[iy, ix] += 1.0
    canvas = np.log1p(canvas)
    canvas /= (canvas.max() + 1e-9)
    return canvas.astype(np.float32)
```

### `colored_noise_field`

```python
def run_colored_noise_field(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params keys: amplitude, frequency_scale, anisotropy,
                 grain_size, color_variation (optional)
    """
    rng = np.random.default_rng(seed)
    freqs = int(np.clip(params["frequency_scale"] * 8 + 2, 2, 12))
    canvas = np.zeros((H, W), dtype=np.float32)
    for f in range(1, freqs + 1):
        layer = rng.standard_normal((H, W)).astype(np.float32)
        sigma = max(1.0, params["grain_size"] * 8 * (1.0 / f))
        from scipy.ndimage import gaussian_filter
        layer = gaussian_filter(layer, sigma=sigma)
        aniso_scale = 1.0 + params["anisotropy"] * (f - 1)
        canvas += layer / aniso_scale
    canvas = canvas - canvas.min()
    canvas = canvas / (canvas.max() + 1e-9)
    canvas = canvas * params["amplitude"]
    return np.clip(canvas, 0.0, 1.0).astype(np.float32)
```

### `symmetry_snowflake`

```python
def run_symmetry_snowflake(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    """
    params keys: branch_count, branch_depth, branch_jitter,
                 radial_scale, rotation_deg
    """
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), dtype=np.float32)
    n_branches = max(3, int(params["branch_count"] * 10 + 3))
    depth = max(1, int(params["branch_depth"] * 5 + 1))
    base_angle = np.radians(params.get("rotation_deg", 0.0))
    scale = params["radial_scale"] * 0.8 + 0.1
    jitter = params["branch_jitter"] * 0.15

    def draw_branch(cx, cy, angle, length, d):
        if d == 0 or length < 2:
            return
        ex = cx + length * np.cos(angle)
        ey = cy + length * np.sin(angle)
        steps = int(length * 3)
        for t in range(steps):
            fx = cx + (ex - cx) * t / steps
            fy = cy + (ey - cy) * t / steps
            ix = int((fx + 1.0) / 2.0 * (W - 1))
            iy = int((fy + 1.0) / 2.0 * (H - 1))
            if 0 <= ix < W and 0 <= iy < H:
                canvas[iy, ix] += 1.0 / (depth - d + 1)
        j = rng.uniform(-jitter, jitter)
        draw_branch(ex, ey, angle + np.pi / 6 + j, length * 0.6, d - 1)
        draw_branch(ex, ey, angle - np.pi / 6 + j, length * 0.6, d - 1)

    for k in range(n_branches):
        angle = base_angle + 2 * np.pi * k / n_branches
        draw_branch(0.0, 0.0, angle, scale * 0.9, depth)

    canvas = canvas / (canvas.max() + 1e-9)
    return canvas.astype(np.float32)
```

---

## 6. Palette Mapper

```python
def apply_palette(orbit_map: np.ndarray, palette: dict) -> np.ndarray:
    """
    orbit_map: float32 [H, W] in [0, 1]
    palette:   стопы из palettes.yaml {'dominant_stops': [{position, color}, ...]}
    возвращает: uint8 [H, W, 4] RGBA
    """
    stops = palette["dominant_stops"]
    positions = np.array([s["position"] for s in stops], dtype=np.float32)
    colors = np.array([
        [int(s["color"][1:3], 16),
         int(s["color"][3:5], 16),
         int(s["color"][5:7], 16)] for s in stops
    ], dtype=np.float32)
    H, W = orbit_map.shape
    result = np.zeros((H, W, 4), dtype=np.uint8)
    flat = orbit_map.ravel()
    for i, v in enumerate(flat):
        idx = np.searchsorted(positions, v) - 1
        idx = np.clip(idx, 0, len(stops) - 2)
        t = (v - positions[idx]) / (positions[idx + 1] - positions[idx] + 1e-9)
        t = np.clip(t, 0.0, 1.0)
        rgb = colors[idx] * (1 - t) + colors[idx + 1] * t
        result.reshape(-1, 4)[i, :3] = rgb.astype(np.uint8)
        result.reshape(-1, 4)[i, 3] = 255
    return result
```

> Замечание: векторизованная реализация через `np.interp` по каждому каналу RGB
будет быстрее, чем цикл by pixel. Используй `np.interp(flat, positions, colors[:, c])`.

---

## 7. Blend Compositor

Реализуем только разрешённые blend_modes из `global_rules`:

| Blend mode | Формула (float32 [0,1]) |
|---|---|
| `normal` | `dst = src × opacity + dst × (1 - opacity)` |
| `screen` | `1 - (1 - src) × (1 - dst)`, затем opacity |
| `add` | `clip(src × opacity + dst, 0, 1)` |
| `multiply` | `src × dst`, затем opacity |
| `soft_light` | стандартная формула soft light PS |
| `max` | `np.maximum(src, dst)`, затем opacity |

Наложение выполняется в порядке возрастания z_index. `silence_mask` применяется
после всех остальных слоёв отдельным проходом.

---

## 8. Silence Mask

```python
def build_silence_mask(
    coverage: float,        # [0, 1] ← silence_rate
    direction: float,       # [0, 1] ← layout_macro_shape (0=top, 0.5=center, 1=bottom)
    edge_softness: float,   # [0, 1] ← tension
    W: int, H: int
) -> np.ndarray:            # float32 [H, W], 0=чёрный, 1=прозрачный
    """
    Градиентная маска по вертикали. coverage определяет долю
    затемнённой области, direction сдвигает её по высоте,
    edge_softness управляет sigma гауссовой размывки границы.
    """
```

---

## 9. Точка входа

```python
# lib/renderer/reference_renderer.py

def render(plan_path: str | Path, output_dir: str | Path = "output/previews") -> Path:
    """
    Вход:  plan_path — путь к plan.json
    Выход: путь к preview_<plan_id>.png

    Правила:
    - Размер холста: читается из plan.canvas.width_px / height_px
    - Каждый слой выполняется на computation_resolution_fraction от полного размера,
      затем upscale до 1024×1024
    - rotation_range_deg: используется средина диапазона как base_rotation
    - enabled_if: plan.json уже содержит вычисленный флаг enabled,
      рендерер просто пропускает слои с enabled=false
    - Постпроцессинг в C1 не реализуется
    """
```

---

## 10. Unit-тесты

| Тест | Что проверяется |
|---|---|
| `test_plan_loader_valid` | plan.json загружается, plan_id совпадает |
| `test_theta_builder_julia` | theta[0..3] соответствуют значениям из plan |
| `test_theta_builder_scattering` | та же для scattering, нет Duffing-ключей |
| `test_fractal_runner_output_shape` | `RunResult.orbit_map.shape == (H*frac, W*frac)` |
| `test_procedural_runner_shape` | все 3 procedural возвращают `[H, W]` float32 в [0,1] |
| `test_palette_mapper_output` | uint8 RGBA [H, W, 4], alpha=255 везде |
| `test_blend_modes_all` | каждый из 6 blend_mode работает без ошибок |
| `test_silence_mask_coverage` | фактическое покрытие маски соответствует coverage ±0.03 |
| `test_render_output_shape` | `render(plan_path)` возвращает Path к PNG |
| `test_render_png_size` | PNG размер 1024×1024 |
| `test_render_deterministic` | два вызова с одинаковым plan.json дают идентичные PNG |
| `test_render_all_profiles` | 5 профилей проходят без исключений |

### Команда полного прогона

```bat
python -m pytest lib/renderer/test_renderer.py -v
```

---

## 11. Критерий закрытия C1

- [ ] все unit-тесты из раздела 10 зелёные
- [ ] `render(plan_path)` отрабатывает без исключений для всех 5 профилей
- [ ] PNG 1024×1024 sRGB сохраняется в `output/previews/`
- [ ] два вызова с одинаковым plan.json дают байт-идентичные PNG
- [ ] 5 × PNG визуально отличаются друг от друга (визуальная приёмка)
- [ ] прогон до полного pytest: `lib/composition/ + lib/renderer/` всё зелёное

---

## 12. Чего в C1 не бывает

- Постпроцессинг (grainfilm, fullcolor) — отдельная подфаза
- Обученный маппинг признаков — после E2E-валидации
- Пользовательские пресеты — `allow_user_presets: false` в plan
- Экспорт финального PNG в production-качестве — `allow_final_export: false` в plan
