from __future__ import annotations

FEATURE_GROUPS = {
    "pulse": ("bpm", "beat_confidence", "pulse_regularity", "onset_density", "syncopation_index"),
    "envelope": ("dynamic_range", "attack_sharpness", "sustain_ratio", "macro_energy_arc", "silence_ratio"),
    "form": ("section_count", "section_contrast", "climax_position", "intro_length_ratio", "ending_decay_ratio"),
    "recurrence": ("self_similarity", "motif_return_strength", "repetition_ratio", "variation_ratio"),
    "timbre": ("spectral_centroid", "spectral_rolloff", "spectral_flatness", "spectral_flux", "roughness", "brightness"),
    "harmony": ("harmonic_ratio", "chroma_stability", "harmonic_change_rate", "tonal_stability", "dissonance_proxy"),
    "space": ("spectral_bandwidth", "stereo_width", "reverb_proxy", "depth_proxy"),
}


def validate_features(features: dict) -> None:
    if set(features) != set(FEATURE_GROUPS):
        raise ValueError("MusicFeaturesV2 groups do not match the contract")
    for group, names in FEATURE_GROUPS.items():
        if set(features[group]) != set(names):
            raise ValueError(f"MusicFeaturesV2 fields do not match contract: {group}")
        for name, value in features[group].items():
            if group == "pulse" and name == "bpm":
                if not 0.0 <= float(value) <= 220.0:
                    raise ValueError("bpm outside declared range")
            elif group == "form" and name == "section_count":
                if not 1 <= int(value) <= 12:
                    raise ValueError("section_count outside declared range")
            elif not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"normalized feature outside range: {group}.{name}")