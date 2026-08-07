# ТЗ для программиста — обновление до MVP v0.2.1 (backend + analysis)

## 0. Контекст

У нас уже поднят живой backend:
- FastAPI сервер;
- SQLite-база `data/fractal_identity.db`;
- сущности и эндпоинты:
  - `POST /project`, `GET /project/{id}`;
  - `POST /upload` (создаёт Track и привязывает к проекту);
  - `POST /analyze` (пока создаёт пустой AudioAnalysis);
  - заглушки `/capture`, `/resolve-style`, `/generate/poster`, `/export`.

Архитектура и план зафиксированы в:
- `RFC_0.2.md` (базовый MVP);
- `RFC_v0.2.1.md` (перцептивный слой);
- `plan_v0.2.md` и `plan_v0.2.1.md` (этапы реализации);
- Issue 1–2 и P1–P4 (архитектурные задачи).

Твоя задача — обновить существующие backend и analysis блоки до версии v0.2.1: сделать реальный аудио-анализ и добавить перцептивный слой (`PerceptualLatent`), не ломая текущий API.

---

## 1. Общая цель

Сделать так, чтобы цепочка:

`upload → analyze → (perceptual) → style → render`

работала на реальных данных, а не на заглушках. На этом этапе тебя интересуют только два слоя:
- backend (хранение, модели, эндпоинты);
- analysis (извлечение аудиофич и перцептивных осей).

Style engine, renderer и UI трогаем минимально или не трогаем совсем — они будут подключаться следующим шагом.

---

## 2. Обновление доменной модели (backend)

### 2.1 AudioAnalysis

Расширь текущую модель `AudioAnalysis` до следующего минимального набора полей:

Обязательные числовые признаки:
- `bpm` (float)
- `key` (string, например `"A minor"` или `"unknown"`)
- `energy` (float 0..1)
- `spectral_centroid` (float)
- `brightness` (float 0..1, можно derived от centroid)
- `rhythm_density` (float 0..1)
- `dynamic_range` (float, примерно в dB или условных единицах)
- `duration_sec` (float)
- `repetition_score` (float 0..1)
- `suggested_music_style` (string: `"techno"`, `"classical"`, `"ambient"`, `"cinematic"` и т.д.)

Структурные поля (можно как JSON):
- `sections` — список сегментов:
  - формат: JSON-массив объектов `{id, label, start_sec, end_sec}`
- `recurrence_groups` — группы повторов:
  - формат: JSON-массив объектов `{group_id, sections: [section_ids...]}`
- `events` — крупные события:
  - формат: JSON-массив `{type, time_sec, description}`

Важно:
- сделай эту структуру так, чтобы её было удобно расширять без миграционной боли;
- если проще, можешь держать `sections`, `recurrence_groups`, `events` одним JSON-полем с вложенной структурой.

### 2.2 PerceptualLatent

Введи сущность `PerceptualLatent`. Можно как отдельную таблицу или как вложенный блок в `AudioAnalysis`. На этом этапе проще сделать отдельную таблицу:

Поля:
- `id`
- `analysis_id`
- `track_id`
- `energy`
- `tension`
- `density`
- `brightness`
- `stability`
- `smoothness`
- `repetition`
- `section_complexity`
- `macro_shape_hint` (string, например `"ABA_like"`, `"strophic_like"`, `"unknown"`)
- `created_at`

Это минимальный перцептивный вектор, который потом будет использовать style engine.

### 2.3 Связи и миграции

- Убедись, что `AudioAnalysis` связан с `Track` и `UserProject` как и раньше.
- Добавь связь `PerceptualLatent.analysis_id → AudioAnalysis.id`.
- При необходимости добавь индексы по `track_id`, `analysis_id`.

Если для этого нужно обновить схему SQLite:
- добавь миграционный скрипт или аккуратную инициализацию при старте;
- предусмотрительно обработай существующие записи (placeholder-значения допускаются, но без фиктивных аудиофич).

---

## 3. Реализация анализа (analysis)

### 3.1 Входы для /analyze

Текущий `/analyze` должен принимать как минимум:
- `project_id`
- `track_id`

Убедись, что:
- для `track_id` реально существует файл в storage;
- формат файла поддерживается (MP3/WAV);
- файл доступен для чтения.

### 3.2 Извлечение аудиопризнаков

Используй Python-библиотеки (например, `librosa`, `pydub`, `mutagen`, `soundfile`, `numpy`) для расчёта:

- BPM: tempo по onset envelope или эквиваленту;
- Key/mode: хрома-профиль + простая тональная модель (или библиотечный метод);
- Energy: интегральная энергия/громкость (например, нормализованный RMS);
- Spectral centroid: стандартный показатель по спектру;
- Brightness: нормализованная версия spectral centroid (0..1);
- Rhythm density: отношение количества onset’ов/событий к длительности;
- Dynamic range: разница между тихими и громкими участками;
- Duration: длина файла в секундах (по метаданным или sample count / sample rate);
- Repetition_score: грубая оценка повторяемости (например, на основе autocorrelation / self-similarity по frame’ам).

