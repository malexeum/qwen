# plan_v0.2.1 — Perceptual Layer Integration

## 0. Purpose
Update the v0.2 implementation plan to include the perceptual latent layer and interpretation profiles without breaking the existing MVP roadmap.

## 1. Summary of changes
- Add a `PerceptualLatent` layer between `AudioAnalysis` and `RenderParams`.
- Add `InterpretationProfile` configs to interpret perceptual axes.
- Split the style engine into perceptual and visual layers.
- Update `POST /analyze` and `POST /resolve-style` implementations.
- Adjust the poster renderer to respond to perceptual/interpretive signals.

## 2. New milestones

### M_perc_1 — PerceptualLatent minimal

**Goal:** Implement a minimal `PerceptualLatent` representation and simple mapping from `AudioAnalysis`.

Tasks:
- Extend `AudioAnalysis` with required fields (if not already present).
- Implement `PerceptualLatent` entity (table or embedded JSON).
- Implement rule-based mapping:
  - Audio features → energy, tension, density, brightness, stability, smoothness, repetition, macro_shape_hint.

### M_perc_2 — Interpretation profiles

**Goal:** Introduce interpretation profiles as configs.

Tasks:
- Define 2–3 interpretation profiles (e.g., `organic_fluid`, `geometric_rhythmic`, `dark_tense`).
- Implement config loading for interpretation profiles.
- Define mapping rules: perceptual axes → fractal parameters.

### M_perc_3 — Style engine split

**Goal:** Split style engine into perceptual and visual layers and update `resolve-style`.

Tasks:
- Refactor style engine:
  - Perceptual resolver: `AudioAnalysis` → `PerceptualLatent`.
  - Visual resolver: `PerceptualLatent` + `StyleProfile` + `InterpretationProfile` + `UserPreset` → `RenderParams`.
- Update `POST /resolve-style` to use the new flow.

### M_perc_4 — Poster renderer adaptation

**Goal:** Make the poster renderer respond visibly to perceptual/interpretive signals.

Tasks:
- Adjust `RenderParams` schema to carry perceptual/interpretive influence.
- Update renderer logic:
  - use macro/micro hints for composition and density;
  - vary symmetry, recursion depth, stochasticity based on profiles;
  - ensure each profile yields a distinct visual behavior.

## 3. Updated sequencing

Compared to plan_v0.2, we append perceptual-layer milestones between analysis and style engine completion:

1. Complete v0.2 analysis implementation.
2. M_perc_1 — implement minimal `PerceptualLatent`.
3. M_perc_2 — add interpretation profiles.
4. M_perc_3 — refactor style engine and `resolve-style`.
5. M_perc_4 — adapt poster renderer.
6. Continue with preview UI, export, project history, mobile wrapper as planned.

## 4. New issues (high-level)

- `Issue P1 — Implement PerceptualLatent`:
  - Create entity / JSON structure.
  - Implement mapping from `AudioAnalysis`.

- `Issue P2 — Add InterpretationProfiles`:
  - Create config files.
  - Implement loader and validation.

- `Issue P3 — Split StyleEngine`:
  - Refactor into perceptual + visual layers.
  - Update `resolve-style`.

- `Issue P4 — Adapt PosterRenderer`:
  - Make renderer use perceptual/interpretive params.

## 5. Estimates

Approximate additional effort:
- M_perc_1: 1–2 weeks.
- M_perc_2: 3–5 days.
- M_perc_3: 4–7 days.
- M_perc_4: 1–2 weeks (including visual iteration).

Total: ~2–3 weeks on top of the v0.2 implementation, depending on team size and parallelization.

## 6. Risks

- **Scope creep:** limit v0.2.1 to rule-based perceptual mapping and a small number of profiles.
- **Complexity:** avoid over-engineering the structural analysis; start with robust heuristics.
- **UX drift:** ensure that interpretation profiles are exposed as simple, understandable choices.

## 7. Definition of done for v0.2.1

- `PerceptualLatent` is computed and stored for analyzed tracks.
- Interpretation profiles exist and can be selected.
- `resolve-style` uses perceptual and interpretive layers to produce `RenderParams`.
- Poster visuals visibly differ between interpretation profiles for the same track.
- The MVP flow (upload → analyze → style → sliders → preview → export) remains intact.
