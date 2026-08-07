Plan_v0.3 — схема и план реализации
Этап 0 — Ничего не ломать
Существующие endpoint’ы и стабильный pipeline:

text

/project → /upload → /analyze → /resolve-style
не меняются. Переход происходит между resolve-style и бывшим single-generator generate/poster путём добавления planner-а.

Запрещено на этом этапе:

переписывать существующие математические генераторы;

улучшать старый renderer случайными эффектами;

добавлять ещё alias в fallback-ветки;

запускать Java renderer;

реализовывать export выше 1024 px на Python.

Этап 1 — Новая схема
Файл
text

D:\WORK\AVCoder\lib\composition\schema.py
Требуется реализовать
python

@dataclass
class TrackIdentity:
    audio_content_hash: str
    canonical_title: str | None
    canonical_artist: str | None
    duration_ms: int | None
    base_seed: int
    variation_seed: int

@dataclass
class CanvasSpec:
    width_px: int = 1024
    height_px: int = 1024
    color_space: str = "sRGB"
    background_rgba: list[int] = field(
        default_factory=lambda: [7, 9, 18, 255]
    )
    mode: str = "preview"

@dataclass
class LayerSpec:
    layer_id: str
    role: str
    enabled: bool
    z_index: int
    source_kind: str
    generator_id: str | None
    generator_version: str | None
    seed: int
    computation_resolution_px: tuple[int, int]
    sim_state: dict | None
    palette_id: str | None
    opacity: float
    blend_mode: str
    transform: dict
    mask: dict | None = None
    parameter_coverage: dict = field(default_factory=dict)

@dataclass
class VisualCompositionPlan:
    schema_version: str
    plan_id: str
    profile_version: str
    config_hash: str
    track_identity: TrackIdentity
    canvas: CanvasSpec
    visual_identity: dict
    layers: list[LayerSpec]
    composition: dict
    postprocess: dict
    validation: dict
Валидация схемы
Добавить validate_plan(plan).

Обязательные проверки:

canvas.width_px == 1024;

canvas.height_px == 1024;

mode == "preview";

opacity находится в диапазоне 0..1;

z_index уникален или имеет определённый стабильный порядок;

generator_id канонический и описан в generator_catalog.yaml;

blend_mode находится в whitelist;

transform использует нормализованные canvas coordinates;

seed есть у каждого вычислительного слоя;

план содержит от 3 до 5 включённых независимых слоёв;

запрещён output/export policy на стороне Python.

Результат этапа: вручную созданный тестовый JSON проходит schema validation и сохраняется/загружается без изменений.

Этап 2 — Каталог генераторов
Файл
text

D:\WORK\AVCoder\configs\generator_catalog.yaml
Черновой формат
text

schema_version: generator-catalog/v0.3

