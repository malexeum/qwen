ТЗ: Composition Planner v0.3
Цель
Реализовать слой:

text

AudioAnalysis + PerceptualLatent + RenderParams + TrackMetadata
                         ↓
            VisualCompositionPlanner
                         ↓
        VisualCompositionPlan v0.3 JSON
На этом этапе не запускать фрактальные генераторы, Pillow, matplotlib и не создавать PNG. Единственный результат — валидный plan.json, сохранённый рядом с будущим preview в D:\WORK\AVCoder\storage\poster_runs\{plan_id}\.

Почему именно сейчас
Три YAML уже разделили систему на:

каталог реальных генераторов и alias;

палитры;

жанровую/композиционную грамматику.

Теперь planner должен соединить их с фактическим треком и превратить абстрактные указания вроде trap_radius: density_level в конкретный JSON-план с canonical generator IDs, seeds, нормализованными transform и JSON-представлением SimState. Это устраняет старую архитектурную дыру, где alias попадал в fallback-builder и разные треки становились визуальными близнецами.
Memory

Новые модули
text

D:\WORK\AVCoder\lib\composition\
  __init__.py
  schema.py
  config_loader.py
  seed_policy.py
  canonicalize.py
  planner.py
  validation.py
  coverage.py
  storage.py
  mappings\
    __init__.py
    julia.py
    ifs.py
    duffing.py
    scattering.py
    procedural.py
Принцип границ
config_loader.py читает и валидирует YAML.

canonicalize.py превращает alias в canonical_id.

seed_policy.py вычисляет стабильные base/layer seeds.

