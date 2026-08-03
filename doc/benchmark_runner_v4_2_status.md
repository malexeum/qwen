$ sed -n '1,260p' output/benchmark_runner_v4_2_status.md
# Финальный отчет по статусу benchmark-runner_v4_2

## 1. Общий статус и объем эксперимента

Раннер benchmark-runner_v4_2 успешно выполнен на конфигурации feature_schema_v2 и identity_schema_v2 без ошибок загрузки и без failed runs.[file:154]
Всего отработано 59 976 запусков, распределенных равномерно по семи генераторам (по 8 568 прогонов на генератор) и шести классам, с увеличенным объемом для переходных и гармонических семейств.[file:154]

## 2. Конфигурация и версии компонентов

- Источник конфигурации: yaml-fallback + manifest-generated, что зафиксировано в summary.json.[file:154]
- Версии компонентов:
  - generator_version = 3.1.0
  - observer_version = 3.2.0
  - feature_schema_version = 2.0.0
  - identity_schema_version = 2.0.0
  - distance_metric_version = 1.0.0
  - bifurcation_detector_version = 4.0.0
  Эти версии согласованы и используются последовательно по всей выборке.[file:154]
- Distance metric: euclidean.
- Нормализация признаков: robust_zscore_per_feature.[file:154]
- Feature schema v2:
  - n_morphology_features = 89; схема успешно загружена из configs/feature_schema_v2.yaml без ошибок.[file:154]
- Identity schema v2:
  - valid_run_table = true; missing_run_table_fields = [];
  - источник configs/identity_schema_v2.yaml; ошибок валидации нет.[file:154]

## 3. Структура данных и распределения по генераторам/классам

### 3.1 Распределение прогонов по генераторам

Сводка summary.json показывает равномерное распределение по генераторам:[file:154]

| Генератор                    | Число прогонов |
|------------------------------|----------------|
| julia_orbit_trap             | 8 568 |
| orbit_ifs_multi_trap         | 8 568 |
| duffing_lyapunov             | 8 568 |
| chaotic_scattering           | 8 568 |
| random_baseline              | 8 568 |
| smooth_geometric_baseline    | 8 568 |
| single_parameter_map_baseline| 8 568 |

Такой дизайн обеспечивает сопоставимость метрик по всем генераторам при фиксированном бюджете запусков.[file:154]

### 3.2 Распределение прогонов по классам

По классам нагрузка распределена неравномерно, с акцентом на переходные и гармонические семейства:[file:154]

| Класс                  | Число прогонов |
|------------------------|----------------|
| harmonic_symmetric     | 16 968 |
| harmonic_dense_irregular | 1 344 |
| periodic_ostinato      | 6 384 |
| sparse_free_texture    | 6 384 |
| tense_cluster          | 11 928 |
| asymmetry_transition   | 16 968 |

Такое распределение отражает прицельное тестирование устойчивости идентичности на наиболее сложных для классификации классах.[file:154]

### 3.3 Баланс типов переходов

По summary:
- preserved: 16 836,
- transformed: 4 997,
- broken: 38 143.
Это означает, что примерно две трети всех переходов приводят к разрыву идентичности, что соответствует целям стресс-тестирования identity-слоя.[file:154]

## 4. Ключевые метрики качества

### 4.1 Глобальные метрики

Глобальные показатели по всей выборке:[file:154]
- separability = 0.0439,
- retrieval_top1 = 0.668,
- retrieval_top3 = 0.8.
- mean_family_continuity_score = 0.1067,
- mean_class_stability_index = 0.2512,
- mean_morphology_persistence_score = 0.6316,
- mean_observer_stability_score = -0.6554.

Separability ~ 0.044 соответствует сложной задаче разделения классов в высокоразмерном пространстве, при этом retrieval-метрики показывают, что топ-1 и топ-3 выбор по ближайшему соседу остаются информативными для практического поиска похожих реализаций.[file:154]

### 4.2 Лидеры по сохранению и continuity

По summary.json лучшие генераторы по сохранению (по доле preserved) — duffing_lyapunov, single_parameter_map_baseline, chaotic_scattering, orbit_ifs_multi_trap, julia_orbit_trap.[file:154]

По агрегированному by_generator_family_continuity и class_stability_index:

| Генератор                 | family_continuity | class_stability_index |
|---------------------------|-------------------|------------------------|
| duffing_lyapunov          | 0.313             | 0.503 |
| single_parameter_map_baseline | 0.175       | 0.391 |
| smooth_geometric_baseline | 0.053             | 0.414 |
| julia_orbit_trap          | 0.095             | 0.200 |
| orbit_ifs_multi_trap      | 0.063             | 0.102 |
| chaotic_scattering        | 0.048             | 0.147 |
| random_baseline           | ~1.2e-5           | ~9.7e-5 |

Здесь duffing_lyapunov выступает как главный “физически содержательный” генератор, наиболее надёжно сохраняющий как семейство, так и метку класса.[file:154]

Лучшие по preservation классы по summary: harmonic_dense_irregular, tense_cluster, harmonic_symmetric, periodic_ostinato, asymmetry_transition.[file:154]

## 5. Итоговые таблицы по парам генератор–класс

### 5.1 Лучшие preserved-пары

Файл table_best_preserved_pairs.csv фиксирует пары с максимальным preserved_rate и дополнительными метриками continuity и stability.[file:156]

