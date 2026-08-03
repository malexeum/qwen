# Отчет по двум последним тестам: preserved/broken и family continuity

## Краткое резюме
По итогам набора из 59 976 прогонов без failed runs наиболее сильным генератором по сохранению класса и семейства оказался `duffing_lyapunov`, тогда как `random_baseline` выступил как предельный отрицательный контроль с полной потерей идентичности по всем классам.[file:154] Два последних теста — анализ лучших сохраняемых/наиболее сломанных пар и анализ лучших пар по family continuity — показывают, что benchmark различает по меньшей мере три режима: реальное сохранение идентичности, морфологически гладкую, но чужую динамику, и полностью деградировавший шумовой режим.[file:156][file:157][file:158]

## Контекст и состав эксперимента
В сводке указано 59 976 запусков, равномерно распределённых по семи генераторам, по 8 568 прогонов на каждый генератор.[file:154] По классам наибольший объём пришёлся на `harmonic_symmetric` и `asymmetry_transition` — по 16 968 прогонов, тогда как `harmonic_dense_irregular` имел 1 344 прогона, что важно учитывать при сравнении устойчивости редких и массовых классов.[file:154]

Суммарно зафиксировано 16 836 переходов `preserved`, 4 997 `transformed` и 38 143 `broken`.[file:154] Средние значения по всему прогону составили: `mean_family_continuity_score = 0.1067`, `mean_class_stability_index = 0.2512`, `mean_morphology_persistence_score = 0.6316`, `mean_observer_stability_score = -0.6554`, что задаёт общий фон для интерпретации частных пар generator–class.[file:154]

## Тест 1: лучшие preserved и наиболее broken пары
Первый из двух последних тестов фактически разделяет пространство пар generator–class на полюс сохранения и полюс разрушения идентичности.[file:156][file:158] На вершине списка preserved находится `single_parameter_map_baseline → periodic_ostinato` с `preserved_rate = 1.0` при `broken_rate = 0.0`, а также `duffing_lyapunov → tense_cluster` с `preserved_rate = 0.9847` и `broken_rate = 0.0153`.[file:156]

У `duffing_lyapunov → tense_cluster` одновременно высоки `family_continuity_score = 0.3974`, `morphology_persistence_score = 0.7020`, `observer_stability_score = 0.6147` и `class_stability_index = 0.5605`, что делает эту пару наиболее физически и классификационно согласованной среди верхних результатов.[file:156][file:157] Для `single_parameter_map_baseline → periodic_ostinato` сохранение формально идеально, но `observer_stability_score = -0.0981` заметно слабее, чем у лучших пар Duffing, то есть класс удерживается, но наблюдательная устойчивость остаётся умеренной.[file:156][file:157]

Сильный второй эшелон сохранения образуют `single_parameter_map_baseline → harmonic_symmetric` с `preserved_rate = 0.8053` и `class_stability_index = 0.6348`, а также `duffing_lyapunov → harmonic_symmetric` с `preserved_rate = 0.7525`, `family_continuity_score = 0.3843` и `observer_stability_score = 0.6414`.[file:156][file:157] Это означает, что гармонически организованные классы лучше всего поддерживаются не случайными и не слишком грубыми генераторами, а динамиками с выраженной внутренней структурой.[file:155][file:156]

На противоположном полюсе `random_baseline` даёт `broken_rate = 1.0` для всех представленных классов, при почти нулевом `family_continuity_score` порядка `1e-5`, `class_stability_index` порядка `1e-4` и `observer_stability_score` около `-4.91`.[file:158] Это хороший отрицательный контроль: схема identity не путает шум с “новой семьёй”, а классифицирует его как полный разрыв идентичности.[file:158]

Особенно интересен `smooth_geometric_baseline`, который для `tense_cluster`, `asymmetry_transition`, `sparse_free_texture`, `harmonic_symmetric` и `periodic_ostinato` показывает `broken_rate` от 0.9265 до 1.0 при одновременно высоком `morphology_persistence_score` около 0.822 и положительном `observer_stability_score` около 0.93.[file:158] Это означает, что генератор создаёт устойчивую и гладкую морфологию, но она систематически принадлежит не тому классу и не той семье, то есть benchmark различает морфологическую гладкость и идентичность как разные сущности.[file:158]

Ещё один важный контраст — `single_parameter_map_baseline` одновременно идеально сохраняет `periodic_ostinato` и полностью ломает `asymmetry_transition` с `broken_rate = 1.0`.[file:156][file:158] Такой результат трудно объяснить случайностью; скорее всего, этот baseline хорошо согласован с квазипериодической структурой, но плохо переносит переходные и асимметричные семейства.[file:156][file:158]

## Тест 2: лучшие пары по family continuity
Во втором тесте ранжирование идёт по `family_continuity_score`, и здесь лидирует снова `duffing_lyapunov → tense_cluster` со значением 0.3974.[file:157] Далее идут `duffing_lyapunov → harmonic_symmetric` с 0.3843, `single_parameter_map_baseline → harmonic_symmetric` с 0.3463, `single_parameter_map_baseline → periodic_ostinato` с 0.3431 и `duffing_lyapunov → asymmetry_transition` с 0.3290.[file:157]

