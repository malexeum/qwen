# ТЗ E2: HarmonyEncoder — θ-артефакт

> **Статус:** Draft v1.0 · 2026-08-10  
> **Контекст:** Этап E2 системы `H → F(H, θ)`. θ — вектор гармонической сигнатуры трека, порождаемый HarmonyEncoder. Используется как часть seed-политики и как независимый управляющий параметр для генераторов.

---

## 1. Зачем это нужно

Текущая seed-политика (`sha256` по `audio_content_hash + canonical_title + ...`) даёт детерминизм, но не смысловую связь между гармоническим содержанием трека и визуальным результатом. Два трека с одинаковым названием, но разной гармоникой дадут похожий visual. Два трека с противоположной гармоникой, но одинаковым `energy` — один и тот же тип картинки.

HarmonyEncoder решает это: он кодирует **гармоническую личность трека** в компактный вектор θ ∈ ℝ^d (d=8), который:

1. Однозначно привязан к аудио-содержанию, а не к метаданным
2. Непрерывен — близкие треки дают близкие θ
3. Детерминирован — тот же трек всегда даёт тот же θ
4. Управляет генераторами напрямую через `harmony_theta` mapping-оси

---

## 2. Место в архитектуре

```
audio file
    │
    ▼
[AudioFeatureExtractor]  →  feature_vector (существует, E1)
    │
    ▼
[HarmonyEncoder]         →  θ ∈ ℝ^8  (E2, этот модуль)
    │              │
    ▼              ▼
 seed_policy   generator mapping
 (часть base)  harmony_theta_0..7
```

Вход HarmonyEncoder — срез `feature_vector`, соответствующий гармоническим осям.  
Выход — вектор θ, сохраняемый как `harmony_theta` в артефакте трека.

---

## 3. Входные оси (источник: feature_schema_v2.yaml)

HarmonyEncoder потребляет следующие оси из `feature_vector`:

| Ось | Описание | Диапазон |
|---|---|---|
| `symmetry_bias` | Доля симметричных интервалов | [0, 1] |
| `tension` | Дисгармоническое напряжение | [0, 1] |
| `harmonic_stability` | Стабильность гармонического центра | [0, 1] |
| `harmonic_change_rate` | Скорость смены гармоний | [0, 1] |
| `texture_complexity` | Полифоническая сложность | [0, 1] |
| `recursion_depth` | Глубина структурной вложенности | [0, 1] |
| `section_complexity` | Контраст между секциями | [0, 1] |
| `noise_level` | Недетерминированность тембра | [0, 1] |

Все 8 осей — уже нормализованы в [0,1] на выходе E1.

---

## 4. Алгоритм кодирования

### 4.1 Базовая версия (v1 — детерминированная, без ML)

θ строится как **нелинейное преобразование** входных осей с перекрёстными взаимодействиями:

```
θ_0 = symmetry_bias * (1 - tension)                       # гармоническая чистота
θ_1 = harmonic_stability * harmonic_change_rate            # динамика vs стабильность
θ_2 = texture_complexity * recursion_depth                 # структурная плотность
θ_3 = tension * (1 - harmonic_stability)                   # неразрешённое напряжение
θ_4 = section_complexity * (1 - noise_level)               # чистый контраст секций
θ_5 = noise_level * texture_complexity                     # тембральный хаос
θ_6 = harmonic_change_rate * section_complexity            # энтропия развития
θ_7 = symmetry_bias * harmonic_stability * (1 - tension)   # "кристалличность" трека
```

Каждый θ_i ∈ [0, 1]. Вектор θ не нормируется дополнительно — интерпретируется поосно.

### 4.2 Расширенная версия (v2 — обучаемая, опционально)

Линейная проекция поверх базового θ с матрицей W (8×8), обученной на парах (θ, visual_quality_score) из бенчмарка. Замораживается после обучения. Активируется флагом `harmony_encoder_version: v2` в `experiment_protocol.yaml`.

> **Архитектурное решение:** начинаем с v1. v2 — опция для E4 (оптимизация по визуальному качеству).

---

## 5. Артефакт: `harmony_theta`

HarmonyEncoder сохраняет результат в структуру трека:

```yaml
harmony_theta:
  version: "1.0"
  algorithm: "crossproduct_v1"
  source_axes:
    - symmetry_bias
    - tension
    - harmonic_stability
    - harmonic_change_rate
    - texture_complexity
    - recursion_depth
    - section_complexity
    - noise_level
  values: [0.412, 0.187, 0.634, 0.091, 0.523, 0.301, 0.448, 0.267]  # пример
  norm: null  # не нормируется поосевой вариант
```

Поле добавляется в `track_artifact.yaml` рядом с `feature_vector`.

---

## 6. Интеграция в seed_policy

В `global_rules.seed_policy.base_components` добавляется:

```yaml
seed_policy:
  base_components:
    - audio_content_hash
    - canonical_title
    - canonical_artist
    - duration_ms
    - style_profile_slug
    - profile_library_version
    - harmony_theta_hash  # NEW: sha256 от rounded(θ, 3)
```

