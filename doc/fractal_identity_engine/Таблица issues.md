MVP v0.2 — GitHub Issues
1. Freeze MVP scope and API contracts
Priority: P0
Depends on: —

Description:
Зафиксировать окончательный scope MVP: web-first продукт с mobile wrapper, input через microphone live и audio file upload, генерация poster preview + GIF preview, watermark, project history, paid hi-res export.
Нужно утвердить финальные API endpoints, domain model и границы MVP / post-MVP.

Acceptance criteria:

Scope зафиксирован.

Все основные сущности и endpoints согласованы.

Loop-video и pro mode явно вынесены за MVP.

2. Define domain model and storage schema
Priority: P0
Depends on: Issue 1

Description:
Описать доменную модель и схему хранения для:

Track

AudioAnalysis

StyleProfile

UserPreset

GenerationJob

PosterAsset

ExportJob

UserProject

Нужно разделить authoritative и derived данные, определить связи между сущностями и статусы жизненного цикла.

Acceptance criteria:

Есть финальная схема сущностей.

Есть storage layout.

Есть описание жизненного цикла объектов.

3. Create backend skeleton and project CRUD
Priority: P0
Depends on: Issues 1, 2

Description:
Поднять минимальный backend каркас:

создание проекта;

получение проекта;

базовая структура хранения;

подготовка к дальнейшим endpoint-ам.

Acceptance criteria:

Проект можно создать и получить.

Backend знает, где хранить track, analysis и assets.

Есть базовый project CRUD.

4. Implement upload endpoint for MP3/WAV
Priority: P0
Depends on: Issue 3

Description:
Сделать загрузку файла через API:

принять MP3/WAV;

валидировать формат и размер;

создать Track;

привязать его к UserProject.

Acceptance criteria:

Файл загружается успешно.

Создаётся Track.

Файл сохраняется в storage.

Ошибки валидации отрабатывают корректно.

5. Implement microphone capture ingestion contract
Priority: P0
Depends on: Issue 3

Description:
Определить и реализовать контракт для microphone live input.
На MVP можно сделать минимальную интеграцию: клиент захватывает звук, backend принимает chunk/stream metadata или surrogate input для анализа.

Acceptance criteria:

Есть рабочий путь для live mic input.

Контракт совместим с дальнейшим анализом.

Не ломает upload flow.

6. Implement audio analysis pipeline
Priority: P0
Depends on: Issues 3, 4

Description:
Сделать серверный анализ звука и формировать AudioAnalysis JSON:

BPM;

key / mode;

energy;

spectral centroid / brightness;

rhythm density;

dynamic range;

duration;

repetition / structure score;

suggested music style.

Acceptance criteria:

Анализ создаётся по track_id.

Результат сохраняется как immutable derived object.

Для одного и того же входа результат стабилен.

7. Define StyleProfile configs for MVP styles
Priority: P0
Depends on: Issues 1, 2

Description:
Сделать конфиги стилей для MVP.
Минимум:

music style hint;

visual mood;

palette;

contrast;

geometry;

density;

motion intensity;

noise level;

symmetry bias;

complexity bias.

Acceptance criteria:

Есть минимум 4 MVP style profiles.

Профили лежат в конфиг-файлах.

Стиль не хардкодится в генераторе.

8. Implement style resolver and render params mapping
Priority: P0
Depends on: Issues 6, 7

Description:
Сделать слой, который превращает AudioAnalysis + выбранный StyleProfile + UserPreset в RenderParams.

Acceptance criteria:

Один анализ может дать разные render params в зависимости от стиля.

Есть авто-выбор стиля.

Есть ручной override стиля.

Результат сохраняется как snapshot.

9. Implement slider-to-parameter mapping
Priority: P1
Depends on: Issues 7, 8

Description:
Добавить пользовательские слайдеры:

Complexity;

Symmetry;

Density;

Noise;

Motion.

Нужно связать их с render params и сохранять в UserPreset.

Acceptance criteria:

Слайдеры влияют на результат.

Значения сохраняются в проекте.

UI и backend используют один контракт параметров.

