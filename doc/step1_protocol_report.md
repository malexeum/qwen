# Шаг 1. Протокол воспроизводимого benchmark-эксперимента для фрактального движка

## Краткое резюме

На первом шаге сформирован не новый генератор, а **исследовательский каркас**, который фиксирует, как именно запускать эксперименты, чтобы результаты можно было повторить, сравнить и включить в отчёт или статью без ручной магии. Для нелинейных систем это критично, потому что бифуркации, basin-структуры и хаотическое рассеяние чувствительны к начальному состоянию, шуму и численной схеме, а basin entropy как раз применяется для количественной оценки непредсказуемости и анализа бифуркаций.[cite:39][cite:40]

В результате подготовлены три режима вычислений — `research-fast`, `research-final`, `publication` — а также единый конфиг протокола, механизм заморозки параметров запуска и шаблон метрик для дальнейших серийных прогонов. Такой подход соответствует хорошей практике исследований нелинейной динамики, где сравниваются не отдельные картинки, а статистически устойчивые семейства результатов при фиксированном протоколе.[cite:35][cite:36]

## Что именно сделано

Подготовлен YAML-конфиг `experiment_protocol.yaml`, где зафиксированы режимы расчёта, seeds, уровни стохастики, перечень генераторов, набор экспериментов и список итоговых метрик. Отдельно реализован Python-раннер `run_protocol.py`, который читает протокол, выбирает режим, формирует **frozen configuration** и сохраняет его вместе с шаблоном CSV-таблицы метрик.

Смысл этого шага в том, что каждый будущий запуск получает собственную замороженную спецификацию, то есть исследование можно воспроизвести даже спустя время. В нелинейных осцилляторных системах, включая Duffing-подобные режимы, контроль параметров, начальных условий и режимов возмущения напрямую влияет на наблюдаемую степень хаотизации и управляемости динамики.[cite:35][cite:41]

## Логика протокола

Протокол разделён на три уровня вычислительной плотности:

| Режим | Назначение | Типичная роль |
|---|---|---|
| `research-fast` | Быстрая отладка гипотез и кода | Проверка пайплайна, smoke-test |
| `research-final` | Основной исследовательский режим | Сравнение методов и прогон таблиц |
| `publication` | Плотный финальный режим | Экспорт иллюстраций и финальных метрик |

Такое разделение нужно, чтобы не смешивать инженерную отладку и финальные выводы. Для basin- и bifurcation-анализов слишком грубая сетка может скрывать тонкую структуру, а слишком дорогой режим на раннем этапе только съедает время и мешает нормальной итерации.[cite:36][cite:40]

## Формализация задачи

Пусть входная гармоническая конфигурация задаётся вектором признаков

\[
H = (h_1, h_2, \dots, h_m),
\]

где компоненты могут включать спектральный профиль, частотные отношения, ритмическую периодичность, меру напряжения, симметрию и плотность структуры. Обучаемый энкодер переводит этот вектор в управляющее пространство нелинейной системы:

\[
\theta = E_\phi(H),
\]

где \(E_\phi\) — параметризованный оператор кодирования с параметрами \(\phi\).

Далее генератор реализует нелинейное отображение

\[
X_{t+1} = G(X_t, \theta, \xi_t),
\]

где \(X_t\) — состояние динамической системы, а \(\xi_t\) — контролируемый стохастический член. Наличие такого члена важно, потому что в ряде экспериментов требуется не абсолютная детерминированность, а измеряемая устойчивость класса образов к малому шуму.[cite:35][cite:39]

Наблюдаемое визуальное состояние получается уже на уровне оператора наблюдения:

\[
Y = \mathcal{O}(X_{0:T}),
\]

а затем из него извлекается вектор морфологических и статистических признаков

\[
z = \Psi(Y).
\]

Именно в пространстве \(z\) сравниваются классы входов, потому что basin entropy, separability и близкие меры описывают не исходный сигнал, а структуру выходной динамической картины.[cite:39][cite:40]

## Ключевые метрики

В протоколе зафиксированы как минимум следующие величины:

- Воспроизводимость через `mean_cv` и `max_cv` по ансамблю повторов.
- Межклассовая и внутриклассовая дистанции через `between_mean` и `within_mean`.
- Разделимость классов через

\[
S = \frac{d_{between}}{d_{within} + \varepsilon},
\]

