Техническое задание: Benchmark v4.2
1. Цель версии
Сделать следующий шаг benchmark-архитектуры:

усилить morphology layer так, чтобы классы стали лучше различаться;

сохранить и доработать identity layer с generator-specific thresholds;

измерять не только сохранение/разрушение классов, но и family continuity, sensitivity, stability gradients, а также качество separability;

устранить текущую проблему: низкая separability при высоком retrieval и высокой observer variance.

Цель v4.2 — не просто расширить масштаб, а сделать систему тоньше: чтобы она лучше отделяла близкие классы, выявляла ломкие генераторы и давала более осмысленную картину по семействам.
summary.json

2. Исходные результаты v4.1, от которых отталкиваемся
Из текущего отчёта видно следующее:

n_total_runs = 59976, n_failed_runs = 0.

top-1 retrieval = 0.758, top-3 = 0.858.

separability = 0.0196 — всё ещё низкая.

within_mean = 75.21, between_mean = 1.48.

class_preservation_rate = 0.5432.

class_breakage_rate = 0.4218.

n_bifurcations = 8818.

observer_variance = 73.7055.

лучшая сохранность у single_parameter_map_baseline, smooth_geometric_baseline, duffing_lyapunov, chaotic_scattering, julia_orbit_trap.
summary.json

Вывод: пайплайн уже работает, но сейчас требуется тонкая переработка признаков и стабилизации наблюдателя, иначе separability не вырастет достаточно.

3. Что менять в v4.2
3.1 Усилить morphology layer
Нужно заменить часть грубых признаков на более структурные и multi-scale признаки.

Требования к новому morphology layer
Добавить минимум следующие группы признаков:

multi-scale morphology: признаки на разных масштабах разрешения;

topological connectivity: связность, число компонент, устойчивость компонент;

boundary complexity: сложность границ и контуров;

basin geometry: форма и распределение бассейнов;

local curvature descriptors: локальная кривизна и изломы;

structure persistence scores: устойчивость формы при малых деформациях.

Почему это важно
Сейчас классы различаются, но не очень сильно; морфология слишком “средняя”. Поэтому separability низкая, а within-class variance высокая.
summary.json

Нужно более тонко кодировать форму, чтобы близкие классы перестали сливаться.

3.2 Стабилизировать observer layer
observer_variance слишком высокая, значит наблюдатель вносит лишний шум.

Требования
сделать observer version 3.2.0 или выше;

уменьшить чувствительность к мелким колебаниям;

зафиксировать способ нормализации;

добавить тест стабильности observer на контрольном наборе;

при необходимости ввести observer profiles per generator family.

Acceptance target
В v4.2 observer variance должна стать заметно ниже текущей, иначе смысла в усложнении morphology layer мало.
summary.json

3.3 Поднять separability
Сейчас separability ≈ 0.0196, а это мало.
Чтобы улучшить её, нужно:

пересобрать feature schema;

убрать слабые и шумные признаки;

усилить признаки, отвечающие за форму;

отдельно использовать generator-specific morphology features;

проверить, не маскируют ли baselines реальные классы.

Требование
В v4.2 separability должна стать заметно выше текущей.
Целевое значение можно уточнить после первого тестового прогона, но важен именно положительный сдвиг, а не формальный “успех по факту запуска”.

3.4 Сохранить identity layer, но сделать его более информативным
Identity layer уже работает: retrieval не нулевой, labels стабильны.
Здесь задача не ломать, а расширить.

Добавить в identity layer
family_continuity_score;

identity_confidence;

breakage_confidence;

transition_confidence;

class_stability_index.

Логика
Identity layer должен не только говорить, preserved это или broken, но и объяснять:

насколько класс удержан;

насколько он близок к родственным семействам;

насколько transition осмыслен;

насколько run близок к границе бифуркации.

4. Что проверить по генераторам
4.1 Duffing
По твоей просьбе и по данным отчёта нужно отдельно проверить duffing_lyapunov с deformation_amplitude = 0.80:

не слишком ли часто уходит в emergent / broken;

как ведут себя n_bifurcations;

как выглядит stability_gradient;

не слишком ли узок/широк порог transition.

Ожидание
Duffing должен остаться хорошим генератором перехода между мягкой трансформацией и хаосом.
Он не должен стать генератором бесконечного broken-like режима.

4.2 Julia
julia_orbit_trap надо оставить как хрупкий, но очень красивый и информативный режим.
В v4.2 важно проверить, что она не “ломается” раньше времени из-за слишком грубой шкалы признаков.

Ожидание
Она должна:

быстро показывать transformed → broken,

но не теряться в шуме observer-а.

4.3 Orbit IFS
orbit_ifs_multi_trap должен остаться лучшим carrier для устойчивого удержания формы.

Ожидание
family_continuity_score должен быть высоким;

