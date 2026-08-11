# Архитектурный обзор проекта Fractal Identity Engine

> **Состояние на:** 11 августа 2026  
> **Репозиторий:** `malexeum/qwen`  
> **HEAD:** `b973cafe50f93c5fb58e18791b540b15c09965c8`  
> **Текущий этап:** завершены E1–E3 и техническая часть E4-C0/C1; следующий практический рубеж — воспроизводимый corpus v2 с честным provenance и ручным перцептивным аудитом.

---

## 1. Замысел

Проект строит причинную визуальную идентичность музыкального трека. Его цель не в том, чтобы подобрать случайную абстрактную картинку по жанровому ярлыку, а в том, чтобы преобразовать свойства аудио в объяснимую цепочку визуальных решений.

Целевая формула:

```text
Audio → E1 perceptual features → E2 harmony vector θ
      → Style/Interpretation profiles → RenderParams
      → Composition layers → Fractal generators → PNG + provenance
```

Ключевой критерий качества: для любого visual можно ответить на вопрос «почему он получился именно таким?» через feature artifact, θ-вектор, formula trace, параметры конкретного generator layer и seed.

---

## 2. Пройденные этапы

| Этап | Что сделал | Статус |
|---|---|---|
| E1 | Извлечение признаков из аудио: energy, tension, density, stability, section complexity, spectral данные, noise proxy | Закрыт |
| E1 fixes | Исправлены деградировавшие `symmetry_bias`, `section_complexity`, `noise_level`; добавлены проверки разброса | Закрыт |
| E2 | `HarmonyEncoder`: 8-мерный θ-вектор, θ-hash, seed integration, mapping axes | Закрыт |
| E2 integration | Реальные E1 данные проверены в цепочке feature → θ → seed → StyleEngine | Закрыт |
| E3 | θ-оси добавлены в `RenderParams`, resolver, trace и profile mappings | Закрыт |
| E3-C | Исправлены aliases, `noise_proxy`, palette/registry contracts, CWD-зависимость конфигов | Закрыт |
| E4 v1 | Первые 22 reference renders и технический baseline | Исторический corpus; не baseline для E5 |
| E4-CB | Выявлены требования к canonical θ-hash, реальным feature hashes и provenance v2 | В работе |
| C0/C1 | `GeneratorRuntime` и его подключение к E4 harness через canonical composition YAML | Закрыт технически |

---

## 3. Слои системы

### 3.1 E1: Audio and perceptual layer

**Назначение:** извлечь из аудио не жанровый label, а нормализованные наблюдаемые характеристики.

Основные оси:

```text
energy, tension, density, brightness, stability, smoothness,
repetition, section_complexity, noise_proxy, macro_shape_hint
```

`noise_proxy` — нормализованный proxy спектральной шумности. Он не заменяется `density` или `tension`:

```text
noise_proxy explicit → использовать напрямую
spectral_flatness present → log-normalize
неизвестно → 0.5, нейтральный fallback
```

### 3.2 E2: HarmonyEncoder

`HarmonyEncoder` строит вектор гармонической сигнатуры:

| Ось | Семантика |
|---|---|
| θ₀ | Гармоническая чистота |
| θ₁ | Стабильность × смена гармоний |
| θ₂ | Структурная плотность |
| θ₃ | Неразрешённое напряжение |
| θ₄ | Чистый контраст секций |
| θ₅ | Тембральный хаос |
| θ₆ | Энтропия развития |
| θ₇ | Кристалличность |

θ участвует в двух разных механизмах:

1. **Identity / seed:** именованный canonical θ-hash влияет на variation seed.
2. **Causality:** θ входит в formula mappings и меняет `RenderParams`.

Правильный hash строится из именованного вектора, а не из отсортированного набора значений:

```text
{theta_0: 0.10, theta_1: 0.90} ≠ {theta_0: 0.90, theta_1: 0.10}
```

### 3.3 StyleEngine: interpretation layer

`lib/style_engine/engine.py` соединяет style profile, perceptual axes, θ и user preset.

Последовательность resolver:

```text
Base style layer
  → Interpretation formulas
  → User preset layer
  → Guardrails / clamp
  → RenderParams + MappingTrace
```

`MappingTraceEntry` содержит:

```text
param, source, raw, final, stage,
source_axes, formula, input_values,
layer_id, generator_id
```

### 3.4 Canonical style registry

Canonical directory:

```text
lib/style_engine/configs/style_profiles/
```

| Slug | Palette | Роль |
|---|---|---|
| ambient | lunar_mist | Пространство и плавность |
| blues_jazz | warm_midnight | Органическая ночная импровизация |
| jazz | nocturne_amber | Контрапункт и тёплая гармоническая активность |
| classical | ivory_cobalt | Иерархия и ясный центр |
| electronic | neon_dark | Синтетическая плотность |
| rock | dark_saturated | Напряжение и контролируемый разлом |
| pop | vivid_light | Центрированный чистый мотив |
| default | neutral_noir | Явный fallback/smoke profile |

Все параметры StyleProfile находятся на верхнем уровне YAML. Legacy `base_params` не считается canonical schema.

### 3.5 Composition and generator layer

Canonical composition contract:

```text
lib/style_engine/configs/visual_composition_profiles.yaml
```

Он определяет для каждого genre profile:

```text
profile slug → palette → ordered layers → builder IDs → mappings
```

`GeneratorRuntime` в `lib/style_engine/generator_runtime.py` — адаптер между StyleEngine и production backend `lib/generators.py`.

