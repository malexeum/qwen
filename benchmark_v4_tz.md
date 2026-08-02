# Техническое задание: Benchmark v4

## 1. Назначение документа

Настоящее техническое задание описывает требования к разработке **Benchmark v4** для фрактального / нелинейного движка. Цель версии v4 — превратить существующий исследовательский pipeline в строгую систему сравнения, которая умеет:

- различать выходные классы;
- отделять слой **морфологии** от слоя **идентичности**;
- оценивать сохранение, трансформацию и разрушение классов;
- измерять устойчивость к seed noise, parameter noise и observer variance;
- выявлять бифуркационные переходы;
- обеспечивать воспроизводимость и версионирование всех стадий вычисления.

Benchmark v4 должен стать не просто более крупной серией прогонов, а новой аналитической архитектурой, где каждая сущность в данных имеет собственную роль, версию и метрики.

## 2. Цель версии v4

Benchmark v4 должен ответить на следующие вопросы:

1. Какой генератор лучше всего сохраняет идентичность входного класса.
2. Какие выходные классы можно различить надёжно и устойчиво.
3. Как отличить морфологическое сходство от идентичности класса.
4. Какие преобразования приводят к сохранению, переходу или разрушению класса.
5. На каких деформациях система переходит в новый режим поведения.
6. Какие признаки отвечают за морфологию, а какие — за идентичность.

## 3. Основные проблемы, которые должен решить v4

### 3.1 Смешение морфологии и идентичности

В текущем состоянии система может извлекать полезные морфологические признаки, но не всегда понимает, сохраняется ли идентичность класса. Это приводит к тому, что генератор может выглядеть "структурно богатым", но при этом разрушать класс.

В v4 эти два слоя должны быть отделены:

- **Morphology layer** — описывает форму, структуру, плотность, симметрию, фрактальность, энтропию и другие геометрические характеристики.
- **Identity layer** — описывает, к какому классу относится результат, сохраняется ли родство, произошёл ли переход или разрушение.

### 3.2 Невнятные output classes

Нужно перестать считать выход просто "результатом генератора". Каждый результат должен быть отнесён к явному output class.

### 3.3 Недостаточная интерпретируемость

Система должна отвечать не только цифрами, но и понятной классификацией:

- preserved;
- transformed;
- broken;
- emergent.

## 4. Термины и сущности

### 4.1 Input class

Исходный класс структуры, подаваемый на генератор. Примеры: `harmonic_symmetric`, `asymmetry_transition`, `tense_cluster`.

### 4.2 Generator family

Семейство преобразования. Примеры: `julia_orbit_trap`, `orbit_ifs_multi_trap`, `duffing_lyapunov`, `chaotic_scattering`.

### 4.3 Morphology

Набор признаков, характеризующих форму и структуру результата.

### 4.4 Identity

Категория, определяющая, насколько результат сохраняет принадлежность исходному классу.

### 4.5 Output class

Класс, присвоенный результату после наблюдения и классификации.

### 4.6 Transition type

Тип перехода между input class и output class:

- `preserved`;
- `transformed`;
- `broken`;
- `emergent`.

## 5. Требования к архитектуре

### 5.1 Разделение слоёв

В архитектуре должны быть отдельные модули:

1. **Generator layer** — генерирует результат.
2. **Observer layer** — извлекает признаки.
3. **Morphology layer** — описывает морфологические свойства.
4. **Identity layer** — присваивает output class и оценивает родство.
5. **Metrics layer** — считает similarity, separability, retrieval, transition rates.
6. **Reporting layer** — формирует итоговые таблицы и отчёты.

### 5.2 Версионирование

Каждый слой обязан иметь версию:

- `generator_version`;
- `observer_version`;
- `feature_schema_version`;
- `identity_schema_version`;
- `distance_metric_version`;
- `bifurcation_detector_version`.

Если версия меняется, эксперимент должен считаться новым benchmark-прогоном.

### 5.3 Заморозка критических компонентов