10. Build poster renderer for low-res preview
Priority: P0
Depends on: Issues 8, 9

Description:
Реализовать генератор постера:

low-res preview;

генерация PNG/JPG;

визуальное отличие между стилями;

использование render params.

Acceptance criteria:

Можно получить poster preview по проекту.

Постер меняется при смене стиля и параметров.

Генератор не зависит от UI.

11. Add watermark pipeline for preview assets
Priority: P0
Depends on: Issue 10

Description:
Добавить watermark на preview assets для free tier.

Acceptance criteria:

Watermark применяется к preview poster.

hi-res export может быть без watermark при оплате.

Пайплайн не ломает качество превью.

12. Build preview screen in web UI
Priority: P0
Depends on: Issues 3, 10, 11

Description:
Сделать экран превью:

показать poster preview;

показать status generation;

дать выбрать style;

дать крутить слайдеры;

дать сохранить проект;

дать перейти к export.

Acceptance criteria:

Пользователь может дойти от input до preview.

UI не требует developer assistance.

Preview screen выглядит как продукт, а не как debug panel.

13. Add save project flow and project history
Priority: P1
Depends on: Issues 2, 3, 12

Description:
Добавить сохранение проекта и историю:

список проектов;

возврат к проекту;

повторная генерация без новой загрузки;

лимит 5 проектов в MVP.

Acceptance criteria:

Проект можно сохранить и открыть снова.

Есть project history.

Лимит проектов работает.

14. Implement export job pipeline
Priority: P1
Depends on: Issues 10, 11, 13

Description:
Добавить экспорт:

отдельный ExportJob;

подготовка downloadable asset;

PNG/JPG export;

hi-res export path;

signed download URL.

Acceptance criteria:

Экспорт работает отдельно от генерации.

Preview и hi-res пути разделены.

Есть статус export job.

15. Add paid hi-res export gate
Priority: P1
Depends on: Issue 14

Description:
Добавить платный доступ к hi-res экспортам.

Acceptance criteria:

Free user видит ограниченный экспорт.

Paid user получает hi-res доступ.

Paywall не мешает preview flow.

16. Add free-tier project limit enforcement
Priority: P1
Depends on: Issue 13

Description:
Ограничить бесплатный тариф до 5 проектов.

Acceptance criteria:

Лимит проектов применяется корректно.

Пользователь получает понятное сообщение при достижении лимита.

Ограничение не ломает уже сохранённые проекты.

17. QA: visual sanity-check across styles
Priority: P0
Depends on: Issues 8, 10, 12

Description:
Сделать визуальную проверку MVP:

проверить различия между стилями;

проверить repeatability;

проверить корректность preview;

проверить, что styles не выглядят как копии друг друга.

Acceptance criteria:

Есть ручной/полуавтоматический sanity-check.

Можно быстро понять, работает ли стильная дифференциация.

Найдены и описаны основные visual defects.

18. Build mobile wrapper / responsive shell
Priority: P2
Depends on: Issues 12, 14

Description:
Сделать мобильную оболочку или адаптивный shell поверх web product.

Acceptance criteria:

Интерфейс работает на mobile.

Основной flow не ломается.

Web и mobile используют один backend.

19. Add mobile microphone access integration
Priority: P2
Depends on: Issues 5, 18

Description:
Подключить microphone access в mobile контуре.

Acceptance criteria:

Microphone capture работает в mobile.

Контракт совместим с backend.

Не создаёт отдельный конфликтный pipeline.

20. Prepare post-MVP backlog: GIF, loop-video, pro mode, text input
Priority: P2
Depends on: Issue 1

Description:
Подготовить список фич следующего этапа:

GIF refinements;

loop-video;

pro mode;

text input;

batch generation;

social publishing tools.

Acceptance criteria:

Есть post-MVP backlog.

Loop-video не входит в текущий релиз.

Команда знает, что делать после MVP.

Suggested labels
priority:P0

priority:P1

priority:P2

area:backend

area:frontend

area:analysis

area:renderer

area:export

area:mobile

area:qa

blocked

needs-design

Suggested milestone
MVP v0.2