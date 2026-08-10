# ТЗ E3-C: Corrective Pass — канонические профили и контракт двух слоёв

> **Статус:** Approved for implementation
> **Дата:** 2026-08-11
> **Предусловие:** E3 engine-layer и `test12.py` существуют; задача закрывает архитектурные расхождения до E4 (reference renders).

---

## 1. Цель

Закрепить единую художественную и техническую семантику style-профилей перед визуальным бенчмарком. E3-C устраняет три класса рисков:

1. `jazz` недостижим из-за жёсткого alias `jazz → blues_jazz`;
2. два YAML-слоя профилей могут конкурировать за один и тот же художественный параметр;
3. `default` неверно выводит `noise_level` из `tension`, а не из шума/θ₅.

**Исходная цель системы сохраняется:** аудио → E1 features → HarmonyEncoder θ → осмысленная, детерминированная и объяснимая визуальная композиция.

---

## 2. Нормативная модель

### 2.1 Последовательность pipeline

```text
AudioFeatureAdapter
  → perceptual/features + harmony_theta_0..7
  → InterpretationProfile  # корректирует нормализованные perceptual axes
  → VisualCompositionProfile  # выбирает palette, generator stack, layers и generator mapping
  → StyleEngine / Renderer
```

### 2.2 Единственный источник истины

| Сущность | Канонический источник | Запрещено в другом слое |
|---|---|---|
| Palette, macro archetype, generator stack, layer order, blend modes, generator mapping | `configs/visual_composition_profiles.yaml` | Переопределять эти свойства в `style_profiles/*.yaml` |
| Нормализованные perceptual biases и формулы их преобразования | `configs/interpretation_profiles/*.yaml` | Выбирать генераторы или palette |
| Жанровый slug и допустимые aliases | единый `_STYLE_ALIASES` в `engine.py` + тест реестра | Дублировать неявные aliases в YAML |

`configs/style_profiles/*.yaml` допускается сохранить только как legacy metadata / input-style registry, если он реально используется загрузчиком. Он не должен менять `palette`, `geometry`, `density`, `contrast` или другие художественные решения, уже определённые в VisualCompositionProfile. Если эти файлы нужны API, их поля должны быть явно помечены как `metadata_only: true`; если не нужны — удалить отдельной миграцией, не в рамках E3-C.

---

## 3. Канонические жанры и aliases

### 3.1 Canonical slugs

Следующие профили должны быть адресуемыми напрямую и не могут быть alias-целями друг друга:

```text
ambient
blues_jazz
jazz
classical
electronic
rock
pop
default
```

### 3.2 Обязательная правка alias-реестра

Удалить правило `jazz → blues_jazz`. `jazz` — самостоятельный профиль и должен резолвиться как `jazz`.

Допустимый минимум aliases:

```python
_STYLE_ALIASES = {
    "blues": "blues_jazz",
    "blues_jazz": "blues_jazz",
    "electro": "electronic",
    "cinematic": "soundtrack",  # только после появления soundtrack profile
}
```

`cinematic → soundtrack` запрещён, пока `soundtrack` отсутствует в реестре профилей. На этот период: удалить alias либо направить в `default` с явным warning.

### 3.3 Семантическое различие

| Профиль | Образ | Принцип |
|---|---|---|
| `blues_jazz` | тёплая человеческая импровизация | органика, средняя плотность, тёплая асимметрия |
| `jazz` | активный контрапункт | θ₁, θ₂ и θ₆ проявляются сильнее; композиция сложнее, но не грязнее |
| `rock` | удар и контролируемый разлом | θ₃/θ₅/θ₆ усиливают давление, но шум не является постоянным фоном |
| `pop` | центрированный запоминаемый мотив | θ₀/θ₁/θ₇ дают ясность, пульс и симметрию |

---

## 4. Обязательные изменения

### C1. Исправить alias-contract

**Файл:** `lib/style_engine/engine.py`

- Удалить `"jazz": "blues_jazz"`.
- Сохранить применение aliases до registry lookup.
- Для отсутствующего destination slug бросать `ValidationError` с текстом, содержащим исходный slug, нормализованный slug и список доступных canonical profiles.

### C2. Исправить default interpretation

**Файл:** `configs/interpretation_profiles/default.yaml`

Заменить неверную формулу:

```yaml
noise_level:
  formula: "base + (tension - 0.5) * 0.4"
```

на формулу, где главный сигнал — измеренный шум и θ₅:

```yaml
noise_level:
  formula: "base + (noise_level - 0.5) * 0.35 + (harmony_theta_5 - 0.5) * 0.25"
```

