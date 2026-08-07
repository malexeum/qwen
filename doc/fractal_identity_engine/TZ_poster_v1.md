TZ_poster_engine_v0.1 — визуальный движок поверх Fractal Harmony core
0. Контекст и цель
У нас уже есть:

math core:

Harmony, HarmonyEncoder,

SimState, RunResult,

генераторы (julia_orbit_trap, orbit_ifs_multi_trap, duffing_lyapunov_map, …).
core.py
+1

benchmark/identity слой:

feature_schema_v2.yaml, identity_schema_v2.yaml, output_taxonomy.yaml.
feature_schema_v2.yaml
+2

Сейчас core отдаёт осмысленные orbit_map/visit_density, но:

визуальный слой минимальный → картинки простые (почти «сырые» карты);
generators.py
+1

генерация медленная, потому что нет разделения на preview/final режимы.
experiment_protocol.yaml
+1

Цель этого ТЗ — описать визуальный движок (poster_engine), который:

Поверх существующего core строит визуальный DSL и Renderer.

Делит ответственность между:

выбором генератора и его параметров,

построением композиции/слоёв,

форматом/масштабом вывода.

Готовит почву для будущего Java‑рендера (на клиенте) и возможного GPU‑core.

1. Архитектурное разделение слоёв
Нужно реализовать новый пакет poster_engine (Python), который живёт поверх core.py/generators.py и не ломает их.
core.py
+1

1.1. Слои и ответственность
Fractal core (уже есть):

Модули: core.py, generators.py, observe.py, metrics.py.
observe.py
+3

Контракт:

вход: SimState (generator_name, theta, resolution, domain, max_iter, escape_radius, stochastic_scale, extra);
core.py

выход: RunResult(orbit_map: np.ndarray, visit_density: np.ndarray, aux: dict).
generators.py
+1

Здесь не добавляем цвет, палитры и т.п.

Poster Engine (новый пакет):

Модули:

adapter.py — RenderParams → SimState.

visual_dsl.py — декларативное описание слоёв и цветовых схем.

renderer.py — Python reference renderer (использует RunResult + DSL и вернёт финальный постер).

Цель: собрать из core‑результатов визуально богатые постеры и подготовить контракт для Java‑рендера.

2. Интерфейсы и сигнатуры
2.1. RenderParams (внешний контракт)
Предполагаем, что RenderParams уже определён StyleEngine, минимум содержит:
poster_styles.yaml

python

@dataclass
class RenderParams:
    style_profile_slug: str              # стиль / класс (harmonicsymmetric, tensecluster, ...)
    interpretation_profile_slug: str     # режим интерпретации
    symmetry_bias: float                 # -1..1
    density_level: float                 # 0..1
    noise_level: float                   # 0..1
    recursion_depth: float               # 0..1 (нормированная глубина)
    motion_intensity: float              # 0..1
    texture_complexity: float            # 0..1
    layout_macro_shape: str              # "centered", "diagonal", "ring", ...
    palette_id: str                      # ссылка на палитру из poster_styles.yaml
    visual_style_slug: str               # "bw", "duotone", "grainy", ...
    variation_seed: int                  # детерминизм
Задача программиста — не менять RenderParams, а использовать их.

2.2. poster_engine.adapter
Задача: реализация маппинга RenderParams → SimState (для выбранного генератора).
generators.py
+1

2.2.1. Выбор генератора
Сигнатура:

python

def select_generator(render_params: RenderParams) -> str:
    """
    Выбирает generator_name по стилю/классу и RenderParams.
    Примеры имен: "julia_orbit_trap", "orbit_ifs_multi_trap", "duffing_lyapunov_map".
    """
Минимальные правила (можно захардкодить):

style_profile_slug или класс трека (из input_registry) → базовый выбор:

гармоничные/симметричные → julia_orbit_trap или single_parameter_map_baseline.
input_registry.yaml
+1

tense/cluster → duffing_lyapunov_map.
experiment_protocol.yaml
+1

dense/irregular → orbit_ifs_multi_trap.

При необходимости: fallback на baselines (smooth_geometric_baseline, random_baseline), когда появятся.

2.2.2. Построение SimState
Сигнатура:

python

from fractal_core import SimState  # core.py

def make_sim_state(render_params: RenderParams,
                   generator_name: str,
                   mode: str = "preview") -> SimState:
    """
    Создает SimState для выбранного генератора с учетом RenderParams и режима render (preview/final).
    """
Требования:

seed = variation_seed из RenderParams.

resolution:

если mode == "preview" → низкая (напр. 128×128 или использование research-fast preset).
experiment_protocol.yaml

если mode == "final" → выше (например, 384×384, синхронно с validation-hires preset).
experiment_protocol.yaml

domain:

базовые значения: (-2, 2, -2, 2) (как сейчас).
core.py

можно модифицировать по layout_macro_shape (например, для «zoom‑in» уменьшать диапазон).

max_iter, extra["n_points"], extra["n_steps"]:

завязать на recursion_depth и texture_complexity;

использовать значения из experiment_protocol.yaml как референс (duffingsteps, ifspoints).
experiment_protocol.yaml

stochastic_scale:

stochastic_scale = noise_level * s_max (например, s_max = 0.02).

Отдельные helper’ы:

python

