"""test10.py — E2 HarmonyEncoder smoke-test.

Проверяет:
    T1. Детерминизм: encode(f) идентичен при двух вызовах
    T2. Диапазон: все θ_i ∈ [0.0, 1.0]
    T3. Хэш: theta.hash — строка из 16 hex-символов
    T4. Хэш-чувствительность: hash меняется при изменении любой оси
    T5. Интеграция с seed_policy: harmony_theta_hash влияет на base_seed
    T6. Обратная совместимость: seed без theta_hash ≠ seed с theta_hash
    T7. KeyError при отсутствующей оси
    T8. Покрытие жанров: theta различимы для 5 контрольных профилей
    T9. as_mapping_axes: возвращает корректный dict harmony_theta_0..7
    T10. HarmonyThetaArtifact схема: to_dict совместим с dataclass

Запуск:
    python test10.py
"""
from __future__ import annotations

import sys

# ─── вспомогательный механизм тестов ──────────────────────────────────────
_PASS: list[str] = []
_FAIL: list[str] = []


def ok(name: str) -> None:
    _PASS.append(name)
    print(f"  [PASS] {name}")


def fail(name: str, reason: str) -> None:
    _FAIL.append(name)
    print(f"  [FAIL] {name} — {reason}")


# ─── фикстуры ─────────────────────────────────────────────────────────────

BASE_FEATURES = {
    # 17 осей из E1 + служебные (duration_sec, style игнорируются encoder'ом)
    "energy":               0.5,
    "tension":              0.4,
    "repetition":           0.6,
    "tempo":                0.55,
    "section_complexity":   0.6,
    "silence_rate":         0.1,
    "harmonic_stability":   0.7,
    "harmonic_change_rate": 0.3,
    "spectral_flatness":    0.25,
    "high_frequency_energy": 0.45,
    "density_level":        0.5,
    "motion_intensity":     0.6,
    "texture_complexity":   0.4,
    "noise_level":          0.2,
    "symmetry_bias":        0.85,
    "layout_macro_shape":   0.05,
    "recursion_depth":      0.55,
    # служебные (encoder игнорирует)
    "duration_sec":         210.0,
    "style":                "jazz",
}

# Профили для теста T8 (имитируют реальные контрольные треки из test9)
GENRE_PROFILES = {
    "blues_jazz": {
        **BASE_FEATURES,
        "tension": 0.584, "harmonic_stability": 0.388,
        "harmonic_change_rate": 0.420, "texture_complexity": 0.55,
        "symmetry_bias": 0.82, "noise_level": 0.25,
        "section_complexity": 0.60, "recursion_depth": 0.50,
    },
    "ambient": {
        **BASE_FEATURES,
        "tension": 0.364, "harmonic_stability": 0.407,
        "harmonic_change_rate": 0.180, "texture_complexity": 0.30,
        "symmetry_bias": 0.90, "noise_level": 0.15,
        "section_complexity": 0.60, "recursion_depth": 0.35,
    },
    "jazz": {
        **BASE_FEATURES,
        "tension": 0.574, "harmonic_stability": 0.471,
        "harmonic_change_rate": 0.520, "texture_complexity": 0.65,
        "symmetry_bias": 0.88, "noise_level": 0.30,
        "section_complexity": 0.60, "recursion_depth": 0.60,
    },
    "classical": {
        **BASE_FEATURES,
        "tension": 0.326, "harmonic_stability": 0.261,
        "harmonic_change_rate": 0.280, "texture_complexity": 0.45,
        "symmetry_bias": 0.92, "noise_level": 0.12,
        "section_complexity": 0.60, "recursion_depth": 0.40,
    },
    "electronic": {
        **BASE_FEATURES,
        "tension": 0.416, "harmonic_stability": 0.361,
        "harmonic_change_rate": 0.350, "texture_complexity": 0.70,
        "symmetry_bias": 0.80, "noise_level": 0.40,
        "section_complexity": 0.60, "recursion_depth": 0.55,
    },
}


# ─── тесты ────────────────────────────────────────────────────────────────

