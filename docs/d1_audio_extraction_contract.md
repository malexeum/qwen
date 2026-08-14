# D1 reproducible audio feature extraction contract

## Scope

This contract specifies a deterministic conversion from approved MP3 source bytes to
exactly eight D1 perceptual values. It establishes extraction policy only. It does
not add audio files, generated feature artifacts, manifests, E4 transitions, renders,
or output hashes.

## Source preflight

Before decoder or analyzer invocation, the extractor shall:

1. Resolve the source beneath the declared repository root.
2. Derive a canonical relative POSIX locator.
3. Find exactly one matching entry in `audio_source_inventory/v1`.
4. Verify `.mp3` suffix, raw-byte SHA-256, and byte size.
5. Emit `inventory_source_id` as `audio_source_inventory/v1/<content_sha256>`.

Any mismatch is fail-closed. No decoder process or analysis function may run after a
failed preflight.

## Environment provenance

The extraction result records:

- `adapter_name`: `d1_perceptual_extractor`
- `adapter_version`: `1.0.0`
- `analysis_config_version`: `d1_perceptual_config/v1`
- `decoder_backend`: `ffmpeg/<exact-version>`
- `config_sha256`: SHA-256 of canonical configuration JSON

The decoder backend is mandatory. An unavailable backend or an undetectable exact
version is a failure, not a fallback condition.

The measurement backend is the repository's E1-fix3 audio analyzer with a fixed
44,100 Hz mono analysis rate, 2048-point FFT, and 512-sample hop length. These
settings are recorded in `configs/d1_perceptual_config.v1.json`.

## Canonical D1 outputs

The output order and membership are fixed:

1. `symmetry_bias`
2. `tension`
3. `harmonic_stability`
4. `harmonic_change_rate`
5. `texture_complexity`
6. `recursion_depth`
7. `section_complexity`
8. `noise_level`

For finite raw measurements, formulas are:

```text
symmetry_bias        = clip01(symmetry_bias)
tension              = clip01(dynamic_range / 30.0)
harmonic_stability   = clip01(mfcc_variance_norm)
harmonic_change_rate = clip01(harmonic_change_rate_hz / 2.0)
texture_complexity   = clip01(0.50*spectral_flatness
                              + 0.30*spectral_centroid_norm
                              + 0.20*onset_rate_norm)
recursion_depth      = clip01(0.50*spectral_centroid_norm
                              + 0.30*tension
                              + 0.20*spectral_flatness)
section_complexity   = clip01(section_complexity)
noise_level          = clip01(noise_level)
```

All canonical values are clipped to the closed interval `[0, 1]`, rounded to six
decimal places using `ROUND_HALF_EVEN`, and serialized through the repository's
canonical JSON implementation. The extractor has no random seed, path-dependent
normalization, directory enumeration, or unversioned decoder fallback.

## Diagnostics

Diagnostics are explicitly separated from canonical D1 perceptual output. They may
include duration in seconds, raw spectral flatness, normalized spectral centroid,
normalized onset rate, dynamic range in dB, and harmonic-change rate in s^-1.

Diagnostics are not members of `artifact.perceptual` and do not enter D1 feature
identity unless a future schema revision explicitly changes that rule.

## Reproducibility boundary

Given identical source bytes, approved inventory entry, decoder identity, analyzer
implementation, and configuration bytes, the extractor produces byte-identical
canonical perceptual output. Changing configuration bytes changes `config_sha256`
and therefore the recorded extraction-contract provenance.

This contract proves deterministic extraction and source traceability. It does not
materialize `d1_rock_v1`, select an E4 scenario, or establish cryptographic author
attestation for an otherwise self-consistent generated artifact.
