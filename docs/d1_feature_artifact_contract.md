# D1 canonical feature-artifact contract

## Scope

D1-D.1 defines an in-memory canonical feature artifact. It performs no file I/O, creates no manifests, writes no fixture JSON, and does not generate E4 renders.

## Hash preimage

`feature_sha256` is calculated only from the canonical semantic payload:

```text
semantic payload -> canonical_json_bytes -> SHA-256 -> feature_sha256
```

The semantic payload contains `schema_version`, `analysis_id`, `source_identity`, strict `perceptual`, bridge metadata, encoder metadata, named theta, and `canonical_theta_hash`.

It excludes `feature_sha256`, `git_sha`, timestamps, artifact paths, URI/path locators, disk layout, renderer parameters, and seeds. `git_sha` is envelope provenance: it records the code that produced an artifact but does not alter semantic feature identity.

## Source identity

Audio sources use exactly:

```text
kind: audio_file
content_sha256: sha256:<64 lowercase hex>
adapter_name: audio_file_adapter
adapter_version: explicit stable version
analysis_config_version: explicit stable version
```

Synthetic sources use exactly:

```text
kind: synthetic_fixture
fixture_id: stable fixture identifier
fixture_spec_sha256: sha256:<64 lowercase hex>
```

Paths, URI, URL, location, timestamps, and arbitrary fields are rejected. `analysis_id` is a separate stable scenario identifier and does not replace source content identity.

## Dataflow

```text
strict source identity + strict perceptual payload
  -> D1HarmonyBridge
  -> named theta + canonical_theta_hash
  -> canonical semantic payload
  -> feature_sha256
  -> immutable D1FeatureArtifact envelope + git_sha
```

The bridge owns perceptual validation and the existing E2 HarmonyEncoder transform. The artifact builder does not duplicate perceptual formulas or construct theta manually. `named_theta` follows shared `THETA_AXES`; `canonical_theta_hash` is computed from its named-axis contract, not from legacy positional `HarmonyTheta.hash`.

## Immutability

`source_identity`, `perceptual`, and `named_theta` are `MappingProxyType` mappings. Callers cannot mutate an artifact after construction and silently invalidate its provenance.