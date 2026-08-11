from decimal import Decimal

import pytest

from lib.style_engine.canonicalization import (
    THETA_AXES,
    canonical_feature_hash,
    canonical_file_hash,
    canonical_float,
    canonical_json_bytes,
    canonical_theta_hash,
)


def theta_vector(value: float = 0.5) -> dict[str, float]:
    return {axis: value for axis in THETA_AXES}


def test_canonical_float_uses_half_even_and_fixed_point() -> None:
    assert canonical_float("0.1234565") == "0.123456"
    assert canonical_float("0.1234575") == "0.123458"
    assert canonical_float(0.5) == "0.500000"
    assert canonical_float(Decimal("1")) == "1.000000"


def test_canonical_json_bytes_are_order_independent_and_quantized() -> None:
    left = {"beta": 0.5, "alpha": {"value": 0.12345651}}
    right = {"alpha": {"value": Decimal("0.12345651")}, "beta": 0.5000000}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes(left) == b'{"alpha":{"value":"0.123457"},"beta":"0.500000"}'


def test_feature_hash_is_full_sha256_and_uses_canonical_object_bytes() -> None:
    left = canonical_feature_hash({"b": 1, "a": 0.5})
    right = canonical_feature_hash({"a": 0.500000, "b": 1})
    assert left == right
    assert left.startswith("sha256:")
    assert len(left.removeprefix("sha256:")) == 64


def test_file_hash_uses_raw_bytes_without_newline_normalization(tmp_path) -> None:
    lf_path = tmp_path / "lf.txt"
    crlf_path = tmp_path / "crlf.txt"
    lf_path.write_bytes(b"a\nb\n")
    crlf_path.write_bytes(b"a\r\nb\r\n")
    lf_hash = canonical_file_hash(lf_path)
    assert lf_hash != canonical_file_hash(crlf_path)
    assert lf_hash.startswith("sha256:")
    assert len(lf_hash.removeprefix("sha256:")) == 64


def test_theta_hash_uses_named_axes_not_input_mapping_order() -> None:
    theta = theta_vector()
    assert canonical_theta_hash(theta) == canonical_theta_hash(dict(reversed(list(theta.items()))))


def test_theta_hash_changes_when_values_move_between_named_axes() -> None:
    baseline = theta_vector()
    changed = theta_vector()
    changed["harmony_theta_0"] = 0.2
    changed["harmony_theta_3"] = 0.8
    swapped = dict(changed)
    swapped["harmony_theta_0"] = 0.8
    swapped["harmony_theta_3"] = 0.2
    assert canonical_theta_hash(changed) != canonical_theta_hash(swapped)
    assert canonical_theta_hash(baseline) != canonical_theta_hash(changed)


def test_theta_hash_is_short_sha256_format() -> None:
    result = canonical_theta_hash(theta_vector())
    assert result.startswith("sha256:")
    assert len(result.removeprefix("sha256:")) == 16


@pytest.mark.parametrize(
    "mutator",
    [
        lambda theta: theta.pop("harmony_theta_7"),
        lambda theta: theta.__setitem__("theta_0", 0.5),
        lambda theta: theta.__setitem__("harmony_theta_1", True),
        lambda theta: theta.__setitem__("harmony_theta_1", float("nan")),
        lambda theta: theta.__setitem__("harmony_theta_1", float("inf")),
        lambda theta: theta.__setitem__("harmony_theta_1", "0.5"),
        lambda theta: theta.__setitem__("harmony_theta_1", {"value": 0.5}),
        lambda theta: theta.__setitem__("harmony_theta_1", [0.5]),
        lambda theta: theta.__setitem__("harmony_theta_1", 1.000001),
        lambda theta: theta.__setitem__("harmony_theta_1", -0.000001),
    ],
)
def test_theta_hash_rejects_invalid_axis_contract(mutator) -> None:
    theta = theta_vector()
    mutator(theta)
    with pytest.raises(ValueError):
        canonical_theta_hash(theta)
