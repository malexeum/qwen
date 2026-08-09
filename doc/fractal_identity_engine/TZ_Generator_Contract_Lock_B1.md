# ТЗ: Generator Contract Lock — Подфаза B1

**Статус:** обязательная подфаза перед Python reference renderer  
**Блокирует:** рендер 1024×1024, новые художественные эффекты  
**Версия:** B1.0

---

## Цель

Превратить `generator_catalog.yaml` из декларации намерений в фактический контракт
между planner-ом и builder-ами. После завершения B1 каждый `mapping:` target в
`visual_composition_profiles.yaml` должен быть верифицирован против реальной
сигнатуры соответствующего builder/renderer.

---

## 1. Сверить реальные сигнатуры

Программист обязан открыть исходный код и зафиксировать фактические параметры
для каждого из следующих builder-ов:

| Builder | Функция / класс |
|---|---|
| `julia_orbit_trap` | `make_sim_state_for_julia` / `julia_orbit_trap()` |
| `orbit_ifs_multi_trap` | `make_sim_state_for_ifs` / `orbit_ifs_multi_trap()` |
| `duffing_lyapunov` | `make_sim_state_for_duffing` / `duffing_lyapunov_map()` |
| `chaotic_scattering_basins` | `make_sim_state_for_scattering` / `chaotic_scattering_basins()` |
| `orbital_field` | procedural spec — определить как `ProcLayerSpec` |
| `colored_noise_field` | procedural spec — определить как `ProcLayerSpec` |
| `symmetry_snowflake` | procedural spec — определить как `ProcLayerSpec` |

---

## 2. Добавить раздел `parameters` в `generator_catalog.yaml`

Не предполагаемые — реально поддерживаемые targets. Для каждого параметра указать
тип, диапазон, единицу и обязательность.

### Пример для `julia_orbit_trap`

```yaml
julia_orbit_trap:
  canonical_id: julia_orbit_trap
  builder_id: julia_v1
  parameters:
    c_real:
      type: float
      range: [-1.5, 1.5]
      unit: normalized
      required: true
    c_imag:
      type: float
      range: [-1.5, 1.5]
      unit: normalized
      required: true
    exponent_p:
      type: float
      range: [1.5, 5.0]
      unit: scalar
      required: true
    trap_radius:
      type: float
      range: [0.01, 1.0]
      unit: domain_units
      required: true
    max_iter:
      type: integer
      range: [32, 2048]
      unit: iterations
      required: true
    stochastic_scale:
      type: float
      range: [0.0, 0.05]
      unit: normalized
      required: false
    domain_zoom:
      type: float
      range: [0.5, 4.0]
      unit: scalar
      required: false
```

### Пример для `chaotic_scattering_basins`

```yaml
chaotic_scattering_basins:
  canonical_id: chaotic_scattering_basins
  builder_id: scattering_v1
  parameters:
    scatterer_radius:
      type: float
      range: [0.05, 0.35]
      unit: domain_units
      required: true
    center_phase_offset:
      type: float
      range: [0.0, 1.0]
      unit: normalized
      required: false
    center_radius:
      type: float
      range: [0.3, 1.0]
      unit: domain_units
      required: false
    initial_velocity_x:
      type: float
      range: [0.0, 0.1]
      unit: domain_units_per_step
      required: true
    initial_velocity_y:
      type: float
      range: [0.0, 0.1]
      unit: domain_units_per_step
      required: false
    max_steps:
      type: integer
      range: [200, 2000]
      unit: steps
      required: true
    stochastic_scale:
      type: float
      range: [0.0, 0.05]
      unit: normalized
      required: false
```

---

## 3. Усилить `_validate_profiles()` в `config_loader.py`

```python
def _validate_profiles(self, profiles: dict, catalog: dict) -> None:
    for profile_slug, profile in profiles.items():
        for layer in profile.get("layers", []):
            layer_id = layer.get("id", "<unknown>")
            generator_id = layer.get("generator_id")

            # Пропускаем procedural_mask — у него нет catalog entry
            if layer.get("source_kind") == "procedural_mask":
                continue

            if generator_id not in catalog:
                raise CompositionConfigError(
                    f"profile={profile_slug}; layer={layer_id}: "
                    f"unknown generator_id='{generator_id}'"
                )

            generator_spec = catalog[generator_id]
            known_targets = set(generator_spec.get("parameters", {}).keys())
            mapping_targets = set(layer.get("mapping", {}).keys())

            # Прямая проверка: mapping target должен существовать в catalog
            unknown_targets = mapping_targets - known_targets
            if unknown_targets:
                raise CompositionConfigError(
                    f"profile={profile_slug}; layer={layer_id}; "
                    f"generator={generator_id}; "
                    f"unsupported mapping targets={sorted(unknown_targets)}"
                )

            # Обратная проверка: каждый required параметр должен быть покрыт
            for param_name, param_spec in generator_spec.get("parameters", {}).items():
                if param_spec.get("required", False):
                    if param_name not in mapping_targets:
                        has_default = "builder_default" in param_spec
                        if not has_default:
                            raise CompositionConfigError(
                                f"profile={profile_slug}; layer={layer_id}; "
                                f"generator={generator_id}: "
                                f"required parameter '{param_name}' not in mapping "
                                f"and has no builder_default"
                            )
```

