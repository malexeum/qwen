TZ_generator_cheatsheet_v1.md
Cheat sheet по генераторам и связи с RenderParams

0. Общая шапка: SimState как контейнер
Все генераторы используют общий контейнер:

python

@dataclass
class SimState:
    generator_name: str
    theta: np.ndarray
    resolution: Tuple[int, int] = (400, 400)
    domain: Tuple[float, float, float, float] = (-2.0, 2.0, -2.0, 2.0)
    max_iter: int = 200
    escape_radius: float = 4.0
    trap_kind: str = "point"
    seed: int = 0
    stochastic_scale: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)
Идея: RenderParams не лезут внутрь генератора, они заполняют SimState:

generator_name ← выбор генератора (rule-based по стилю/классу).
experiment_protocol.yaml
+1

theta ← компактный вектор параметров генератора (главный канал).
generators.py

resolution, domain, max_iter, escape_radius, extra ← контролируются RenderParams (или режимом render: macro/meso/final).

stochastic_scale ← связывается с noise_level / motion_intensity.

Во всех cheat sheet ниже подразумевается:

RenderParams содержит хотя бы:

symmetry_bias

density_level

noise_level

recursion_depth

motion_intensity

texture_complexity

layout_macro_shape

variation_seed

visual_style_slug
(точные имена можно подстроить к твоему StyleEngine, главное — семантика).

1. julia_orbit_trap
1.1. Как генератор устроен в коде
Сигнатура: julia_orbit_trap(state: SimState) -> RunResult.
generators.py

Главные шаги:

theta используется так:

python

th = state.theta
c = complex(th * 1.2, th[1] * 1.2)
p = 2.0 + (th[2] + 1) * 1.0          # степень порядка ~2–3
trap_r = 0.05 + 0.25 * (th[3] + 1)/2 # радиус ловушки ~0.05–0.3
trap_c = complex(th[4] * 0.5, th * 0.5) if len(th) > 5 else 0j
generators.py

Сетка: resolution, domain задают XY-плоскость.

Итерации: цикл for n in range(state.max_iter), внутри:

радиальная степенная карта с параметром p,

добавление c,

опциональный шум (stochastic_scale),

orbit trap по расстоянию до trap_c с экспоненциальным весом.
generators.py

Escape: по state.escape_radius.

Морфология: классическая Джулия с orbit trap-декорациями — богатые линии, сильная чувствительность к c, p, трап-радиусу и позиции.

1.2. Theta и RenderParams
Предлагаемый mapping:

Элемент	Описание в генераторе	RenderParams-ось
th[0], th[1]	комплексный параметр c	symmetry_bias, layout_macro_shape
th[2]	степень p (плотность/извилистость)	texture_complexity
th[3]	радиус ловушки trap_r	density_level
th[4], th[5]	центр ловушки trap_c	layout_macro_shape, symmetry_bias
Осмысленная схема:

symmetry_bias:

при высоком симметрийном bias → выбирать th[0], th[1] так, чтобы c ближе к оси или симметричным точкам (например, зеркально по real/imag).

при низком/отрицательном → смещать c в “кривые” зоны, ломая зеркальность.

texture_complexity:

низкая → th[2] ближе к -1 → p ≈ 2.0 (простые структуры).

высокая → th[2] ближе к +1 → p ≈ 3.0 (густые, извилистые линии).

density_level:

управляет trap_r:

низкая плотность → trap_r ближе к нижней границе (локальные декорации).

высокая → trap_r ближе к верхней (шире зона захвата, более “залитые” орнаменты).

layout_macro_shape:

можно закодировать ориентацию/центр композиции в trap_c:

макро-форма “центрированная” → trap_c ≈ 0.

макро-форма “смещённая” → trap_c смещаем в соответствующий квадрант.

1.3. SimState и RenderParams
Рекомендуемый mapping:

recursion_depth → max_iter:

max_iter = base_iter + k * recursion_depth (например, от 80 до 320).

noise_level → stochastic_scale:

