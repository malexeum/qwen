# D1 Audio Perceptual Extraction Contract

## Purpose and scope

The D1 extractor maps approved audio-analysis measurements into a fixed,
canonical eight-axis perceptual vector. It defines output order, mapping policy,
rounding, source preflight, configuration identity, and decoder capability
evidence.

This PR defines extraction policy only. It does not attest actual decode
provenance and does not materialize an audio-derived D1 feature artifact.

The implementation is:

- `tools/d1_extract.py`
- `configs/d1_perceptual_config.v1.json`
- `lib.audio_analysis.analysis.analyze_audio_file`

## Canonical vector

The output contains exactly these axes in this order:

1. `symmetry_bias`
2. `tension`
3. `harmonic_stability`
4. `harmonic_change_rate`
5. `texture_complexity`
6. `recursion_depth`
7. `section_complexity`
8. `noise_level`

Every axis must be finite, bounded to `[0.0, 1.0]`, and quantized to six decimal
places using decimal `ROUND_HALF_EVEN`.

## Source identity preflight

Only an inventory-approved `.mp3` source may be extracted. Before decoder or
analyzer invocation, the extractor verifies:

- source path resolves inside repository root;
- canonical relative path matches exactly one inventory entry;
- source suffix is `.mp3`;
- byte size matches inventory;
- raw-byte SHA-256 matches inventory.

The source identity is:

```text
audio_source_inventory/v1/sha256:<hex-digest>
```

A failed source preflight prevents decoder and analyzer execution.

## Measurement contract

The mapping is valid only for this exact measurement implementation contract:

```json
{
  "module": "lib.audio_analysis.analysis",
  "function": "analyze_audio_file",
  "implementation_contract": "e1_fix3_fixed_44100hz_mono_nfft2048_hop512"
}
```

This denotes analysis at 44,100 Hz, mono input, FFT length 2,048 samples, and
hop length 512 samples. A different backend declaration or implementation
contract is rejected before extraction.

## Decoder capability evidence

The preflight detects installed FFmpeg capability through:

```text
ffmpeg -version
```

The detected identity is recorded in provenance as:

```text
decoder_capability_backend = "ffmpeg/<exact-version>"
```

The current extraction-contract preflight requires an exact FFmpeg capability
identity. It does not yet attest the actual decoder implementation that
produced PCM samples.

`decoder_capability_backend` is capability evidence only. It is not proof of
bit-exact PCM equivalence across FFmpeg builds, operating systems, compiler
options, linked codec libraries, or downstream processing stages.

## Formula registry

The JSON configuration contains only non-executable `formula_id` references.
The Python extractor dispatches them only through an allow-listed registry.

| Axis | Formula ID | Mapping |
|---|---|---|
| `symmetry_bias` | `symmetry_bias_identity_clip01` | `clip01(symmetry_bias)` |
| `tension` | `dynamic_range_div_30_clip01` | `clip01(dynamic_range / 30.0)` |
| `harmonic_stability` | `mfcc_variance_identity_clip01` | `clip01(mfcc_variance_norm)` |
| `harmonic_change_rate` | `harmonic_change_rate_div_2_clip01` | `clip01(harmonic_change_rate_hz / 2.0)` |
| `texture_complexity` | `flatness_centroid_onset_weighted_v1` | `clip01(0.50 × spectral_flatness + 0.30 × spectral_centroid_norm + 0.20 × onset_rate_norm)` |
| `recursion_depth` | `centroid_tension_flatness_weighted_v1` | `clip01(0.50 × spectral_centroid_norm + 0.30 × tension + 0.20 × spectral_flatness)` |
| `section_complexity` | `section_complexity_identity_clip01` | `clip01(section_complexity)` |
| `noise_level` | `noise_level_identity_clip01` | `clip01(noise_level)` |

```text
clip01(x) = min(1.0, max(0.0, x))
```

Evaluation follows canonical axis order. Therefore, `recursion_depth` consumes
the already mapped canonical `tension` value.

Test-only formula IDs may be temporarily injected in isolated unit tests to
prove dispatch isolation. They are never committed to the production JSON and
must not be passed through `load_config()` as accepted production formulas.

## Required measurements

The analyzer must return finite real numeric values for:

- `duration_sec`
- `symmetry_bias`
- `dynamic_range`
- `mfcc_variance_norm`
- `harmonic_change_rate_hz`
- `spectral_flatness`
- `spectral_centroid_norm`
- `onset_rate_norm`
- `section_complexity`
- `noise_level`

Missing values, booleans, non-numeric values, `NaN`, and infinities fail closed.

## Output structure

```json
{
  "perceptual": {
    "symmetry_bias": 0.0,
    "tension": 0.0,
    "harmonic_stability": 0.0,
    "harmonic_change_rate": 0.0,
    "texture_complexity": 0.0,
    "recursion_depth": 0.0,
    "section_complexity": 0.0,
    "noise_level": 0.0
  },
  "diagnostics": {
    "duration_sec": 0.0,
    "spectral_flatness": 0.0,
    "spectral_centroid_norm": 0.0,
    "onset_rate_norm": 0.0,
    "dynamic_range": 0.0,
    "harmonic_change_rate_hz": 0.0
  },
  "provenance": {
    "inventory_source_id": "audio_source_inventory/v1/sha256:<hex-digest>",
    "content_sha256": "sha256:<hex-digest>",
    "byte_size": 0,
    "suffix": ".mp3",
    "registry_path": "corpus/audio/example.mp3",
    "adapter_name": "d1_perceptual_extractor",
    "adapter_version": "1.0.0",
    "analysis_config_version": "d1_perceptual_config/v1",
    "decoder_capability_backend": "ffmpeg/<exact-version>",
    "config_sha256": "sha256:<hex-digest>"
  }
}
```

`diagnostics` are not canonical perceptual axes and are excluded from
canonical perceptual bytes.

## Verification

Run from repository root:

```cmd
python -m py_compile tools\d1_extract.py
python -m pytest -q tests\test15_d1_extraction_contract.py
python -m pytest -q
git diff --check
```

The contract test suite uses synthetic temporary `.mp3` bytes and injected
decoder/analyzer stubs. It must not invoke `ffmpeg`, invoke
`analyze_audio_file`, or access `tests/audio/Rock.mp3`.

## Fail-closed conditions

Extraction fails for unsupported config identity, changed canonical axes, an
unknown formula ID, changed measurement contract, malformed or non-FFmpeg
decoder-capability identity, source inventory mismatch, invalid raw
measurements, or output that fails the fixed six-place decimal policy.