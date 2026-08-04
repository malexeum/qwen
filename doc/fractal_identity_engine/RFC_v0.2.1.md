# RFC_v0.2.1 — Perceptual Latent Layer

## 1. Problem

The current MVP pipeline is:

`AudioAnalysis → StyleProfile → RenderParams → Poster`

This is sufficient for simple mappings but has important limitations:
- Direct feature-to-fractal mappings can feel arbitrary to users.
- Users cannot easily see how the visual relates to the music.
- The musical structure (form, repetition, climaxes) is weakly represented.
- The system lacks an explicit explanatory chain from audio to visual decisions.

We need an explicit **perceptual latent layer** between audio analysis and the fractal generator.

## 2. Proposal

Insert two new conceptual levels between `AudioAnalysis` and `RenderParams`:

1. `PerceptualLatent` — a compact representation of the track in perceptual axes.
2. `InterpretationProfile` — a profile that describes how those axes become visual decisions.

New pipeline:

`AudioAnalysis → PerceptualLatent → InterpretationProfile + StyleProfile + UserPreset → RenderParams → PosterRenderer`

This keeps the architecture layered and makes the mapping more explainable and perceptually meaningful.

## 3. PerceptualLatent entity

`PerceptualLatent` is logically tied to `AudioAnalysis` and captures human-interpretable axes such as:

- `energy` — overall energy and variability.
- `tension` — perceived tension vs resolution.
- `density` — event / rhythm density.
- `brightness` — perceived brightness / spectral lightness.
- `stability` — tonal/formal stability.
- `smoothness` — smooth vs sharp transitions.
- `repetition` — degree of motif/section repetition.
- `section_complexity` — coarse measure of structural richness.
- `macro_shape_hint` — coarse form hint (e.g., A–B–A-like, strophic-like).

Implementation options:
- separate `perceptual_latent` table referencing `AudioAnalysis` and `Track`;
- or embedded JSON field within `AudioAnalysis` as a `perceptual` block.

The choice for v0.2.1 is flexible, but the contract must be explicit and serializable.

## 4. AudioAnalysis extensions

To support `PerceptualLatent`, we extend `AudioAnalysis` with structural information:

- `sections` — list of segments with approximate time boundaries (intro, verse, chorus, bridge, outro, etc.).
- `section_labels` / `section_ids` — identifiers for sections and their types.
- `recurrence_groups` — groups of recurring sections (A1–A2–A3, etc.).
- `events` — key events such as breaks, climaxes, key changes.

These do not need to be perfect; v0.2.1 can use simple, robust heuristics. The key is to encode structure explicitly in the model.

## 5. InterpretationProfile

`InterpretationProfile` is a declarative configuration describing how to “read” the perceptual axes into visual decisions.

Examples:
- `organic_fluid`
- `geometric_rhythmic`
- `dark_tense`
- `minimal_stable`
- `exploratory_chaotic`

Each profile defines:
- which axes are emphasized;
- how axes map to fractal parameters (symmetry bias, recursion depth, stochastic term, palette, density, evolution speed, etc.).

Implementation:
- YAML/JSON configs loaded alongside `StyleProfile`.

## 6. Updated style engine

We split the style engine into two layers:

1. **Perceptual resolver**
   - Input: `AudioAnalysis`.
   - Output: `PerceptualLatent`.

2. **Visual resolver**
   - Input: `PerceptualLatent` + `StyleProfile` + `InterpretationProfile` + `UserPreset`.
   - Output: `RenderParams`.

`StyleProfile` remains the primary music-style + visual mood descriptor. `InterpretationProfile` describes how to interpret the perceptual axes; `UserPreset` carries user sliders.

## 7. Explainability chain

We explicitly preserve the following chain:

`audio → AudioAnalysis → PerceptualLatent → InterpretationProfile + StyleProfile → RenderParams → Poster`

The system can store metadata describing:
- which perceptual axes were key for this visual;
- which interpretation profile was applied;
- which musical events influenced the composition.

This can later be exposed in pro-mode and simple user-facing explanations.

## 8. API changes

### 8.1 /analyze

`POST /analyze` must:
- compute and store `AudioAnalysis`;
- compute and store `PerceptualLatent` or embed it into `AudioAnalysis`.

### 8.2 /resolve-style

`POST /resolve-style` must:
- accept `analysis_id`;
- load `AudioAnalysis` + `PerceptualLatent`;
- accept chosen `StyleProfile` and `InterpretationProfile` identifiers;
- accept `UserPreset`.

Output: `RenderParams` that incorporates perceptual axes and visual interpretation.

No other endpoints are structurally changed, but their internal use of style/params must be updated accordingly.

## 9. Scope for v0.2.1

For v0.2.1 we aim for a minimal, yet functional perceptual integration:

- Implement `PerceptualLatent` with a basic set of axes (energy, tension, density, brightness, stability, repetition, macro_shape_hint).
- Implement rule-based mapping from `AudioAnalysis` to `PerceptualLatent`.
- Implement 2–3 `InterpretationProfile` configs.
- Update `resolve-style` to use `PerceptualLatent` and interpretation profiles.
- Update the poster renderer to respond visibly to different interpretation profiles.

Full structural analysis (rich section/motif detection) may be partially implemented and extended in future versions.

## 10. Non-goals

v0.2.1 explicitly does not aim to:
- implement full musicological segmentation;
- add loop-video;
- introduce pro-mode;
- change the core MVP user flow;
- introduce new input modalities beyond audio.

## 11. Risks and mitigation

### Risk: scope creep
- Mitigation: limit v0.2.1 to rule-based perceptual mapping and a small number of profiles.

### Risk: overfitting to specific genres
- Mitigation: design perceptual axes and profiles to generalize; test across multiple genres.

### Risk: performance and complexity
- Mitigation: keep perceptual computation lightweight and reuse audio features where possible.

## 12. Acceptance criteria

- `PerceptualLatent` is computed and stored for analyzed tracks.
- `InterpretationProfile` configs are in place and used.
- `resolve-style` produces different `RenderParams` depending on interpretation profile.
- Poster visuals visibly differ per interpretation profile while remaining tied to the audio.
- The MVP user flow remains intact.
