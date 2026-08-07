TZ_poster_renderer_v0.2.1 — Fractal Poster Renderer (mid-res)
1. Цель и масштаб
Сделать минимальный, но научно обоснованный PosterRenderer, который:

принимает RenderParams (результат style engine v0.2.1);

генерирует фрактальный постер в среднем разрешении 1200×1200;

поддерживает три режима рендера: macro, meso, final;

сохраняет результат как PNG и регистрирует PosterAsset / обновляет GenerationJob;

реализует визуальную интерпретацию перцептивных параметров (symmetry, recursion, density, noise, motion, texture, layout) и финального визуального стиля (visual_style_slug).
proposal_perceptual_layer.md

2. Научный и дизайнерский фон
2.1 Перцептивные оси и визуальные параметры
В перцептивных моделях музыки и визуальной эстетики принято разделять:

low-level признаки (энергия, спектр, ритмическая плотность);

perceptual признаки (скорость, напряжённость, стабильность, яркость);

семантические/стилевые признаки (эмоция, жанр, movement).
arxiv

В нашей архитектуре:

AudioAnalysis → low-level/структура;

PerceptualLatent → perceptual layer (energy, tension, density, brightness, stability, smoothness, repetition, section_complexity);
Memory
proposal_perceptual_layer.md

RenderParams → визуальные контролы:

symmetry_bias, recursion_depth, density_level, noise_level, motion_intensity, texture_complexity, layout_macro_shape, palette_id, visual_style_slug, variation_seed.

Задача renderer’а — трактовать эти контролы в визуальные решения так, чтобы:

симметрия, плотность, шум и текстура соответствовали перцептивным осям;

композиция отражала макроформу (layout_macro_shape);

стиль (цвет и финальная стилизация) был согласован с StyleProfile, InterpretationProfile и poster_styles.yaml.
proposal_perceptual_layer.md

2.2 Фрактальные постеры как макро/микро карта
Фрактальные/генеративные постеры естественно поддерживают идею трёх уровней формы:

макроуровень — общая композиция (центры масс, зоны, симметрия);

мезоуровень — крупные паттерны/flows;

микроуровень — текстура и шум.

Renderer должен использовать RenderParams так, чтобы:

layout_macro_shape задавал макрокомпозицию;

symmetry_bias, motion_intensity, density_level — определяли мезоуровень;

recursion_depth, texture_complexity, noise_level — определяли микроуровень.

3. Разрешение и формат
3.1 Разрешение
Для v0.2.1:

базовое mid-res: width = 1200, height = 1200.

Параметры width/height остаются настраиваемыми (запаз), но MVP фокусируется на 1200×1200 для скорости и удобства тестов.

3.2 Формат
Выход: PNG, sRGB.

Файлы: data/posters/poster_{project_id}_{job_id}.png (или аналогичная схема).

4. Контракт PosterRenderer
4.1 Функция
Внутренний API:

python

def render_poster(
    render_params: RenderParams,
    output_path: str,
    width: int = 1200,
    height: int = 1200,
    mode: str = "final"  # "macro" | "meso" | "final"
) -> PosterMetadata:
    ...
RenderParams включает:

style_profile_slug

interpretation_profile_slug

preset_id

symmetry_bias

recursion_depth

density_level

noise_level

motion_intensity

palette_id

stochastic_term

layout_macro_shape

texture_complexity

variation_seed

visual_style_slug (см. раздел 8)

PosterMetadata (dict):

width, height

palette_id

style_profile_slug

interpretation_profile_slug

visual_style_slug

created_at

опционально: creation_map (см. раздел 7).

4.2 Интеграция с backend
GenerationJob:

хранит render_params (JSON);

имеет status (pending, success, failed).

/generate/poster:

на вход: job_id и, опционально, modes (["final"] или ["macro","meso","final"]);

грузит GenerationJob, RenderParams;

вызывает render_poster для каждого режима;

создаёт/обновляет PosterAsset(ы);

обновляет статус job.

5. Геометрический слой (flow-based генератор)
5.1 Flow field
Canvas 1200×1200, сетка flow field (например, 40×40 узлов).

В каждом узле — вектор (направление + длина), задающий направление “движения” линий.

Генерация:

базовый угол зависит от:

layout_macro_shape:

linear: единый глобальный flow (горизонталь/вертикаль);

