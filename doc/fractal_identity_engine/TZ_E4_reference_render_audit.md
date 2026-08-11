# ТЗ E4: Reference Renders и перцептивный аудит

> **Статус:** Ready for implementation
> **Предусловие:** E1, E2, E3 и E3-C закрыты; `nocturne_amber` и все palette slugs сначала проходят registry validation.
> **Цель:** доказать не кодовую, а визуальную состоятельность цепочки `audio → θ → profile → render`.

---

## 1. Результат E4

Создать воспроизводимый набор из **21 reference render**: 7 canonical профилей × 3 pinned audio/input fixtures. Для каждого рендера сохранить PNG, полный provenance JSON и запись в сводной матрице. Затем провести ручной перцептивный аудит.

Canonical профили:

```text
ambient, blues_jazz, jazz, classical, electronic, rock, pop
```

`default` — fallback-профиль: не входит в 21 художественный reference render, но проходит один smoke-render.

---

## 2. Gate 0 — до рендеров

До запуска E4 выполнить и сохранить результат:

1. Полный regression suite `test9.py`–`test13_e3_corrective.py`.
2. Palette validation для всех profile YAML.
3. Устранить `nocturne_amber` из списка неизвестных / невалидных палитр.
4. Убедиться, что `jazz` — canonical slug, а не alias `blues_jazz`.
5. Проверить, что `mapping_trace` включает θ-driven mappings, `noise_proxy`, input values, resolved values и variation seed.

Если любой пункт Gate 0 не проходит, reference renders не создаются.

---

## 3. Fixture protocol

### 3.1 Три входа на профиль

Для каждого профиля подготовить три фиксированных входа:

| Fixture | Назначение | Требование |
|---|---|---|
| A — archetypal | Характерный для профиля трек | Реальный аудиофайл или pinned feature artifact |
| B — boundary | Пограничный случай | По крайней мере две ключевые оси θ заметно отличаются от A |
| C — stress | Трудный случай | Высокие tension/noise/section contrast либо их жанрово осмысленный аналог |

Не подбирать треки задним числом для «красивой картинки». Сначала фиксируются input hashes, profile slug и seed, затем выполняется рендер.

### 3.2 Manifest

Создать `artifacts/e4/fixtures_manifest.yaml`:

```yaml
experiment_id: e4_reference_render_audit_v1
renderer_version: <git SHA>
profile_library_version: "0.4.0"
fixtures:
  - id: jazz_A
    profile_slug: jazz
    audio_content_hash: <sha256>|null
    feature_artifact: <path>
    feature_hash: <sha256>
    harmony_theta: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    harmony_theta_hash: <hash>
    variation_seed: <positive int>
    expected_palette: <canonical palette slug>
```

Manifest нельзя перезаписывать после первого успешного рендера; изменения требуют нового `experiment_id`.

---

## 4. Рендер и provenance

### 4.1 Формат артефактов

```text
artifacts/e4/<experiment_id>/
  manifest.yaml
  renders/<profile_slug>/<fixture_id>.png
  provenance/<profile_slug>/<fixture_id>.json
  contact_sheet.png
  audit_matrix.csv
  report.md
```

Не коммитить PNG больших размеров в Git без принятой LFS-политики. В Git обязательно коммитятся manifest, provenance JSON, audit matrix и report; сами PNG хранятся согласно политике артефактов проекта или через Git LFS.

### 4.2 Обязательный provenance JSON

```json
{
  "fixture_id": "jazz_A",
  "profile_slug": "jazz",
  "git_sha": "...",
  "feature_hash": "...",
  "harmony_theta": [0.0],
  "harmony_theta_hash": "...",
  "variation_seed": 0,
  "palette_id": "...",
  "generator_stack": ["..."],
  "mapping_trace": ["..."],
  "output_sha256": "...",
  "renderer_params": {"width": 0, "height": 0}
}
```

### 4.3 Reproducibility test

Для трёх произвольно выбранных fixtures повторить рендер без изменения manifest. `output_sha256` должен совпасть. При расхождении E4 останавливается и создаётся bug report.

---

## 5. Перцептивный аудит

Оценка проводится человеком по шкале 0–3; нельзя подменять её метрикой пиксельной разницы.

| Критерий | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Идентичность жанра | Неотличим | Случайные намёки | Узнаваем с оговорками | Ясно выражен |
| Реакция на θ | Не видна | Случайна | Частично читается | Причинно читается по trace и картинке |
| Композиция | Разваливается | Есть дефекты | Устойчива | Цельна и выразительна |
| Техническая чистота | Артефакты/ошибки | Заметные дефекты | Приемлемо | Чисто |
| Межпрофильная различимость | Похожа на другой профиль | Слабо отличается | Отличается | Не спутать |

Каждый render получает оценку и короткий комментарий. Общий проходной порог: среднее ≥ 2.0 по каждому критерию; ни один render не имеет 0 по технической чистоте или композиции.

---

## 6. Контрольные сравнения

### C1. Same audio, different profile

Для одного pinned input отрендерить `jazz`, `blues_jazz`, `rock`, `pop`. Ожидание: разные palette/generator stack и минимум три отличающихся resolved parameters на пару профилей.

### C2. Same profile, changed θ

Для одного профиля и fixture A создать controlled variant: изменить одну используемую θ-ось на `+0.15` c clip `[0,1]`, не меняя остальные features. Ожидание: новый seed, changed mapping_trace и наблюдаемая, но не разрушающая, разница изображения.

### C3. Noise semantics

Для fixture с одинаковыми energy/density сравнить `noise_proxy=0.2` и `noise_proxy=0.8`. Ожидание: контролируемый рост фактуры/хаоса, без необъяснимого роста motion или density.

---

## 7. Автотест `test14_e4_provenance.py`

- Каждый fixture manifest валиден, profile/palette существуют.
- Есть 21 ожидаемый provenance artifact или осмысленная причина skip.
- Все JSON содержат обязательные поля и не имеют silent fallback.
- `mapping_trace` содержит минимум 3 θ-driven entries для genre profile.
- Output hashes присутствуют; повторные 3 renders совпадают.
- C1/C2/C3 имеют trace-based доказательства изменений.

---

## 8. Definition of Done

- [ ] Gate 0 пройден, включая palette registry и `nocturne_amber`.
- [ ] 21 reference render созданы по immutable manifest.
- [ ] Provenance JSON и output hashes есть для каждого рендера.
- [ ] Contact sheet и `audit_matrix.csv` собраны.
- [ ] Минимум три rerender совпадают по SHA-256.
- [ ] Все критерии аудита имеют среднее ≥ 2.0; нет критических 0.
- [ ] `test14_e4_provenance.py` проходит.
- [ ] `docs/E4_report_<date>.md` содержит результаты, провалы, ссылки на артефакты и решение: tune E3 / начать E5.

---

## 9. Запреты E4

- Не менять E1/E2 формулы или профили в процессе оценки без отдельного issue и нового experiment_id.
- Не менять seed после неудачного изображения.
- Не подменять ручной аудит только метриками изображений.
- Не расширять генераторный каталог до завершения аудита.