generators:
  julia_orbit_trap:
    canonical_id: julia_orbit_trap
    python_entrypoint: fractal_core.generators.julia_orbit_trap
    builder: make_sim_state_for_julia
    family: nonlinear_fractal
    roles: [macro_structure, contour, counterpoint]
    supports:
      - symmetry_bias
      - density_level
      - noise_level
      - recursion_depth
      - texture_complexity
      - motion_intensity
    aliases:
      - smooth_geometric_baseline

  orbit_ifs_multi_trap:
    canonical_id: orbit_ifs_multi_trap
    python_entrypoint: fractal_core.generators.orbit_ifs_multi_trap
    builder: make_sim_state_for_ifs
    family: iterated_function_system
    roles: [meso_rhythm, microtexture, density_field]
    supports:
      - density_level
      - motion_intensity
      - noise_level
      - recursion_depth
      - texture_complexity
    aliases:
      - single_parameter_map_baseline

  duffing_lyapunov:
    canonical_id: duffing_lyapunov
    python_entrypoint: fractal_core.generators.duffing_lyapunov_map
    builder: make_sim_state_for_duffing
    family: nonlinear_dynamics
    roles: [macro_structure, tension_field, atmosphere]
    supports:
      - tension
      - energy
      - motion_intensity
      - texture_complexity
      - noise_level
      - recursion_depth
    aliases: []

  chaotic_scattering_basins:
    canonical_id: chaotic_scattering_basins
    python_entrypoint: fractal_core.generators.chaotic_scattering_basins
    builder: make_sim_state_for_scattering
    family: basin_dynamics
    roles: [accent, transition_field, counterpoint]
    supports:
      - tension
      - energy
      - motion_intensity
      - texture_complexity
      - noise_level
    aliases:
      - random_baseline

  orbital_field:
    canonical_id: orbital_field
    python_entrypoint: reference_renderer.layers.orbital_field
    builder: make_orbital_field_spec
    family: procedural_visual
    roles: [meso_rhythm, flow]
    supports:
      - tempo
      - repetition
      - motion_intensity
      - symmetry_bias
    aliases: []

  colored_noise_field:
    canonical_id: colored_noise_field
    python_entrypoint: reference_renderer.layers.colored_noise_field
    builder: make_colored_noise_spec
    family: procedural_visual
    roles: [microtexture, atmosphere]
    supports:
      - noise_level
      - spectral_flatness
      - high_frequency_energy
      - texture_complexity
    aliases: []

  symmetry_snowflake:
    canonical_id: symmetry_snowflake
    python_entrypoint: reference_renderer.layers.symmetry_snowflake
    builder: make_snowflake_spec
    family: procedural_visual
    roles: [accent, ornament, harmonic_refrain]
    supports:
      - symmetry_bias
      - repetition
      - texture_complexity
      - harmonic_stability
    aliases: []
Требования
Alias всегда канонизируется вызовом canonicalize_generator_id().

После canonicalization используется только canonical_id.

Builder выбирается только по canonical_id.

Нельзя иметь fallback theta для неизвестного generator ID.

Неизвестный alias/ID должен завершать построение плана ошибкой конфигурации.

Результат этапа: вывод smooth_geometric_baseline всегда приводит к julia_orbit_trap → make_sim_state_for_julia, а не к универсальному fallback. Это устраняет обнаруженную ошибку параметризации.
Memory

Этап 3 — Визуальные профили
Файл
text

D:\WORK\AVCoder\configs\visual_composition_profiles.yaml
text

schema_version: visual-composition-profile/v0.3
profile_version: 0.3.0

defaults:
  canvas:
    width_px: 1024
    height_px: 1024
    color_space: sRGB
    background_rgba: [7, 9, 18, 255]
    mode: preview

  output_policy:
    python_reference_only: true
    final_layers_min: 3
    final_layers_max: 5

  seed_policy:
    base_source: audio_content_hash
    include_normalized_title: true
    include_normalized_artist: true
    include_duration_ms: true
    algorithm: sha256

  composition_defaults:
    blend_modes: [normal, screen, add, multiply, soft_light, max]
    coordinate_space: normalized_canvas
    angle_unit: deg

