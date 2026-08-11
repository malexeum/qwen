"""test13_e3_corrective.py — E3-C corrective tests T1–T7

T1  noise_proxy_independence   — noise_proxy ≠ density; log-norm spectral_flatness ≠ density
T2  log_normalize              — _log_normalize: монотонность, граничные случаи, масштаб
T3  morphology_guard           — _compute_morphology_guard: формула весов
T4  palette_derivation         — _derive_palette_id: brightness thresholds
T5  dangling_alias_guard       — _normalize_style_slug: dangling alias → ValueError
T6  validate_mapping_source    — _validate_mapping_source: strict mode
T7  theta_hash                 — _compute_theta_hash: детерминизм, чувствительность, длина

Запуск:
    python -m pytest test13_e3_corrective.py -v
"""

from __future__ import annotations

import pytest

from lib.style_engine.engine import (
    THETA_AXES,
    _THETA_DEFAULT,
    _clamp01,
    _compute_morphology_guard,
    _compute_theta_hash,
    _compute_variation_seed,
    _derive_palette_id,
    _extract_theta_axes,
    _log_normalize,
    _prepare_noise_proxy,
    _validate_mapping_source,
    _normalize_style_slug,
)
from lib.style_engine.config_loader import load_style_profiles


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BASE_PERCEPTUAL: dict = {
    "energy": 0.6,
    "tension": 0.4,
    "density": 0.5,
    "brightness": 0.5,
    "stability": 0.5,
    "smoothness": 0.4,
    "repetition": 0.3,
    "section_complexity": 0.5,
    "macro_shape_hint": "ABA_like",
    "silence_rate": 0.1,
    "tempo": 0.5,
    "spectral_flatness": 0.025,
    "high_frequency_energy": 0.3,
    "harmonic_stability": 0.6,
    "harmonic_change_rate": 0.3,
}


# ===========================================================================
# T1 — noise_proxy vs density (физическая независимость)
# ===========================================================================

class TestT1NoiseProxyIndependence:
    """T1: noise_proxy и density — независимые физические оси.

    E3-C контракт:
      - noise_proxy: log-нормированная spectral_flatness (тембральный шум)
      - density: плотность событий/текстуры (из perceptual["density"])
      Формула noise_level НЕ должна смешивать их при тождественных значениях.
    """

    def test_noise_proxy_from_spectral_flatness(self):
        """_prepare_noise_proxy использует spectral_flatness, не density."""
        p = dict(BASE_PERCEPTUAL)
        p["spectral_flatness"] = 0.025
        p["density"] = 0.0   # density = 0, не должно влиять на noise_proxy
        result = _prepare_noise_proxy(p)
        # При sf=0.025 результат должен быть > 0 (log_normalize не нулевой)
        assert result > 0.0, (
            f"noise_proxy should be >0 for spectral_flatness=0.025, got {result}"
        )

    def test_noise_proxy_ignores_density(self):
        """Одинаковый spectral_flatness → одинаковый noise_proxy независимо от density."""
        sf = 0.025
        p_low  = {**BASE_PERCEPTUAL, "spectral_flatness": sf, "density": 0.0}
        p_high = {**BASE_PERCEPTUAL, "spectral_flatness": sf, "density": 1.0}
        r_low  = _prepare_noise_proxy(p_low)
        r_high = _prepare_noise_proxy(p_high)
        assert r_low == pytest.approx(r_high), (
            f"noise_proxy must not depend on density: {r_low} != {r_high}"
        )

    def test_noise_proxy_explicit_field_takes_priority(self):
        """Если noise_proxy уже задан upstream, он имеет приоритет над spectral_flatness."""
        p = {**BASE_PERCEPTUAL, "noise_proxy": 0.77, "spectral_flatness": 0.001}
        result = _prepare_noise_proxy(p)
        assert result == pytest.approx(0.77, abs=1e-6), (
            f"Explicit noise_proxy=0.77 should take priority, got {result}"
        )

    def test_noise_proxy_clamped_when_explicit_out_of_range(self):
        """Явный noise_proxy > 1.0 зажимается до 1.0."""
        p = {**BASE_PERCEPTUAL, "noise_proxy": 1.5}
        result = _prepare_noise_proxy(p)
        assert result == pytest.approx(1.0)

    def test_noise_proxy_none_fallback(self):
        """Если нет ни noise_proxy, ни spectral_flatness → 0.5 (нейтральный fallback)."""
        p = {k: v for k, v in BASE_PERCEPTUAL.items()
             if k not in ("noise_proxy", "spectral_flatness")}
        result = _prepare_noise_proxy(p)
        assert result == pytest.approx(0.5), (
            f"Fallback without sf/noise_proxy should be 0.5, got {result}"
        )