```text
StyleEngine RenderParams
  → GeneratorRuntime.resolve_stack()
  → ResolvedGeneratorLayer[]
  → GeneratorRuntime.render()
  → output + runtime journal
```

`generator_stack` — не декларация YAML и не строка harness. Это журнал реально вызванных builders, созданный только после успешного исполнения layer.

### 3.6 E4 harness and provenance

`e4_render_harness.py` использует canonical composition YAML по умолчанию и рассчитывает hash именно реально загруженного файла.

Provenance v2 должен содержать:

```text
experiment_id
manifest_sha256
renderer_sha / git_sha
profile_config_hash
palette_config_hash
feature_hash
canonical_theta_hash
variation_seed
resolved generator stack
mapping_trace
output_sha256
```

Stub renderer допустим только для development; для baseline corpus он обязан приводить к ошибке без явного `--allow-stub`.

---

## 4. Текущая точка

На HEAD `b973cafe` система технически умеет провести доказуемую цепочку:

```text
harmony_theta_5 changes
  → noise_level / texture_complexity formula changes
  → RenderParams changes
  → GeneratorRuntime receives changed mapping
  → actual builder execution is journaled
  → output can be signed with SHA-256
```

Достигнуты ключевые инварианты:

- registry не зависит от CWD;
- canonical genre profiles существуют и имеют разные palette identities;
- θ=0.5 нейтрален для formula deltas;
- relevant θ меняет ожидаемый target;
- irrelevant θ не меняет несвязанный target;
- composition YAML реально загружается harness;
- отсутствие composition slug вызывает ошибку, не fallback;
- runtime stack отражает исполнение, а не описание.

Последний технический merge объединил A0, A1, B, C0 и C1; заявленный suite — 227 tests, 0 failures.

---

## 5. Незакрытые риски

### 5.1 E4 v1 — исторический, но не финальный baseline

Corpus v1 нельзя использовать для E5 regression gate, потому что до corrective work он мог содержать:

- placeholder feature hashes;
- старую схему θ-hash;
- provenance без полного runtime/manifest/config context;
- рендеры до строгого runtime composition contract.

Его нельзя удалять: это исторический след проектных решений. Но re-baseline должен быть v2.

### 5.2 Реальные feature artifacts

Каждый fixture v2 обязан иметь либо:

```text
audio_content_hash + feature_hash
```

либо честную маркировку:

```text
synthetic_fixture: true + feature_hash
```

Placeholder values запрещены.

### 5.3 Human audit

Технический SHA не отвечает на вопрос, выразителен ли visual. E4 считается полностью завершённым только после ручного аудита 21 canonical render по критериям:

```text
genre identity, theta response, composition,
technical cleanliness, inter-profile differentiation
```

---

## 6. Дорожная карта

### Шаг D1 — real feature provenance

Создать 22 pinned feature artifacts и immutable `fixtures_manifest_v2.yaml`.

**Gate:**
- отсутствуют `placeholder_*` hashes;
- каждый fixture имеет real feature hash;
- θ-hash пересчитывается из именованного вектора;
- manifest/profile/feature hashes совпадают.

### Шаг D2 — E4 v2 render corpus

Запустить harness с canonical composition YAML и реальным `GeneratorRuntime`.

Создать:

```text
22 PNG
22 provenance JSON
contact sheet
technical report
```

**Gate:**
- output hashes реальны и уникальны;
- минимум 3 rerender совпадают bit-exact;
- stub mode не использовался;
- runtime journal содержит реальные builders и layer IDs.

### Шаг D3 — human perceptual audit

Оценить 21 canonical render по шкале 0–3.

**Gate:**
- среднее по каждому критерию ≥ 2.0;
- нет оценки 0 по композиции или технической чистоте;
- есть комментарий на каждый score < 2;
- `default_smoke` оценивается только как технический fallback.

Если порог не достигнут: создать issue и начать отдельный tuning experiment v3. Не менять fixture или seed задним числом.

### Шаг E5 — regression gate

Только после D1–D3:

```text
strict SHA-256 baseline comparison
+ SSIM ≥ 0.995 as secondary perceptual signal
```

Любое одобренное визуальное изменение создаёт новый `experiment_id`; старый baseline архивируется, не перезаписывается.

### Cleanup — legacy palette-named profiles

Отдельно проаудировать прямые использования `lunar_mist.yaml` и `ivory_cobalt.yaml` как style profiles. Решение принимается только после поиска потребителей:

```text
remove / migrate / explicitly deprecate
```

Не путать palette slug и genre style slug.

---

## 7. Правила, которые нельзя нарушать

- Не строить θ-hash из сортированных значений без имён осей.
- Не использовать CWD как источник конфигурации.
- Не заменять отсутствующий profile молча на `default`.
- Не создавать provenance до фактического PNG render.
- Не считать harness generator-ом.
- Не принимать stub output как E4/E5 baseline.
- Не менять seed, feature artifact или profile после неудачной картинки.
- Не перезаписывать исторический corpus: новый experiment → новый immutable baseline.
- Не подменять human audit техническими метриками.

---

## 8. Критерий успеха проекта

Проект достигнет следующей зрелости, когда для каждого PNG можно автоматически восстановить и человеку объяснить:

```text
какой input был подан
→ какие features и θ получены
→ какие формулы изменили RenderParams
→ какие layers/builders были вызваны
→ с какими параметрами и seed
→ почему получился этот visual
```

Тогда система станет не генератором случайных обложек, а воспроизводимой машиной перевода музыкальной структуры в фрактальную идентичность.