где \(\varepsilon\) — малый регуляризатор для предотвращения деления на ноль.
- Связность семейства деформаций через `cohesion_ratio`.
- Структурные признаки изображения: `basin_entropy`, `symmetry_score`, `fractal_dim_proxy`.
- Количество обнаруженных бифуркационных точек `n_bifurcations`.

Такая комбинация метрик согласуется с практикой анализа basin-структур и бифуркаций, где важно различать локальную устойчивость, глобальную непредсказуемость и изменение морфологии фазового пространства при вариации параметров.[cite:39][cite:40]

## Правило обнаружения бифуркаций

Для серии параметрических прогонов по параметру \(p\) формируется последовательность векторов признаков \(z_i\). Далее вычисляется дискретный градиент:

\[
g_i = \frac{\lVert z_{i+1} - z_i \rVert_2}{|p_{i+1} - p_i| + \varepsilon}.
\]

После этого используется z-score тест:

\[
\zeta_i = \frac{g_i - \mu_g}{\sigma_g + \varepsilon}.
\]

Точки, где \(\zeta_i\) превышает выбранный порог, маркируются как кандидаты на бифуркационный переход. Это инженерно удобный критерий: он не заменяет строгую теорию бифуркаций, но хорошо работает как автоматический детектор резкой смены режима в параметрических картах.[cite:36][cite:40]

## Структура каталогов

Рекомендуемая структура шага 1:

```text
fractal_engine_v3/
├── configs/
│   └── experiment_protocol.yaml
├── output/
│   ├── frozen_run_config.json
│   ├── experiment_protocol_copy.yaml
│   ├── metrics_template.csv
│   └── manifest.json
├── docs/
│   └── step1_protocol_report.md
└── run_protocol.py
```

Это позволяет отделить спецификацию эксперимента, выходные артефакты и документацию. Для модульной научной разработки такой подход особенно удобен, потому что конфиг, код и отчёт не смешиваются в одном файле и могут версионироваться независимо.[cite:27]

## Конфиг протокола

Ниже приведён рабочий конфиг первого шага.

```yaml
protocol_version: 1.0
project: fractal_harmony_engine
objective: reproducible_benchmark_protocol
modes:
  research-fast:
    resolution_default: [96, 96]
    resolution_duffing: [96, 96]
    resolution_scattering: [96, 96]
    repeats_per_class: 3
    sensitivity_steps: 15
    deformation_steps: 6
    duffing_steps: 220
    ifs_points: 20000
  research-final:
    resolution_default: [128, 128]
    resolution_duffing: [128, 128]
    resolution_scattering: [128, 128]
    repeats_per_class: 7
    sensitivity_steps: 31
    deformation_steps: 12
    duffing_steps: 400
    ifs_points: 40000
  publication:
    resolution_default: [192, 192]
    resolution_duffing: [192, 192]
    resolution_scattering: [192, 192]
    repeats_per_class: 11
    sensitivity_steps: 41
    deformation_steps: 16
    duffing_steps: 700
    ifs_points: 80000
randomness:
  encoder_seed: 12345
  seeds: [0,1,2,3,4,5,6,7,8,9,10]
  numpy_rng: PCG64
stochastic_scale:
  julia_orbit_trap: 0.01
  orbit_ifs_multi_trap: 0.0
  duffing_lyapunov: 0.002
  chaotic_scattering: 0.0005
generators:
  - julia_orbit_trap
  - orbit_ifs_multi_trap
  - duffing_lyapunov
  - chaotic_scattering
experiments:
  - stability
  - sensitivity
  - bifurcation_detection
  - separability
  - family_deformation
outputs:
  images: true
  json_report: true
  csv_metrics: true
  save_config_copy: true
metrics:
  - mean_cv
  - max_cv
  - within_mean
  - between_mean
  - separability
  - cohesion_ratio
  - basin_entropy
  - symmetry_score
  - fractal_dim_proxy
  - n_bifurcations
```

## Python-код протокольного раннера

Ниже приведён базовый код, который не выполняет все тяжёлые эксперименты, а именно **готовит воспроизводимый запуск**: читает протокол, выбирает режим, формирует frozen config и создаёт шаблоны артефактов.