Для benchmark v4 должны быть зафиксированы:

- observer;
- feature schema;
- normalization scheme;
- distance metric;
- output class rules;
- transition taxonomy.

## 6. Структура классов

### 6.1 Input registry

Нужно создать и поддерживать `input_registry.yaml` или `input_registry.json`. В нём для каждого input class указываются:

- `class_name`;
- `parent_family`;
- `description`;
- `base_vector`;
- `allowed_deformations`;
- `perturbation_scales`;
- `n_instances`;
- `generator_compatibility`;
- `priority`.

### 6.2 Output taxonomy

Выходные классы должны быть структурированы по иерархии:

- `preserved_*` — структура сохранена;
- `transformed_*` — структура стала родственной, но не тождественной;
- `broken_*` — структура разрушена;
- `emergent_*` — возник новый устойчивый паттерн.

### 6.3 Пример разбиения

Для класса `harmonic_symmetric`:

- `preserved_harmonic_symmetric`;
- `slightly_deformed_harmonic_symmetric`;
- `broken_harmonic_symmetric`.

Для класса `asymmetry_transition`:

- `preserved_asymmetry_transition`;
- `shifted_asymmetry_transition`;
- `collapsed_asymmetry_transition`.

Для класса `tense_cluster`:

- `preserved_tense_cluster`;
- `expanded_tense_cluster`;
- `fragmented_tense_cluster`.

## 7. Разделение морфологии и идентичности

### 7.1 Morphology layer

Морфология должна считать признаки, описывающие форму результата независимо от того, к какому классу он относится.

Примеры морфологических признаков:

- `symmetry_score`;
- `fractal_dim_proxy`;
- `basin_entropy`;
- `density_variation`;
- `edge_density`;
- `kurt_orbit`;
- `skew_orbit`;
- `std_orbit`;
- `std_visit`;
- `entropy_orbit`;
- `entropy_visit`.

### 7.2 Identity layer

Identity layer должен работать поверх морфологии и отвечать на вопрос:

- к какому output class относится результат;
- сохранился ли input class;
- произошёл ли переход;
- разрушена ли идентичность;
- появился ли новый класс.

### 7.3 Правило разделения

Нельзя использовать одни и те же признаки и одну и ту же логику одновременно как для морфологии, так и для identity без отдельного слоя интерпретации.

### 7.4 Выход identity layer

Identity layer должен возвращать:

- `input_class`;
- `output_class`;
- `transition_type`;
- `family_relation`;
- `identity_confidence`;
- `identity_breakage_score`.

## 8. Features schema

### 8.1 Общие признаки

Общие признаки используются для всех генераторов:

- `symmetry_score`;
- `fractal_dim_proxy`;
- `basin_entropy`;
- `density_variation`;
- `edge_density`;
- `entropy_orbit`;
- `entropy_visit`;
- `kurt_orbit`;
- `skew_orbit`;
- `std_orbit`;
- `std_visit`.

### 8.2 Generator-specific признаки

Для отдельных генераторов нужны дополнительные признаки:

- `lyapunov_mean`;
- `lyapunov_std`;
- `stability_gradient`;
- `escape_time_mean`;
- `escape_time_std`;
- `escape_ratio`;
- `orbit_occupancy`;
- `support_area`;
- `trap_interaction_score`;
- `trap_response_mean`.

### 8.3 Ограничение

Generator-specific признаки не должны влиять на output class classification, если это нарушает сопоставимость между генераторами. Их задача — усилить морфологический анализ и помочь объяснять поведение.

## 9. Нормализация и метрики

### 9.1 Нормализация

Перед расчётом расстояний все признаки должны быть нормализованы.

Рекомендуемая схема по умолчанию:

- `robust_zscore_per_feature`.

Допустимые альтернативы:

- `zscore_per_feature`;
- `minmax_per_feature` только для отладки;
- `whitened_embedding`, если версия зафиксирована.

### 9.2 Distance metric

