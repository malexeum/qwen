# Sanity-check v3 и калибровка generator-specific thresholds

## Краткое резюме

Подготовлен отдельный скрипт `sanity_check_v3`, который калибрует пороги отдельно для `julia_orbit_trap`, `orbit_ifs_multi_trap` и `duffing_lyapunov` на одном фиксированном input class `harmonic_symmetric`. Логика v3 уходит от глобальных порогов и сохраняет калиброванные профили в `threshold_profiles.yaml`, а также формирует `manifest` и `summary` для воспроизводимого ручного контроля.

## Что реализовано

### Режим запуска

Скрипт работает как отдельный компактный режим:

```json
{
  "mode": "sanity_check_v3"
}
```

Выходные артефакты изолированы в папке:

- `sanity_check_v3_outputs/`
- `sanity_check_v3_outputs/images/`
- `sanity_check_v3_outputs/sanity_check_manifest.csv`
- `sanity_check_v3_outputs/sanity_check_summary.json`
- `sanity_check_v3_outputs/threshold_profiles.yaml`

### Generator-specific windows

Используются разные окна шагов деформации для разных семейств, чтобы не сравнивать хрупкие и устойчивые динамики по одной линейке:

| Generator | Steps |
|---|---|
| `julia_orbit_trap` | 1, 3, 5, 7, 9 |
| `orbit_ifs_multi_trap` | 1, 5, 9, 12, 16, 20 |
| `duffing_lyapunov` | 1, 5, 9, 12, 15 |

### Амплитуды деформации

Внутри скрипта введены generator-specific amplitudes:

| Generator | Amplitude |
|---|---|
| `julia_orbit_trap` | 0.12 |
| `orbit_ifs_multi_trap` | 0.25 |
| `duffing_lyapunov` | 0.80 |

Это сделано потому, что визуальные и численные наблюдения показали принципиально разную чувствительность семейств: Julia быстро ломается, IFS долго сохраняет форму, Duffing требует более широкого окна для выхода к бифуркации.

## Методика калибровки

### Raw score

Для каждого запуска вычисляется относительный морфологический сдвиг относительно базового состояния того же генератора и seed:

\[
S_{raw} = \frac{\operatorname{mean}(|V_0 - V_k|)}{\operatorname{mean}(|V_0|) + \varepsilon}
\]

где:
- \(V_0\) — карта visit density на baseline-шаге;
- \(V_k\) — карта visit density на шаге деформации \(k\);
- \(\varepsilon\) — малый стабилизирующий член.

### Normalized score

После калибровки по каждому генератору строится собственная шкала:

\[
S_{norm} = \frac{S_{raw}}{\text{score\_scale(generator)}}
\]

Это позволяет сравнивать runs внутри одного семейства без ложного выравнивания между семействами.

### Калибровка порогов

Для каждого генератора автоматически оцениваются:

- `preserved_threshold`
- `transformed_threshold`
- `weakly_transformed_threshold`
- `broken_threshold`
- `score_scale`

Логика калибровки опирается на контрольные шаги и ожидаемые зоны поведения. Например, для `duffing_lyapunov` шаги 5 и 9 рассматриваются как мягкая трансформация, а шаги 12 и 15 — как граница бифуркационного слома.

## Логика классификации

Классификация выполняется правилом:

```text
label = classify(score, generator_profile)
```

Порядок приоритета реализован в соответствии с ТЗ:

1. `broken-like`
2. `emergent-like`
3. `weakly-transformed`
4. `transformed-like`
5. `preserved`
6. `baseline`

Практически правило работает через generator-specific thresholds. Если `score` превышает `broken_threshold`, кадр получает `broken-like`; если он находится между `weakly_transformed_threshold` и `broken_threshold`, присваивается `weakly-transformed`, и так далее.

## Структура manifest

`sanity_check_manifest.csv` содержит минимум следующие поля:

- `run_id`
- `generator`
- `input_class`
- `seed`
- `deformation_step`
- `raw_score`
- `normalized_score`
- `preview_label`
- `status`
- `threshold_profile_version`
- `observer_version`
- `feature_schema_version`
- `output_file`
- `identity_confidence`