input_perturbation_sensitivity — умеренным;

broken не должен появляться слишком рано;

форма должна хорошо держаться даже при сильной деформации.

4.4 Baselines
Нужно обязательно проверить:

random_baseline;

single_parameter_map_baseline;

smooth_geometric_baseline.

Зачем
Чтобы убедиться, что:

новые признаки не делают baseline слишком “умными”;

separability не улучшается просто за счёт артефактов;

identity layer не путает простые режимы с реально нелинейными.

5. Новые метрики v4.2
Помимо уже существующих, добавить или усилить:

family_continuity_score;

stability_gradient;

breakage_confidence;

identity_confidence;

class_stability_index;

morphology_persistence_score;

multi_scale_separability;

observer_stability_score.

Приоритет
family_continuity_score, input_perturbation_sensitivity, seed_sensitivity, within_mean / between_mean / separability остаются ключевыми для анализа.
summary.json

6. Обновление конфигурации
6.1 Версии
Обновить версии компонентов, например:

feature_schema_version = 2.0.0

identity_schema_version = 2.0.0

observer_version = 3.2.0

distance_metric_version = 1.1.0 или оставить euclidean, если метрика ещё не меняется

6.2 Threshold profiles
Сохранить generator-specific thresholds, но теперь хранить:

base profile;

override profile per generator;

calibration notes;

last validation run.

6.3 Deformation profiles
Для v4.2 надо явно фиксировать, что:

у duffing_lyapunov амплитуда может быть отдельной от остальных;

у julia_orbit_trap окно деформации короче;

у orbit_ifs_multi_trap окно длиннее.

7. Формат запуска
Режим
Добавить отдельный режим:

json

{
  "mode": "benchmark_v4_2"
}
Входные данные
все ключевые генераторы из v4.1;

расширенный набор input classes;

generator-specific thresholds;

новая feature schema;

стабилизированный observer.

Рекомендуемые input classes
Оставить и использовать:

harmonic_symmetric

harmonic_dense_irregular

periodic_ostinato

sparse_free_texture

tense_cluster

asymmetry_transition

Можно добавить ещё 1–2 класса, если они уже формализованы и не ломают структуру.

8. Выходные артефакты
Обязательные файлы
benchmark_v4_2_manifest.csv

benchmark_v4_2_summary.json

aggregate_by_generator.csv

aggregate_by_class.csv

aggregate_by_transition.csv

pairwise_distance_matrix.csv

bifurcation_events.csv

threshold_profiles.yaml

feature_schema_v2.yaml

observer_profile.yaml

research_report.md

В manifest должны быть
run_id

generator

input_class

output_class

transition_type

seed

deformation_step

raw_score

normalized_score

identity_confidence

family_continuity_score

status

threshold_profile_version

observer_version

feature_schema_version

9. Пошаговый план реализации
Шаг 1. Подготовить новую schema
Добавить multi-scale morphology признаки.

Добавить топологические признаки.

Зафиксировать feature schema v2.

Шаг 2. Стабилизировать observer
Уменьшить variance.

Протестировать на контрольных runs.

Зафиксировать observer profile.

Шаг 3. Подключить v4.2 thresholds
Использовать generator-specific thresholds.

Проверить, что classify(score, generator_profile) работает без fallback-ошибок.

Шаг 4. Запустить короткий test-run
Прогнать ключевые генераторы.

Сравнить labels с визуальным поведением.

Проверить mismatch cases.

Шаг 5. Поднять full v4.2
Расширить на все классы.

Снять агрегаты.

Проверить, выросла ли separability.

Оценить observer variance и family continuity.

10. Критерии приёмки
Этап v4.2 считается успешным, если:

separability заметно выше, чем в v4.1.

observer_variance уменьшилась.

family_continuity_score стабильно считается и полезен.

duffing_lyapunov не переходит в чрезмерный broken-like режим.

julia_orbit_trap остаётся чувствительной, но не шумовой.

orbit_ifs_multi_trap стабильно удерживает форму.

Baselines не маскируют реальные генераторы.

В отчёте нет silent NaNs и не объяснённых провалов.

11. Что не делать
Не менять всё сразу без контрольного прогона.

Не увеличивать количество генераторов раньше, чем стабилизируется morphology layer.

Не возвращать глобальные пороги вместо generator-specific.

Не смешивать baseline и non-baseline в одной логике оценки.

Не трогать identity layer так, чтобы он потерял связь с визуальной интерпретацией.

12. Итог
Benchmark v4.2 — это не расширение ради расширения.
Это следующий уровень точности: сделать морфологию богаче, observer тише, identity честнее, а separability выше.
Если v4.1 доказал, что система вообще работает, то v4.2 должен доказать, что она различает формы достаточно тонко, чтобы с ней уже можно было строить зрелый исследовательский и продуктовый pipeline.
summary.json

