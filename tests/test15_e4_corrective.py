"""test15_e4_corrective.py — CB-1 gate: canonical named θ-hash contract.

ТЗ E4_corrective_rebaseline_E5.md §2.3 — 6 обязательных тестов:
  1. reversed dict order → same hash
  2. 10 random key permutations → same hash
  3. swap values of θ₀ and θ₃ → different hash
  4. each axis +0.01 → different hash
  5. missing axis → ValidationError с именем оси
  6. unsupported key → ValidationError (контракт: reject unsupported keys)

Gate: все существующие тесты + эти тесты должны быть green до создания v2 fixtures/PNG.
"""

from __future__ import annotations

import random
import pytest

from lib.style_engine.engine import THETA_AXES, ValidationError, compute_theta_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_theta(**overrides: float) -> dict:
    """Construct a full valid theta dict with default 0.5 values."""
    base = {axis: 0.5 for axis in THETA_AXES}
    base.update(overrides)
    return base


def _make_theta_from_list(values: list) -> dict:
    """Construct theta dict from an 8-element list."""
    assert len(values) == 8
    return {THETA_AXES[i]: values[i] for i in range(8)}


# ---------------------------------------------------------------------------
# Class TestCanonicalThetaHash
# ---------------------------------------------------------------------------

class TestCanonicalThetaHash:
    """CB-1 hash contract tests."""

    # -----------------------------------------------------------------------
    # Test 1: reversed dict order → same hash
    # -----------------------------------------------------------------------
    def test_reversed_dict_order_same_hash(self):
        """Input dict key order must not affect the hash."""
        theta_fwd = _make_theta_from_list([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        theta_rev = dict(reversed(list(theta_fwd.items())))
        assert compute_theta_hash(theta_fwd) == compute_theta_hash(theta_rev), (
            "Hash must be invariant to input dict key order."
        )

    # -----------------------------------------------------------------------
    # Test 2: 10 random key permutations → same hash
    # -----------------------------------------------------------------------
    def test_random_permutations_same_hash(self):
        """10 random key permutations of the same theta → identical hashes."""
        rng = random.Random(42)
        theta_base = _make_theta_from_list([0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85])
        expected = compute_theta_hash(theta_base)
        axes_list = list(THETA_AXES)
        for _ in range(10):
            rng.shuffle(axes_list)
            permuted = {k: theta_base[k] for k in axes_list}
            assert compute_theta_hash(permuted) == expected, (
                "Hash must be identical for any permutation of the same key-value pairs."
            )

    # -----------------------------------------------------------------------
    # Test 3: swap values of θ₀ and θ₃ → different hash
    # -----------------------------------------------------------------------
    def test_swap_theta0_theta3_different_hash(self):
        """Swapping values between θ₀ and θ₃ must produce a different hash."""
        theta_original = _make_theta(
            harmony_theta_0=0.10,
            harmony_theta_3=0.90,
        )
        theta_swapped = _make_theta(
            harmony_theta_0=0.90,
            harmony_theta_3=0.10,
        )
        assert compute_theta_hash(theta_original) != compute_theta_hash(theta_swapped), (
            "Swapping θ₀ ↔ θ₃ values must change the hash "
            "(ТЗ §2.1: {theta_0:0.10, theta_3:0.90} != {theta_0:0.90, theta_3:0.10})."
        )

    # -----------------------------------------------------------------------
    # Test 4: each axis +0.01 → different hash
    # -----------------------------------------------------------------------
    def test_each_axis_increment_changes_hash(self):
        """Incrementing any single axis by 0.01 must change the hash."""
        base = _make_theta()  # all 0.5
        base_hash = compute_theta_hash(base)
        for axis in THETA_AXES:
            modified = base.copy()
            modified[axis] = round(base[axis] + 0.01, 6)
            modified_hash = compute_theta_hash(modified)
            assert modified_hash != base_hash, (
                f"Incrementing axis '{axis}' by 0.01 must change the hash."
            )

    # -----------------------------------------------------------------------
    # Test 5: missing axis → ValidationError с именем оси
    # -----------------------------------------------------------------------
    def test_missing_axis_raises_validation_error(self):
        """A dict missing any required axis must raise ValidationError naming the axis."""
        for missing_axis in THETA_AXES:
            incomplete = {ax: 0.5 for ax in THETA_AXES if ax != missing_axis}
            with pytest.raises(ValidationError) as exc_info:
                compute_theta_hash(incomplete, strict=True)
            assert missing_axis in str(exc_info.value), (
                f"ValidationError message must name the missing axis '{missing_axis}'."
            )

    # -----------------------------------------------------------------------
    # Test 6: unsupported key → ValidationError (contract: reject)
    # -----------------------------------------------------------------------
    def test_unsupported_key_raises_validation_error(self):
        """
        A dict containing an unsupported key must raise ValidationError.
        Contract choice per ТЗ §2.3: unsupported keys are *rejected*.
        """
        theta_with_extra = _make_theta()
        theta_with_extra["harmony_theta_99"] = 0.5  # unsupported
        with pytest.raises(ValidationError) as exc_info:
            compute_theta_hash(theta_with_extra, strict=True)
        assert "harmony_theta_99" in str(exc_info.value), (
            "ValidationError message must name the unsupported key."
        )

    # -----------------------------------------------------------------------
    # Bonus: strict=False ignores extra/missing keys (non-gate, sanity check)
    # -----------------------------------------------------------------------
    def test_strict_false_tolerates_extra_key(self):
        """With strict=False, extra keys are silently ignored."""
        theta = _make_theta()
        theta["harmony_theta_99"] = 0.5
        # Should not raise
        h = compute_theta_hash(theta, strict=False)
        assert isinstance(h, str) and len(h) == 16

    def test_strict_false_fills_missing_with_default(self):
        """With strict=False, missing axes are filled with _THETA_DEFAULT=0.5."""
        from lib.style_engine.engine import _THETA_DEFAULT
        partial = {ax: 0.5 for ax in THETA_AXES[:-1]}  # missing last axis
        full_default = _make_theta()  # all 0.5
        # Both must yield same hash since default IS 0.5
        assert compute_theta_hash(partial, strict=False) == compute_theta_hash(full_default, strict=False)