Важно:
- не гнаться за идеальной музыкологией на этом шаге;
- сделать стабильный, воспроизводимый расчёт.

### 3.3 Suggested music style

Реализуй простую rule-based функцию, которая по признакам выдаёт одну из стилей:
- `"techno"`
- `"classical"`
- `"ambient"`
- `"cinematic"`

Пример эвристик (можно скорректировать):
- high BPM + высокая rhythm_density + высокая energy → `techno`;
- низкая energy + низкая rhythm_density + высокая smoothness → `ambient`;
- широкая dynamic_range + средний tempo + богатый спектр → `cinematic`;
- более стабильная тональность + умеренная динамика → `classical`.

Эта функция должна быть прозрачной и легко редактируемой (без ML).

### 3.4 Запись AudioAnalysis

После расчёта всех признаков:
- создай запись `AudioAnalysis`;
- заполни все числовые поля;
- запиши `sections` / `recurrence_groups` / `events` хотя бы в виде простых сегментов (например, деление трека на 4–8 равных частей + отметки по energy peaks, чтобы позже можно было улучшить алгоритм);
- сохрани запись в SQLite.

### 3.5 API-ответ /analyze

Обнови ответ `POST /analyze`, чтобы он возвращал:
- `status` (`success` / `error`);
- `project_id`;
- `track_id`;
- `analysis_id`;
- блок `features` с основными полями;
- `suggested_music_style`.

Пример:
```json
{
  "status": "success",
  "project_id": "...",
  "track_id": "...",
  "analysis_id": "...",
  "features": {
    "bpm": 128.4,
    "key": "A minor",
    "energy": 0.82,
    "spectral_centroid": 2450.1,
    "brightness": 0.76,
    "rhythm_density": 0.71,
    "dynamic_range": 12.4,
    "duration_sec": 183.2,
    "repetition_score": 0.63
  },
  "suggested_music_style": "techno"
}
```

При ошибках:
- возвращай понятный `error` с описанием;
- не создавай пустых AudioAnalysis.

---

## 4. Реализация перцептивного слоя (backend + analysis)

### 4.1 Mapping в PerceptualLatent

После того как `AudioAnalysis` сохранён, реализуй функцию:

```python
perceptual = build_perceptual_latent(audio_analysis)
```

которая:
- берёт готовый `AudioAnalysis`;
- вычисляет перцептивные оси:
  - `energy` → нормализованная `energy` из анализа;
  - `tension` → комбинация dynamic_range + вариативность энергии/тональности;
  - `density` → нормализованная `rhythm_density`;
  - `brightness` → нормализованный spectral_centroid/brightness;
  - `stability` → обратная вариативность ключа/тональности;
  - `smoothness` → “плавность” по градиентам энергии/спектра (чем меньше резких скачков, тем выше smoothness);
  - `repetition` → нормализованный `repetition_score`;
  - `section_complexity` → функция от числа секций и разнообразия labels;
  - `macro_shape_hint` → простая строка (`"ABA_like"`, `"linear"`, `"unknown"`) по грубой форме.

### 4.2 Сохранение PerceptualLatent

- Создай запись `PerceptualLatent` и сохрани её в БД;
- Привяжи её к `analysis_id` и `track_id`.

### 4.3 Расширение ответа /analyze перцептивным блоком

Добавь в ответ `/analyze` дополнительный блок:

```json
"perceptual": {
  "energy": 0.82,
  "tension": 0.67,
  "density": 0.71,
  "brightness": 0.76,
  "stability": 0.54,
  "smoothness": 0.61,
  "repetition": 0.63,
  "section_complexity": 0.4,
  "macro_shape_hint": "ABA_like"
}
```

Если какие-то оси посчитать не удалось — явно укажи `null` и, по возможности, добавь поле `notes` или лог.

---

## 5. Нефункциональные требования

- Детеминизм: для одного и того же файла, при той же версии кода, результаты анализа и перцептивного слоя должны быть стабильны.
- Логи: логируй старт/конец анализа, track_id, длительность анализа, ключевые признаки и ошибки.
- Производительность: анализ одного трека должен укладываться в разумное время для MVP. Если трек большой, можно ограничивать анализ по длине (например, первые N секунд) — но это нужно явно зафиксировать в коде/комментарии.
- Безопасность: не допускай падения сервера из-за повреждённых файлов, обрабатывай исключения при чтении аудио.

---

## 6. Definition of Done (для этого ТЗ)

1. `POST /analyze`:
   - читает реальный audio-файл по `track_id`;
   - считает аудиопризнаки;
   - создаёт `AudioAnalysis` в БД;
   - создаёт `PerceptualLatent` в БД;
   - возвращает JSON с `features` и `perceptual`.

2. БД:
   - содержит таблицу/структуру для `PerceptualLatent`;
   - расширенный `AudioAnalysis` с структурными полями.

3. Логи:
   - позволяют отследить, что анализ и перцептивный слой отработали корректно.

4. Код:
   - не ломает существующие endpoints;
   - готов для подключения следующего слоя: `/resolve-style` и style engine.
