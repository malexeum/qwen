# D1 audio artifact provenance v2

`d1_feature_artifact/v1` is historical validation compatibility. A new `audio_file` artifact must use explicit `d1_feature_artifact/v2`; v1 synthetic fixtures remain supported.

The v2 semantic `source_identity` contains the content-addressed inventory ID, raw-byte SHA-256, byte size, `.mp3` suffix, adapter name/version, analysis-config version, and versioned decoder identity (`<backend>/<exact-version>`). Every field contributes to `feature_sha256`.

`source_locator.registry_path` is mandatory for v2 auditability, must be canonical relative POSIX syntax, and is intentionally excluded from the semantic hash preimage. Relocation of identical bytes in the registry must not change feature identity.

Commit 2 adds publish-time bridge re-derivation and immutable no-clobber validation.