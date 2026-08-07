# Отчёт по этапу: аудио-анализ и style engine

## Краткое резюме

На текущем этапе стабилизирован полный пайплайн `upload -> analyze -> resolve-style`, добавлены отдельные стилевые профили для музыкальных классов `rock`, `blues_jazz`, `ambient`, `electronic`, `soundtrack`, а выбор визуального профиля перестал зависеть только от `default` и теперь может автоматически выводиться из `suggested_music_style`.[file:50][file:103]

Исправлены две архитектурные проблемы: небезопасная работа с numpy-типами в аудиоанализе и потеря смысловой связи между музыкальной классификацией и визуальным профилем в style engine.[file:50][file:103]

## Что реализовано

### 1. Аудиоанализ

В `lib/audio_analysis/analysis.py` закреплена расширенная версия анализатора, которая безопасно приводит значения numpy к Python scalar через `_to_python_scalar()` и формирует устойчивый набор признаков: `bpm`, `energy`, `brightness`, `rhythm_density`, `dynamic_range`, `repetition_score`, а также структурные поля `sections`, `recurrence_groups`, `events`.[file:50]

Сохранён слой `build_perceptual_latent()`, который переводит raw audio features в промежуточное пространство `PerceptualLatent` с осями `energy`, `tension`, `density`, `brightness`, `stability`, `smoothness`, `repetition`, `section_complexity`, `macro_shape_hint`.[file:50]

### 2. API и автоматический выбор стиля

В `api/main.py` добавлен helper `derive_style_profile_slug()`, который интерпретирует `analysis_db.suggested_music_style` и переводит его в slug существующего визуального профиля.[file:103]

Эндпоинт `/resolve-style` изменён так, что `style_profile_slug` больше не является строго обязательным входом: если он не передан клиентом явно, сервер автоматически берёт `analysis_db.suggested_music_style` и резолвит его в допустимый `StyleProfile`.[file:103]

Текущий маппинг реализован по безопасной схеме:

| suggested_music_style | style_profile_slug |
|---|---|
| `rock` | `rock` |
| `jazz`, `blues` | `blues_jazz` |
| `ambient` | `ambient` |
| `electronic` | `electronic` |
| `soundtrack`, `classical` | `soundtrack` |
| `pop` | `rock` |
| `mixed` | `default` |

Такая схема сохраняет музыкальную классификацию в аудиослое и отдельно управляет визуальной классификацией на уровне style engine, не смешивая эти ответственности.[file:103]

### 3. Style profiles

Подготовлены и подключены отдельные профили `rock`, `blues_jazz`, `ambient`, `electronic`, `soundtrack`, чтобы разные музыкальные классы начинали резолв не из одного и того же baseline, а из разных базовых значений `palette`, `geometry`, `density`, `motion_intensity`, `noise_level`, `symmetry_bias`, `complexity_bias`.[file:92]

Это создаёт архитектурно правильное разделение: `analysis.py` отвечает за музыкальную интерпретацию, `main.py` — за трансляцию в визуальный slug, `engine.py` — за финальную сборку `RenderParams`.[file:50][file:103]

## Изменения в engine.py

### Что было проблемой

В исходной версии `lib/style_engine/engine.py` resolver требовал точного попадания `style_profile_slug` в registry и сразу выбрасывал `unknown_style_profile`, если slug не совпадал с YAML-профилем один в один.[file:103]

Это делало систему хрупкой: музыкальные ярлыки `jazz`, `blues`, `classical`, `techno`, `cinematic` не были связаны с фактическими визуальными профилями, а визуальная логика легко скатывалась к fallback-сценарию.[file:92][file:103]

### Что исправлено

Обновлённый `engine.py` делает следующее:

- вводит `_safe_float()` для безопасного приведения входных значений и защиты от `None` и нечисловых значений;
- вводит `_normalize_style_slug()`, который поддерживает alias-мэппинг музыкальных ярлыков в реальные slug профилей;
- нормализует `style_profile_slug` до lookup в registry, но в `RenderParams` и ответах возвращает реальный `style_profile.slug` из загруженного профиля;
- выносит вычисление `palette_id` в отдельную функцию `_derive_palette_id()`;
- делает расчёт `RenderParams` устойчивее к неполным perceptual/input данным.[code_file:0]

Alias-мэппинг в engine дополнительно покрывает совместимость:

| Входной slug | Нормализованный slug |
|---|---|
| `jazz`, `blues` | `blues_jazz` |
| `classical`, `cinematic` | `soundtrack` |
| `techno`, `electro`, `electronic_music` | `electronic` |
| `space` | `ambient` |
| `pop` | `rock` |
| `mixed` | `default` |

Это снижает связанность между аудиоклассификатором, API-слоем и YAML-конфигами, а также уменьшает вероятность отказа из-за несовпадения имён.[code_file:0]

## Результаты тестирования

По итогам интеграционного прогона весь контур `analyze -> resolve-style` проходил успешно по всем тестовым трекам: `status_analyze = success`, `status_style = success`, а поле `render_params_warnings` оставалось пустым.[file:92]

Численные `RenderParams` уже различаются содержательно между треками разных классов: меняются `symmetry_bias`, `density_level`, `noise_level`, `motion_intensity`, `texture_complexity`, `variation_seed`, а также `palette_id` в зависимости от яркости и базового style profile.[file:92][code_file:0]

Ранее наблюдавшееся залипание на `default` устранено на уровне логики выбора профиля, а оставшиеся случаи `default` теперь интерпретируются как осознанный fallback для `mixed` и нераспознанных случаев, а не как архитектурная неисправность.[file:92][file:103]

## Архитектурный эффект

После правок система получила более чистую трёхслойную схему:

1. `analysis.py` — извлечение аудиопризнаков и музыкальная классификация.
2. `main.py` — orchestration, сохранение в БД, вывод `style_profile_slug` из `suggested_music_style`.
3. `engine.py` — нормализация slug, применение `StyleProfile`, `InterpretationProfile`, `PerceptualLatent` и `UserPreset` для сборки финальных `RenderParams`.[file:50][file:103][code_file:0]

Это уменьшает связность модулей и готовит систему к следующему этапу: более сложным `mapping_rules`, контекстным palette families, отдельным layout rules и визуальному генератору, который сможет опираться на уже согласованный набор `RenderParams`.[code_file:0]

## Следующая стадия

Следующим этапом рекомендуется перейти от линейного resolver к rule-driven style engine с четырьмя направлениями развития:

- вынести palette, layout и mapping rules из Python-кода в конфигурацию профилей;
- добавить в `PerceptualLatent` временную и секционную динамику, а не только усреднённые скаляры;
- внедрить явный отчёт о provenance: какие оси и профили внесли вклад в каждый параметр `RenderParams`;
- связать `RenderParams` с генератором графики и начать верификацию визуального результата, а не только численных параметров.[file:50][code_file:0]

## Артефакты

Подготовлены два артефакта для внедрения в кодовую базу:

- обновлённый `lib/style_engine/engine.py`;
- Markdown-отчёт для архитектурного ревью текущего этапа.[code_file:0]
