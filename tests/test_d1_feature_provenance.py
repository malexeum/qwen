from lib.style_engine.seed_policy import compute_variation_seed


FEATURE_HASH = "sha256:" + "a" * 64
THETA_HASH = "sha256:0123456789abcdef"


def test_variation_seed_is_deterministic() -> None:
    assert compute_variation_seed("jazz", FEATURE_HASH, THETA_HASH) == compute_variation_seed(
        "jazz", FEATURE_HASH, THETA_HASH
    )


def test_variation_seed_changes_with_each_causal_component() -> None:
    baseline = compute_variation_seed("jazz", FEATURE_HASH, THETA_HASH)
    assert baseline != compute_variation_seed("rock", FEATURE_HASH, THETA_HASH)
    assert baseline != compute_variation_seed("jazz", "sha256:" + "b" * 64, THETA_HASH)
    assert baseline != compute_variation_seed("jazz", FEATURE_HASH, "sha256:fedcba9876543210")


def test_variation_seed_is_a_non_negative_64_bit_integer() -> None:
    seed = compute_variation_seed("jazz", FEATURE_HASH, THETA_HASH)
    assert isinstance(seed, int)
    assert 0 <= seed < 2**64