---

## 4. Семантический уровень mapping (архитектурная цель)

Текущий плоский формат `mapping: target: source` допустим для Python v0.3.
Но архитектурная цель — разделить **semantic control** (язык профиля) и
**builder parameter** (язык Python/Java реализации).

### Правильная форма в профиле

```yaml
mapping:
  basin_separation:
    source: tension
    mapper: tension_to_basin_bias

  local_instability:
    source: motion_intensity
    mapper: motion_to_scattering_perturbation

  boundary_complexity:
    source: texture_complexity
    mapper: complexity_to_scattering_detail
```

### Соответствующая запись в catalog

```yaml
chaotic_scattering_basins:
  semantic_controls:
    basin_separation:
      builder_parameter: scatterer_radius
      description: "Визуальный разлом между бассейнами притяжения"
    local_instability:
      builder_parameter: initial_velocity_x
      description: "Локальная неустойчивость траекторий"
    boundary_complexity:
      builder_parameter: center_radius
      description: "Сложность границ бассейнов"
```

**Почему это важно:**
- Профиль говорит языком композиции: «дать больше разлома и неустойчивости»
- Builder переводит это на язык математики: `scatterer_radius`, `initial_velocity_x`
- Java-реализация позже может исполнить те же semantic controls иначе (шейдером,
  полем, другой оптимизацией) — не меняя художественный YAML

Переход к semantic mapping — **следующая итерация** после B1. В B1 достаточно
плоского контракта с проверкой типов и диапазонов.

---

## 5. Unit-тесты (обязательный набор)

| Тест | Что проверяется | Файл |
|---|---|---|
| `test_all_mapping_targets_known` | Каждый `mapping` target присутствует в catalog | `test_composition.py` |
| `test_required_params_covered` | Каждый `required` param покрыт mapping или builder_default | `test_composition.py` |
| `test_layer_to_sim_state` | Каждый enabled layer без procedural_mask можно превратить в SimState | `test_planner_v03.py` |
| `test_jazz_no_duffing_targets` | `jazz` / `scatter_base` не использует `forcing`, `damping`, `forcing_frequency`, `nonlinear_stiffness` | `test_composition.py` |
| `test_classical_palette_not_gold_only` | `classical` / `classical_structure` использует `ivory_cobalt`, не `pale_gold_accent` | `test_composition.py` |

---

## 6. Исправления профилей по итогам B1

### 6.1. `jazz` — scattering-native mapping (критический)

Заменить в `scatter_base` слое:

```yaml
# БЫЛО (неверно — Duffing targets):
mapping:
  forcing: energy
  damping: tension
  forcing_frequency: motion_intensity
  nonlinear_stiffness: texture_complexity
  n_steps: recursion_depth
  stochastic_scale: noise_level
  gamma_window: density_level
  omega_window: density_level

# СТАЛО (scattering-native):
mapping:
  scatterer_radius: density_level
  center_phase_offset: symmetry_bias
  center_radius: texture_complexity
  initial_velocity_x: energy
  initial_velocity_y: motion_intensity
  max_steps: recursion_depth
  stochastic_scale: noise_level
```

### 6.2. `classical` — базовая палитра (художественный блокер)

`pale_gold_accent` — прозрачная акцентная палитра. Использовать как основную
палитру для `classical_structure` нельзя.

Добавить в `palettes.yaml`:

```yaml
ivory_cobalt:
  family: classical
  background_rgba: [20, 23, 27, 255]
  dominant_stops:
    - { position: 0.00, color: "#111820" }
    - { position: 0.42, color: "#314F78" }
    - { position: 0.76, color: "#B8C9D7" }
    - { position: 1.00, color: "#F0E8D8" }
  accent_color: "#C89B43"
  saturation_budget: 0.42
  contrast: 1.08
  luminance_gamma: 0.98
```

Обновить `classical_structure.palette_id: ivory_cobalt`.

---

## 7. Порядок выполнения

```
1. git pull / sync с origin/main
2. Сверить сигнатуры builders → зафиксировать реальные параметры
3. Обновить generator_catalog.yaml (раздел parameters)
4. Обновить _validate_profiles() в config_loader.py
5. Исправить jazz profile (scattering-native mapping)
6. Добавить ivory_cobalt в palettes.yaml
7. Обновить classical profile (palette_id: ivory_cobalt)
8. Запустить полный pytest:

   python -m pytest lib/composition/test_composition.py \
                    lib/composition/test_planner_v03.py \
                    lib/test_integration_e2e.py -v

9. Собрать plan.json для каждого из 5 профилей (без PNG)
10. ✅ Generator Contract Lock закрыт — переходить к Python reference renderer
```

---

## 8. Критерий закрытия B1

- [ ] `generator_catalog.yaml` содержит `parameters` для всех 7 generators
- [ ] `_validate_profiles()` бросает `CompositionConfigError` на неизвестный target
- [ ] Все 5 unit-тестов из раздела 5 проходят зелёным
- [ ] `jazz` не содержит Duffing targets в `scatter_base`
- [ ] `classical` использует `ivory_cobalt` как основную палитру
- [ ] Полный pytest зелёный (0 failed, 0 errors)
- [ ] 5 × `plan.json` собраны и сохранены в `output/plans/`
