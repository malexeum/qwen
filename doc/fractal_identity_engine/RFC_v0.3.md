RFC_v0.3 — Visual Composition Architecture
Статус: Proposed
Дата: 2026-08-07
Проект: AVCoder / Fractal Music Identity
Заменяет: архитектурные допущения reference-render этапа v0.2

Контекст
Reference Python-этап подтвердил работоспособность server-side контура:

text

upload → analyze → resolve-style → generate/poster
Существующие генераторы воспроизводимы, а StyleEngine способен передавать часть параметров в нелинейную модель. Однако один запуск генератора и последующий цветовой overlay не создают многослойную музыкальную композицию: это один математический материал, а не визуальная полифония.
Memory

Следующая версия должна перенести источник художественных решений из renderer.py в декларативный план, который создаётся сервером до рендера. Этот план будет общим входом Python-reference renderer и будущего Java production renderer.

Цель
Один трек должен создавать:

Один детерминированный VisualCompositionPlan v0.3.

Один Python reference preview размером 1024×1024 px.

Набор метаданных и исходных параметров, сохранённых рядом с preview.

Самодостаточный JSON-контракт для Java-клиента.

Java-клиент отвечает за:

пользовательские визуальные пресеты;

интерактивные правки;

создание вариантов;

увеличение разрешения;

export в 2048–8192 px или другие форматы;

production-quality rendering.

Не-цели
В RFC v0.3 не входят:

реализация Java renderer;

server-side final/export PNG больше 1024×1024;

preset sweep в пользовательском API;

автоматическое обучение художественного маппинга;

видео, анимация, 3D/4D-пространство;

перенос математических генераторов на GPU.

Существующий Python renderer остаётся reference-исполнителем, а не финальным production-renderer.

Основной поток
text

Track + audio_content_hash + canonical metadata
                  ↓
             Audio analysis
                  ↓
          Perceptual latent space
                  ↓
 Style / Interpretation profiles + RenderParams
                  ↓
       VisualCompositionPlanner v0.3
                  ↓
      VisualCompositionPlan v0.3 JSON
             ↙                   ↘
Python reference preview       Java client renderer
  1024×1024 only              presets / export / final
Архитектурные роли
Слой	Ответственность	Не отвечает за
fractal_core	Математические генераторы: SimState → RunResult	Палитры, post-processing, UI
StyleEngine	Перцептивная интерпретация музыки и RenderParams	Вычисление пикселей
VisualCompositionPlanner	План слоёв, seeds, ролей, параметров, transforms, палитр	Рендер PNG
Python reference renderer	Исполняет утверждённый план в 1024×1024	Пользовательские вариации, export
Java renderer	Исполняет план, применяет user presets, делает final/export	Выбор музыкального стиля или генераторной грамматики
UI	Управляет разрешёнными пользовательскими настройками Java-клиента	Изменение math core
fractal_core сохраняет канонические SimState и RunResult. В них запрещено добавлять цвета, blend mode, typographic data или canvas-specific параметры.
core.py
+1

Единый источник правды
VisualCompositionPlan v0.3 — неизменяемый, сериализуемый и версионируемый объект между backend и renderer’ами.

При одинаковых:

audio_content_hash;

нормализованных title/artist и длительности;

Style/Interpretation profile;

версии YAML-конфигурации;

variation_seed;

версии planner;

должен получаться идентичный plan. Это делает систему воспроизводимой и пригодной для regression testing, даже если Python и Java будут иметь разные реализации рендеринга.
Memory

Правило «один трек — один постер»
Production-путь:

text

1 track → 1 analysis → 1 visual plan → 1 preview PNG 1024×1024
Preset sweep не вызывается из пользовательского endpoint. Он остаётся в:

text

pytest / CI / benchmark / manual R&D
Отдельные тестовые режимы:

Режим	Планов	Рендеров	Назначение
preview	1	1, Python 1024×1024	Reference preview
validation	1	2 одинаковых	Детерминизм
sensitivity	6–7	6–7	Только лабораторный тест
java_final	1	Java	Пользовательский final
java_export	1	Java	Высокое разрешение и файлы
Независимые слои
Визуальный слой — это отдельный источник материала со своей ролью, seed, параметрами и transform. Два массива одного RunResult (orbit_map и visit_density) допустимо смешивать внутри одного слоя, но это не считается многослойной композицией.
Memory

Минимальный финальный preview должен включать от трёх до пяти независимых слоёв:

Роль	Стартовый источник	Назначение
macro_structure	Julia / Duffing / scattering	Крупная масса, композиционная ось, атмосфера
meso_rhythm	Orbit-IFS multi-trap / orbital field	Пульс, повтор, внутренняя ритмика
microtexture	Colored noise field	Воздух, зерно, спектральная шероховатость
accent	Symmetry snowflake / scattering fragment	Редкая кульминация и локальный контраст
silence_mask	Procedural mask	Negative space, пауза и иерархия
Нельзя использовать один генератор full-canvas как единственное визуальное решение вне специально разрешённого quiet_field профиля.