# ===========================================================================
# T2 — _log_normalize
# ===========================================================================

class TestT2LogNormalize:
    """T2: _log_normalize корректно отображает spectral_flatness в [0, 1].

    spectral_flatness ∈ [0, 0.05]; scale=0.05.
    """

    def test_zero_input_near_zero(self):
        """sf=0 → результат близок к 0 (eps-защита, не NaN)."""
        result = _log_normalize(0.0)
        assert 0.0 <= result <= 0.05, (
            f"_log_normalize(0) should be near 0, got {result}"
        )

    def test_scale_max_gives_one(self):
        """sf=scale → результат = 1.0."""
        result = _log_normalize(0.05, scale=0.05)
        assert result == pytest.approx(1.0, abs=1e-6), (
            f"At sf=scale=0.05 result should be 1.0, got {result}"
        )

    def test_above_scale_clamped(self):
        """sf > scale → зажато до 1.0."""
        result = _log_normalize(0.1, scale=0.05)
        assert result == pytest.approx(1.0)

    def test_monotonic_increasing(self):
        """Увеличение sf → увеличение результата (монотонность)."""
        vals = [_log_normalize(sf) for sf in [0.001, 0.005, 0.010, 0.025, 0.050]]
        for i in range(len(vals) - 1):
            assert vals[i] < vals[i + 1], (
                f"_log_normalize not monotonic at index {i}: {vals[i]} >= {vals[i+1]}"
            )

    def test_negative_input_treated_as_zero(self):
        """Отрицательный sf трактуется как 0 (физически невозможен)."""
        result_neg = _log_normalize(-0.01)
        result_zero = _log_normalize(0.0)
        assert result_neg == pytest.approx(result_zero, abs=1e-9), (
            "Negative sf should behave same as 0"
        )

    def test_result_in_unit_range(self):
        """Результат всегда ∈ [0, 1] для любого sf ∈ [0, 1]."""
        for sf in [0.0, 0.001, 0.01, 0.025, 0.05, 0.5, 1.0]:
            result = _log_normalize(sf)
            assert 0.0 <= result <= 1.0, (
                f"_log_normalize({sf}) = {result} out of [0,1]"
            )


# ===========================================================================
# T3 — _compute_morphology_guard
# ===========================================================================

class TestT3MorphologyGuard:
    """T3: _compute_morphology_guard весовая формула.

    Formula: w1*section_complexity + w2*tension - w3*repetition - w4*stability
    w1=0.5, w2=0.4, w3=0.3, w4=0.3
    """

    def test_high_complexity_and_tension_raises_guard(self):
        """Высокая section_complexity + tension → высокий guard (> 0.5)."""
        p = {
            "section_complexity": 1.0,
            "tension": 1.0,
            "repetition": 0.0,
            "stability": 0.0,
        }
        result = _compute_morphology_guard(p)
        assert result > 0.5, f"Expected >0.5, got {result}"

    def test_high_repetition_and_stability_lowers_guard(self):
        """Высокая repetition + stability → низкий guard (< 0.5)."""
        p = {
            "section_complexity": 0.0,
            "tension": 0.0,
            "repetition": 1.0,
            "stability": 1.0,
        }
        result = _compute_morphology_guard(p)
        assert result < 0.5, f"Expected <0.5, got {result}"

    def test_neutral_inputs_near_midpoint(self):
        """Нейтральные входы (0.5 везде): формула даёт (0.5+0.4)*0.5 - (0.3+0.3)*0.5 = 0.45*0.5 = 0.15."""
        p = {
            "section_complexity": 0.5,
            "tension": 0.5,
            "repetition": 0.5,
            "stability": 0.5,
        }
        # raw = 0.5*0.5 + 0.4*0.5 - 0.3*0.5 - 0.3*0.5 = 0.25 + 0.20 - 0.15 - 0.15 = 0.15
        result = _compute_morphology_guard(p)
        assert result == pytest.approx(0.15, abs=1e-6), (
            f"Neutral inputs should give 0.15, got {result}"
        )

    def test_result_clamped_to_unit(self):
        """Результат всегда ∈ [0, 1]."""
        for sc, te, re, st in [
            (1.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 1.0),
            (0.5, 0.5, 0.5, 0.5),
        ]:
            p = {"section_complexity": sc, "tension": te,
                 "repetition": re, "stability": st}
            result = _compute_morphology_guard(p)
            assert 0.0 <= result <= 1.0, f"Out of [0,1]: {result}"

    def test_missing_fields_default_to_zero(self):
        """Отсутствующие поля → 0.0 (не KeyError)."""
        result = _compute_morphology_guard({})
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ===========================================================================
# T4 — _derive_palette_id
# ===========================================================================

