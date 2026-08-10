# ТЗ: Visual Differentiation — Подфаза D1

**Статус:** следует после Reference Renderer (C1 ✅)
**Проблема:** 4 из 5 постеров выглядят одинаково — разноцветные круги
**Версия:** D1.0

---

## 1. Диагноз

Доминанта профилей blues/ambient/classical — процедурные генераторы:
`orbital_field`, `colored_noise_field`, `symmetry_snowflake`.

Текущая `run_orbital_field` рисует случайные точки без непрерывности траекторий:
после `canvas[iy, ix] += 1.0` позиция возобновляется через `x0, y0`, но
никакой связи между текущей и предыдущей точкой нет: `x0` и `y0` пересчитываются
в `x0 += ...` сразу после рисовки. Геометрически это означает, что линия рисуется как
отдельные пиксели, а не цельные дуги. После `log1p` + нормализации получаем
пятна вместо потоков. Отсюда — одинаковые круги без структуры.

---

## 2. Исправление `run_orbital_field`

**Проблема:** Траектория не рисуется как цепочка пикселей. Текущая версия
обновляет `x0/y0` после оценки пиксельных координат, а не при подготовке
перемещения. Исправленный логический порядок:

```python
def run_orbital_field(params: dict, W: int, H: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), dtype=np.float32)
    n = int(np.clip(params.get("line_count", 0.5) * 120 + 40, 40, 200))
    flow_speed = float(params.get("flow_speed", 0.5))
    amplitude = float(params.get("amplitude", 0.5))
    angular_break = float(params.get("angular_break", 0.0))
    orbit_radius = float(params.get("orbit_radius", 0.5)) * 0.6 + 0.15
    steps = int(flow_speed * 400 + 100)

    for _ in range(n):
        # Начальная точка — цепочка HILTается из неё
        x0 = rng.uniform(-1.0, 1.0)
        y0 = rng.uniform(-1.0, 1.0)
        angle = np.arctan2(y0, x0)  # угол от центра

        for _ in range(steps):
            r = np.sqrt(x0 ** 2 + y0 ** 2) + 1e-9
            # Радиальное притяжение к orbit_radius
            dr = (orbit_radius - r) * amplitude * 0.04
            # Тангенциальная скорость (орбитальное движение)
            dtheta = (angular_break * 0.5 + 0.5) / (r + 0.3)
            # Перемещаем точку PERЕД записью
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            x0 += dr * cos_a - dtheta * sin_a
            y0 += dr * sin_a + dtheta * cos_a
            angle = np.arctan2(y0, x0)  # обновляем после движения

            # Записываем текущее положение
            ix = int((x0 + 1.0) / 2.0 * (W - 1))
            iy = int((y0 + 1.0) / 2.0 * (H - 1))
            if 0 <= ix < W and 0 <= iy < H:
                canvas[iy, ix] += 1.0

    canvas = np.log1p(canvas)
    mx = canvas.max()
    if mx > 0:
        canvas /= mx
    return canvas.astype(np.float32)
```

**Что изменилось:**
- `orbit_radius` отвечает за радиус аттрактора: `dr = (orbit_radius - r) * ...`
- `angle` обновляется после каждого шага — траектория следует за фазой
- Запись пикселя происходит после движения, не до

**Результат:** видимые орбитальные траектории вместо рассеянных пятен.

---

## 3. Усиление `run_symmetry_snowflake`

Текущий снежинка рисует линейные ветви шагами с шагом 1/`steps` — они выглядят
прямыми пиксельными линиями, но без толщины и гауссовой оболочки — хрупкие.

**Исправление:** добавить gaussian_filter после заполнения, до нормализации:

```python
    # в конце run_symmetry_snowflake, заменить финальную нормализацию:
    from scipy.ndimage import gaussian_filter as gf
    line_width = float(params.get("branch_jitter", 0.05)) * 3.0 + 0.8
    canvas = gf(canvas, sigma=line_width)
    mx = canvas.max()
    if mx > 0:
        canvas /= mx
    return canvas.astype(np.float32)
```

**Что даёт:** ветви становятся видимыми лучами с мягкими краями,
а не хрупкими пиксельными линиями.

---

## 4. Основной диагноз единообразия

Глубже причина в том, что все профили запускаются с одинаковыми **синтетическими features**.
`run_full.py` подаёт `_BASE = {...}` с захардкоженными `energy=0.6, tension=0.4, ...` для
всех профилей. Планнер даёт почти одинаковые `params`, слои смешиваются похоже.
Цвет разный (палитры), но структура одинаковая.

**Фикс: добавить дифференцированные синтетические features в `run_full.py`.**

