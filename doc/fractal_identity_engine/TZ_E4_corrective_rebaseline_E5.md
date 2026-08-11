# ТЗ E4-CB: Коррекция baseline E4 и подготовка E5

> **Статус:** обязательная доработка. Не запускать E5 regression gate и не объявлять E4 полностью закрытым до выполнения всех пунктов.
> **Причина:** текущий E4 corpus технически воспроизводим, но θ-hash построен как hash множества значений, а не именованного вектора; `feature_hash` содержит placeholders; отсутствует обязательный ручной перцептивный аудит.

---

## 1. Цель и границы

Цель — создать новый, семантически корректный и полностью трассируемый corpus `e4_reference_render_audit_v2`. Старый corpus `e4_reference_render_audit_v1` не удалять и не изменять: это исторический артефакт.

Входит:
- исправление canonical θ-hash;
- реальные hashes входных features/audio;
- новый immutable manifest и новый render corpus;
- технический regression suite;
- ручной перцептивный аудит.

Не входит:
- новые генераторы, новые жанры, изменение формул E1/E2, тюнинг профилей по результатам рендера без отдельного issue.

---

## 2. Блокер CB-1: canonical θ-hash

### 2.1 Запрещённая реализация

Запрещено строить `theta_hash` из отсортированных **значений** θ. Такая схема одинаково хэширует разные семантические назначения значений осям.

```text
{theta_0: 0.10, theta_1: 0.90} != {theta_0: 0.90, theta_1: 0.10}
```

Эти два входа обязаны иметь разные hash и seed.

### 2.2 Обязательная реализация

```python
THETA_AXES = (
    "harmony_theta_0", "harmony_theta_1",
    "harmony_theta_2", "harmony_theta_3",
    "harmony_theta_4", "harmony_theta_5",
    "harmony_theta_6", "harmony_theta_7",
)

def compute_theta_hash(theta: Mapping[str, float]) -> str:
    payload = {axis: round(float(theta[axis]), 6) for axis in THETA_AXES}
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
```

Требования:
- обязательны все 8 именованных осей; missing axis → `ValidationError`;
- input dict в любом порядке даёт одинаковый hash;
- перестановка значений между двумя именованными осями даёт другой hash;
- изменение каждой отдельной оси даёт другой hash;
- float precision фиксируется ровно в 6 десятичных знаков; политика округления документируется.

### 2.3 Тесты CB-1

Создать `test15_e4_corrective.py`, класс `TestCanonicalThetaHash`:
- reversed dict order → same hash;
- 10 random key permutations → same hash;
- swap values of θ₀ and θ₃ → different hash;
- each axis +0.01 → different hash;
- missing axis → ValidationError с именем оси;
- unsupported key не влияет на hash либо явно rejected: выбрать один контракт и тестировать его; рекомендовано reject.

---

## 3. Блокер CB-2: реальные feature hashes

### 3.1 Контракт fixture

Запрещены строки вида `sha256:placeholder_*` в immutable manifest и provenance v2.

Каждый fixture обязан содержать ровно один из вариантов:

```yaml
# Реальный audio-derived fixture
audio_content_hash: "sha256:<64 hex>
feature_artifact_path: "artifacts/e4/features/jazz_A.json"
feature_hash: "sha256:<64 hex>"

# Синтетический pinned fixture
synthetic_fixture: true
feature_artifact_path: "artifacts/e4/features/jazz_A.json"
feature_hash: "sha256:<64 hex>"
```

`feature_hash` = SHA-256 от canonical JSON feature artifact: UTF-8, `sort_keys=True`, compact separators, все float округляются до 6 знаков до сериализации. Путь входит в provenance, но не в hash.

### 3.2 Feature artifact

Для всех 22 fixtures создать `artifacts/e4/features/<fixture_id>.json`. В нём должны быть именно features, использованные resolver: perceptual axes, `noise_proxy`, 8 θ-осей, profile slug и schema version.

Нельзя восстановить эти features «примерно» из PNG, seed или provenance предыдущей версии. Артефакт является источником истины для rerender.

### 3.3 Тесты CB-2

`TestFeatureProvenance`:
- 22 artifact files существуют;
- каждый feature_hash real SHA-256, не placeholder;
- hash пересчитывается и совпадает с manifest/provenance;
- каждый fixture имеет `audio_content_hash` или `synthetic_fixture: true`;
- изменение feature artifact меняет feature_hash и variation_seed;
- profile slug manifest совпадает с profile slug provenance.

---

## 4. Новый corpus v2

### 4.1 Новый experiment_id

