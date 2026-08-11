# D1 Production Identity Contract Audit

## Scope

This document records the production ownership of identity, hashing, and seed derivation contracts before D1 creates a perceptual-to-harmony bridge, immutable feature artifacts, or a D1 manifest.

D1-B changes no renderer formula, generator mapping, legacy E4 artifact, PNG, or corpus input.

## Ownership matrix

| Operation | Authoritative implementation | Owner | Consumers | D1 decision |
|---|---|---|---|---|
| Harmony theta calculation | `lib.composition.harmony_encoder.HarmonyEncoder.encode()` | E2 / Composition | E2, D1, StyleEngine | Production source |
| Named theta mapping | `HarmonyTheta.as_mapping_axes()` | E2 / Composition | D1, StyleEngine | Production source |
| Legacy harmony theta hash | `HarmonyTheta.hash` | E2 / Composition | Existing composition seed policy | Preserve unchanged |
| Render variation seed | `lib.style_engine.engine._compute_variation_seed()` | E3 / StyleEngine | Resolver, E4 harness, GeneratorRuntime | Export through one public adapter |
| Composition base seed | `lib.composition.seed_policy.compute_base_seed()` | Composition | Composition planner | Preserve as a distinct derivation level |
| Composition layer seed | `lib.composition.seed_policy.compute_layer_seed()` | Composition | Composition planner | Preserve unchanged |
| Generator-ID canonicalization | `lib.composition.canonicalize` | Composition | Composition planner | Not a JSON/hash canonicalization contract |
| D1 semantic canonical bytes and raw file hash | D1 shared identity utility | D1 / shared infrastructure | D1 validator, future provenance | One shared implementation |

## Theta identity contracts

Two theta hashes must remain explicit and must not be substituted for each other.

| Field | Format | Meaning |
|---|---|---|
| `legacy_harmony_theta_hash` | `^[0-9a-f]{16}$` | E2 compatibility hash: positional theta list, rounded to three decimal places |
| `canonical_theta_hash` | `sha256:` plus 16 hex characters | D1 identity hash: complete named `harmony_theta_0` through `harmony_theta_7` mapping, raw range validation, six-place canonical serialization |

`HarmonyTheta.hash` remains unchanged. D1 must obtain named theta values through `HarmonyTheta.as_mapping_axes()` and must not reconstruct a positional list manually.

## Seed derivation levels

1. `HarmonyEncoder.encode()` creates `HarmonyTheta` from the eight required E2 feature axes.
2. StyleEngine derives the 32-bit render variation seed from `project_id`, `analysis_id`, `preset_id`, style slug, interpretation slug, and named theta values.
3. Composition derives its 64-bit base seed from composition metadata, the render variation seed, and the legacy E2 theta hash.
4. Composition derives a layer seed from the base seed, layer ID, and canonical generator ID.

The D1 manifest must store an immutable `render_identity` object because feature file hashes are provenance identities, not direct inputs to the current StyleEngine render-seed formula.

```yaml
render_identity:
  project_id: e4_reference_render_audit_v2
  analysis_id: ambient_A
  preset_id: d1_neutral
  style_profile_slug: ambient
  interpretation_profile_slug: default
```

## D1-B invariants

- No independent second variation-seed formula is permitted.
- D1 raw file hashes use SHA-256 of physical bytes with no newline, encoding, or float normalization.
- D1 semantic hashes use one canonical serialization implementation.
- Raw numeric theta values are validated in `[0, 1]` before six-place `ROUND_HALF_EVEN` quantization.
- Historical E4 positional theta vectors, placeholder feature hashes, legacy seeds, and legacy provenance are candidate metadata only, never D1 identities.
- Until D1-B, D1-C, D1-D, and D1-E pass, no v2 PNG corpus or E5 baseline may be created.

## Next implementation steps

1. Move D1 semantic canonicalization to a shared utility with a thin explicit StyleEngine re-export.
2. Replace the temporary D1 seed helper with a public adapter to the existing StyleEngine render-seed implementation.
3. Add compatibility tests for E2 legacy theta identity, D1 canonical theta identity, StyleEngine render seed, and composition base seed.
4. Only then implement the versioned perceptual-to-harmony bridge.