```python
# Текущее (все одинаково):
_BASE = {
    "energy": 0.6, "tension": 0.4, "repetition": 0.5,
    "tempo": 0.5, "section_complexity": 0.5, "silence_rate": 0.2,
    ...
}
FEATURES = {style: _BASE for style in PROFILES}

# Нужно:
FEATURES = {
    "blues_jazz": {
        "energy": 0.55, "tension": 0.38, "repetition": 0.62,
        "tempo": 0.42, "section_complexity": 0.58, "silence_rate": 0.24,
        "harmonic_stability": 0.72, "harmonic_change_rate": 0.28,
        "noise_level": 0.18, "spectral_flatness": 0.22,
        "high_frequency_energy": 0.20, "density_level": 0.55,
        "motion_intensity": 0.40, "texture_complexity": 0.52,
        "symmetry_bias": 0.45, "layout_macro_shape": 0.35,
        "recursion_depth": 0.62,
    },
    "electronic": {
        "energy": 0.88, "tension": 0.82, "repetition": 0.70,
        "tempo": 0.78, "section_complexity": 0.75, "silence_rate": 0.08,
        "harmonic_stability": 0.25, "harmonic_change_rate": 0.72,
        "noise_level": 0.55, "spectral_flatness": 0.80,
        "high_frequency_energy": 0.78, "density_level": 0.85,
        "motion_intensity": 0.88, "texture_complexity": 0.82,
        "symmetry_bias": 0.22, "layout_macro_shape": 0.62,
        "recursion_depth": 0.90,
    },
    "jazz": {
        "energy": 0.52, "tension": 0.48, "repetition": 0.38,
        "tempo": 0.48, "section_complexity": 0.65, "silence_rate": 0.32,
        "harmonic_stability": 0.55, "harmonic_change_rate": 0.45,
        "noise_level": 0.22, "spectral_flatness": 0.35,
        "high_frequency_energy": 0.28, "density_level": 0.42,
        "motion_intensity": 0.55, "texture_complexity": 0.60,
        "symmetry_bias": 0.30, "layout_macro_shape": 0.48,
        "recursion_depth": 0.55,
    },
    "ambient": {
        "energy": 0.22, "tension": 0.12, "repetition": 0.80,
        "tempo": 0.18, "section_complexity": 0.30, "silence_rate": 0.52,
        "harmonic_stability": 0.88, "harmonic_change_rate": 0.10,
        "noise_level": 0.08, "spectral_flatness": 0.15,
        "high_frequency_energy": 0.08, "density_level": 0.22,
        "motion_intensity": 0.18, "texture_complexity": 0.25,
        "symmetry_bias": 0.70, "layout_macro_shape": 0.50,
        "recursion_depth": 0.30,
    },
    "classical": {
        "energy": 0.48, "tension": 0.30, "repetition": 0.68,
        "tempo": 0.38, "section_complexity": 0.55, "silence_rate": 0.28,
        "harmonic_stability": 0.82, "harmonic_change_rate": 0.22,
        "noise_level": 0.08, "spectral_flatness": 0.18,
        "high_frequency_energy": 0.15, "density_level": 0.45,
        "motion_intensity": 0.30, "texture_complexity": 0.48,
        "symmetry_bias": 0.72, "layout_macro_shape": 0.28,
        "recursion_depth": 0.65,
    },
}
```

**Ключевые различия:**
- `electronic`: `energy=0.88`, `tension=0.82`, `density_level=0.85`, `silence_rate=0.08`
- `ambient`: `energy=0.22`, `silence_rate=0.52`, `harmonic_stability=0.88`
- `classical`: `symmetry_bias=0.72`, `harmonic_stability=0.82`, `noise_level=0.08`
- `jazz`: `silence_rate=0.32`, `symmetry_bias=0.30`, `density_level=0.42`
- `blues_jazz`: посредина по всем осям

---

## 5. AudioFileAdapter (отдельное {ТЗ})

В D1 реальный аудио не подключается. После D1 (визуальное качество проверено) —
подфаза E1 `AudioFileAdapter`.

Интерфейс:

```python
# lib/audio_analysis/audio_file_adapter.py

def extract_features(audio_path: str | Path) -> dict:
    """
    Вход:  audio_path (любой формат, поддерживаемый librosa)
    Выход: dict — все перцептивные оси (тот же формат, что FEATURES[профиль])
    """
```

**Ответа на вопрос про librosa:** использовать `librosa` достаточно.
Форматы WAV/MP3/FLAC все поддерживаются через `soundfile`/`audioread`.
Маппинг raw признаков → перцептивных осей:

| Ось | Источник librosa |
|---|---|
| `energy` | `librosa.feature.rms` → среднее, [0,1] |
| `tension` | изменчивость чрома (`chroma_stft` std) |
| `repetition` | ACF пик или `librosa.autocorrelate` |
| `tempo` | `librosa.beat.beat_track` BPM / 200.0 |
| `section_complexity` | число сегментов `librosa.segment` |
| `silence_rate` | доля фреймов, где rms < threshold |
| `harmonic_stability` | 1 - `chroma_stft` среднее std |
| `harmonic_change_rate` | HPCP скорость изменения |
| `spectral_flatness` | `librosa.feature.spectral_flatness` |
| `high_frequency_energy` | RMS выше 4 кГц |
| `density_level` | onset rate / max_onset_rate |
| `motion_intensity` | среднее `spectral_rolloff` |
| `texture_complexity` | среднее `spectral_bandwidth` |
| `noise_level` | `spectral_flatness` (alias) |
| `symmetry_bias` | 1 - относительная ошибка chroma (std) |
| `layout_macro_shape` | позиция пика energy_envelope |
| `recursion_depth` | спектральная ширина огибания |

---

## 6. Порядок выполнения D1

```
1. Исправить run_orbital_field() — баг обновления x0/y0
2. Добавить gaussian_filter в run_symmetry_snowflake()
3. Заменить _BASE на дифференцированные FEATURES в run_full.py
4. Запустить полный pytest — все 32+ теста зелёные
5. Рендерить все 5 профилей заново
6. Визуальный аудит: 5 PNG должны отличаться друг от друга визуально
```

---

## 7. Критерий закрытия D1

- [ ] `run_orbital_field` рисует дуги, а не пятна (визуальная проверка)
- [ ] `run_symmetry_snowflake` даёт видимые лучи, не хрупкие линии
- [ ] `FEATURES` в `run_full.py` дифференцированы по 5 профилям
- [ ] все тесты зелёные
- [ ] 5 PNG визуально различимы (не просто разные цвета — разная структура)