Для v4 нужно жёстко фиксировать distance metric. Все расчёты должны использовать одну и ту же метрику, например:

- cosine distance;
- euclidean distance;
- Mahalanobis-like distance — только если заранее зафиксированы covariance rules.

### 9.3 Обязательные метрики

Система должна считать:

- `within_class_distance`;
- `between_class_distance`;
- `separability`;
- `top1_retrieval`;
- `top3_retrieval`;
- `class_preservation_rate`;
- `class_transition_rate`;
- `class_breakage_rate`;
- `family_continuity_score`;
- `seed_sensitivity`;
- `input_perturbation_sensitivity`;
- `observer_variance`;
- `bifurcation_count`;
- `bifurcation_stability`.

### 9.4 Статистика по метрикам

Для каждой метрики считать:

- mean;
- std;
- median;
- iqr;
- min;
- max;
- n;
- bootstrap 95% CI.

## 10. Pipeline выполнения

### Шаг 1. Загрузка конфигурации

Runner загружает frozen config и проверяет версии компонентов.

### Шаг 2. Загрузка registries

Загружаются:

- input registry;
- output taxonomy;
- feature schema;
- transition rules;
- distance metric config.

### Шаг 3. Формирование матрицы прогонов

Runner строит декартово произведение:

- generator;
- input_class;
- instance_id;
- seed;
- deformation_step;
- noise profile;
- mapping mode.

### Шаг 4. Генерация

Для каждой комбинации создаётся результат.

### Шаг 5. Observer

Из результата извлекаются сырые признаки.

### Шаг 6. Morphology classification

Формируется набор морфологических признаков.

### Шаг 7. Identity classification

Определяются:

- output class;
- transition type;
- identity confidence.

### Шаг 8. Distance computation

Считаются within/between и pairwise matrix.

### Шаг 9. Bifurcation scan

Проводится поиск устойчивых скачков параметров и признаков.

### Шаг 10. Aggregation

Формируются сводные таблицы и отчёт.

## 11. Формат итоговых артефактов

### 11.1 Обязательные файлы

- `run_table.csv`;
- `features_raw.csv` или `features_raw.parquet`;
- `features_normalized.csv` или `features_normalized.parquet`;
- `aggregate_by_generator.csv`;
- `aggregate_by_class.csv`;
- `aggregate_by_transition.csv`;
- `pairwise_distance_matrix.csv`;
- `bifurcation_events.csv`;
- `failed_runs.csv`;
- `summary.json`;
- `research_report.md`.

### 11.2 Содержимое run_table

Каждая строка — один run.

Поля:

- `run_id`;
- `generator`;
- `input_class`;
- `output_class`;
- `transition_type`;
- `instance_id`;
- `seed`;
- `deformation_step`;
- `noise_level`;
- `mapping_mode`;
- `observer_version`;
- `feature_schema_version`;
- `identity_schema_version`;
- `distance_metric_version`;
- `status`;
- `metric_missing_reason`.

## 12. Output class rules

### 12.1 Rule-based classification

Если используется rule-based подход, нужно зафиксировать пороги:

- centroid distance threshold;
- family affinity threshold;
- breakage threshold;
- emergent class threshold.

### 12.2 Nearest-centroid classification

Если используется nearest-centroid, необходимо:

- обучить centroids на frozen reference set;
- сохранить centroids version;
- не обновлять centroids в основном benchmark cycle.

### 12.3 Confidence score

Для каждого output class присваивать confidence:

- `identity_confidence`;
- `transition_confidence`;
- `breakage_score`.

## 13. Bifurcation detector v4

### 13.1 Требование

Детектор должен выявлять не только резкие скачки, но и устойчивые изменения режима.

### 13.2 Алгоритм

1. Сглаживание локального окна.
2. Расчёт градиента.
3. Z-score фильтрация.
4. Проверка устойчивости на окне.
5. Запись события.

### 13.3 Формат события

