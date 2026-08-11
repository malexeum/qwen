"""
CB-3.1-A0/A1 diagnostic tests: config path independence + formula roundtrip.

Цели:
  1. CWD-independence: config dirs не зависят от рабочей директории pytest.
  2. Formula roundtrip: YAML-файл → parsed dict → resolved rule → trace.formula
     должны быть одной и той же строкой для каждого θ-driven параметра.
  3. Canonical theta axes: каждая formula содержит задекларированные θ-оси.
  4. noise_proxy tri-state: три состояния входа дают ожидаемые значения.

Diagnostic output при падении выводит:
  loaded_yaml_path, profile_slug, parsed_formula,
  resolved_rule_formula, trace_formula, source_axes

Запуск:
  pytest tests/test_cb31_config_paths.py -v
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Optional

import pytest
import yaml

from lib.style_engine.config_loader import (
    INTERPRETATION_PROFILES_DIR,
    STYLE_PROFILES_DIR,
    load_interpretation_profiles,
)
from lib.style_engine.engine import resolve_render_params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_ws(s: str) -> str:
    """Схлопывает любые пробельные последовательности в один пробел."""
    return " ".join(s.split())


_DEFAULT_PRESET = {
    "id": "neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}


def _neutral_perceptual(**overrides) -> dict:
    base = {
        "energy": 0.5, "tension": 0.5, "density": 0.5,
        "brightness": 0.5, "stability": 0.5, "smoothness": 0.5,
        "repetition": 0.5, "section_complexity": 0.5,
        "noise_proxy": 0.5, "macro_shape_hint": "unknown",
        "harmony_theta_0": 0.5, "harmony_theta_1": 0.5,
        "harmony_theta_2": 0.5, "harmony_theta_3": 0.5,
        "harmony_theta_4": 0.5, "harmony_theta_5": 0.5,
        "harmony_theta_6": 0.5, "harmony_theta_7": 0.5,
    }
    base.update(overrides)
    return base


def _resolve(perceptual: dict) -> object:
    rp, _, _ = resolve_render_params(
        project_id="diag",
        analysis_id="roundtrip",
        perceptual=perceptual,
        style_profile_slug="default",
        interpretation_profile_slug="default",
        user_preset=_DEFAULT_PRESET,
        strict_theta=True,
    )
    return rp


def _trace_perceptual(rp, param: str):
    return next(
        (e for e in rp.mapping_trace if e.param == param and e.stage == "perceptual"),
        None,
    )


# ---------------------------------------------------------------------------
# 1. CWD-independence
# ---------------------------------------------------------------------------

class TestConfigPathIndependence:
    """
    Проверяем что config dirs — абсолютные пути, не зависящие от CWD.
    """

    def test_interpretation_profiles_dir_is_absolute(self):
        assert INTERPRETATION_PROFILES_DIR.is_absolute(), (
            f"INTERPRETATION_PROFILES_DIR is not absolute: {INTERPRETATION_PROFILES_DIR}"
        )

    def test_style_profiles_dir_is_absolute(self):
        assert STYLE_PROFILES_DIR.is_absolute(), (
            f"STYLE_PROFILES_DIR is not absolute: {STYLE_PROFILES_DIR}"
        )

    def test_dirs_point_inside_lib_style_engine(self):
        # Canonical location: lib/style_engine/configs/
        expected_fragment = Path("lib") / "style_engine" / "configs"
        assert expected_fragment.parts[-3:] == ("lib", "style_engine", "configs"), \
            "test precondition"
        for part in INTERPRETATION_PROFILES_DIR.parts:
            _ = part  # just iterate
        # Check that 'lib/style_engine/configs' appears in the path
        interp_str = str(INTERPRETATION_PROFILES_DIR).replace("\\", "/")
        assert "lib/style_engine/configs" in interp_str, (
            f"INTERPRETATION_PROFILES_DIR does not point inside lib/style_engine/configs/:\n"
            f"  got: {INTERPRETATION_PROFILES_DIR}"
        )

    def test_profiles_load_regardless_of_cwd(self, tmp_path, monkeypatch):
        """
        При смене CWD на пустую tmp_path профиль 'default' всё равно загружается.
        """
        monkeypatch.chdir(tmp_path)
        profiles = load_interpretation_profiles()
        assert "default" in profiles, (
            f"Profile 'default' not found after chdir to {tmp_path}.\n"
            f"INTERPRETATION_PROFILES_DIR = {INTERPRETATION_PROFILES_DIR}\n"
            f"Loaded slugs: {list(profiles.keys())}"
        )

    def test_loaded_path_is_canonical_not_root_configs(self, tmp_path, monkeypatch):
        """
        Убеждаемся что загружается lib/style_engine/configs/, а не корневой configs/.
        Если в корневом configs/ была старая формула без θ₀ — этот тест её поймает.
        """
        monkeypatch.chdir(tmp_path)
        profiles = load_interpretation_profiles()
        default = profiles["default"]
        src = getattr(default, "_source_path", "") or ""
        src_normalized = src.replace("\\", "/")
        assert "lib/style_engine/configs" in src_normalized, (
            f"default profile loaded from wrong location:\n"
            f"  _source_path = {src}\n"
            f"  Expected path to contain 'lib/style_engine/configs'"
        )


# ---------------------------------------------------------------------------
# 2. Formula roundtrip
# ---------------------------------------------------------------------------

# Канонические ожидаемые θ-оси для каждого параметра (source of truth)
THETA_CONTRACT = {
    "symmetry_bias":      ["harmony_theta_0", "harmony_theta_7"],
    "recursion_depth":    ["harmony_theta_2"],
    "density_level":      ["harmony_theta_3"],
    "noise_level":        ["harmony_theta_5"],
    "motion_intensity":   ["harmony_theta_6"],
    "texture_complexity": ["harmony_theta_2", "harmony_theta_5"],
}


class TestFormulaRoundtrip:
    """
    Для каждого θ-driven параметра:
      parsed YAML formula == resolved rule formula == trace.formula
    """

    @pytest.fixture(scope="class")
    def yaml_data(self):
        yaml_path = INTERPRETATION_PROFILES_DIR / "default.yaml"
        assert yaml_path.exists(), f"default.yaml not found at {yaml_path}"
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data, str(yaml_path)

    @pytest.fixture(scope="class")
    def resolved_profile(self):
        profiles = load_interpretation_profiles()
        return profiles["default"]

    @pytest.fixture(scope="class")
    def resolved_rp(self):
        return _resolve(_neutral_perceptual())

    @pytest.mark.parametrize("param", list(THETA_CONTRACT.keys()))
    def test_formula_consistent_across_layers(self, param, yaml_data, resolved_profile, resolved_rp):
        data, yaml_path = yaml_data
        sha256 = hashlib.sha256(Path(yaml_path).read_bytes()).hexdigest()[:16]

        # Layer 1: raw YAML
        parsed_formula_raw = data.get("mapping_rules", {}).get(param, {}).get("formula", "")
        parsed_formula = _normalize_ws(str(parsed_formula_raw or ""))

        # Layer 2: resolved InterpretationProfile.mapping_rules
        rule = resolved_profile.mapping_rules.get(param, {})
        rule_formula = _normalize_ws(str(rule.get("formula", "") if isinstance(rule, dict) else ""))

        # Layer 3: MappingTraceEntry.formula
        entry = _trace_perceptual(resolved_rp, param)
        trace_formula = _normalize_ws(str(entry.formula or "")) if entry else ""

        diagnostic = (
            f"\n--- roundtrip diagnostic: param='{param}' ---\n"
            f"  loaded_yaml_path : {yaml_path}\n"
            f"  config_file_sha256: {sha256}\n"
            f"  profile_slug     : default\n"
            f"  parsed_formula   : {parsed_formula!r}\n"
            f"  rule_formula     : {rule_formula!r}\n"
            f"  trace_formula    : {trace_formula!r}\n"
            f"  source_axes      : {entry.source_axes if entry else 'NO ENTRY'}\n"
            f"  expected_theta   : {THETA_CONTRACT[param]}\n"
        )

        # Все три слоя должны быть одинаковы (после normalize_ws)
        assert parsed_formula == rule_formula, (
            f"YAML formula ≠ resolved rule formula for '{param}'" + diagnostic
        )
        assert rule_formula == trace_formula, (
            f"Resolved rule formula ≠ trace formula for '{param}'" + diagnostic
        )

    @pytest.mark.parametrize("param,expected_axes", list(THETA_CONTRACT.items()))
    def test_formula_contains_canonical_theta_axes(self, param, expected_axes, yaml_data):
        data, yaml_path = yaml_data
        formula = str(
            data.get("mapping_rules", {}).get(param, {}).get("formula", "") or ""
        )
        for ax in expected_axes:
            assert ax in formula, (
                f"Canonical theta axis '{ax}' not found in formula for '{param}'.\n"
                f"  yaml_path : {yaml_path}\n"
                f"  formula   : {formula!r}"
            )

    def test_symmetry_bias_formula_has_theta0_not_only_theta7(self, yaml_data):
        """Ключевая регрессия: старый root configs/ имел только θ₇, без θ₀."""
        data, yaml_path = yaml_data
        formula = str(
            data.get("mapping_rules", {}).get("symmetry_bias", {}).get("formula", "") or ""
        )
        assert "harmony_theta_0" in formula, (
            f"harmony_theta_0 MISSING from symmetry_bias formula — "
            f"loading old root configs/?\n"
            f"  yaml_path: {yaml_path}\n"
            f"  formula  : {formula!r}"
        )
        assert "harmony_theta_7" in formula, (
            f"harmony_theta_7 missing from symmetry_bias formula.\n"
            f"  yaml_path: {yaml_path}\n"
            f"  formula  : {formula!r}"
        )

    def test_noise_level_base_is_0_5(self, yaml_data):
        """Регрессия: старый root configs/ имел base: 0.25 для noise_level."""
        data, yaml_path = yaml_data
        rule = data.get("mapping_rules", {}).get("noise_level", {})
        base_val = float(rule.get("base", -1))
        assert math.isclose(base_val, 0.5, abs_tol=1e-9), (
            f"noise_level base expected 0.5, got {base_val} — "
            f"loading old root configs/?\n"
            f"  yaml_path: {yaml_path}"
        )

    def test_texture_complexity_has_theta2_theta5_not_theta6(self, yaml_data):
        """Регрессия: старый root configs/ имел θ₆ в texture_complexity вместо θ₂+θ₅."""
        data, yaml_path = yaml_data
        formula = str(
            data.get("mapping_rules", {}).get("texture_complexity", {}).get("formula", "") or ""
        )
        assert "harmony_theta_2" in formula, (
            f"harmony_theta_2 missing from texture_complexity formula.\n"
            f"  yaml_path: {yaml_path}\n  formula: {formula!r}"
        )
        assert "harmony_theta_5" in formula, (
            f"harmony_theta_5 missing from texture_complexity formula.\n"
            f"  yaml_path: {yaml_path}\n  formula: {formula!r}"
        )
        assert "harmony_theta_6" not in formula, (
            f"harmony_theta_6 FOUND in texture_complexity formula — θ₆ ∉ texture_complexity.\n"
            f"  yaml_path: {yaml_path}\n  formula: {formula!r}"
        )


# ---------------------------------------------------------------------------
# 3. noise_proxy tri-state
# ---------------------------------------------------------------------------

class TestNoiseTuningTriState:
    """
    Три состояния входа noise_proxy:
      explicit 0.5  → noise_level == base (нейтраль)
      explicit 0.0  → noise_level < base (чистый тон)
      no field      → noise_level == base (нейтральный fallback)
    """

    def _noise_level_for(self, perceptual_extra: dict) -> float:
        base = _neutral_perceptual()
        base.update(perceptual_extra)
        return _resolve(base).noise_level

    def test_noise_proxy_explicit_neutral_gives_base(self):
        # noise_proxy=0.5, все θ=0.5 → formula delta = 0 → noise_level = base = 0.5
        val = self._noise_level_for({"noise_proxy": 0.5})
        assert math.isclose(val, 0.5, abs_tol=1e-5), (
            f"noise_proxy=0.5 expected noise_level≈0.5, got {val}"
        )

    def test_noise_proxy_zero_gives_below_base(self):
        # noise_proxy=0.0 → (0.0-0.5)*0.30 = -0.15 → raw=0.35 → clamped=0.35
        val = self._noise_level_for({"noise_proxy": 0.0})
        assert val < 0.5, (
            f"noise_proxy=0.0 expected noise_level < 0.5, got {val}"
        )
        assert math.isclose(val, 0.35, abs_tol=0.01), (
            f"noise_proxy=0.0 expected noise_level≈0.35, got {val}"
        )

    def test_no_noise_field_gives_neutral_fallback(self):
        # Убираем noise_proxy и spectral_flatness → fallback 0.5
        perc = _neutral_perceptual()
        perc.pop("noise_proxy", None)
        perc.pop("spectral_flatness", None)
        rp = _resolve(perc)
        assert math.isclose(rp.noise_level, 0.5, abs_tol=1e-5), (
            f"Missing noise fields: expected noise_level≈0.5 (neutral fallback), got {rp.noise_level}"
        )

    def test_spectral_flatness_zero_gives_low_noise(self):
        # spectral_flatness=0.0 (чистый тон) → _log_normalize(0) ≈ 0.0 → < base
        perc = _neutral_perceptual()
        perc.pop("noise_proxy", None)  # убрать noise_proxy чтобы sf взял приоритет
        perc["spectral_flatness"] = 0.0
        rp = _resolve(perc)
        assert rp.noise_level < 0.5, (
            f"spectral_flatness=0.0 expected noise_level < 0.5, got {rp.noise_level}"
        )