Ключевые наблюдения:
- single_parameter_map_baseline → periodic_ostinato: preserved_rate = 1.0, broken_rate = 0.0, family_continuity_score ≈ 0.343, class_stability_index ≈ 0.590.[file:156]
- duffing_lyapunov → tense_cluster: preserved_rate ≈ 0.985, broken_rate ≈ 0.015, family_continuity_score ≈ 0.397, morphology_persistence ≈ 0.702, observer_stability ≈ 0.615, class_stability_index ≈ 0.560.[file:156]
- single_parameter_map_baseline → harmonic_symmetric: preserved_rate ≈ 0.805, class_stability_index ≈ 0.635, family_continuity ≈ 0.346.[file:156]

Эти пары являются эталонными примерами сохранения для разных типов классов и используются как ориентиры при дальнейшей настройке раннера и схем идентичности.[file:156]

### 5.2 Лучшие пары по family continuity

Файл table_best_family_continuity_pairs.csv ранжирует пары по family_continuity_score.[file:157]

Здесь повторно подтверждается лидерство:
- duffing_lyapunov → tense_cluster (0.397),
- duffing_lyapunov → harmonic_symmetric (0.384),
- single_parameter_map_baseline → harmonic_symmetric (0.346),
- single_parameter_map_baseline → periodic_ostinato (0.343).[file:157]

Также в верхней части списка появляются пары с умеренным preserved-rate, но высокой continuity и morphology persistence, например julia_orbit_trap → harmonic_dense_irregular.[file:157]

### 5.3 Наиболее сломанные пары

Файл table_most_broken_pairs.csv описывает пары с максимальным broken_rate и высокими identity_breakage_score.[file:158]

Основные выводы:
- random_baseline даёт broken_rate = 1.0 для всех классов при почти нулевых continuity и stability и сильно отрицательном observer_stability (около -4.91), выступая чистым отрицательным контролем.[file:158]
- single_parameter_map_baseline → asymmetry_transition: broken_rate = 1.0 при относительно мягких morphology_persistence и observer_stability, что показывает селективную неспособность baseline удерживать переходное семейство.[file:158]
- smooth_geometric_baseline по ряду классов (tense_cluster, asymmetry_transition, sparse_free_texture, harmonic_symmetric, periodic_ostinato) демонстрирует broken_rate ≈ 0.95–1.0 при очень высокой morphology_persistence (~0.82) и положительном observer_stability (~0.93), то есть создаёт устойчивую, но чужую морфологию.[file:158]

## 6. Статус кода benchmark-runner_v4_2.py

По текущим данным, раннер:
- Корректно читает и применяет feature_schema_v2 и identity_schema_v2.[file:154]
- Генерирует полную матрицу запусков по генераторам и классам, с ожидаемыми объемами прогонов по summary.[file:154]
- Сохраняет run-таблицу в формате, валидным для identity_schema_v2 (valid_run_table = true, отсутствуют missing_run_table_fields).[file:154]
- Отдельные диагностические таблицы по парам generator–class (best preserved, best family continuity, most broken) формируются корректно, без пропущенных классов и без NaN в основных метриках.[file:155][file:156][file:157][file:158]

Внесенные изменения по ходу работы (с точки зрения архитектуры):
- Уточнена логика построения job matrix, включая явную обработку отсутствующих классов и неполных offsets при генерации экземпляров классов.
- Обеспечено использование deformation_steps и sensitivity_steps в зависимости от типа эксперимента (family_deformation, sensitivity), что позволяет согласованно управлять глубиной деформаций по конфигу.
- Уточнена привязка deformation_amplitude к генератору через mode/конфиг так, чтобы family_deformation была действительно generator-specific, а не глобально одинаковой.

Эти изменения направлены на повышение устойчивости раннера к кривым конфигам и на более физически содержательную интерпретацию family_deformation и sensitivity.

## 7. Риски и ограничения

- Средняя separability ~0.044 говорит о том, что классы частично пересекаются в признаковом пространстве, и любая архитектура, использующая этот раннер, должна учитывать, что identity-слой работает в режиме “сложной геометрии”, а не тривиальных кластеров.[file:154]
- Большая доля broken-переходов (38 143 из 59 976) означает, что большинство генераторов в стрессовом режиме нарушают идентичность; это хорошо для тестов, но требует осторожности при использовании этих же конфигов в продуктивных режимах визуализации.[file:154]
- Пары с высоким morphology_persistence и высоким identity_breakage (smooth_geometric_baseline по ряду классов) демонстрируют, что визуальная похожесть может вводить в заблуждение без опоры на identity-метрики, и архитектура должна явно разводить морфологическую и классовую идентичность.[file:155][file:158]

## 8. Рекомендации архитектору проекта

1. Зафиксировать текущие версии схем и раннера benchmark-runner_v4_2 как стабильную базу для следующей итерации архитектуры, с явным указанием component_versions и источников YAML-конфигов.[file:154]
2. Использовать duffing_lyapunov и single_parameter_map_baseline в качестве основных генераторов для эталонного тестового набора, а random_baseline и smooth_geometric_baseline — как стандартные стресс-тесты для identity-слоя.[file:154][file:156][file:158]
3. В архитектуре визуализации и отчётности выделить четыре режима: preserved, transformed, broken, а также “morphology preserved b
... (output truncated)