Требования:
- Формула должна вычисляться в существующем безопасном formula evaluator.
- Результат клипируется в `[0, 1]` единственным централизованным механизмом.
- `tension` не участвует в вычислении target `noise_level`; он остаётся доступным для contrast/deformation mappings.

### C3. Развести два профилирующих слоя

- Зафиксировать loading order согласно разделу 2.1.
- `VisualCompositionProfile` — единственный владелец palette/generator stack/layer order/blend mode.
- `InterpretationProfile` — только numeric axis transforms и `layout_macro_shape`.
- Если `style_profiles/*.yaml` остаются используемыми, добавить комментарий-схему и `metadata_only: true`; загрузчик не должен брать из них palette/geometry/density/contrast для рендера.
- Не удалять legacy `style_profiles` в E3-C без отдельного migration plan.

### C4. Palette registry audit

**Файлы:** palette registry и все затронутые profile YAML.

- Проверить, что каждый palette slug, используемый всеми слоями, существует в едином registry.
- Не создавать второй синоним палитры без причины.
- Если `dark_saturated`, `vivid_light`, `warm_midnight` являются legacy-названиями для `crimson_forge`, `vivid_bloom`, `nocturne_amber`, выбрать одно canonical name и выполнить явную миграцию references.
- Добавить validation: неизвестный palette slug → `ValidationError`, не fallback.

### C5. Художественные defaults (только если `style_profiles` остаются active)

Если style profile влияет на actual render params, применить следующие стартовые значения:

```yaml
rock:
  contrast: 0.72
  density: 0.66
  motion_intensity: 0.74
  noise_level: 0.42
  symmetry_bias: 0.35
  complexity_bias: 0.68

pop:
  contrast: 0.60
  density: 0.55
  motion_intensity: 0.60
  noise_level: 0.30
  symmetry_bias: 0.65
  complexity_bias: 0.50
```

Для rock динамический рост хаоса должен приходить от E1 `noise_level` и `harmony_theta_5`, а не быть навечно зашитым в profile default.

---

## 5. Тесты

Расширить `test12.py` либо создать `test13_e3_corrective.py`. Все тесты обязаны использовать реальные pinned E1/θ data, где это применимо.

### T1. Canonical genre resolution

```python
assert normalize_style_slug("jazz") == "jazz"
assert normalize_style_slug("blues") == "blues_jazz"
assert resolve("jazz").profile_slug == "jazz"
assert resolve("blues_jazz").profile_slug == "blues_jazz"
```

### T2. No dangling aliases

Для каждого alias destination существует canonical profile. `cinematic` не может резолвиться в отсутствующий `soundtrack`.

### T3. Default noise semantic test

При фиксированных прочих axes увеличение `noise_level` или `harmony_theta_5` повышает resolved `noise_level`; изменение `tension` при тех же `noise_level`/θ₅ его не меняет.

### T4. Layer ownership

Проверить, что palette, generators, layer order и blend mode берутся только из VisualCompositionProfile. InterpretationProfile не может их определить или переопределить.

### T5. Palette registry validation

Все palette slugs всех profile YAML резолвятся; неизвестный slug вызывает `ValidationError`.

### T6. Jazz vs blues_jazz differentiation

На одном и том же pinned feature/θ input `jazz` и `blues_jazz` дают разные composition identity либо минимум три разных resolved generator parameters.

### T7. Determinism / regression

Все существующие E1/E2/Test11/Test12 тесты зелёные. Тот же input + canonical profile → тот же `RenderParams`, `mapping_trace` и seed.

---

## 6. Definition of Done

- [ ] `jazz` больше не alias `blues_jazz` и доступен как самостоятельный профиль.
- [ ] Нет alias, ведущих в несуществующий profile.
- [ ] `default.noise_level` семантически зависит от `noise_level` + `harmony_theta_5`, не от `tension`.
- [ ] Чётко реализован и задокументирован порядок Interpretation → VisualComposition.
- [ ] Palette registry валидируется; нет неявных / дублирующихся palette names.
- [ ] Тесты T1–T7 проходят, как и регрессионные test9–test12.
- [ ] В отчёте прогона указаны resolved mappings для `jazz`, `blues_jazz`, `rock`, `pop`.

---

## 7. Что дальше

После E3-C не расширять число профилей и не добавлять генераторы. Следующий этап E4: по 3 фиксированных reference render на 7 жанровых профилей, визуальная матрица и ручной перцептивный аудит различимости.