stochastic_scale = noise_level * s_max (например, 0–0.02).

density_level (дополнительно):

кроме trap_r, может влиять на escape_radius (но осторожно).

layout_macro_shape:

через domain:
макро-форма “zoomed-in” → уменьшать диапазон domain (более крупные детали),
макро-форма “wide” → расширять.

2. orbit_ifs_multi_trap
2.1. Как генератор устроен в коде
Сигнатура: orbit_ifs_multi_trap(state: SimState) -> RunResult.
generators.py

По шагам:

theta формирует набор аффинных карт:

python

n_maps = 4
for i in range(n_maps):
    a = 0.5 + 0.3 * th[i % len(th)]
    b = 0.3 * th[(i + 1) % len(th)]
    cx = th[(i + 2) % len(th)] * 1.0
    cy = th[(i + 3) % len(th)] * 1.0
    maps.append((a, b, cx, cy))
generators.py

Основная орбитальная динамика:

начальная точка (x, y) = (0, 0),

n_points = state.extra.get("n_points", 20_000),

burn-in 20 шагов, далее накапливаем точки (tanh для стабилизации).

Visit map:

дискретизация траектории по resolution и domain.

Orbit traps:

фиксированные ловушки traps (треугольник на окружности),

экспоненциальная функция по расстоянию (trap_score).
generators.py

Морфология: классический IFS-аттрактор с многокартовым контрактором и орбит-ловушками; подходит для многокомпонентных, “растущих” структур.

2.2. Theta и RenderParams
Элемент	Описание	RenderParams-ось
a, b	коэффициенты линейной части (масштаб/вращение)	symmetry_bias, motion_intensity
cx, cy	сдвиги карт	layout_macro_shape, density_level
n_points (extra)	число точек	density_level, texture_complexity
Осмысленная связь:

symmetry_bias:

высокая симметрия → выбирать a, b так, чтобы карты примерно одинаковые и ближе к изотропным (похожие a по всем картам, маленький b).

асимметрия → варьировать a/b по картам, вводя явную “заваленность” фигуры.

motion_intensity:

большее |b| и более сильные сдвиги cx/cy → более “вращательные”/турбулентные орбиты.

низкая интенсивность → мелкие b, близость к чистому схлопывающему контрактору.

density_level:

напрямую → n_points:

n_points = base + density_level * range, например от 10k до 80k.

частично → распределение cx/cy: более высокие значения → более “разбросанная” структура.

texture_complexity:

может маппиться в разнообразие карт:

низкая → theta делает карты похожими (малые различия).

высокая → theta модулируется так, чтобы карты были более разными (по a, b, cx, cy).

2.3. SimState и RenderParams
Рекомендуемый mapping:

recursion_depth → длина орбит / n_points:

для IFS recursion вполне осмысленно через количество точек.
Можно делать:
n_points = round(n_points_base * (1 + alpha * recursion_depth)).

noise_level → stochastic_scale:

чем больше noise, тем больше jitter траекторий (фазовое “размазывание”).

layout_macro_shape:

через domain:

например, разные макро-формы (круг, диагональ, “X”) достигаются выбором домена и комбинации карт;
на уровне adapter’а можно задать шаблоны:

“радиальная” макро-форма → домен ближе к кругу (-1.2, 1.2, -1.2, 1.2).

“диагональная” → растянутость по одной оси.

3. duffing_lyapunov_map
3.1. Как генератор устроен в коде
Сигнатура: duffing_lyapunov_map(state: SimState) -> RunResult.
generators.py

Внутренности:

theta задаёт физические параметры:

python

delta = 0.1 + 0.25 * (th + 1)/2
alpha = -1.0 + 0.5 * th[1]
beta  = 1.0 + 0.5 * th[2]
gamma0 = 0.2 + 0.6 * (th[3] + 1)/2
omega0 = 0.8 + 0.6 * (th[4] + 1)/2
generators.py

resolution задаёт сетку по 
𝛾
γ, 
𝜔
ω:

python

