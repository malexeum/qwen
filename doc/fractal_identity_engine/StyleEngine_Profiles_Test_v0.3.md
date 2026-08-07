
# StyleEngine Profiles Test v0.3

## Краткое резюме

Проведён интеграционный тест Style Engine на наборе треков, покрывающих музыкальные профили `jazz`, `blues`, `rock`, `ambient`, `electronic`, `soundtrack` и `mixed`.

Система корректно резолвит музыкальные стили в визуальные профили (`style_profile_slug`), выбирает соответствующие палитры (`palette_id`) и даёт осмысленные различия в параметрах `RenderParams` для разных стилей.

## Набор треков и стили

В тест вошли следующие треки и профили:

| file                          | expected_music_profile | suggested_music_style | style_profile_slug |
|-------------------------------|------------------------|-----------------------|--------------------|
| 03 - 99 Miles from LA.mp3     | jazz                   | jazz                  | blues_jazz         |
| 04 - Autumn Leaves.mp3        | jazz                   | blues                 | blues_jazz         |
| Action_Movie.mp3              | electronic             | electronic            | electronic         |
| Front_Porch_Blues.mp3         | blues                  | blues                 | blues_jazz         |
| Man From Mars.mp3             | mixed                  | mixed                 | default            |
| Rock.mp3                      | rock                   | rock                  | rock               |
| Space.mp3                     | ambient                | ambient               | ambient            |
| Tom Waits New Year's Eve.mp3  | blues_jazz             | ambient               | ambient            |
| caravan - Ella.mp3            | soundtrack             | soundtrack            | soundtrack         |

Все треки дали `status_analyze = success` и `status_style = success`, `macro_shape_match = True`, а `render_params_warnings` остался пустым.

## Палитры и визуальные профили

Style Engine выбирает палитру в зависимости от StyleProfile и яркости трека:

- `blues_jazz` → `sepia_dark` (джаз/блюзовая тёплая палитра).
- `electronic` → `neon_dark` (электронный, контрастный профиль).
- `rock` → `ember_dark` (огненная, насыщенная палитра для рок-сцен).
- `ambient` → `abyss_dark` (глубокий, спокойный ambient).
- `soundtrack` → `aurora_dark` (кино/оркестровая палитра).
- `default` → `default_dark` (fallback для mixed-профиля).

## Поведение RenderParams по стилям

### Ambient / Space

Для ambient-профиля (`Space.mp3`, `Tom Waits New Year's Eve`):

- высокая `symmetry_bias` (≈ 0.67–0.86) и низкая `motion_intensity` (≈ 0.13–0.02),
- низкий `noise_level` (≈ 0.20–0.11) и умеренная `density_level` (≈ 0.38–0.36),
- средняя `texture_complexity` (≈ 0.41).

Это даёт визуальный образ тихой, симметричной, малошумной ambient-сцены.

### Rock

Для rock-профиля (`Rock.mp3`):

- `density_level ≈ 0.75`, `motion_intensity ≈ 0.48`,
- `texture_complexity ≈ 0.72`,
- умеренная `symmetry_bias ≈ 0.55` и средний `noise_level ≈ 0.33`.

Профиль отражает плотную, динамичную, текстурно богатую сцену, но не полностью хаотичную.

### Electronic

Для electronic-профиля (`Action_Movie.mp3`):

- `density_level ≈ 0.83`, `motion_intensity ≈ 0.69`,
- повышенный `noise_level ≈ 0.51`,
- высокая `texture_complexity ≈ 0.88`.

Это соответствует перегруженной, энергичной сцене для экшен-электро трека.

### Blues / Jazz

Для blues/jazz-профиля (`99 Miles from LA`, `Autumn Leaves`, `Front_Porch_Blues`):

- `density_level ≈ 0.54–0.55`,
- умеренный `noise_level ≈ 0.29–0.40`,
- `motion_intensity ≈ 0.23–0.28`,
- `texture_complexity ≈ 0.56–0.57`,
- `symmetry_bias` ниже, чем у ambient, но выше, чем у самых нервных сцен.

Профиль даёт органическую, умеренно плотную сцену, без чрезмерного шума.

### Soundtrack

Для soundtrack-профиля (`caravan - Ella`):

- `symmetry_bias ≈ 0.69`, `recursion_depth ≈ 0.56`,
- `density_level ≈ 0.65`,
- низкий `noise_level ≈ 0.23`,
- высокая `texture_complexity ≈ 0.82`.

Это похоже на оркестровую/кино сцену: сложную, но без грязи.

### Default / Mixed

Для default-профиля (`Man From Mars`):

- значения большинства параметров находятся в среднем диапазоне,
- `symmetry_bias ≈ 0.57`, `density_level ≈ 0.59`, `noise_level ≈ 0.46`, `motion_intensity ≈ 0.32`, `texture_complexity ≈ 0.62`.

Такой профиль используется как mid-level fallback для смешанных или нераспознанных стилей.

## Выводы

1. Маппинг `suggested_music_style -> style_profile_slug` работает: для каждого музыкального стиля используется свой StyleProfile (`rock`, `blues_jazz`, `ambient`, `electronic`, `soundtrack`, `default`).
2. Палитры (`palette_id`) и численные параметры `RenderParams` различаются между профилями и соответствуют ожиданиям по эстетике стиля.
3. Пайплайн `analyze -> resolve-style` стабилен: нет ошибок, все джобы `success`, предупреждения не генерируются.

Тест подтверждает, что этап подключения стилевых профилей и перцептивного резолвера завершён и система готова к следующей стадии — rule-driven style engine и визуальному генератору.