class TestT4PaletteDerivation:
    """T4: _derive_palette_id корректно применяет brightness thresholds."""

    def test_brightness_above_060_gives_bright(self):
        result = _derive_palette_id("cinematic", 0.7)
        assert result == "cinematic_bright"

    def test_brightness_below_030_gives_dark(self):
        result = _derive_palette_id("cinematic", 0.2)
        assert result == "cinematic_dark"

    def test_brightness_at_threshold_060_is_not_bright(self):
        """brightness = 0.60 (не строго >0.60) → не bright."""
        result = _derive_palette_id("minimal", 0.60)
        assert not result.endswith("_bright"), (
            f"brightness=0.60 should NOT be bright, got {result!r}"
        )

    def test_brightness_at_threshold_030_is_not_dark(self):
        """brightness = 0.30 (не строго <0.30) → не dark."""
        result = _derive_palette_id("minimal", 0.30)
        assert not result.endswith("_dark"), (
            f"brightness=0.30 should NOT be dark, got {result!r}"
        )

    def test_mid_brightness_returns_base(self):
        """brightness ∈ (0.30, 0.60] → базовый palette без суффикса."""
        result = _derive_palette_id("ambient_warm", 0.45)
        assert result == "ambient_warm"

    def test_none_base_palette_fallback(self):
        """None base_palette → 'default_dark' fallback."""
        result = _derive_palette_id(None, 0.5)
        assert result == "default_dark"

    def test_empty_string_base_palette_fallback(self):
        """Пустая строка base_palette → 'default_dark' fallback."""
        result = _derive_palette_id("", 0.5)
        assert result == "default_dark"


# ===========================================================================
# T5 — dangling_alias guard
# ===========================================================================

class TestT5DanglingAliasGuard:
    """T5: _normalize_style_slug бросает ValueError для dangling alias.

    E3-C: алиас 'cinematic' был удалён (destination 'soundtrack' не существует).
    Каждый destination алиаса обязан присутствовать в реестре.
    """

    def test_valid_alias_blues_resolves(self):
        """Валидный алиас blues → blues_jazz (blues_jazz в реестре)."""
        registry = load_style_profiles()
        result = _normalize_style_slug("blues", registry)
        assert result == "blues_jazz", f"Expected 'blues_jazz', got {result!r}"

    def test_idempotent_alias_blues_jazz(self):
        """blues_jazz → blues_jazz (идемпотентный алиас)."""
        registry = load_style_profiles()
        result = _normalize_style_slug("blues_jazz", registry)
        assert result == "blues_jazz"

    def test_unknown_slug_returned_as_is(self):
        """Неизвестный slug (не алиас, не в реестре) → возвращается как есть."""
        registry = load_style_profiles()
        result = _normalize_style_slug("nonexistent_genre_xyz", registry)
        assert result == "nonexistent_genre_xyz", (
            "Unknown slug should be returned as-is; engine will raise ValueError"
        )

    def test_jazz_not_alias(self):
        """E3-C: jazz — canonical профиль, не алиас. _STYLE_ALIASES не содержит 'jazz'."""
        from lib.style_engine.engine import _STYLE_ALIASES
        assert "jazz" not in _STYLE_ALIASES, (
            "jazz must NOT be in _STYLE_ALIASES (E3-C contract: jazz is canonical)"
        )

    def test_cinematic_not_alias(self):
        """E3-C: cinematic алиас удалён (dangling → soundtrack)."""
        from lib.style_engine.engine import _STYLE_ALIASES
        assert "cinematic" not in _STYLE_ALIASES, (
            "cinematic alias was removed (dangling). Must not be in _STYLE_ALIASES."
        )

    def test_dangling_alias_raises_value_error(self):
        """Инъекция dangling alias: если destination отсутствует в реестре → ValueError."""
        from lib.style_engine import engine as eng
        import copy
        original = copy.copy(eng._STYLE_ALIASES)
        try:
            eng._STYLE_ALIASES["test_dangling"] = "nonexistent_destination_xyz"
            registry = load_style_profiles()
            with pytest.raises(ValueError, match="dangling_alias"):
                _normalize_style_slug("test_dangling", registry)
        finally:
            # Обязательное восстановление глобального состояния
            eng._STYLE_ALIASES.clear()
            eng._STYLE_ALIASES.update(original)