- `generator`;
- `input_class`;
- `output_class`;
- `parameter_name`;
- `parameter_value`;
- `feature_name`;
- `gradient_norm`;
- `zscore`;
- `confirmed_event`.

## 14. Обработка ошибок

### 14.1 Общий принцип

Ошибки не скрываются. Если модуль не может посчитать значение, он должен явно сообщить об этом.

### 14.2 Обязательные статусы

- `success`;
- `failed`;
- `partial`;
- `skipped`.

### 14.3 Причины ошибок

Нужно фиксировать:

- `metric_missing_reason`;
- `module_name`;
- `version`;
- `input_id`;
- `failure_stage`.

### 14.4 Запрещено

- silent `nan`;
- скрытые падения;
- подмена отсутствующих данных нулями;
- неотличимые от успеха ошибки.

## 15. Отчётность

### 15.1 `summary.json`

Должен содержать:

- общее число прогонов;
- число прогонов по генераторам;
- число прогонов по классам;
- число переходов;
- итоговые метрики;
- список лучших генераторов;
- список проблемных модулей;
- список классов с лучшим preservation;
- список классов с лучшей separability.

### 15.2 `research_report.md`

Должен включать:

1. Цель benchmark v4.
2. Архитектуру pipeline.
3. Структуру классов.
4. Слой morphology.
5. Слой identity.
6. Итоговые метрики.
7. Анализ переходов.
8. Анализ бифуркаций.
9. Рекомендации по генераторам.
10. Рекомендации по следующему этапу.

## 16. Пошаговый план реализации

### Этап 1. Схемы данных

- создать input registry;
- создать output taxonomy;
- создать feature schema;
- создать transition rules.

### Этап 2. Конфигурация

- расширить frozen config;
- добавить версии компонентов;
- добавить режимы noise, deformation, mapping.

### Этап 3. Runner

- реализовать полный перебор комбинаций;
- добавить resume и skip_completed;
- записывать run_table и failed_runs.

### Этап 4. Observer и features

- сохранять raw features;
- сохранять normalized features;
- разделить common и generator-specific признаки.

### Этап 5. Morphology layer

- вычислять морфологические индексы;
- сохранять их отдельно от identity.

### Этап 6. Identity layer

- присваивать output class;
- определять transition type;
- считать confidence и breakage.

### Этап 7. Metrics layer

- within/between;
- separability;
- retrieval;
- transition rates;
- sensitivity metrics.

### Этап 8. Bifurcation detector

- улучшить критерии события;
- сохранять события в таблицу;
- привязать события к генераторам и классам.

### Этап 9. Reporting

- собрать summary;
- сформировать markdown report;
- подготовить таблицы для анализа и статьи.

## 17. Acceptance criteria

Benchmark v4 считается готовым, если:

- output classes различаются и воспроизводимы;
- morphology и identity не смешиваются;
- pairwise distance matrix заполнен;
- top1/top3 retrieval дают ненулевые результаты на sanity-check наборе;
- separability статистически интерпретируема;
- stage-2 метрики не падают в `nan` без причины;
- output taxonomy дает понятные preserved/transformed/broken переходы;
- отчёт версионирован и воспроизводим.

## 18. Приоритеты

### Критично до запуска

- registries;
- output taxonomy;
- separation of morphology and identity;
- distance matrix;
- retrieval metrics;
- versioning;
- error logging.

### Во второй очереди

- better bifurcation detection;
- generator-specific analysis;
- hi-res validation mode;
- feature importance analysis.

### После первого полного прогона

- автоматический выбор лучшего семейства;
- публикационный отчёт;
- автоматические сравнительные таблицы;
- оптимизация вычислений.

## 19. Итог

Benchmark v4 должен стать строгой исследовательской рамкой, в которой результат генерации можно не только визуально увидеть, но и формально классифицировать. Главный технический принцип v4 — разделить морфологию и идентичность так, чтобы система могла объяснить: что именно изменилось, почему изменилось и к какому классу теперь относится результат.
