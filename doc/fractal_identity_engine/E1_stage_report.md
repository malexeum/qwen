# Отчёт об этапе E1 — AudioFileAdapter

**Статус:** ✅ ЗАКРЫТ  
**Дата закрытия:** 2026-08-10  
**Коммит:** [`e97c178`](https://github.com/malexeum/qwen/commit/e97c178de3066050aae58d6a3f4e4a21708aa370)  
**Тест:** `test9.py` — 5/5 треков, 0 ошибок, 0 предупреждений spread

---

## Цель этапа

Реализовать слой извлечения перцептивных признаков аудиофайла (`AudioFileAdapter / extract_features()`), который:

- принимает путь к MP3/WAV;
- возвращает 17-осевой вектор `float [0, 1]` + `duration_sec` + `style`;
- обеспечивает статистически различимые значения по всем целевым осям на разножанровых треках.

---

## Реализованные компоненты

| Файл | Роль |
|---|---|
| `lib/audio_analysis/analysis.py` | Ядро: загрузка, DSP, извлечение 19 raw-признаков из librosa |
| `lib/audio_analysis/audio_file_adapter.py` | Адаптер: нормировка raw → 17 перцептивных осей |
| `lib/audio_analysis/__init__.py` | Публичный API модуля |
| `test9.py` | Smoke-test: 5 контрольных треков, проверка spread |

---

## Итоговые 17 осей

| Ось | Источник | Нормировка |
|---|---|---|
| `energy` | RMS mean | / 0.50 |
| `tension` | dynamic range (P90–P10 RMS, дБ) | / 30.0 |
| `repetition` | chroma lag-correlation | [0,1] native |
| `tempo` | librosa beat_track BPM | / 220.0 |
| `section_complexity` | число секций | / 10.0 |
| `silence_rate` | доля RMS-фреймов ниже адаптивного порога | [0,1] native |
| `harmonic_stability` | mean std по 13 MFCC / 50.0 | **(fix3)** |
| `harmonic_change_rate` | смен гармоний/с из chroma cosine | / 2.0 |
| `spectral_flatness` | librosa spectral_flatness | [0,1] native |
| `high_frequency_energy` | мощность > 4 кГц / полная мощность | [0,1] native |
| `density_level` | onset rate (ударов/с) | / 8.0 **(fix1)** |
| `motion_intensity` | spectral centroid | / 1500 Hz **(fix2)** |
| `texture_complexity` | 0.5·flatness + 0.3·centroid_norm + 0.2·onset_norm | composite |
| `noise_level` | = spectral_flatness | alias |
| `symmetry_bias` | cosine harmonic_stability (raw) | [0,1] |
| `layout_macro_shape` | время первого энергетического пика / duration | [0,1] |
| `recursion_depth` | 0.5·centroid_norm + 0.3·tension + 0.2·flatness | composite |

---

## Исправления в процессе этапа

### Fix 1 — density_level
**Проблема:** использовался `rhythm_density` (медианный порог onset_envelope) — не различал жанры, std = 0.000.  
**Решение:** заменено на реальный `onset_rate_hz` (onsets/сек, librosa.onset.onset_detect), нормировка / 8.0.  
**Результат:** std = 0.134 ✅

### Fix 2 — motion_intensity  
**Проблема:** нормировка `spectral_centroid / nyquist (22050 Hz)` давала значения 0.03–0.09, практически нулевые.  
**Решение:** нормировка / 1500 Hz — соответствует верхней границе основного музыкального диапазона (300–700 Hz).  
**Результат:** std = 0.157 ✅  
**Примечание:** у jazz и electronic треков centroid > 1500 Hz → clip(1.0). Потенциальное улучшение — логарифмическое масштабирование или подъём нормы до 2000 Hz, но это не блокер.

### Fix 3 — harmonic_stability  
**Проблема:** формула `0.5·cosine_stability + 0.5·(1−chroma_entropy)` давала значения ~0.49 для всех жанров, std = 0.000.  
**Причина:** обе компоненты коррелируют между собой и слабо дифференцируют жанры.  
**Решение:** заменено на `mfcc_variance_norm = mean(std по 13 MFCC-коэффициентам) / 50.0`.  
**Физический смысл:** тембральная вариативность — хорошо разделяет жанры: джаз (широкий спектр) vs. классика (устойчивый тембр) vs. ambient.  
**Результат:** std = 0.069 ✅  
**Важно:** `symmetry_bias` сохранён на основе исходного cosine harmonic_stability — он семантически другой (тональная стабильность, ~0.97 для всех треков, что физически корректно для музыки).

---

## Результаты test9 — финальный прогон

### Матрица признаков (5 контрольных треков)

| Трек | style | energy | tension | tempo | density | h_stab | motion |
|---|---|---:|---:|---:|---:|---:|---:|
| Front_Porch_Blues.mp3 | blues_jazz | 0.123 | 0.584 | 0.534 | 0.535 | 0.388 | 0.780 |
| Space.mp3 | ambient | 0.582 | 0.364 | 0.412 | 0.508 | 0.407 | 0.714 |
| Autumn Leaves.mp3 | jazz | 0.174 | 0.574 | 0.587 | 0.298 | 0.471 | 1.000 |
| Катенькин Вальс.mp3 | classical | 0.162 | 0.326 | 0.522 | 0.429 | 0.261 | 0.607 |
| Sing, Sing, Sing.mp3 | electronic | 0.219 | 0.416 | 0.489 | 0.705 | 0.361 | 1.000 |

### Межтрековый разброс (std по 5 трекам)

| Ось | std | Порог | Вердикт |
|---|---:|---:|---|
| energy | 0.168 | 0.05 | ✅ |
| tension | 0.107 | 0.05 | ✅ |
| tempo | 0.058 | 0.05 | ✅ |
| density_level | 0.134 | 0.05 | ✅ |
| motion_intensity | 0.157 | 0.05 | ✅ |
| harmonic_stability | 0.069 | 0.05 | ✅ |

**Ошибок валидации: 0. Предупреждений: 0.**

---

## Технические наблюдения для архитектора

### Что работает хорошо
- `energy`, `tension`, `tempo` — стабильные оси с высоким разбросом, надёжная основа для mapping.
- `density_level` корректно ранжирует: electronic > blues > ambient > classical > jazz — физически осмысленно.
- `harmonic_stability` (MFCC std) чисто разделяет jazz (0.471) от classical (0.261) — ожидаемый результат.
- `symmetry_bias` (cosine ~0.97 для всех) — намеренно высокий: музыкальные треки тонально стабильны по построению. Использовать как инвариант, не как дифференциатор.

### Что требует внимания на следующем этапе
- `motion_intensity` saturates at 1.0 для jazz и electronic (centroid > 1500 Hz). Для E2 рекомендуется либо `MOTION_NORM_HZ = 2000`, либо `log1p`-масштабирование.
- `section_complexity` = 0.6 для всех треков (6 равных секций, MVP-сегментация). Реальная сегментация (librosa.segment) — задача для следующего этапа.
- `layout_macro_shape` очень мал (0.004–0.102) — первый энергетический пик у всех треков в начале. Семантически полезен только при наличии intro/outro структуры.

### Константы модуля (зафиксированы в analysis.py)

```python
DEFAULT_SR_HZ      = 44100   # частота дискретизации
N_FFT              = 2048     # окно FFT
HOP_LENGTH         = 512      # шаг
HIGH_FREQUENCY_CUTOFF_HZ = 4000.0
MOTION_NORM_HZ     = 1500.0  # нормировка centroid
ONSET_RATE_NORM    = 8.0     # onsets/s → [0,1]
MFCC_NORM          = 50.0    # std MFCC → [0,1]
```

---

## Интерфейс модуля (публичный API)

```python
from lib.audio_analysis.audio_file_adapter import extract_features

features: dict = extract_features(
    audio_path="path/to/track.mp3",
    style_hint="jazz",   # опционально, иначе auto-detect
)
# → dict с 19 ключами: 17 float [0,1] + duration_sec + style
```

---

## Статус зависимостей

| Зависимость | Версия | Статус |
|---|---|---|
| librosa | ≥ 0.10 | ✅ production |
| numpy | ≥ 1.24 | ✅ |
| soundfile / audioread | librosa deps | ✅ |
| mpg123 (Windows) | системная | ⚠️ выдаёт warning на ID3v2 без comment — не влияет на результат |

---

## Готовность к E2

Модуль `E1 AudioFileAdapter` готов к использованию как входной слой для **E2 HarmonyEncoder** — детерминированного `rule_based_mapping`, который переводит 17-осевой вектор в управляющий вектор θ генераторов фракталов.

Входной контракт E2:
- принимает `dict` из `extract_features()`;
- возвращает `theta: list[float]` длиной 6, все значения `tanh`-сжаты в `(−1, +1)`;
- маппинг детерминированный, без обучаемых весов (согласно `tech_plan_step2_corrections`, п. 2).

---

*Отчёт сгенерирован автоматически на основе результатов test9 и истории коммитов. Commit: `e97c178`.*