profiles:
  blues_jazz:
    identity:
      palette_family: nocturne_amber
      macro_archetype: orbital_flow
      visual_keywords: [organic, improvisational, nocturnal, warm]

    layers:
      - id: macro_orbit
        role: macro_structure
        generator: julia_orbit_trap
        enabled: true
        opacity: 0.92
        blend_mode: normal
        resolution_fraction: 0.78
        parameter_mapping:
          c_real: symmetry_bias
          c_imag: tension
          trap_radius: density_level
          max_iter: recursion_depth
          rotation_deg: motion_intensity

      - id: rhythmic_points
        role: meso_rhythm
        generator: orbit_ifs_multi_trap
        enabled: true
        opacity: 0.40
        blend_mode: screen
        resolution_fraction: 0.60
        parameter_mapping:
          n_points: density_level
          map_diversity: texture_complexity
          attractor_spread: motion_intensity
          stochastic_scale: noise_level

      - id: grain_field
        role: microtexture
        generator: colored_noise_field
        enabled: true
        opacity: 0.09
        blend_mode: soft_light
        resolution_fraction: 1.00
        parameter_mapping:
          amplitude: noise_level
          scale: spectral_flatness
          anisotropy: repetition

      - id: crystalline_accent
        role: accent
        generator: symmetry_snowflake
        enabled_if:
          section_complexity_min: 0.56
        opacity: 0.11
        blend_mode: add
        resolution_fraction: 0.42
        parameter_mapping:
          branches: symmetry_bias
          branch_depth: texture_complexity
          rotation_deg: harmonic_change_rate

      - id: silence
        role: silence_mask
        source_kind: procedural_mask
        enabled: true
        opacity: 1.0
        blend_mode: normal
        parameter_mapping:
          coverage: silence_rate
          direction: layout_macro_shape

  ambient:
    identity:
      palette_family: lunar_mist
      macro_archetype: quiet_field
      visual_keywords: [spacious, cold, submerged, slow]

    layers:
      - id: macro_field
        role: macro_structure
        generator: julia_orbit_trap
        enabled: true
        opacity: 0.76
        blend_mode: normal
        resolution_fraction: 0.72
        parameter_mapping:
          c_real: symmetry_bias
          c_imag: tension
          trap_radius: density_level
          max_iter: recursion_depth
          domain_zoom: motion_intensity

      - id: orbital_breath
        role: meso_rhythm
        generator: orbital_field
        enabled: true
        opacity: 0.24
        blend_mode: screen
        resolution_fraction: 0.60
        parameter_mapping:
          flow_speed: tempo
          radius: repetition
          symmetry: symmetry_bias

      - id: mist
        role: microtexture
        generator: colored_noise_field
        enabled: true
        opacity: 0.08
        blend_mode: soft_light
        resolution_fraction: 1.00
        parameter_mapping:
          amplitude: noise_level
          scale: spectral_flatness

      - id: silence
        role: silence_mask
        source_kind: procedural_mask
        enabled: true
        opacity: 1.0
        blend_mode: normal
        parameter_mapping:
          coverage: silence_rate
          direction: layout_macro_shape

  electronic:
    identity:
      palette_family: spectral_neon
      macro_archetype: bifurcation_impulse
      visual_keywords: [electric, unstable, kinetic, synthetic]

    layers:
      - id: tension_field
        role: macro_structure
        generator: duffing_lyapunov
        enabled: true
        opacity: 0.86
        blend_mode: normal
        resolution_fraction: 0.74
        parameter_mapping:
          forcing: energy
          damping: tension
          omega: motion_intensity
          n_steps: recursion_depth
          nonlinearity: texture_complexity

      - id: pulse_density
        role: meso_rhythm
        generator: orbit_ifs_multi_trap
        enabled: true
        opacity: 0.48
        blend_mode: screen
        resolution_fraction: 0.64
        parameter_mapping:
          n_points: density_level
          attractor_spread: motion_intensity
          map_diversity: texture_complexity

      - id: spectral_grain
        role: microtexture
        generator: colored_noise_field
        enabled: true
        opacity: 0.12
        blend_mode: add
        resolution_fraction: 1.00
        parameter_mapping:
          amplitude: high_frequency_energy
          scale: spectral_flatness

      - id: crystal_pulse
        role: accent
        generator: symmetry_snowflake
        enabled_if:
          energy_min: 0.54
        opacity: 0.13
        blend_mode: add
        resolution_fraction: 0.38
        parameter_mapping:
          branches: symmetry_bias
          branch_depth: texture_complexity
          rotation_deg: harmonic_change_rate

  soundtrack:
    identity:
      palette_family: crimson_gold_noir
      macro_archetype: cinematic_tension
      visual_keywords: [dramatic, deep, cinematic, contrastive]

    layers:
      - id: dramatic_field
        role: macro_structure
        generator: duffing_lyapunov
        enabled: true
        opacity: 0.80
        blend_mode: normal
        resolution_fraction: 0.75
        parameter_mapping:
          forcing: energy
          damping: tension
          n_steps: recursion_depth
          nonlinearity: texture_complexity

      - id: contour
        role: counterpoint
        generator: julia_orbit_trap
        enabled: true
        opacity: 0.38
        blend_mode: screen
        resolution_fraction: 0.56
        parameter_mapping:
          c_real: symmetry_bias
          c_imag: tension
          trap_radius: density_level
          rotation_deg: motion_intensity

      - id: scene_break
        role: accent
        generator: chaotic_scattering_basins
        enabled: true
        opacity: 0.17
        blend_mode: add
        resolution_fraction: 0.48
        parameter_mapping:
          basin_bias: tension
          perturbation: motion_intensity
          complexity: texture_complexity

      - id: atmospheric_grain
        role: microtexture
        generator: colored_noise_field
        enabled: true
        opacity: 0.07
        blend_mode: soft_light
        resolution_fraction: 1.00
        parameter_mapping:
          amplitude: noise_level
          scale: spectral_flatness

  rock:
    identity:
      palette_family: charcoal_red_white
      macro_archetype: fractured_drive
      visual_keywords: [raw, loud, fractured, physical]

    layers:
      - id: fracture_field
        role: macro_structure
        generator: chaotic_scattering_basins
        enabled: true
        opacity: 0.88
        blend_mode: normal
        resolution_fraction: 0.76
        parameter_mapping:
          basin_bias: tension
          perturbation: motion_intensity
          complexity: texture_complexity

      - id: dense_body
        role: meso_rhythm
        generator: orbit_ifs_multi_trap
        enabled: true
        opacity: 0.44
        blend_mode: screen
        resolution_fraction: 0.64
        parameter_mapping:
          n_points: density_level
          attractor_spread: motion_intensity
          map_diversity: texture_complexity

      - id: broken_traces
        role: counterpoint
        generator: orbital_field
        enabled: true
        opacity: 0.30
        blend_mode: add
        resolution_fraction: 0.56
        parameter_mapping:
          flow_speed: tempo
          angular_break: tension
          amplitude: energy

      - id: abrasive_grain
        role: microtexture
        generator: colored_noise_field
        enabled: true
        opacity: 0.12
        blend_mode: soft_light
        resolution_fraction: 1.00
        parameter_mapping:
          amplitude: noise_level
          scale: high_frequency_energy
