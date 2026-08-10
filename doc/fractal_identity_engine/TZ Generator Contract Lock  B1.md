Перед Python reference renderer вводим обязательную подфазу B1: Generator Contract Lock.

Не начинать рендер 1024×1024 и не делать новые художественные эффекты, пока каталог не станет фактическим договором между planner и builder-ами.

Что должен сделать программист
Сверить реальные сигнатуры:

make_sim_state_for_julia;

make_sim_state_for_ifs;

make_sim_state_for_duffing;

make_sim_state_for_scattering;

будущие procedural builders: orbital_field, colored_noise_field, symmetry_snowflake.

Добавить в generator_catalog.yaml раздел parameters — не предполагаемые, а реально поддерживаемые builder targets.

Добавить метаданные типов, единиц и диапазонов:

text

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
Изменить _validate_profiles():

python

unknown_targets = (
    set(layer.get("mapping", {}))
    - set(generator_spec["parameters"])
)

if unknown_targets:
    raise CompositionConfigError(
        f"profile={profile_slug}; layer={layer_id}; "
        f"generator={generator_id}; "
        f"unsupported mapping targets={sorted(unknown_targets)}"
    )
Добавить обратную проверку: каждый обязательный parameter target генератора либо указан в profile mapping, либо имеет builder default, явно зафиксированный в catalog.

Создать unit-тесты:

«каждый mapping target известен catalog»;

«каждый catalog target действительно принимается соответствующим builder»;

«каждый включённый layer можно превратить в SimState/procedural spec без renderer-а»;

«jazz не использует Duffing targets в chaotic_scattering_basins».

Важная правка схемы
В текущем словаре стоит различать semantic target и builder parameter. Иначе YAML начнёт копировать Python-детали, а Java окажется привязана к theta текущего core.

Правильная форма:

text

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
А catalog знает, во что это превращается в текущем Python builder:

text

chaotic_scattering_basins:
  semantic_controls:
    basin_separation:
      builder_parameter: basin_bias
    local_instability:
      builder_parameter: perturbation
    boundary_complexity:
      builder_parameter: complexity
Почему это принципиально
Профиль говорит на языке композиции: «дать больше разлома и неустойчивости».

Builder переводит это на языке конкретной математики: basin_bias, perturbation, complexity.

Java затем может исполнить те же semantic controls иначе — шейдером, полем или другой оптимизированной реализацией — не меняя художественный YAML.

Это одновременно защищает от технического долга и сохраняет смысловую архитектуру проекта.

Уточнение по пяти профилям
Профиль	Предварительная оценка	Что проверить
blues_jazz	Хорошая база: Julia + IFS + grain + акцент	Реальные Julia/IFS targets
electronic	Логичная динамика: Duffing + IFS	Реальные Duffing ranges и стоимость
jazz	Самый рискованный	Полностью заменить «duffing-like» mapping на scattering-native
ambient	Правильная идея, но менее фрактальная	Убедиться, что orbital_field определён как procedural spec
classical	Перспективен как тест симметрии	Развести pale_gold_accent как accent от основной palette




Отдельно: у classical нельзя использовать pale_gold_accent как full-canvas главную палитру. Судя по утверждённой схеме, это прозрачная акцентная палитра, а не поле фона и не доминирующий цветовой язык. Для classical лучше добавить отдельную базовую палитру: ivory_cobalt, cathedral_blue_gold или ink_ochre. Это не блокер planner-а, но блокер художественной связности.
Memory

Порядок дальше
Закончить sync с origin/main.

Прогнать полный pytest и приложить фактический результат, не шаблон.

Сделать Generator Contract Lock: реальные parameter catalogs, ranges, types, defaults.

Усилить валидацию profiles: invalid target должен ломать загрузку config.

Исправить jazz profile на scattering-native semantic controls.

Добавить базовую палитру для classical.

Собрать по одному plan.json на все пять профилей без PNG.

Только после зелёного контура переходить к исполнению плана в Python и созданию единственного 1024×1024 preview.ph