gamma_range = np.linspace(max(0.01, gamma0 - 0.15), gamma0 + 0.15, W)
omega_range = np.linspace(max(0.1, omega0 - 0.15), omega0 + 0.15, H)
Gamma, Omega = np.meshgrid(gamma_range, omega_range)
Временная интеграция:

шаг dt=0.01,

n_steps = state.extra.get("n_steps", 400),

RK4-интегратор по системе:

𝑥
˙
=
𝑣
,
𝑣
˙
=
−
𝛿
𝑣
−
𝛼
𝑥
−
𝛽
𝑥
3
+
𝛾
cos
⁡
(
𝜔
𝑡
)
x
˙
 =v, 
v
˙
 =−δv−αx−βx 
3
 +γcos(ωt)
параллельно считается Ляпунов-подобный экспонент (через дублированную траекторию Xp / Vp, log_sum).
generators.py

Морфология: карта Ляпунова в параметрическом пространстве 
(
𝛾
,
𝜔
)
(γ,ω), где цвет/яркость ~ уровень хаоса; даёт крупномасштабные полосы/острова стабильности и хаотические “моря”.

3.2. Theta и RenderParams
Элемент	Физический смысл	RenderParams-ось
delta	диссипация	motion_intensity, noise_level
alpha	линейная жёсткость	symmetry_bias (частично)
beta	нелинейная жёсткость	texture_complexity
gamma0	амплитуда форсинга	motion_intensity, tension
omega0	частота форсинга	motion_intensity, density_level
Осмысленная связь:

motion_intensity:

ключевой параметр → комбинация gamma0, omega0, delta:

высокая интенсивность → выше gamma0, ближе к критическим omega0, чуть меньше delta → больше хаоса.

низкая интенсивность → наоборот: умеренный forcing, выше диссипация → устойчивые структуры.

texture_complexity:

через beta:

низкая сложность → beta ближе к базовому (1.0–1.2).

высокая → увеличение beta → более нелинейные отклики → богатые границы между режимами.

symmetry_bias:

Duffing симметричен по 
𝑥
x при определённых знаках 
𝛼
,
𝛽
α,β;
можно использовать bias, чтобы:

при высоком symmetry_bias выбирать 
𝛼
α ближе к значениям, где система даёт симметричные аттракторы;

при низком — сдвигать 
𝛼
α так, чтобы возникали асимметричные ответы (разные слои стабильности / хаос).

density_level:

может управлять шириной диапазона 
𝛾
γ, 
𝜔
ω (через gamma_range, omega_range):

низкая плотность → узкий диапазон (больше “стены” с несколькими полосами).

высокая → широкий диапазон → больше уровней “слоёв”.

3.3. SimState и RenderParams
Рекомендуемый mapping:

recursion_depth → n_steps:

n_steps = base_steps + k * recursion_depth (например, от 240 до 600 — уже у тебя есть preset’ы в experiment_protocol.yaml).
experiment_protocol.yaml

Для разных render mode:

macro → использовать research-fast preset (меньше шагов, ниже resolution).

final → publication или validation-hires будущие аналоги для прод.

noise_level → stochastic_scale:

низкий noise → почти детерминированный Duffing (в стиле бенчмарка).

высокий → добавление стохастического члена в v (твоё dv_noise).

layout_macro_shape:

через domain:

хотя здесь domain — параметрическое пространство, можно настроить “рамку”:

разные макро-формы → выбор диапазона 
𝛾
γ/
𝜔
ω вокруг разных gamma0, omega0.

4. Общий формат cheat sheet для остальных генераторов
Когда ты добавишь остальные генераторы (например, chaotic_scattering, smooth_geometric_baseline, single_parameter_map_baseline), для каждого повторяем шаблон из этого файла:

Блок “Как устроен генератор”:

разбор интерпретации theta,

какие поля SimState реально используются.

Таблица theta/extra ↔ RenderParams-оси.

Рекомендации по:

где этот генератор “доминирует” (какие стили/классы),

каких зон избегать (слишком smooth / слишком шум).