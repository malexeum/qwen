import pytest

from lib import canonicalization as shared
from lib.style_engine import canonicalization as style_engine


def theta_vector(value=0.5):
    return {axis: value for axis in shared.THETA_AXES}


@pytest.mark.parametrize("invalid_value", [1.0000004, -0.0000004])
def test_theta_range_is_validated_before_quantization(invalid_value):
    theta = theta_vector()
    theta["harmony_theta_3"] = invalid_value
    with pytest.raises(ValueError, match="outside"):
        shared.canonical_theta_hash(theta)


def test_style_engine_reexport_matches_shared_canonicalization():
    theta = theta_vector()
    payload = {"z": 0.5, "a": {"value": 0.1234565}}
    assert style_engine.canonical_json_bytes(payload) == shared.canonical_json_bytes(payload)
    assert style_engine.canonical_feature_hash(payload) == shared.canonical_feature_hash(payload)
    assert style_engine.canonical_theta_hash(theta) == shared.canonical_theta_hash(theta)
