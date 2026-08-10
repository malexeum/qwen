Ниже ТЗ, которое можно прямо передавать программисту.

ТЗ E3: θ-driven Style Profiles v0.4
1. Цель
Сделать так, чтобы HarmonyEncoder не был лишь корректным артефактом и участником seed, а материально менял визуальную композицию: одинаковый жанр с разной гармонической, структурной и шумовой природой должен вести к разным параметрам генераторов.

E3 — не про новые ML-модели и не про рендер-оптимизацию. Это этап:

text
real AudioFeatureAdapter data
 → HarmonyEncoder θ[0..7]
 → profile mapping
 → StyleEngine RenderParams
 → различимый, детерминированный visual
2. Границы задачи
Входит в E3
Подключить harmony_theta_0..7 к параметрам генераторов в профилях.

Довести библиотеку до 7 профилей: пять текущих тестовых жанров плюс rock и pop.

Сохранить и усилить визуальную идентичность уже существующих профилей.

Ввести тесты, доказывающие, что изменение θ меняет RenderParams и не ломает детерминизм.

Увеличить profile_library_version на minor-версию: 0.3.4 → 0.4.0.

Не входит в E3
Профиль vocal/singer_songwriter.

Новые генераторы: Lorenz, reaction-diffusion, L-system, fractal flame, domain-warp Julia.

Обучаемая версия HarmonyEncoder v2.

Автоматическая классификация жанра.

Pixel-level визуальный benchmark — это E4/E5.

Почему не vocal сейчас: в E1 пока нет надёжной оси вокальности (voice_presence, vocal_to_instrumental_ratio, formant_stability). Без неё vocal-профиль будет просто стилевым label, а не следствием аудио. Его надо делать отдельно после добавления vocal-features — иначе получится красивый, но нечестный профиль.

3. Семантика θ
Ось	Имя	Смысл	Использовать для
θ₀	harmony_theta_0	Гармоническая чистота	Геометрическая ясность, центр Julia
θ₁	harmony_theta_1	Стабильность × смена гармоний	Ритм орбит, степень движения
θ₂	harmony_theta_2	Структурная плотность	Детализация IFS, число итераций
θ₃	harmony_theta_3	Неразрешённое напряжение	Duffing forcing, scattering, деформация
θ₄	harmony_theta_4	Чистый контраст секций	Масштаб контрастных слоёв
θ₅	harmony_theta_5	Тембральный хаос	Noise/IFS/diversity, но не opacity фона
θ₆	harmony_theta_6	Энтропия развития	Асимметрия, angular break, flow
θ₇	harmony_theta_7	Кристалличность	Симметрия, snowflake, устойчивые контуры
Правила маппинга
Использовать θ как модификатор, а не как единственный источник параметра: базовый характер задаёт профиль, θ индивидуализирует конкретный трек.

На один параметр — один dominant source. Не смешивать θ₀ и θ₇ в одном target без явной формулы.

В каждом профиле задействовать минимум 3 разные θ-оси, среди них хотя бы одну из θ₃, θ₅, θ₆ — иначе визуалы будут слишком стерильными.

Не использовать θ₅ для повышения прозрачности или глобальной яркости: высокий шум должен добавлять фактуру/хаос, а не делать постер белее.

Все итоговые параметры обязаны проходить диапазоны из generator_catalog.yaml; никаких silent clip без записи причины.