```python
from __future__ import annotations
import os, json, csv, shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any
import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
CONFIG = ROOT / 'configs' / 'experiment_protocol.yaml'

@dataclass
class RunMode:
    resolution_default: tuple
    resolution_duffing: tuple
    resolution_scattering: tuple
    repeats_per_class: int
    sensitivity_steps: int
    deformation_steps: int
    duffing_steps: int
    ifs_points: int


def load_protocol(path: Path = CONFIG) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_mode(protocol: Dict[str, Any], mode_name: str) -> RunMode:
    m = protocol['modes'][mode_name]
    return RunMode(
        resolution_default=tuple(m['resolution_default']),
        resolution_duffing=tuple(m['resolution_duffing']),
        resolution_scattering=tuple(m['resolution_scattering']),
        repeats_per_class=int(m['repeats_per_class']),
        sensitivity_steps=int(m['sensitivity_steps']),
        deformation_steps=int(m['deformation_steps']),
        duffing_steps=int(m['duffing_steps']),
        ifs_points=int(m['ifs_points']),
    )


def freeze_run_config(protocol: Dict[str, Any], mode_name: str) -> Dict[str, Any]:
    mode = get_mode(protocol, mode_name)
    frozen = {
        'protocol_version': protocol['protocol_version'],
        'project': protocol['project'],
        'objective': protocol['objective'],
        'mode_name': mode_name,
        'mode': asdict(mode),
        'randomness': protocol['randomness'],
        'stochastic_scale': protocol['stochastic_scale'],
        'generators': protocol['generators'],
        'experiments': protocol['experiments'],
        'outputs': protocol['outputs'],
        'metrics': protocol['metrics'],
    }
    return frozen


def write_frozen_config(frozen: Dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / 'frozen_run_config.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(frozen, f, ensure_ascii=False, indent=2)
    return path


def write_metrics_template(protocol: Dict[str, Any], out_dir: Path) -> Path:
    path = out_dir / 'metrics_template.csv'
    header = [
        'generator', 'experiment', 'class_name', 'seed',
        'mean_cv', 'max_cv', 'within_mean', 'between_mean', 'separability',
        'cohesion_ratio', 'basin_entropy', 'symmetry_score', 'fractal_dim_proxy', 'n_bifurcations'
    ]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
    return path


def prepare_run(mode_name: str = 'research-final') -> Dict[str, str]:
    protocol = load_protocol()
    frozen = freeze_run_config(protocol, mode_name)
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = write_frozen_config(frozen, OUT)
    metrics = write_metrics_template(protocol, OUT)
    shutil.copy2(CONFIG, OUT / 'experiment_protocol_copy.yaml')
    manifest = {
        'config_json': str(cfg),
        'config_yaml_copy': str(OUT / 'experiment_protocol_copy.yaml'),
        'metrics_template_csv': str(metrics),
    }
    with open(OUT / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


if __name__ == '__main__':
    manifest = prepare_run('research-final')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
```

## Как запускать

Минимальный сценарий запуска выглядит так:

```bash
cd fractal_engine_v3
python3 run_protocol.py
```

После выполнения будут созданы три ключевых файла:

- `frozen_run_config.json` — точная зафиксированная спецификация запуска.
- `experiment_protocol_copy.yaml` — копия исходного протокола на момент расчёта.
- `metrics_template.csv` — шаблон для накопления всех будущих численных результатов.

Эти артефакты нужны для того, чтобы следующий шаг — полноценный benchmark-runner — не принимал решения “на лету”, а опирался на уже замороженный протокол. Для воспроизводимых серий по нелинейной динамике это ровно тот слой инженерной дисциплины, который потом спасает от головной боли в статье и при повторении экспериментов через месяцы.[cite:35][cite:39]

## Что получится на следующем шаге

После протокольного шага можно безопасно переходить к полному benchmark-runner. Его задача — уже не генерировать конфиг, а читать `frozen_run_config.json`, прогонять все генераторы по фиксированным seed и классам входов, собирать CSV/JSON, строить таблицы по `within-class` и `between-class` дистанциям, а затем формировать финальный markdown-отчёт по режиму `research-final` или `publication`.

На практике это означает переход от “подготовки лаборатории” к настоящей серийной науке: ансамбли прогонов, доверительные интервалы, benchmark-таблицы и готовый материал для short paper или технического отчёта. Тут уже начинается нормальная взрослая нелинейная кухня, без шаманства и с минимальным количеством сюрпризов от хаоса — насколько хаос вообще готов сотрудничать.[cite:36][cite:39]