```text
e4_reference_render_audit_v2
```

Нельзя перезаписывать v1 PNG, manifest, JSON или output hashes.

### 4.2 Структура

```text
artifacts/e4/
  fixtures_manifest_v2.yaml
  features/<fixture_id>.json                 # 22 files
  e4_reference_render_audit_v2/
    provenance/<profile>/<fixture_id>.json   # создаётся только harness после PNG
    renders/<profile>/<fixture_id>.png
    contact_sheet.png
    audit_matrix.csv
    technical_report.md
    perceptual_audit.md
```

### 4.3 Harness rules

`e4_render_harness.py` обязан:
1. валидировать manifest, feature artifact, profile, palette и canonical θ-hash до render;
2. рендерить PNG;
3. вычислять output SHA-256;
4. писать provenance JSON атомарно через temp file + rename;
5. писать в provenance: experiment_id, git SHA, renderer SHA, manifest hash, feature hash, audio/synthetic identity, canonical theta hash, variation seed, palette, generator stack, full mapping_trace, output hash;
6. при PNG without JSON восстанавливать provenance только если manifest hash, renderer SHA и feature hash совпадают; иначе завершаться ошибкой без overwrite;
7. не принимать `--rerender` без нового experiment_id или явного `--allow-baseline-replacement` с отказом по умолчанию.

---

## 5. Перцептивный аудит — обязательная часть E4

Технические SHA не заменяют человеческую оценку. Создать `perceptual_audit.md` и заполнить для 22 renders таблицу 0–3:

| Критерий | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Жанровая идентичность | отсутствует | слабые намёки | узнаваема | очевидна |
| θ-реакция | нет | случайна | частична | причинно читается |
| Композиция | развалена | дефекты | устойчива | выразительна |
| Техническая чистота | критический дефект | заметный дефект | приемлемо | чисто |
| Межпрофильная различимость | неотличима | слаба | различима | не спутать |

Условия прохода:
- среднее по каждому критерию среди canonical 21 renders ≥ 2.0;
- ни один render не имеет 0 по композиции или технической чистоте;
- минимум один комментарий на каждый score < 2;
- `default_smoke` оценивается только по технической чистоте и композиции, не входит в жанровое среднее.

---

## 6. План очередности работ

### Commit 1 — CB-1 hash contract

Изменить engine/hash implementation и добавить `test15_e4_corrective.py::TestCanonicalThetaHash`.

**Gate:** все существующие tests + hash tests green. Никаких v2 fixture/PNG до этого commit.

### Commit 2 — CB-2 input provenance

Добавить canonical feature serialization, 22 feature artifacts, `fixtures_manifest_v2.yaml` и tests provenance.

**Gate:** 22 feature hashes real; placeholders = 0; manifest immutable/valid.

### Commit 3 — Run B v2 corpus

Запустить harness. Создать 22 PNG, 22 provenance JSON, contact sheet, technical report.

**Gate:** все output hashes реальны, уникальны; минимум 3 rerender идентичны; v1 не изменён.

### Commit 4 — Human audit

Добавить заполненный `perceptual_audit.md` и `audit_matrix.csv`. Если порог не достигнут — не тюнить молча: создать issue, зафиксировать baseline v2 и открыть отдельный E4-tuning experiment v3.

---

## 7. E5 prerequisites и запреты

E5 разрешён только после закрытия всех CB gates. Тогда создать `test_e5_regression.py`:
- строгий SHA match против v2;
- SSIM ≥ 0.995 только как дополнительный perceptual signal, не замена SHA;
- SSIM сравнивается в фиксированном RGB/sRGB, при одинаковом размере и без alpha ambiguity;
- intentional visual change требует новый experiment_id и re-baseline, v2 архивируется.

Запрещено:
- использовать sorted-value θ hash;
- использовать placeholder feature hash;
- менять seed/feature/профиль после неудачного изображения;
- заменять v1 или v2 baseline вместо создания нового experiment_id;
- объявлять E4 закрытым без human audit.

---

## 8. Definition of Done

- [ ] Canonical named θ-hash реализован и покрыт tests CB-1.
- [ ] 22 feature artifacts существуют, hashes реальны и проверяемы.
- [ ] Manifest v2 и corpus v2 не содержат placeholders.
- [ ] 22 PNG и 22 provenance JSON созданы harness-ом; v1 сохранён.
- [ ] Минимум 3 bit-exact rerender совпали по SHA-256.
- [ ] Human audit completed и проходит пороги.
- [ ] E5 regression gate создан только после завершения всех предыдущих пунктов.
