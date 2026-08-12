# D1 perceptual-to-harmony bridge contract

## Scope

`lib.composition.d1_harmony_bridge.project_perceptual_to_harmony` is the D1 adapter boundary between a canonical D1 perceptual payload and the existing E2 `HarmonyEncoder.crossproduct_v1` transform. It does not extract features, derive perceptual values, calculate render parameters, or calculate render seeds.

The one-way chain is:

```text
canonical D1 perceptual payload
  -> d1_perceptual_projection/v1
  -> harmony_crossproduct/v1.0
  -> named harmony_theta_0 .. harmony_theta_7
  -> canonical_theta_hash
  -> StyleEngine.resolve_render_params
  -> compute_render_variation_seed
```

## Metadata

```text
bridge.name: perceptual_projection
bridge.version: v1
encoder.name: crossproduct
encoder.version: 1.0
```

`HarmonyEncoder.crossproduct_v1` is retained as the legacy E2 production transform. D1 does not create a second theta encoder.

## Strict input schema

The bridge accepts exactly one mapping: the `perceptual` object from a canonical D1 artifact. It accepts exactly these finite real-valued fields in the closed interval `[0, 1]`:

| HarmonyEncoder input | D1 perceptual origin | Upstream transformation | Bridge action | Why upstream |
|---|---|---|---|---|
| `symmetry_bias` | `symmetry_bias` | consonance-energy metric, clipped | validate and pass through | does not depend on StyleEngine |
| `tension` | `tension` | `dynamic_range / 30`, clipped | validate and pass through | does not depend on theta |
| `harmonic_stability` | `harmonic_stability` | `mfcc_variance_norm`, clipped | validate and pass through | does not depend on render parameters |
| `harmonic_change_rate` | `harmonic_change_rate` | `harmonic_change_rate_hz / 2`, clipped | validate and pass through | does not depend on render parameters |
| `texture_complexity` | `texture_complexity` | `0.50 * spectral_flatness + 0.30 * spectral_centroid_norm + 0.20 * onset_rate_norm`, clipped | validate and pass through | does not depend on StyleEngine |
| `recursion_depth` | `recursion_depth` | `0.50 * spectral_centroid_norm + 0.30 * tension + 0.20 * spectral_flatness`, clipped | validate and pass through | does not depend on StyleEngine |
| `section_complexity` | `section_complexity` | RMS-segment coefficient of variation, clipped | validate and pass through | does not depend on StyleEngine |
| `noise_level` | `noise_level` | upstream log-noise metric, clipped | validate and pass through | does not depend on renderer |

The bridge rejects missing fields, unexpected fields, booleans, non-real values, `NaN`, infinities, and values outside `[0, 1]`. It performs no defaults, clamping, quantization, or formula evaluation.

## Isolation policy

The bridge must not import `lib.style_engine.engine`, `RenderParams`, or `compute_render_variation_seed`. It must not accept variation seed, renderer, style, interpretation, or legacy theta fields. Its two result mappings are `MappingProxyType` instances and cannot be mutated by callers.

## Downstream seed

The bridge obtains named theta only from `HarmonyEncoder().encode(encoder_features).as_mapping_axes()`. `compute_render_variation_seed` is a downstream StyleEngine operation over explicit render identity and the bridge-produced named theta. A perceptual perturbation is not required to change theta or seed; many-to-one projections are permitted by the mapping contract.