Это ранжирование важно тем, что оно чуть шире, чем простой preserved-rate.[file:157] Например, `julia_orbit_trap → harmonic_dense_irregular` имеет `preserved_rate = 0.6979`, но при этом `family_continuity_score = 0.3213` и `morphology_persistence_score = 0.8127`, поэтому по continuity он поднимается выше многих пар с формально сопоставимым уровнем сохранения.[file:157]

Содержательно этот тест показывает, что `duffing_lyapunov` лучше остальных удерживает не только метку класса, но и внутреннюю структуру семейства на уровне непрерывности морфологии и наблюдаемых признаков.[file:154][file:157] В агрегированной сводке это подтверждается лучшим средним `by_generator_family_continuity = 0.3128` и лучшим `by_generator_class_stability_index = 0.5031` среди всех генераторов.[file:154]

При этом `smooth_geometric_baseline` иногда попадает в верхнюю часть списка continuity не из-за высокого preserved-rate, а из-за устойчивой геометрической формы, например `smooth_geometric_baseline → harmonic_dense_irregular` имеет `family_continuity_score = 0.0990`, `morphology_persistence_score = 0.8225` и `observer_stability_score = 0.9321`, хотя `broken_rate = 0.7344`.[file:157][file:158] Это ещё раз подтверждает, что continuity и identity_breakage нельзя сводить к одной оси: морфология может быть последовательной, но семейство — уже не тем.[file:157][file:158]

## Сопоставление результатов двух тестов
Оба теста вместе показывают устойчивую иерархию генераторов.[file:154][file:156][file:157][file:158] `duffing_lyapunov` — лучший физически содержательный генератор по сохранению идентичности и continuity; `single_parameter_map_baseline` — селективно сильный, но класс-зависимый; `smooth_geometric_baseline` — морфологически аккуратный, но часто чужой; `random_baseline` — корректный нулевой контроль.[file:154][file:156][file:157][file:158]

Таблица ниже сводит ключевые интерпретации по генераторам.

| Генератор | Поведение по тестам | Интерпретация |
|---|---|---|
| `duffing_lyapunov` | Лучшие preserved и лучшие family continuity для нескольких классов.[file:156][file:157] | Наиболее согласованный генератор по сохранению семейства и класса.[file:154][file:157] |
| `single_parameter_map_baseline` | Идеален для `periodic_ostinato`, силён для гармонических классов, но полностью ломает `asymmetry_transition`.[file:156][file:158] | Селективный baseline с выраженной зависимостью от типа класса.[file:156][file:158] |
| `julia_orbit_trap` | Умеренное preserved при высокой morphology persistence, но отрицательном observer stability.[file:155][file:157] | Морфологию держит лучше, чем наблюдательную согласованность.[file:155][file:157] |
| `orbit_ifs_multi_trap` | Высокая morphology persistence, но часто слабый class stability и высокий broken-rate.[file:155][file:158] | Порождает структурно похожие, но неидентичные семейства.[file:155][file:158] |
| `smooth_geometric_baseline` | Очень высокая morphology persistence и observer stability при высоком broken-rate.[file:157][file:158] | “Гладкий чужой мир”: форма устойчива, идентичность — нет.[file:158] |
| `random_baseline` | Везде `broken_rate = 1.0`.[file:158] | Чистый отрицательный контроль, подтверждающий работоспособность критерия разрыва идентичности.[file:158] |

## Основной научный результат
Главный вывод двух последних тестов состоит в том, что система метрик не сваливает все случаи в одну грубую шкалу “похоже/не похоже”, а различает по меньшей мере три режима: сохранение идентичности, трансформацию при частичной continuity и полный breakage.[file:154][file:156][file:157][file:158] Особенно убедительно это видно на различии между `random_baseline` и `smooth_geometric_baseline`: оба часто не сохраняют класс, но первый ведёт к тотальному шумовому разрыву, а второй — к морфологически устойчивой, но чужой конфигурации.[file:158]

Для последующего развития benchmark наиболее перспективны пары `duffing_lyapunov → tense_cluster`, `duffing_lyapunov → harmonic_symmetric`, `single_parameter_map_baseline → periodic_ostinato` и `julia_orbit_trap → harmonic_dense_irregular`, потому что они задают полезные эталоны сохранения на разных типах структур.[file:156][file:157] В качестве стресс-тестов логично оставить `random_baseline` по всем классам, `single_parameter_map_baseline → asymmetry_transition` и набор `smooth_geometric_baseline` по основным классам, поскольку именно они лучше всего проявляют чувствительность identity-слоя к ложной морфологической похожести.[file:158]

## Рекомендации по следующему шагу
Для публикационного или инженерного продолжения стоит добавить визуальный отчёт по representative run-level примерам из четырёх корзин: `preserved`, `transformed`, `broken`, а также “morphology preserved but identity broken”.[file:154][file:158] Кроме того, полезно вывести отдельные scatter-диаграммы `family_continuity_score` против `identity_breakage_score` и `morphology_persistence_score` против `observer_stability_score`, чтобы разделение режимов стало видно не только в таблицах, но и в геометрии облаков точек.[file:154][file:155]
