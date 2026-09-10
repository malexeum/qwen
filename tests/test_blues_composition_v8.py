from lib.style_engine.blues_composition_v8 import resolve_blues_composition_v8


def _portrait(**perceptual):
    return {
        "perceptual": {
            "brightness": 0.50,
            "density": 0.50,
            "stability": 0.50,
            "smoothness": 0.50,
            "tension": 0.50,
            "repetition": 0.50,
            "noise_proxy": 0.50,
            "symmetry_bias": 0.40,
            "energy": 0.50,
            **perceptual,
        },
        "harmony_theta": {
            "theta_3": 0.50,
            "theta_5": 0.50,
            "theta_6": 0.50,
        },
        "bpm": 92.0,
        "spectral_skewness": 0.50,
        "dynamic_range": 0.50,
    }


def test_blues_bridge_has_canonical_identity():
    bridge, _ = resolve_blues_composition_v8(_portrait())

    assert bridge["grammar"] == "BluesGravityWellCompositionV8"
    assert bridge["dominant_mode"] == "slow_blues"
    assert bridge["palette_id"] == "warm_midnight"
    assert bridge["junction"] == {"x": 540.0, "y": 520.0}


def test_blues_parameters_stay_in_safe_ranges():
    bridge, _ = resolve_blues_composition_v8(
        _portrait(
            brightness=0.0,
            density=1.0,
            stability=0.0,
            smoothness=1.0,
            tension=1.0,
            repetition=0.0,
            noise_proxy=1.0,
            symmetry_bias=0.0,
            energy=1.0,
        )
    )

    for key in (
        "gravity",
        "inflow",
        "blue_note_bend",
        "tube_warmth",
        "smoke_density",
        "swing_lag",
        "ring_fragmentation",
    ):
        assert 0.0 <= bridge[key] <= 1.0

    assert 54.0 <= bridge["void_radius"] <= 88.0
    assert 0.55 <= bridge["spiral_turns"] <= 1.0


def test_more_tension_increases_inflow():
    low, _ = resolve_blues_composition_v8(_portrait(tension=0.10))
    high, _ = resolve_blues_composition_v8(_portrait(tension=0.90))

    assert high["inflow"] > low["inflow"]


def test_more_darkness_and_low_frequency_weight_increase_gravity():
    light, _ = resolve_blues_composition_v8(
        _portrait(brightness=0.85, density=0.20)
    )
    heavy, _ = resolve_blues_composition_v8(
        _portrait(brightness=0.15, density=0.85)
    )

    assert heavy["gravity"] > light["gravity"]
    assert heavy["void_radius"] > light["void_radius"]


def test_default_portrait_is_slow_and_non_aggressive():
    bridge, _ = resolve_blues_composition_v8(_portrait())

    assert bridge["spiral_turns"] < 0.90
    assert bridge["void_radius"] < 80.0
    assert bridge["inflow"] < 0.70