Seed-политика
Базовый seed должен быть производным от устойчивой идентичности трека:

text

base_seed = SHA-256(
  audio_content_hash
  + canonical_title
  + canonical_artist
  + duration_ms
  + style_profile_slug
  + config_hash
)
Затем seed каждого слоя выводится детерминированно:

text

layer_seed = SHA-256(base_seed + layer_id + generator_id)
variation_seed — это осознанный номер варианта, а не UUID backend-сессии. Его можно изменять только на Java-клиенте, когда пользователь запросил другую трактовку того же трека.
Memory

Alias-политика
Alias допустимы только на уровне пользовательского/профильного имени.

До создания SimState planner обязан выполнить:

text

profile alias → canonical generator_id → matching state builder → SimState
Пример:

text

smooth_geometric_baseline
      ↓ canonicalize
julia_orbit_trap
      ↓ build
make_sim_state_for_julia(...)
Alias не может попасть в fallback-builder. Это устраняет выявленный дефект, при котором разные треки попадали в одинаковую параметризацию.
Memory

Coverage параметров
Перед рендером planner обязан создавать отчёт parameter_coverage:

json

{
  "symmetry_bias": ["macro_orbit.theta[0]", "crystalline_accent.branches"],
  "density_level": ["macro_orbit.theta[3]", "rhythmic_points.n_points"],
  "noise_level": ["grain_field.amplitude"],
  "recursion_depth": ["macro_orbit.max_iter"],
  "motion_intensity": ["rhythmic_points.attractor_spread", "macro_orbit.rotation_deg"],
  "texture_complexity": ["crystalline_accent.branch_depth"],
  "layout_macro_shape": ["composition.archetype", "macro_orbit.transform"],
  "palette_id": ["palette.family"]
}
Если параметр не используется, planner обязан записать явное объяснение:

json

{
  "parameter": "noise_level",
  "status": "not_applicable",
  "reason": "quiet_field profile disables microtexture by design"
}
«Мёртвых» параметров без отчёта быть не должно. Это предотвращает повтор ситуации с high_motion у Julia и high_complexity в alias-ветках.
Memory

Хранение результатов
Все артефакты одного reference-preview должны лежать в отдельной папке внутри:

text

D:\WORK\AVCoder\storage\
Рекомендованная структура:

text

D:\WORK\AVCoder\storage\
  poster_runs\
    {plan_id}\
      preview.png
      visual_composition_plan.json
      render_metadata.json
      parameter_coverage.json
      layer_manifest.json
      preview_sha256.txt
Где:

preview.png — единственный Python-render, строго 1024×1024 px;

visual_composition_plan.json — единственный источник художественной истины;

render_metadata.json — версии renderer/planner/config, время и режим;

parameter_coverage.json — доказательство, как применены RenderParams;

layer_manifest.json — список слоёв, canonical generator IDs, seeds и пути/хэши промежуточных материалов;

preview_sha256.txt — контроль детерминизма и целостности.

Никакие final/export-версии не создаются Python-сервером. Их хранение и путь — зона ответственности Java-клиента.

Конфигурационный слой
На v0.3 вводятся три конфигурационных файла:

text

D:\WORK\AVCoder\configs\
  visual_composition_profiles.yaml
  generator_catalog.yaml
  palettes.yaml
visual_composition_profiles.yaml — художественно-музыкальная грамматика профилей;

generator_catalog.yaml — canonical generator IDs, aliases, builders, допустимые параметры и capabilities;

palettes.yaml — именованные палитры, tone mapping, контраст и ограничения насыщенности.

Ни один из файлов не содержит Python/Java-код. Их задача — задать declarative semantics, которые обе реализации смогут одинаково прочитать.

Переход к Java
Java-клиент получает от API:

text

VisualCompositionPlan v0.3 JSON
+ config version/hash
+ optional preview.png
Он:

валидирует schema и config hash;

исполняет базовый план;

предоставляет пользователю разрешённые local presets;

меняет variation_seed и presentation-level настройки, не изменяя музыкальный анализ;

экспортирует размеры и форматы выше Python preview.

Backend остаётся автором музыкально-визуальной композиции. Java остаётся автором быстрого и качественного исполнения, вариаций и экспорта.

Definition of Done
RFC v0.3 считается реализованным, когда:

существует schema VisualCompositionPlan v0.3;

planner строит один детерминированный plan на один трек;

plan содержит минимум три независимых слоя;

все aliases канонизированы до state builder;

существует parameter_coverage.json;

Python исполняет plan ровно в 1024×1024;

все reference-артефакты находятся в D:\WORK\AVCoder\storage\poster_runs\{plan_id}\;

Python не делает high-resolution final/export;

Java может получить self-contained JSON-plan без необходимости читать Python-код.