Важное замечание
В YAML не должны находиться произвольные формулы Python. Там должны быть лишь:

параметр-источник;

допустимая target-семантика;

включение/выключение слоя;

архитектура композиции;

стиль/палитра/порядок.

Формулы преобразований живут в версионируемом planner mapping library, например:

text

lib/composition/mappings/
  julia.py
  ifs.py
  duffing.py
  scattering.py
  procedural.py
Так YAML остаётся языком дизайна, а не неотлаживаемым языком программирования.

Этап 4 — Палитры
Файл
text

D:\WORK\AVCoder\configs\palettes.yaml
Минимальный контракт:

text

schema_version: palettes/v0.3

palettes:
  nocturne_amber:
    background_rgba: [7, 9, 18, 255]
    dominant:
      stops:
        - [0.00, "#06111D"]
        - [0.40, "#0D4B63"]
        - [0.72, "#2D8C93"]
        - [1.00, "#F2B84B"]
    accent: "#FFC766"
    saturation_budget: 0.70
    contrast: 1.10

  lunar_mist:
    background_rgba: [9, 16, 26, 255]
    dominant:
      stops:
        - [0.00, "#07131F"]
        - [0.52, "#496C86"]
        - [1.00, "#D5E7EA"]
    accent: "#A8E3EE"
    saturation_budget: 0.38
    contrast: 0.92

  spectral_neon:
    background_rgba: [5, 4, 18, 255]
    dominant:
      stops:
        - [0.00, "#08172A"]
        - [0.45, "#00C8FF"]
        - [0.74, "#8D48FF"]
        - [1.00, "#FF3EA5"]
    accent: "#D7FFFF"
    saturation_budget: 0.92
    contrast: 1.24

  crimson_gold_noir:
    background_rgba: [10, 5, 8, 255]
    dominant:
      stops:
        - [0.00, "#0A0508"]
        - [0.46, "#49151D"]
        - [0.76, "#AF3832"]
        - [1.00, "#D7A649"]
    accent: "#FFE0A1"
    saturation_budget: 0.74
    contrast: 1.22

  charcoal_red_white:
    background_rgba: [11, 11, 12, 255]
    dominant:
      stops:
        - [0.00, "#111114"]
        - [0.45, "#49494C"]
        - [0.72, "#B81924"]
        - [1.00, "#EFEDE5"]
    accent: "#FFFFFF"
    saturation_budget: 0.68
    contrast: 1.30
