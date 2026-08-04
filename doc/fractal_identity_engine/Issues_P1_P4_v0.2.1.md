# Issue P1 — Implement PerceptualLatent (minimal version)

**Priority:** P0  
**Area:** backend / analysis / storage  
**Depends on:** Issue 1 (RFC v0.2.1), Issue 2 (domain v0.2.1)

## Goal
Реализовать минимальный слой `PerceptualLatent`, который строится на основе `AudioAnalysis` и сохраняет человеческо-понятные оси (energy, tension, density, brightness, stability, smoothness, repetition, macro_shape_hint) для дальнейшего использования style engine.

## Context
- `POST /analyze` уже существует и создаёт `AudioAnalysis`.
- RFC_v0.2.1 описывает `PerceptualLatent` как обязательный слой между analysis и style engine.
- Сейчас perceptual слой отсутствует — style resolver работает напрямую от сырого анализа (или заглушек).

## Tasks
1. **Структура PerceptualLatent**
   - Определить модель:
     - `id`
     - `analysis_id`
     - `track_id`
     - `energy`
     - `tension`
     - `density`
     - `brightness`
     - `stability`
     - `smoothness`
     - `repetition`
     - `section_complexity`
     - `macro_shape_hint`
     - `created_at`

   - Решить, хранится ли:
     - в отдельной таблице `perceptual_latent`;
     - или как JSON-поле `perceptual` внутри `AudioAnalysis`.

2. **Mapping AudioAnalysis → PerceptualLatent**
   - Реализовать функцию, которая:
     - читает `AudioAnalysis`;
     - вычисляет оси:
       - `energy` (по RMS/loudness),
       - `tension` (по динамике/гармоническим сдвигам),
       - `density` (по rhythm_density),
       - `brightness` (по spectral_centroid/brightness),
       - `stability` (по tonal stability и variance),
       - `smoothness` (по плавности изменений энергии/спектра),
       - `repetition` (по repetition_score, recurrence),
       - `section_complexity` (по количеству/разнообразию секций),
       - `macro_shape_hint` (простая метка формы).
     - возвращает `PerceptualLatent`.

3. **Интеграция в /analyze**
   - Обновить `POST /analyze`:
     - после расчёта `AudioAnalysis` вызывать perceptual mapping;
     - сохранять результат в БД;
     - включать перцептивные оси в ответ (или ссылку на `perceptual_id`).

4. **Обработка ошибок**
   - При невозможности расчёта отдельных осей:
     - явно помечать fallback-поля (например, `null` + флаг);
     - не заполнять фиктивными числами.

## Deliverables
- Модель и таблица/JSON для `PerceptualLatent`.
- Функция mapping AudioAnalysis → PerceptualLatent.
- Обновлённый `/analyze`, создающий и возвращающий перцептивные оси.

## Acceptance criteria
- Для любого валидного `AudioAnalysis` создаётся связанный `PerceptualLatent`.
- Повторный анализ того же трека даёт те же (или близкие) значения осей.
- `POST /analyze` возвращает перцептивные оси или ссылку на них.
- Перцептивный слой не ломает существующий pipeline, если его временно игнорировать в style engine.

---

# Issue P2 — Add InterpretationProfiles configs

**Priority:** P0  
**Area:** backend / style engine / config  
**Depends on:** Issue 1, Issue 2, Issue P1

## Goal
Ввести `InterpretationProfile` как конфигурационный слой, который описывает, как `PerceptualLatent` превращается в фрактальные параметры. Добавить 2–3 профиля для v0.2.1 и обеспечить их загрузку style engine.

## Context
Профили нужны, чтобы пользователь (или система) выбирал не “сырые параметры генератора”, а характер интерпретации (organic, geometric, dark и т.п.), а движок уже решал, как именно перцептивные оси управляют фракталом.

## Tasks
1. **Формат профиля**
   - Определить формат (YAML/JSON):
     - `slug`
     - `name`
     - `description`
     - `axis_weights` (energy, tension, density, brightness, stability, smoothness, repetition)
     - `mapping_rules` (описание функций/шаблонов):
       - какие оси влияют на `symmetry_bias`,
       - какие — на `recursion_depth`,
       - какие — на `stochastic_term`,
       - какие — на `palette`, `density`, `motion_intensity`.

2. **Минимальный набор профилей**
   - Создать хотя бы 2–3 профиля:
     - `organic_fluid`
     - `geometric_rhythmic`
     - `dark_tense`

   - Описать для каждого:
     - какие оси усиливаются/ослабляются;
     - как меняются основные параметры рендера.

3. **Loader**
   - Реализовать загрузчик профилей:
     - путь, например `config/interpretation_profiles/*.yaml`;
     - валидация (наличие обязательных полей);
     - кэширование в памяти.

4. **Интеграция**
   - Обеспечить доступ к профилям:
     - style engine должен уметь получить `InterpretationProfile` по `slug`;
     - сохранить выбранный профиль в `GenerationJob`/`UserPreset` (как минимум slug).

## Deliverables
- Формат `InterpretationProfile`.
- 2–3 конфигурационных файла профилей.
- Loader + валидация.
- Интеграция в style engine (без полного рефактора /resolve-style — это в P3).

## Acceptance criteria
- Профили лежат в конфиг-файлах, а не в коде.
- Style engine может получить профиль по slug.
- Профили различаются по mapping_logic (а не только по названию).
- Профиль сохраняется или логируется для каждого рендера.

