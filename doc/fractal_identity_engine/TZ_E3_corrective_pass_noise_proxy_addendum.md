# Дополнение к ТЗ E3-C: контракт `noise_proxy`

> **Статус:** обязательное уточнение к `TZ_E3_corrective_pass.md`
> **Дата:** 2026-08-11
> **Приоритет:** блокирующее для пункта C2 и теста T3

---

## 1. Исправление терминологии

В E3-C входное `noise_level` было ошибочно использовано как имя перцептивной оси в formula evaluator. В текущем `BASE_PERCEPTUAL` входная ось `noise_level` отсутствует; `noise_level` является target-параметром, вычисляемым interpretation profile. Формула вида `noise_level ← noise_level` создаёт self-referential коллизию и запрещена.

`density` не является заменой шума: она описывает плотность событий/текстуры и не должна влиять на target `noise_level`.

---

## 2. Новый входной контракт

Ввести независимую перцептивную ось:

```text
feature.spectral_flatness (raw)
  → log-normalization в [0, 1]
  → BASE_PERCEPTUAL["noise_proxy"]
```

`noise_proxy` — единственный входной proxy тембрального шума для interpretation-layer.

Требования:
- Источник: E1 `spectral_flatness`; raw значение не передаётся непосредственно в formula evaluator.
- Нормировка: логарифмическая, детерминированная, с clip в `[0, 1]`.
- Реализация должна использовать уже принятую E1-политику нормировки шума либо общую функцию, а не дублировать магические константы.
- `noise_proxy` объявляется в контракте/схеме `BASE_PERCEPTUAL` как numeric axis `[0, 1]`, `source: spectral_flatness`.
- Добавление оси backward-compatible: отсутствие значения допускается только с явным нейтральным default `0.5` и warning в mapping_trace.

---

## 3. Замена C2 в ТЗ E3-C

Вместо формулы из раздела C2:

```yaml
noise_level:
  formula: "base + (noise_level - 0.5) * 0.35 + (harmony_theta_5 - 0.5) * 0.25"
```

использовать:

```yaml
noise_level:
  formula: >-
    base
    + (noise_proxy - 0.5) * 0.30
    + (harmony_theta_5 - 0.5) * 0.25
```

Семантика:
- `noise_proxy` измеряет прямую спектральную шумность;
- `harmony_theta_5` добавляет контекст тембрального хаоса;
- θ₅ не заменяет `noise_proxy`, потому что θ₅ также зависит от `texture_complexity`;
- `density` и `tension` не участвуют в target `noise_level`;
- итоговое значение централизованно клипируется в `[0, 1]`.

---

## 4. Обязательные тесты (заменяют T3)

### T3a. Proxy contract

- `noise_proxy` существует в `BASE_PERCEPTUAL`;
- `noise_proxy ∈ [0, 1]`;
- он получен из `spectral_flatness` через определённую log-normalization;
- raw `spectral_flatness` не используется в формуле `noise_level`.

### T3b. Semantic monotonicity

При фиксированных остальных axes:

```python
assert resolve(noise_proxy=0.8, theta_5=0.5).noise_level > resolve(noise_proxy=0.2, theta_5=0.5).noise_level
assert resolve(noise_proxy=0.5, theta_5=0.8).noise_level > resolve(noise_proxy=0.5, theta_5=0.2).noise_level
```

### T3c. Independence

При неизменных `noise_proxy` и `harmony_theta_5` изменение `density` или `tension` не меняет resolved `noise_level`.

### T3d. Traceability

`mapping_trace` для target `noise_level` содержит `noise_proxy`, `harmony_theta_5`, формулу, значения входов и итог до/после clip.

---

## 5. Definition of Done update

Критерий E3-C «`default.noise_level` семантически зависит от `noise_level` + `harmony_theta_5`» заменить на:

- [ ] `default.noise_level` семантически зависит от `noise_proxy` (log-нормированная E1 `spectral_flatness`) и `harmony_theta_5`;
- [ ] Формула не self-referential и не использует `density`/`tension` как proxy шума;
- [ ] T3a–T3d проходят на pinned E1 data.