mappings/* переводят семантические оси в конкретные параметры каждого генератора.

planner.py собирает plan.

validation.py проверяет plan до сохранения.

coverage.py доказывает, как каждый RenderParams был использован.

storage.py создаёт папку запуска и сохраняет JSON.

Ни один модуль на этом этапе не имеет права импортировать PIL, matplotlib или выполнять generator function.

Контракт VisualCompositionPlan
Обязательный JSON
json

{
  "schema_version": "visual-composition-plan/v0.3",
  "plan_id": "3c2cfb46-0000-0000-0000-000000000000",
  "planner_version": "0.3.0",
  "profile_library_version": "0.3.0",
  "config_hash": "sha256:...",
  "track_identity": {
    "audio_content_hash": "sha256:...",
    "canonical_title": "Autumn Leaves",
    "canonical_artist": "…",
    "duration_ms": 0,
    "style_profile_slug": "blues_jazz",
    "base_seed": 123456789,
    "variation_seed": 0
  },
  "canvas": {
    "width_px": 1024,
    "height_px": 1024,
    "mode": "preview",
    "color_space": "sRGB",
    "background_rgba": [7, 9, 18, 255]
  },
  "visual_identity": {
    "palette_id": "nocturne_amber",
    "macro_archetype": "orbital_flow",
    "postprocess_style_slug": "grainfilm"
  },
  "layers": [],
  "composition": {
    "coordinate_system": "normalized_canvas",
    "negative_space": {}
  },
  "postprocess": {},
  "parameter_coverage": {},
  "validation": {}
}
Объект layer
Каждый включённый вычислительный слой обязан быть независимым:

json

{
  "layer_id": "macro_orbit",
  "role": "macro_structure",
  "enabled": true,
  "z_index": 10,
  "source_kind": "fractal_core",
  "generator_id": "julia_orbit_trap",
  "generator_version": "v2",
  "seed": 124003511,
  "computation_resolution_px": [800, 800],
  "sim_state": {
    "generator_name": "julia_orbit_trap",
    "theta": [-0.31, 0.42, 0.12, -0.20, 0.07, -0.05],
    "resolution": [800, 800],
    "domain": [-1.8, 1.8, -1.8, 1.8],
    "max_iter": 214,
    "escape_radius": 4.0,
    "trap_kind": "point",
    "seed": 124003511,
    "stochastic_scale": 0.008,
    "extra": {}
  },
  "transform": {
    "offset_norm": [0.0, 0.0],
    "scale_xy": [0.95, 0.95],
    "rotation_deg": 14.5
  },
  "mask": null,
  "palette_id": "nocturne_amber",
  "opacity": 0.92,
  "blend_mode": "normal",
  "mapping_trace": {
    "c_real": "symmetry_bias",
    "c_imag": "tension",
    "trap_radius": "density_level",
    "max_iter": "recursion_depth",
    "rotation_deg": "motion_intensity"
  }
}
mapping_trace обязателен: он объясняет, почему параметры слоя именно такие, и помогает сравнивать Python/Java.

Порядок сборки
1. Входы
Planner получает:

python

def build_visual_composition_plan(
    *,
    audio_analysis: AudioAnalysis,
    perceptual_latent: PerceptualLatent,
    render_params: RenderParams,
    track_metadata: TrackMetadata,
    variation_seed: int = 0,
) -> VisualCompositionPlan:
    ...
Если текущие классы называются иначе — разрешена adapter-функция, но не дублирование данных.

Обязательные входные поля:

Источник	Поля
Track metadata	audio_content_hash, title, artist, duration
RenderParams	style_profile_slug, symmetry_bias, density_level, noise_level, recursion_depth, motion_intensity, texture_complexity, layout_macro_shape, palette_id, visual_style_slug, variation_seed
Perceptual latent	energy, tension, repetition, tempo, section_complexity, silence_rate, harmonic_stability, harmonic_change_rate, spectral_flatness, high_frequency_energy
Если часть полей пока не производится анализом, planner обязан вернуть не «тихое значение 0», а missing_input в diagnostic report. Разрешено определить явные временные defaults в одном месте input_adapter.py, но с маркировкой provisional: true.

2. Загрузка конфигурации
config_loader.py:

Читает:

configs/generator_catalog.yaml;

configs/palettes.yaml;

configs/visual_composition_profiles.yaml;

существующий configs/poster_styles.yaml.

Проверяет:

schema versions;

ссылки profile → palette;

ссылки layer → generator;

ссылки mapping target → capability generator-а;

допустимые blend mode;

отсутствие циклических imports.

Считает стабильный config_hash по canonical JSON всех загруженных YAML.

Если YAML невалиден, plan не строится.

3. Seed policy
Base seed
python

base_material = "|".join([
    audio_content_hash,
    normalize(title),
    normalize(artist),
    str(duration_ms),
    style_profile_slug,
    profile_library_version,
    str(variation_seed),
])

base_seed = sha256_to_uint64(base_material)
audio_content_hash обязателен. Если его нет — это ошибка production pipeline, а не повод использовать путь к файлу или случайный UUID.

Layer seed
python

layer_seed = sha256_to_uint64(
    f"{base_seed}|{layer_id}|{canonical_generator_id}"
)
Преимущества:

одинаковый трек и параметры → одинаковая композиция;

близкие по аудио треки с разными identity metadata не обязаны быть близнецами;

один и тот же слой стабилен;

пользовательская вариация меняется только изменением variation_seed, уже на Java-клиенте.

4. Канонизация generator ID
Алгоритм обязателен:

python

requested_id = layer_config["generator_id"]
canonical_id = canonicalize_generator_id(requested_id, catalog)

generator = catalog["generators"][canonical_id]
builder_id = generator["builder_id"]
Запрещено:

python

if requested_id not in builders:
    use_generic_fallback_theta()
Неизвестный generator/alias — ошибка CompositionConfigError.

5. Сборка слоёв
Для каждого YAML-layer:

Проверить enabled или вычислить enabled_if.

Канонизировать generator_id.

Вывести layer_seed.

Определить computation_resolution_px:

python

round(1024 * computation_resolution_fraction)
С ограничением: минимум 128 px, максимум 1024 px по каждой стороне.

Вычислить transform:

координаты строго нормализованы: [-1, 1];

угол только в градусах;

transform не изменяет физический SimState без явного mapping target.

Передать mapping в generator-specific builder.

Получить конкретный SimState или procedural layer_params.

Сформировать LayerSpec.

Записать mapping_trace.

6. enabled_if
Поддержать маленький, строго ограниченный DSL:

text

enabled_if:
  all:
    - source: section_complexity
      operator: gte
      value: 0.56
    - source: harmonic_stability
      operator: gte
      value: 0.38
Разрешённые операторы:

text

gt, gte, lt, lte, eq, neq
Разрешённые агрегаторы:

text

all, any
Никакого eval, Python-expression или вызова функций из YAML.

7. Mapping builders
Первый результат этой фазы должен содержать четыре builder-а:

python

build_julia_state(...)
build_ifs_state(...)
build_duffing_state(...)
build_scattering_state(...)
И три procedural spec-builder-а:

python

build_orbital_field_spec(...)
build_colored_noise_spec(...)
build_symmetry_snowflake_spec(...)
Пока procedural generators ещё не реализованы как PNG-генераторы, planner всё равно обязан уметь выписывать им валидные layer_params.

Критичное правило
Если профиль включает motion_intensity, он должен менять хотя бы одно конкретное поле каждого композиционного профиля:

Julia: rotation_deg, domain_zoom, trap_center drift или отдельный orbital layer;

IFS: attractor_spread / rotation_deg;

Duffing: forcing_frequency / rotation_deg;

scattering: perturbation;

procedural layers: flow_speed, anisotropy, etc.

Так мы запрещаем повтор «high_motion ничего не делает».

Parameter coverage
Обязательный артефакт
Planner формирует:

json

{
  "schema_version": "parameter-coverage/v0.3",
  "active_profile": "blues_jazz",
  "used": {
    "symmetry_bias": [
      "macro_orbit.sim_state.theta[0]",
      "crystalline_accent.layer_params.branch_count"
    ],
    "density_level": [
      "macro_orbit.sim_state.theta[3]",
      "rhythmic_points.layer_params.n_points"
    ],
    "noise_level": [
      "macro_orbit.sim_state.stochastic_scale",
      "grain_field.layer_params.amplitude"
    ],
    "recursion_depth": [
      "macro_orbit.sim_state.max_iter"
    ],
    "motion_intensity": [
      "macro_orbit.transform.rotation_deg",
      "rhythmic_points.layer_params.attractor_spread"
    ],
    "texture_complexity": [
      "macro_orbit.sim_state.theta[2]",
      "rhythmic_points.layer_params.map_diversity"
    ],
    "layout_macro_shape": [
      "macro_orbit.transform.offset_norm",
      "silence_mask.layer_params.direction"
    ]
  },
  "not_applicable": [],
  "provisional_defaults": []
}
Валидатор coverage
Для каждого обязательного RenderParams требуется хотя бы один used target.

Если ось конструктивно не нужна профилю — только явный not_applicable с причиной.

Если mapping не сработал из-за отсутствующего audio feature, это блокирующая ошибка для final plan.

parameter_coverage.json пишется до создания PNG.

Файловый контракт
План сохраняется первым
text

D:\WORK\AVCoder\storage\poster_runs\{plan_id}\
  visual_composition_plan.json
  parameter_coverage.json
  planner_diagnostics.json
На этом этапе папка не содержит preview.png, потому что renderer ещё не начат.

planner_diagnostics.json содержит:

json

{
  "planner_version": "0.3.0",
  "config_hash": "sha256:...",
  "loaded_files": [
    "generator_catalog.yaml",
    "palettes.yaml",
    "visual_composition_profiles.yaml",
    "poster_styles.yaml"
  ],
  "canonicalized_generators": {
    "smooth_geometric_baseline": "julia_orbit_trap"
  },
  "warnings": [],
  "provisional_defaults": []
}
Тесты
До перехода к reference renderer должны пройти:

Config integrity: все профили валидны, генераторы/палитры существуют, mapping targets supported.

Canonicalization: все старые aliases приводятся к canonical generator IDs.

Plan determinism: два запуска planner-а дают canonical byte-identical JSON, кроме plan_id; для этого plan_id также лучше сделать детерминированным — хэш от canonical plan без plan_id.

Layer count: у каждого профиля 3–5 включённых слоёв.

Independent layers: включённые вычислительные слои имеют уникальные layer_id и разные layer seeds.

Coverage: отсутствуют silent/missing параметры.

Storage: план, coverage и diagnostics лежат в отдельной папке storage\poster_runs\{plan_id}.

No rendering imports: planner package не импортирует Pillow/matplotlib и не вызывает fractal generator functions.

Definition of Done
Composition Planner v0.3 готов, когда:

для одного blues/jazz и одного electronic трека создаются валидные планы;

каждый план имеет 3–5 независимых слоёв;

canonical generator IDs появляются в плане, aliases — нет;

в каждом плане есть конкретные layer seeds и SimState/procedural parameters;

parameter_coverage.json объясняет пути всех ключевых RenderParams;

результаты лежат в отдельных папках под D:\WORK\AVCoder\storage\poster_runs\;

Python ещё не создаёт PNG;

есть unit-тесты на YAML validation, alias, determinism и coverage.

Следующий конкретный артефакт от программиста: два каталога вида:

text

storage\poster_runs\{blues_plan_id}\
storage\poster_runs\{electronic_plan_id}\
и в каждом — только три JSON-файла: visual_composition_plan.json, parameter_coverage.json, planner_diagnostics.json.