Этап 5 — Planner без рендера
Новый модуль
text

D:\WORK\AVCoder\lib\composition\planner.py
Каноническая функция
python

def build_visual_composition_plan(
    audio_analysis: AudioAnalysis,
    perceptual_latent: PerceptualLatent,
    render_params: RenderParams,
    track_metadata: TrackMetadata,
    mode: str = "preview",
    variation_seed: int = 0,
) -> VisualCompositionPlan:
    ...
Обязанности planner-а
Прочитать и провалидировать YAML-профили.

Получить style_profile_slug.

Выбрать композиционный профиль.

Посчитать audio_content_hash и base_seed.

Вывести seed для каждого слоя.

Канонизировать generator IDs.

Создать независимый LayerSpec для 3–5 слоёв.

Вызвать соответствующие per-generator builders.

Записать SimState в JSON-совместимом виде.

Создать parameter_coverage.

Создать config_hash.

Валидировать plan до сохранения.

Не генерировать изображение и не вызывать Pillow.

Этап 6 — Python reference executor
Новый модуль
text

D:\WORK\AVCoder\lib\reference_renderer\execute_plan.py
Функция
python

def render_reference_preview(
    plan: VisualCompositionPlan,
    output_dir: Path,
) -> RenderArtifact:
    """
    Исполняет готовый plan.
    Единственный разрешённый Python output:
    preview.png (1024×1024).
    """
Требования
Никакой style resolution внутри renderer.

Никакого выбора generator ID внутри renderer.

Никаких aliases.

Никаких final/export resolution.

Каждый generator layer вызывает отдельный вычислительный run.

Между слоями применяются transform, mask, palette, opacity и blend_mode.

Рендерер сохраняет полный набор артефактов в output-dir.

Выходная папка
text

D:\WORK\AVCoder\storage\poster_runs\{plan_id}\
Содержимое:

text

preview.png
visual_composition_plan.json
render_metadata.json
parameter_coverage.json
layer_manifest.json
preview_sha256.txt
Опционально для dev/QA:

text

layers\
  00_macro_structure.png
  10_meso_rhythm.png
  20_microtexture.png
  30_accent.png
  40_silence_mask.png
Эти отдельные слои нельзя считать пользовательским export; это диагностические артефакты, необходимые для layer reveal, QA и сопоставления Python с Java.

Этап 7 — Тесты
Обязательные тесты
Plan determinism
Два построения плана из одинакового входа дают byte-identical canonical JSON.

Alias canonicalization
smooth_geometric_baseline использует Julia builder; random_baseline — scattering builder; single_parameter_map_baseline — IFS builder.

Parameter coverage
Для каждого active RenderParams есть минимум один target или явное N/A.

Layer independence
В финальном preview три и более включённых слоёв имеют разные layer_id, seed и независимые generator/procedural source.

Reference determinism
Один plan, отрендеренный дважды, даёт одинаковый SHA-256 для preview.png.

Storage contract
Все шесть обязательных артефактов создаются в storage\poster_runs\{plan_id}\.

Preview-only policy
Python renderer отвергает любое разрешение, отличное от 1024×1024, и режимы final/export.

Порядок исполнения
Утвердить RFC v0.3 и YAML-схему.

Реализовать schema + validation.

Ввести generator catalog и убить alias fallback.

Завести visual profiles и palettes.

Сделать planner, который только пишет plan.json.

Проверить plan determinism и parameter coverage.

Реализовать Python execution готового плана в 1024×1024.

Провести layer ablation и regression corpus.

Только затем писать отдельное ТЗ для Java renderer.

Непосредственная задача разработчику: начать с этапов 1–5 и принести три артефакта без единого нового PNG:
VisualCompositionPlan v0.3 schema, generator_catalog.yaml, visual_composition_profiles.yaml, а также пример валидного plan.json для одного blues/jazz и одного electronic трека.