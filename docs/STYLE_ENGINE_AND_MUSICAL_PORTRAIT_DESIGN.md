# StyleEngine and MusicalPortrait design

## Goal

This document defines the design contract for the existing StyleEngine to receive a MusicalPortraitV1 and resolve the macro RenderParams for RockCompositionGrammarV8 without introducing a parallel production renderer or changing the canonical D1 artifact layer.

The actual pipeline remains:

MP3
→ AudioFeaturesV2
→ MusicalPortraitV1
→ StyleEngine.resolve(profile="rock")
→ RockCompositionGrammarV8
→ RenderParams + MappingTrace
→ GeneratorRuntime
→ SVG + provenance

Important constraint:

- This is a design and contract document only.
- No new production renderer is created here.
- No V7 outputs are modified.
- No audio-derived V2 features are claimed to be implemented from raw MP3 in production code.

## 1. Existing system to extend

The implementation already contains the relevant layers in the current codebase:

- [lib/style_engine/engine.py](../lib/style_engine/engine.py) — StyleEngine, MappingTraceEntry, and RenderParams
- [lib/style_engine/config_loader.py](../lib/style_engine/config_loader.py) — style and interpretation profiles, schema validation, and provenance
- [lib/style_engine/generator_runtime.py](../lib/style_engine/generator_runtime.py) — runtime adapter that turns RenderParams into generator calls
- [lib/style_engine/configs/style_profiles](../lib/style_engine/configs/style_profiles) — style profile declarations
- [lib/style_engine/configs/interpretation_profiles](../lib/style_engine/configs/interpretation_profiles) — formula-driven interpretation rules

These are the exact extension points that should absorb MusicalPortraitV1. No duplication is needed in a parallel service layer.

## 2. Where MusicalPortraitV1 lives

MusicalPortraitV1 should be introduced as a versioned DTO inside the existing interpretation layer, not as a separate runtime service.

The intended placement is:

- canonical feature data remains in D1 artifact / extracted audio features
- a portrait object is created in the same translation boundary where the current StyleEngine resolves `RenderParams`
- the portrait then feeds into the existing interpretation profile rules and `mapping_trace`

Conceptually:

- D1 / AudioFeaturesV2 are the raw musical input contract
- MusicalPortraitV1 is a normalized, bounded semantic portrait used by StyleEngine
- RockCompositionGrammarV8 is the macro grammar that converts portrait axes to RenderParams

## 3. Existing interfaces to extend

The current style engine already supports a layered contract that matches the design need:

### 3.1 StyleEngine

`RenderParams` in [lib/style_engine/engine.py](../lib/style_engine/engine.py) already defines the final macro parameters used by the generator stack:

- symmetry_bias
- recursion_depth
- density_level
- noise_level
- motion_intensity
- texture_complexity
- harmony theta axes
- palette_id
- stochastic_term
- layout_macro_shape
- variation_seed
- mapping_trace

This object is the correct place to receive portrait-driven macro parameters.

### 3.2 MappingTrace

`MappingTraceEntry` in [lib/style_engine/engine.py](../lib/style_engine/engine.py) already captures:

- parameter name
- source formula
- raw value
- final value
- stage
- source_axes
- formula
- input_values
- layer_id
- generator_id

This is the correct provenance mechanism for portrait-to-grammar-to-render mapping. MusicalPortraitV1 does not require a new trace type; it requires additional trace fields describing source portrait inputs and grammar resolution.

### 3.3 GeneratorRuntime

[lib/style_engine/generator_runtime.py](../lib/style_engine/generator_runtime.py) already adapts `RenderParams` into concrete generator calls. It should stay as the runtime boundary; the v8 grammar only changes the resolved macro parameters given to it.

No new runtime adapter is needed.

## 4. Objects that should not be duplicated

These existing objects are the authoritative building blocks and must not be copied or reimplemented under a new production service:

- D1 feature artifact schema
- `build_d1_feature_artifact()` and artifact validation layer
- `StyleProfile` and `InterpretationProfile` loader
- `MappingTraceEntry`
- `RenderParams`
- `GeneratorRuntime`
- any generator or composition backend in `lib/generators.py`

The design should extend the current stack; it should not create a second independent engine or a shadow v8 renderer file in production.

## 5. Migration path

The intended migration is explicit and layered:

1. D1 or audio-derived feature contract provides raw and normalized musical signal properties.
2. `MusicFeaturesV2` describes the raw feature input domain. This is a schema-only document, not implementation claim.
3. `MusicalPortraitV1` summarizes the signal into bounded portrait axes:
   - pulse: regularity, urgency, impact
   - gesture: continuity, angularity, propulsion
   - form: complexity, recurrence, contrast, climax_position
   - material: roughness, brightness, density, sustain
   - affect: tension, stability, openness
4. `RockCompositionGrammarV8` resolves a deterministic mode from portrait axes.
5. StyleEngine resolves the macro `RenderParams` and records `MappingTrace`.
6. `GeneratorRuntime` consumes the resolved params and emits output.

This path preserves the existing system architecture without creating a separate service or a no-contract production renderer.

## 6. Design contract for MusicalPortraitV1

Each portrait axis must have:

- range: [0.0, 1.0]
- formula specification version
- required raw input features
- neutral fallback value
- trace field names

This contract is expressed in [configs/musical_portrait_v1.yaml](../configs/musical_portrait_v1.yaml).

All values are bounded 0..1, and the fallback is deterministic. The portrait layer is purely a deterministic transformation and does not involve seed-based decisions.

## 7. Design contract for RockCompositionGrammarV8

The grammar file [configs/rock_composition_grammar_v8.yaml](../configs/rock_composition_grammar_v8.yaml) defines:

- modes: monolithic, kinetic_break, recursive_grove, fragmented_signal, open_horizon
- deterministic selection rule per mode
- priority ordering and tie-break rule
- macro params each mode controls
- guardrails and ranges
- required trace payload
- explicit no-seed policy

The grammar must resolve only from portrait axes, never from seed or random state.

## 8. Definition of done for the design contract

The design is complete when the repository contains:

- [configs/music_features_v2.yaml](../configs/music_features_v2.yaml)
- [configs/musical_portrait_v1.yaml](../configs/musical_portrait_v1.yaml)
- [configs/rock_composition_grammar_v8.yaml](../configs/rock_composition_grammar_v8.yaml)
- this design document
- tests covering bounded values, deterministic mode selection, and schema contract validity

The repository should clearly explain how the existing StyleEngine receives MusicalPortraitV1 and resolves rock macro RenderParams for V8, without changing the canonical D1 artifact layer or claiming an end-to-end V8 production runtime.
