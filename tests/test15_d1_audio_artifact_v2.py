import pytest
from lib.d1_feature_artifacts import SCHEMA_V2, validate_source_identity, validate_source_locator

DIGEST = "sha256:" + "a" * 64
IDENTITY = {"kind":"audio_file", "inventory_source_id":"audio_source_inventory/v1/" + DIGEST, "content_sha256":DIGEST, "byte_size":4605149, "suffix":".mp3", "adapter_name":"d1_perceptual_extractor", "adapter_version":"1.0.0", "analysis_config_version":"d1_perceptual_config/v1", "decoder_backend":"ffmpeg/7.1"}


def test_v2_audio_identity_is_strict():
    assert validate_source_identity(SCHEMA_V2, IDENTITY) == IDENTITY
    for changed in ({**IDENTITY, "extra": True}, {**IDENTITY, "byte_size": 0}, {**IDENTITY, "suffix": ".wav"}, {**IDENTITY, "decoder_backend": "unknown"}, {**IDENTITY, "inventory_source_id": "wrong"}):
        with pytest.raises(ValueError):
            validate_source_identity(SCHEMA_V2, changed)


def test_registry_locator_is_canonical_posix():
    assert validate_source_locator({"registry_path":"tests/audio/Rock.mp3"}) == {"registry_path":"tests/audio/Rock.mp3"}
    for path in ("./tests/audio/Rock.mp3", "tests//audio/Rock.mp3", "C:Rock.mp3", "tests/audio/.", "../tests/audio/Rock.mp3", "tests\\audio\\Rock.mp3"):
        with pytest.raises(ValueError):
            validate_source_locator({"registry_path": path})