ABA_like: разные flows в зонах A/B/A;

unknown: радиальный/центральный flow.

motion_intensity — степень отклонения от базового направления;

symmetry_bias — насколько поле симметризуется относительно оси.

5.2 Layout_macro_shape
ABA_like:

делим canvas на три вертикальные зоны: A–B–A;

зоны A используют сходный flow (вариации через seed);

зона B — отличающийся flow (например, более динамичный).

linear:

flow в одном направлении; плотность меняется вдоль оси.

unknown:

радиально-ориентированные или нейтральные flows.

5.3 Линии/ленты (мезоуровень)
Генерируем N базовых линий/ленточных путей:

N = N_min + int(density_level * N_range) (например, от 20 до 200).

Каждая линия:

стартует из seed-пунктов (зависит от layout);

следует flow field, длина зависит от recursion_depth и texture_complexity.

Параметризация:

motion_intensity:

низкое → плавные линии;

высокое → более бурные, криволинейные траектории.

symmetry_bias:

определяет, рисуем ли зеркальные копии линий (и с каким весом).

recursion_depth:

задаёт количество “подветвей” (вторичных линий), отстающих от базовых.

5.4 Микроуровень: детали/texture
Вдоль линий:

рисуем точки/штрихи/мелкие волны.

Параметры:

texture_complexity:

количество деталей на линии;

noise_level:

амплитуда случайных отклонений от flow:

низкая → аккуратные детали;

высокая → “залитая” текстура.

stochastic_term:

плотность/вариативность деталей (при фиксированном variation_seed детерминированно).

6. Цвет и палитры
palette_id → выбора палитры из palettes.yaml:

background_color

primary_color

secondary_color

accent_color
arxiv

Использование:

фон заливается background_color;

основная геометрия — primary_color;

вторичные/подветви — secondary_color;

события/акценты (events из AudioAnalysis) → accent_color.
Memory

Можно учитывать brightness (перцептивная яркость):

для ярких треков усиливать долю акцентных цветов;

для тёмных — оставлять больше фона.

7. Многослойный рендер: macro / meso / final
7.1 Режимы
render_poster принимает mode:

macro — макро-постер (форма, layout, крупные массы);

meso — мезо-постер (flows, основные линии, базовая текстура);

final — полный постер (полные RenderParams).

7.2 Модификация RenderParams по режимам
Все модификации происходят после guardrails InterpretationProfile, но до рендера:

Macro:

recursion_depth → min(recursion_depth, 0.25)

texture_complexity → min(texture_complexity, 0.3)

density_level → clamp(density_level, 0.3, 0.6)

noise_level → min(noise_level, 0.25)

Оставляем:

layout_macro_shape, symmetry_bias, palette_id без изменений.

Meso:

recursion_depth → clamp(recursion_depth, 0.25, 0.6)

texture_complexity → clamp(texture_complexity, 0.3, 0.7)

density_level → clamp(density_level, 0.4, 0.8)

noise_level → clamp(noise_level, 0.2, 0.5)

Final:

используем RenderParams как есть (после guardrails).

8. Карта создания (creation map)
8.1 Назначение
Renderer формирует “карту создания”:

последовательность крупных шагов:

init_canvas

layout_macro

macro_flows

meso_lines

micro_texture

для explainability и простых анимаций.
proposal_perceptual_layer.md

8.2 Формат JSON
Пример:

json

{
  "version": "0.2.1",
  "render_mode": "final",
  "width": 1200,
  "height": 1200,
  "style_profile_slug": "rock",
  "interpretation_profile_slug": "default",
  "visual_style_slug": "full_color",
  "steps": [
    {
      "stage": "init_canvas",
      "params": {
        "background_color": "#0b0b0f",
        "palette_id": "ember_dark"
      }
    },
    {
      "stage": "layout_macro",
      "params": {
        "layout_macro_shape": "ABA_like",
        "symmetry_bias": 0.6
      }
    },
    {
      "stage": "macro_flows",
      "params": {
        "n_flows": 40,
        "motion_intensity": 0.4,
        "density_level": 0.55
      }
    },
    {
      "stage": "meso_lines",
      "params": {
        "recursion_depth": 0.5,
        "texture_complexity": 0.5
      }
    },
    {
      "stage": "micro_texture",
      "params": {
        "noise_level": 0.35,
        "texture_complexity": 0.7,
        "stochastic_term": 0.2
      }
    }
  ]
}
8.3 Реализация
Внутри render_poster:

при каждом шаге добавлять entry в creation_map["steps"].

PosterMetadata:

либо включает creation_map,

либо creation_map сохраняется в отдельный файл poster_{project_id}_{job_id}_creation.json.

Фронтенд может использовать steps для последовательного отображения macro → meso → final.

9. Visual style layer (visual_style_slug)
9.1 Новое поле в RenderParams
Расширить RenderParams:

поле visual_style_slug, например:

full_color

black_and_white

duotone

grain_film

По умолчанию: full_color (или дефолт per-style).

9.2 Файл poster_styles.yaml
Файл poster_styles.yaml:

text

poster_styles:
  - slug: full_color
    name: Full Color
    description: >
      Base color rendering using palette as-is, with moderate contrast and no additional stylization.
    mode: color
    params:
      contrast_boost: 0.0
      saturation_boost: 0.0
      grain_amount: 0.0
      posterize_levels: null
      edge_enhance: 0.0
      vignette_strength: 0.0

  - slug: black_and_white
    name: Black & White
    description: >
      Grayscale rendering with controlled contrast, keeping morphology and macro layout intact.
    mode: bw
    params:
      contrast_boost: 0.3
      saturation_boost: -1.0
      grain_amount: 0.1
      posterize_levels: null
      edge_enhance: 0.2
      vignette_strength: 0.1

  - slug: duotone
    name: Duotone Poster
    description: >
      Two-tone rendering mapping luminance to primary and secondary palette colors.
    mode: duotone
    params:
      contrast_boost: 0.2
      saturation_boost: -0.5
      grain_amount: 0.05
      posterize_levels: 4
      edge_enhance: 0.1
      vignette_strength: 0.1

  - slug: grain_film
    name: Grainy Film
    description: >
      Film-like rendering with subtle grain, slight contrast boost and gentle vignette.
    mode: color
    params:
      contrast_boost: 0.25
      saturation_boost: 0.05
      grain_amount: 0.4
      posterize_levels: null
      edge_enhance: 0.15
      vignette_strength: 0.2
Backend должен загружать этот файл при старте (registry по slug).
proposal_perceptual_layer.md

9.3 apply_visual_style
Renderer реализует:

python

def apply_visual_style(image, visual_style_slug: str) -> Image:
    ...
Поведение:

по visual_style_slug загружается стиль (mode, params);

в зависимости от mode:

color:

применить:

contrast_boost;

saturation_boost;

grain_amount (добавить зерно);

edge_enhance;

vignette_strength.

bw:

конвертировать в grayscale;

усилить контраст;

добавить grain/vignette.

duotone:

grayscale → нормализованная яркость;

яркость → двухцветный маппинг (primary_color/secondary_color);

posterize_levels — число уровней яркости.

Важно:

post-processing не меняет геометрию (layout/lines/flows);

grain подчиняется variation_seed (через seed генератора случайных чисел).

9.4 Интеграция
В конце render_poster:

python

image = base_render(...)
image = apply_visual_style(image, render_params.visual_style_slug)
image.save(output_path)
PosterMetadata фиксирует visual_style_slug.

10. Нефункциональные требования
Генерация одного 1200×1200 постера должна укладываться в ~1–2 секунды (ориентир).

Renderer устойчив к edge-case’ам (минимальные density/noise и т.п.).

Детерминизм:

фиксированный RenderParams + variation_seed → одинаковый результат.

11. Definition of Done
PosterRenderer v0.2.1 готов, когда:

render_poster:

принимает RenderParams, mode, visual_style_slug;

генерирует корректный PNG (macro/meso/final);

формирует PosterMetadata (с creation_map опционально).

/generate/poster:

связывает GenerationJob → RenderParams → файлы постеров → PosterAsset.

Тестовый набор треков (jazz/blues/rock/ambient/electronic/soundtrack/mixed):

даёт различимые постеры по стилям;

macro/meso/final-версии для одного трека показывают последовательное проявление формы;

разные visual_style_slug (full_color / bw / duotone / grain_film) дают ожидаемые вариации без изменения геометрии.
arxiv
proposal_perceptual_layer.md

Генерация детерминирована, creation map логируется и может быть использована для анимации/объяснения.