4. Профили v0.4.0
Существующие 5 профилей
Профиль	Визуальный тезис	Обязательные θ-маппинги
blues_jazz	Тёплая несовершенная гармония, живая текстура	θ₃ → duffing.forcing; θ₂ → ifs.n_points/map_diversity; θ₅ → colored_noise.amplitude; θ₇ → snowflake.branch_depth
ambient	Пространство, плавность, контролируемая неопределённость	θ₀ → julia.c_real; θ₃ → julia.c_imag или duffing.forcing; θ₂ → IFS density; θ₆ → orbital.angular_break
jazz	Активная гармония и контрапункт без визуального хаоса	θ₁ → orbital.flow_speed; θ₂ → IFS diversity; θ₃ → Duffing forcing; θ₇ → snowflake symmetry
classical	Иерархия, ясный центр, сдержанный контраст	θ₇ → julia.exponent_p/snowflake depth; θ₄ → контраст macro-layer; θ₃ → Duffing forcing с жёстким верхним лимитом; θ₅ не должен доминировать
electronic	Плотность, энергия, управляемая нестабильность	θ₂ → IFS density; θ₃ → chaotic_scattering velocity/steps; θ₅ → colored-noise amplitude; θ₆ → orbital flow/rotation
Новые профили
Профиль	Назначение	Визуальный язык	Обязательные генераторы
rock	Живой удар, перегруз, конфликт и ритмическая тяга	Тёмная палитра, плотные траектории, контролируемые разломы, минимум декоративной снежинки	duffing_lyapunov, chaotic_scattering_basins, orbit_ifs_multi_trap; опционально colored_noise_field
pop	Ясный припевный центр, повтор, читаемость, высокая запоминаемость	Яркий центральный мотив, чистые симметрии, периодические орбиты, минимум грязной микротекстуры	julia_orbit_trap, symmetry_snowflake, orbital_field; IFS — только как лёгкий поддерживающий слой
Маппинги новых профилей
Профиль	Target	Source	Роль
rock	duffing.forcing	θ₃	Напряжение и нелинейный импульс
rock	scattering.initial_velocity_x/y	θ₆	Развитие и направленность
rock	ifs.map_diversity	θ₂	Плотность структуры
rock	colored_noise.amplitude	θ₅	Фактура перегруза
pop	julia.c_real	θ₀	Чистота центральной формы
pop	julia.exponent_p	θ₇	Кристалличность/узнаваемый силуэт
pop	orbital.flow_speed	θ₁	Музыкальная динамика внутри стабильности
pop	snowflake.branch_depth	θ₇	Припевная симметрия
pop	orbital.angular_break	θ₆	Малая вариативность, не монотонность
5. Изменения в коде
Конфигурация
Изменить:

configs/visual_composition_profiles.yaml

configs/generator_catalog.yaml

При необходимости configs/feature_schema_v2.yaml — только описание потребления θ, без изменения E1-вычислений.

Требования:

Добавить профили rock и pop.

В каждом профиле добавить явные mapping entries из harmony_theta_0..7.

Во всех генераторах, реально использующих θ-оси, расширить supports, иначе контракт каталога и профиль разойдутся.

В метаданных профиля добавить:

text
profile_library_version: "0.4.0"
theta_mapping_version: "1.0"
Не менять формулы HarmonyEncoder, реализацию E1 и seed-policy в рамках E3.

StyleEngine
StyleEngine.resolve_render_params() должен получать harmony_theta_* через штатный mapping path.

Если профиль ссылается на неизвестную θ-ось, бросать явную validation error; запрещён fallback к 0.0.

В RenderParams или диагностическом артефакте сохранять:

text
mapping_trace:
  generator: duffing_lyapunov
  target: forcing
  source_axis: harmony_theta_3
  source_value: 0.3573
  resolved_value: <value>
Это критично: без trace отладка превращается в гадание.

6. Тесты
Создать test12.py или lib/composition/test_theta_profile_mapping.py.

Обязательные проверки
P1 — profile validation: все 7 профилей валидируются через config loader.

P2 — no silent zero: каждый θ-source из profile mapping существует и передаётся в StyleEngine.

P3 — θ responsiveness: для каждого профиля изменить одну используемую θ-ось на +0.10 с clip в [0,1]; должен измениться минимум один RenderParams.

P4 — locality: изменение θ не должно менять targets, не связанные с этой θ-осью.

P5 — determinism: одинаковые features + θ + profile дают идентичный RenderParams и variation_seed.

P6 — profile differentiation: одни и те же реальные E1/θ данные, пропущенные через rock и pop, дают разные generator stack либо минимум 3 различающихся RenderParams.

P7 — real-data smoke: прогнать пять pinned наборов из Test9 через все их соответствующие профили и сохранить mapping_trace.

P8 — range contract: все target-значения находятся в диапазонах generator catalog.

7. Definition of Done
В библиотеке ровно 7 целевых профилей: blues_jazz, ambient, jazz, classical, electronic, rock, pop.

profile_library_version = 0.4.0.

В каждом профиле подключены минимум 3 θ-оси.

Нет неописанных или неподдерживаемых harmony_theta_* источников.

Есть mapping_trace для каждой θ-driven настройки.

Новый тест профилей проходит без fallback к нулю и без range errors.

Для rock и pop подготовлены минимум по 3 reference renders на фиксированном input/seed.

Коммит содержит конфиги, тест, отчёт прогона и reference render metadata.

8. Критерий качества
У E3 нет права быть просто «ещё двумя YAML-профилями». Его результат считается годным, если можно ответить на вопрос:

Почему этот трек выглядит именно так?

Ответ должен восстанавливаться по trace: например, «высокая θ₃ усилила Duffing в rock, θ₅ увеличила фактуру, θ₆ сдвинула хаотические траектории». Тогда фрактальная идентичность перестаёт быть декоративным слоем и становится причинной моделью аудио.