# ===========================================================================
# T6 — _validate_mapping_source
# ===========================================================================

class TestT6ValidateMappingSource:
    """T6: _validate_mapping_source — строгий режим, no silent-zero."""

    def test_valid_source_no_exception(self):
        """Существующий source — нет исключения."""
        axes = {"energy": 0.6, "tension": 0.4}
        _validate_mapping_source("energy", axes, "noise_level")  # не должен бросить

    def test_missing_source_raises(self):
        """Отсутствующий source → ValueError с 'unknown_mapping_source'."""
        axes = {"energy": 0.6}
        with pytest.raises(ValueError, match="unknown_mapping_source"):
            _validate_mapping_source("nonexistent_axis", axes, "noise_level")

    def test_error_message_contains_param_name(self):
        """ValueError содержит имя param (noise_level) для отладки."""
        axes = {"energy": 0.6}
        with pytest.raises(ValueError, match="noise_level"):
            _validate_mapping_source("bad_axis", axes, "noise_level")

    def test_error_message_contains_source_name(self):
        """ValueError содержит имя source для отладки."""
        axes = {"energy": 0.6}
        with pytest.raises(ValueError, match="bad_axis"):
            _validate_mapping_source("bad_axis", axes, "noise_level")

    def test_theta_axis_as_valid_source(self):
        """harmony_theta_* валидны как mapping source (E3 контракт)."""
        axes = {ax: 0.5 for ax in THETA_AXES}
        for ax in THETA_AXES:
            _validate_mapping_source(ax, axes, "texture_complexity")  # без исключений

    def test_layer_id_in_error_message(self):
        """layer_id появляется в сообщении об ошибке."""
        axes = {}
        with pytest.raises(ValueError, match="layer=my_layer"):
            _validate_mapping_source("energy", axes, "symmetry_bias", layer_id="my_layer")


# ===========================================================================
# T7 — _compute_theta_hash
# ===========================================================================

class TestT7ThetaHash:
    """T7: _compute_theta_hash — детерминизм, чувствительность к осям, формат."""

    def _make_theta(self, **overrides) -> dict:
        base = {ax: _THETA_DEFAULT for ax in THETA_AXES}
        base.update(overrides)
        return base

    def test_deterministic(self):
        """Один и тот же вектор θ всегда даёт один и тот же хэш."""
        theta = self._make_theta(harmony_theta_0=0.3, harmony_theta_7=0.8)
        h1 = _compute_theta_hash(theta)
        h2 = _compute_theta_hash(theta)
        assert h1 == h2

    def test_different_theta_different_hash(self):
        """Разные θ-векторы → разные хэши."""
        h1 = _compute_theta_hash(self._make_theta(harmony_theta_0=0.1))
        h2 = _compute_theta_hash(self._make_theta(harmony_theta_0=0.9))
        assert h1 != h2

    def test_each_axis_contributes(self):
        """Каждая ось независимо влияет на хэш."""
        base_hash = _compute_theta_hash(self._make_theta())
        for axis in THETA_AXES:
            changed_hash = _compute_theta_hash(self._make_theta(**{axis: 0.123}))
            assert changed_hash != base_hash, (
                f"Hash did not change when {axis} changed from {_THETA_DEFAULT} to 0.123"
            )

    def test_hash_is_hex_string(self):
        """Результат — hex-строка (только [0-9a-f])."""
        h = _compute_theta_hash(self._make_theta())
        assert isinstance(h, str)
        assert all(c in "0123456789abcdef" for c in h), (
            f"Hash is not hex: {h!r}"
        )

    def test_hash_length_is_16(self):
        """Длина хэша = 16 символов (SHA-256[:16] hex)."""
        h = _compute_theta_hash(self._make_theta())
        assert len(h) == 16, f"Expected length 16, got {len(h)}: {h!r}"

    def test_neutral_theta_is_stable(self):
        """Все θ=0.5 (нейтральный вектор) → одинаковый хэш при повторных вызовах."""
        neutral = {ax: 0.5 for ax in THETA_AXES}
        assert _compute_theta_hash(neutral) == _compute_theta_hash(neutral)

    def test_empty_dict_uses_defaults(self):
        """Пустой dict → все оси используют _THETA_DEFAULT → корректный хэш."""
        h = _compute_theta_hash({})
        assert isinstance(h, str) and len(h) == 16