Это даёт возможность не только глазами смотреть PNG, но и сразу видеть численную причину assigned label.

## Структура summary

`sanity_check_summary.json` хранит:

- число запусков;
- список генераторов;
- карту шагов;
- распределение labels;
- калиброванные threshold profiles;
- заметки по поведению генераторов;
- список mismatch cases, где численный label расходится с ожидаемой визуальной зоной.

Именно этот блок нужен для последующей интеграции с identity layer и benchmark v4.

## Код

### Основные параметры и generator-specific profiles

```python
CONFIG = {
    'mode': 'sanity_check_v3',
    'input_class': 'harmonic_symmetric',
    'seeds': [42, 101, 999],
    'steps_map': {
        'julia_orbit_trap': [1, 3, 5, 7, 9],
        'orbit_ifs_multi_trap': [1, 5, 9, 12, 16, 20],
        'duffing_lyapunov': [1, 5, 9, 12, 15],
    },
    'amplitude_map': {
        'julia_orbit_trap': 0.12,
        'orbit_ifs_multi_trap': 0.25,
        'duffing_lyapunov': 0.80,
    },
}
```

### Морфологический score

```python
def compute_raw_score(base_result, current_result) -> float:
    a = np.asarray(base_result.visit_density, dtype=float)
    b = np.asarray(current_result.visit_density, dtype=float)
    diff = np.abs(a - b).mean()
    base_mean = np.mean(np.abs(a)) + 1e-8
    return float(diff / base_mean)
```

### Generator-specific classification

```python
def classify(score: float, generator_profile: Dict[str, Any], step: int):
    if step == 1:
        return 'baseline', 1.0
    p = generator_profile['preserved_threshold']
    t = generator_profile['transformed_threshold']
    w = generator_profile['weakly_transformed_threshold']
    b = generator_profile['broken_threshold']
    scale = max(generator_profile.get('score_scale', 1.0), 1e-8)
    emergent_threshold = max(b * 1.35, b + 0.15 * scale)
    if score >= emergent_threshold:
        return 'emergent-like', 1.0
    if score >= b:
        return 'broken-like', 1.0
    if score >= w:
        return 'weakly-transformed', 1.0
    if score >= t:
        return 'transformed-like', 1.0
    return 'preserved', 1.0
```

## Интерпретация по генераторам

### Julia

Для `julia_orbit_trap` ожидается очень короткое окно полезной трансформации и ранний уход в `broken-like`. Поэтому амплитуда снижена, а шаги подобраны плотнее. Цель — не перепутать хрупкую, но осмысленную усложнённую фазу с немедленным разрушением.

### Orbit IFS

Для `orbit_ifs_multi_trap` основной интерес — найти, где заканчивается зона долгого сохранения формы и начинается реальный breakdown. В большинстве случаев этот генератор будет долго жить в `transformed-like` или `weakly-transformed`, а `broken-like` должен либо запаздывать, либо не появляться в заданном окне вовсе.

### Duffing

Для `duffing_lyapunov` критично поймать переход в хаос. Поэтому amplitude повышена, а окно расширено до 15. Если калибровка проходит успешно, то между шагами 9 и 12 должна появляться устойчивая граница между `transformed-like` и `broken-like`.

## Как запускать

```bash
python visual_sanity_v3.py
```

Если файл лежит в `output/`, запускать его лучше либо оттуда, либо перенести в корень проекта рядом с `core.py`/`generators.py` или папками `rdcoder`, `lib`.

## Что делать дальше

1. Прогнать `sanity_check_v3` и посмотреть `threshold_profiles.yaml`.
2. Проверить `mismatch_cases` в `sanity_check_summary.json`.
3. Если mismatch для Julia остаётся большим, ещё уменьшить `amplitude_map['julia_orbit_trap']`.
4. Подключить сохранённые threshold profiles в identity layer большого benchmark-runner.
5. После этого запускать финальный benchmark v4 уже не с глобальными, а с generator-specific thresholds.

## Практический итог

v3 превращает sanity-check из просто набора PNG в компактную лабораторию калибровки. Это уже не “посмотреть картинки”, а способ измерить, где у каждого генератора начинается осмысленная трансформация, где идёт мягкая деградация, а где реально происходит структурный слом.