def make_sim_state_for_julia(render_params: RenderParams, mode: str) -> SimState: ...
def make_sim_state_for_ifs(render_params: RenderParams, mode: str) -> SimState: ...
def make_sim_state_for_duffing(render_params: RenderParams, mode: str) -> SimState: ...
Внутри них — использование cheat sheet для theta (мы уже набросали смысл th[0]..th[4] для каждого генератора).
generators.py

3. visual_dsl — визуальный DSL и слои
Задача: описать, какие слои рендерить из RunResult и как красить.

3.1. Интерфейс PosterSpec
Предлагаемый dataclass:

python

@dataclass
class LayerSpec:
    source: str           # "orbit_map" или "visit_density"
    normalize: str        # "linear", "log", "gamma"
    weight: float         # вклад слоя
    blend_mode: str       # "add", "max", "screen", ...

@dataclass
class ColorSpec:
    palette_id: str       # из poster_styles.yaml
    visual_style_slug: str  # "bw", "duotone", "grainy", ...

@dataclass
class PosterSpec:
    layers: list[LayerSpec]
    color: ColorSpec
3.2. Генерация PosterSpec из RenderParams
Сигнатура:

python

def make_poster_spec(render_params: RenderParams) -> PosterSpec:
    """
    На основе RenderParams и poster_styles.yaml создает PosterSpec:
    - какие слои брать (orbit/visit),
    - как их нормализовать,
    - какую палитру и визуальный стиль применить.
    """
Примеры правил:

Для simple/ambient стилей:

основной слой — orbit_map (smooth), логарифмическая нормализация.

палитра — мягкие градиенты, visual_style_slug = "bw" или "soft_duotone".
poster_styles.yaml

Для tense/electronic:

комбинировать orbit_map + visit_density (с разными weight).

использовать high‑contrast палитры, visual_style_slug = "grainy".
input_registry.yaml
+1

4. renderer.py — reference PosterRenderer
Задача: реализовать серверный рендерер, который соединяет всё:

4.1. Основная функция
python

from fractal_core import generators  # генераторные функции
from .adapter import select_generator, make_sim_state
from .visual_dsl import make_poster_spec

def render_poster(render_params: RenderParams,
                  mode: str = "preview") -> dict:
    """
    Главная точка входа для server-side рендера постера (reference).
    Возвращает:
    - image: np.ndarray (H, W, 3) в sRGB (0..255)
    - metadata: dict (generator_name, sim_state, poster_spec, ...)
    """
Пайплайн внутри:

generator_name = select_generator(render_params).

state = make_sim_state(render_params, generator_name, mode=mode).

Вызов core:

run_fn = getattr(generators, generator_name)

result: RunResult = run_fn(state).
generators.py

spec = make_poster_spec(render_params).

image = apply_poster_spec(result, spec) — см. ниже.

Вернуть:

{"image": image, "metadata": {...}}.

4.2. Функция apply_poster_spec
python

def apply_poster_spec(result: RunResult, spec: PosterSpec) -> np.ndarray:
    """
    Применяет PosterSpec к RunResult, возвращает RGB-изображение.
    """
Шаги:

Собрать scalar base:

Для каждого LayerSpec:

взять result.orbit_map или result.visit_density.
core.py
+1

нормализовать по normalize:

linear → min-max,

log → log1p/логарифмическая шкала,

gamma → gamma-correction.

взвесить weight, накопить в единую scalar map.

Применить палитру:

По spec.color.palette_id найти палитру в poster_styles.yaml.
poster_styles.yaml

По visual_style_slug определить:

BW / duotone / цветной градиент;

добавлять ли grain/noise (можно позже).
poster_styles.yaml

Вернуть np.ndarray(H, W, 3) в sRGB 0..255.

5. Производительность: режимы preview/final
Чтобы картинки стали «быстрыми» в UI, а «богатыми» в финале, в make_sim_state нужно:

поддерживать как минимум два режима:

mode="preview":

resolution низкая (напр. 128×128).

max_iter/n_points/n_steps уменьшены (использовать research-fast presets из experiment_protocol.yaml).
experiment_protocol.yaml

mode="final":

resolution выше (например, 384×384).

n_steps/ifspoints из режима publication или validation-hires.
experiment_protocol.yaml

Эти режимы должны быть конфигурируемы, но не мешать benchmark-протоколу (benchmark остаётся под контролем experiment_protocol.yaml).
experiment_protocol.yaml

6. Definition of Done
poster_engine v0.1 считается реализованным, когда:

Есть модуль poster_engine.adapter с функциями:

select_generator(RenderParams) -> str,

make_sim_state(RenderParams, generator_name, mode) -> SimState,

и (опционально) per-generator helper’ы.
core.py
+1

Есть модуль poster_engine.visual_dsl:

PosterSpec, LayerSpec, ColorSpec,

make_poster_spec(RenderParams) -> PosterSpec.
poster_styles.yaml

Есть модуль poster_engine.renderer:

render_poster(RenderParams, mode="preview") -> dict,

apply_poster_spec(RunResult, PosterSpec) -> np.ndarray.
observe.py
+1

При тестовом прогоне:

Для нескольких разных RenderParams (разные стили/классы):

появляются визуально отличающиеся постеры;

время preview‑рендера заметно меньше final (за счёт resolution/steps).
generators.py
+1

Весь math core (core.py, generators.py, observe.py, metrics.py) не изменён по интерфейсу, и benchmark‑pipeline остаётся рабочим.