---

# Issue P3 — Split StyleEngine (Perceptual + Visual) and update /resolve-style

**Priority:** P0  
**Area:** backend / style engine  
**Depends on:** Issues 1–2, P1, P2

## Goal
Разделить style engine на два слоя:
- perceptual resolver: `AudioAnalysis → PerceptualLatent`;
- visual resolver: `PerceptualLatent + StyleProfile + InterpretationProfile + UserPreset → RenderParams`;
и обновить `/resolve-style`, чтобы он работал через новую схему.

## Context
Сейчас style resolver строит `RenderParams` напрямую из `AudioAnalysis` + `StyleProfile` + `UserPreset`. После P1 и P2 у нас появится `PerceptualLatent` и `InterpretationProfile`, но они ещё не встроены в runtime.

## Tasks
1. **Perceptual resolver**
   - Выделить или реализовать функцию:
     - вход: `AudioAnalysis`;
     - выход: `PerceptualLatent` (если не создан ранее);
   - Обеспечить возможность reuse: если `PerceptualLatent` уже есть, не пересчитывать без необходимости.

2. **Visual resolver**
   - Реализовать функцию:
     - вход: `PerceptualLatent`, `StyleProfile`, `InterpretationProfile`, `UserPreset`;
     - выход: `RenderParams`.

   - Использовать:
     - axis_weights и mapping_rules из `InterpretationProfile`;
     - базовые bias’ы из `StyleProfile`;
     - явные значения слайдеров из `UserPreset`.

3. **Обновить /resolve-style**
   - Новый контракт:
     - вход: `project_id`, `analysis_id`, `style_profile_slug`, `interpretation_profile_slug`, `preset_id` (или inline-параметры);
     - backend:
       - загружает `AudioAnalysis` и `PerceptualLatent`;
       - загружает `StyleProfile` и `InterpretationProfile`;
       - применяет visual resolver;
       - сохраняет `RenderParams` (в `GenerationJob` или отдельном поле).

4. **Совместимость**
   - Обеспечить fallback:
     - если `InterpretationProfile` не указан, использовать default;
     - если `PerceptualLatent` нет (старые проекты), попытаться создать на лету или использовать простое mapping.

## Deliverables
- Переработанный style engine (perceptual + visual).
- Обновлённый `/resolve-style` endpoint.
- Обновлённый `RenderParams` контракт.

## Acceptance criteria
- `resolve-style` больше не работает напрямую только от `AudioAnalysis`.
- `PerceptualLatent` используется в расчёте `RenderParams`.
- Разные `InterpretationProfile` для одного и того же трека дают разные `RenderParams`.
- Старый pipeline не ломается для существующих проектов (минимум — через sensible default).

---

# Issue P4 — Adapt PosterRenderer to Perceptual & Interpretation layers

**Priority:** P1  
**Area:** renderer / backend / visual design  
**Depends on:** Issue P3 (StyleEngine split), косвенно P1–P2

## Goal
Обновить генератор постера так, чтобы `RenderParams`, обогащённые `PerceptualLatent` и `InterpretationProfile`, реально влияли на композицию и стиль, а разные профили давали визуально различимые паттерны для одного и того же трека.

## Context
Сейчас poster renderer рассматривает `RenderParams` без перцептивной семантики. После P3 у нас появится richer `RenderParams` с информацией о energy/tension/density/brightness/stability, выбранном interpretation profile и macro_shape_hint, и это нужно использовать.

## Tasks
1. **Расширить RenderParams**
   - Добавить (или убедиться, что уже есть) поля:
     - symmetry_bias;
     - recursion_depth;
     - stochastic_term;
     - palette_id;
     - density_profile;
     - layout/macro_shape_hint;
     - profile_slug (interpretation).

2. **Композиция и форма**
   - Использовать `macro_shape_hint` и `section_complexity`:
     - для выбора/layout крупных доменов (background vs foreground);
     - для распределения плотности по “зонам” постера;
     - для акцентирования “кульминаций”.

3. **Профили и визуальное поведение**
   - Для каждого `InterpretationProfile` задать характерный режим:
     - `organic_fluid`: плавные, непрерывные структуры, soft noise;
     - `geometric_rhythmic`: жёсткая геометрия, повторяемые паттерны;
     - `dark_tense`: высокая плотность, контраст, асимметрия.
   - Убедиться, что при смене профиля картинка меняется не только по цвету, но и по морфологии.

4. **Сохранение совместимости**
   - Не ломать базовый pipeline:
     - если перцептивная информация частично отсутствует, использовать defaults;
     - в худшем случае — fallback к старому режиму (simple mapping).

5. **Визуальный sanity-check**
   - Собрать небольшой набор тест-треков;
   - для каждого рендерить 2–3 профиля;
   - глазами проверить различимость профилей и связь с energy/tension/density.

## Deliverables
- Обновлённый renderer, учитывающий perceptual/interpretive поля.
- Демонстрационный набор рендеров для разных профилей.
- Документ/ноты, описывающие связь между профилями и визуальным поведением.

## Acceptance criteria
- Один и тот же трек с разными interpretation profiles даёт визуально разные постеры.
- Эти различия согласуются с описанием профилей (organic vs geometric vs dark).
- Poster сохраняет связь с перцептивными осями (пример: более плотный/напряжённый трек → более плотная/напряжённая композиция).