`harmony_theta_hash` = `sha256(json.dumps(θ.round(3).tolist()))` — стабилен при малых изменениях (округление до 3 знаков дробит пространство на ~1000^8 ячеек, чего достаточно).

---

## 7. Интеграция в mapping-оси генераторов

Новые оси `harmony_theta_0` .. `harmony_theta_7` становятся доступны в секции `mapping` любого генератора. Пример использования в профилях (E3 — задача E3, не E2):

```yaml
mapping:
  c_real: harmony_theta_0   # гармоническая чистота управляет формой julia
  c_imag: harmony_theta_3   # напряжение управляет ориентацией
```

Приоритет E2 — **только реализовать оси и артефакт**. Подключение к конкретным профилям — E3.

---

## 8. Реализация: файлы и изменения

### 8.1 Новый файл

```
lib/composition/harmony_encoder.py
```

```python
from dataclasses import dataclass
from typing import List
import hashlib, json
import numpy as np

HARMONY_AXES = [
    "symmetry_bias", "tension", "harmonic_stability",
    "harmonic_change_rate", "texture_complexity",
    "recursion_depth", "section_complexity", "noise_level"
]

@dataclass
class HarmonyTheta:
    version: str
    algorithm: str
    source_axes: List[str]
    values: List[float]

    @property
    def hash(self) -> str:
        rounded = [round(v, 3) for v in self.values]
        return hashlib.sha256(json.dumps(rounded).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "source_axes": self.source_axes,
            "values": self.values,
            "hash": self.hash,
        }


class HarmonyEncoder:
    VERSION = "1.0"
    ALGORITHM = "crossproduct_v1"

    def encode(self, features: dict) -> HarmonyTheta:
        f = features
        theta = [
            f["symmetry_bias"] * (1 - f["tension"]),
            f["harmonic_stability"] * f["harmonic_change_rate"],
            f["texture_complexity"] * f["recursion_depth"],
            f["tension"] * (1 - f["harmonic_stability"]),
            f["section_complexity"] * (1 - f["noise_level"]),
            f["noise_level"] * f["texture_complexity"],
            f["harmonic_change_rate"] * f["section_complexity"],
            f["symmetry_bias"] * f["harmonic_stability"] * (1 - f["tension"]),
        ]
        return HarmonyTheta(
            version=self.VERSION,
            algorithm=self.ALGORITHM,
            source_axes=HARMONY_AXES,
            values=[float(np.clip(v, 0.0, 1.0)) for v in theta],
        )
```

### 8.2 Изменения в существующих файлах

| Файл | Изменение |
|---|---|
| `lib/composition/schema.py` | Добавить `HarmonyTheta` в схему артефакта |
| `lib/composition/seed_policy.py` | Добавить `harmony_theta_hash` в `base_components` |
| `lib/composition/config_loader.py` | Регистрировать `harmony_theta_0..7` как валидные mapping-оси |
| `lib/composition/__init__.py` | Экспортировать `HarmonyEncoder`, `HarmonyTheta` |
| `configs/feature_schema_v2.yaml` | Добавить секцию `harmony_encoder_output` с описанием θ-осей |

### 8.3 Тест

```
lib/composition/test_harmony_encoder.py
```

Проверяет:
- детерминизм: `encode(f) == encode(f)` на тех же данных
- диапазон: все θ_i ∈ [0, 1]
- хэш: `hash` меняется при изменении любой входной оси
- интеграцию с seed: `harmony_theta_hash` влияет на итоговый seed трека

---

## 9. Критерии завершённости E2

- [ ] `harmony_encoder.py` реализован и проходит все тесты
- [ ] `HarmonyTheta` сохраняется в артефакт трека
- [ ] `harmony_theta_hash` включён в seed-политику
- [ ] `harmony_theta_0..7` зарегистрированы как валидные mapping-оси (без ошибки `unsupported_source_axis`)
- [ ] `test_harmony_encoder.py` проходит без ошибок
- [ ] `profile_library_version` не меняется — E2 не трогает профили

---

## 10. Что НЕ входит в E2

- Подключение θ к конкретным генераторам в профилях → **E3**
- Обучение матрицы W (v2 encoder) → **E4**
- Визуализация θ-пространства для разных жанров → **E5 (аналитика)**
- Изменение `feature_schema_v2.yaml` в части источников → **не нужно**

---

## 11. Связанные файлы

- [`configs/visual_composition_profiles.yaml`](../../configs/visual_composition_profiles.yaml) — профили v0.3.4
- [`lib/composition/seed_policy.py`](../../lib/composition/seed_policy.py) — текущая seed-политика
- [`lib/composition/config_loader.py`](../../lib/composition/config_loader.py) — регистрация осей
- [`configs/feature_schema_v2.yaml`](../../configs/feature_schema_v2.yaml) — схема фич
- [ТЗ в корне doc (исходник)](../e2_harmony_encoder_tz.md)