def run_tests() -> None:
    from lib.composition.harmony_encoder import HarmonyEncoder, HARMONY_AXES, HARMONY_THETA_AXES
    from lib.composition.seed_policy import compute_base_seed
    from lib.composition.schema import HarmonyThetaArtifact

    enc = HarmonyEncoder()

    # T1 — детерминизм
    t1_a = enc.encode(BASE_FEATURES)
    t1_b = enc.encode(BASE_FEATURES)
    if t1_a.values == t1_b.values and t1_a.hash == t1_b.hash:
        ok("T1 determinism")
    else:
        fail("T1 determinism", f"{t1_a.values} != {t1_b.values}")

    # T2 — диапазон
    all_in_range = all(0.0 <= v <= 1.0 for v in t1_a.values)
    if all_in_range:
        ok("T2 range [0,1]")
    else:
        fail("T2 range [0,1]", f"out-of-range values: {t1_a.values}")

    # T3 — хэш формат
    h = t1_a.hash
    if isinstance(h, str) and len(h) == 16 and all(c in "0123456789abcdef" for c in h):
        ok("T3 hash format (16 hex chars)")
    else:
        fail("T3 hash format", f"got: '{h}'")

    # T4 — хэш-чувствительность: меняем каждую ось по очереди
    sensitivity_ok = True
    sensitivity_fails = []
    base_hash = t1_a.hash
    for ax in HARMONY_AXES:
        perturbed = dict(BASE_FEATURES)
        original_val = float(perturbed[ax])
        perturbed[ax] = min(1.0, original_val + 0.1) if original_val < 0.9 else max(0.0, original_val - 0.1)
        perturbed_hash = enc.encode(perturbed).hash
        if perturbed_hash == base_hash:
            sensitivity_ok = False
            sensitivity_fails.append(ax)
    if sensitivity_ok:
        ok("T4 hash sensitivity (all 8 axes)")
    else:
        fail("T4 hash sensitivity", f"hash unchanged for axes: {sensitivity_fails}")

    # T5 — интеграция с seed_policy
    seed_with_theta = compute_base_seed(
        audio_content_hash="abc123",
        title="Test Track",
        artist="Artist",
        duration_ms=210000,
        style_profile_slug="jazz_noir",
        profile_library_version="0.3.4",
        variation_seed=0,
        harmony_theta_hash=t1_a.hash,
    )
    seed_without_theta = compute_base_seed(
        audio_content_hash="abc123",
        title="Test Track",
        artist="Artist",
        duration_ms=210000,
        style_profile_slug="jazz_noir",
        profile_library_version="0.3.4",
        variation_seed=0,
    )
    if isinstance(seed_with_theta, int) and seed_with_theta > 0:
        ok("T5 seed_policy integration (returns positive int)")
    else:
        fail("T5 seed_policy integration", f"got: {seed_with_theta}")

    # T6 — обратная совместимость
    if seed_with_theta != seed_without_theta:
        ok("T6 backward compat (seed with theta ≠ seed without)")
    else:
        fail("T6 backward compat", "seed unchanged — theta_hash has no effect")

    # T7 — KeyError при отсутствующей оси
    try:
        bad_features = {k: v for k, v in BASE_FEATURES.items() if k != "tension"}
        enc.encode(bad_features)
        fail("T7 KeyError on missing axis", "no exception raised")
    except KeyError as e:
        ok(f"T7 KeyError on missing axis (caught: {e})")

    # T8 — покрытие жанров: theta различимы
    genre_hashes = {}
    genre_thetas = {}
    for genre, feats in GENRE_PROFILES.items():
        theta = enc.encode(feats)
        genre_hashes[genre] = theta.hash
        genre_thetas[genre] = theta.values
    unique_hashes = len(set(genre_hashes.values()))
    if unique_hashes == len(GENRE_PROFILES):
        ok(f"T8 genre coverage (all {unique_hashes} hashes unique)")
        print("       Genre theta matrix:")
        header = f"{'Genre':>12}  " + "  ".join(f"θ_{i}" for i in range(8))
        print(f"       {header}")
        for genre, vals in genre_thetas.items():
            row = "  ".join(f"{v:.3f}" for v in vals)
            print(f"       {genre:>12}: {row}")
    else:
        fail("T8 genre coverage", f"only {unique_hashes}/{len(GENRE_PROFILES)} unique hashes")

    # T9 — as_mapping_axes
    axes = t1_a.as_mapping_axes()
    expected_keys = set(HARMONY_THETA_AXES)
    if set(axes.keys()) == expected_keys and all(isinstance(v, float) for v in axes.values()):
        ok("T9 as_mapping_axes (harmony_theta_0..7)")
    else:
        fail("T9 as_mapping_axes", f"keys: {set(axes.keys())}")

    # T10 — HarmonyThetaArtifact schema
    theta_dict = t1_a.to_dict()
    artifact = HarmonyThetaArtifact(
        version=theta_dict["version"],
        algorithm=theta_dict["algorithm"],
        source_axes=theta_dict["source_axes"],
        values=theta_dict["values"],
        hash=theta_dict["hash"],
    )
    if len(artifact.values) == 8 and artifact.hash == t1_a.hash:
        ok("T10 HarmonyThetaArtifact schema")
    else:
        fail("T10 HarmonyThetaArtifact schema", f"values len={len(artifact.values)}, hash mismatch")

    # ── итог ──────────────────────────────────────────────────────────────
    print()
    print(f"Results: {len(_PASS)}/{len(_PASS)+len(_FAIL)} passed")
    if _FAIL:
        print(f"FAILED: {_FAIL}")
        sys.exit(1)
    else:
        print("E2 HarmonyEncoder: ALL TESTS PASSED ✅")


if __name__ == "__main__":
    print("=== test10.py — E2 HarmonyEncoder ===")
    run_tests()
