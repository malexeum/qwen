# Technical Specification — Style Engine v0.2.1

## 1. Scientific and design background

### 1.1 Hierarchy of musical representation

In music theory and style analysis, style is treated as a system of interconnected levels: timbre, form, mode/tonality, meter/tempo, harmony, rhythm, texture, and syntax. Effective style analysis starts from coarse outer layers (instrumentation, form, mode, tempo) and then moves to inner layers (harmony, rhythm, motivic structure). This multi-level approach aligns with our macro/meso/micro-form concept for visual identity. [web:120][web:122][web:133]

### 1.2 Perceptual features as a separate layer

In music information retrieval and perceptual music research, audio processing is often structured as:

`audio → low-level features → perceptual features → semantic description`.

Low-level features include signal level, spectrum, MFCCs, and event rates. Perceptual features correspond to human-understandable concepts such as speed/tempo, beat strength, rhythmic regularity, meter, mode, harmonic complexity, tonal stability, and “motional qualities” (movement, tension). [web:132]

This maps directly to our split:
- `AudioAnalysis` stores low-level and structural features.
- `PerceptualLatent` stores perceptual features: energy, tension, density, brightness, stability, smoothness, repetition, etc.

### 1.3 Style and latent spaces

Modern deep-learning-based music generators often separate style into a latent space or high-level embedding, distinct from raw sequence data. This latent space captures style-related attributes and allows interpolation and control. Perceptual features are seen as a human-readable projection of that latent space. [web:125][web:129]

Our `PerceptualLatent` plays this role, and `InterpretationProfile` defines how to read this latent space into visual control parameters for the fractal engine.

## 2. Role of the style engine in v0.2.1

### 2.1 Place in the pipeline

The style engine sits between analysis and rendering:

`AudioAnalysis → PerceptualLatent → StyleEngine → RenderParams → PosterRenderer`.

Within the style engine we distinguish:
- Perceptual resolver: `AudioAnalysis → PerceptualLatent` (mostly implemented by analysis layer).
- Visual resolver: `PerceptualLatent + StyleProfile + InterpretationProfile + UserPreset → RenderParams`.

### 2.2 Goals

The style engine must:
- map perceptual features to visual control parameters in a **declarative**, **config-driven** way;
- make style choices explainable via the chain:
  `audio → AudioAnalysis → PerceptualLatent → InterpretationProfile + StyleProfile → RenderParams → Poster`;
- support multiple interpretation profiles that change how the same track is visualized;
- respect user sliders as a final, controllable adjustment layer.

## 3. Data contracts

### 3.1 Inputs

The core style engine code must operate on the following inputs:

- `AudioAnalysis` (extended v0.2.1 model).
- `PerceptualLatent` (minimal set of axes implemented in P1).
- `StyleProfile` (music style + visual mood config).
- `InterpretationProfile` (perceptual mapping config).
- `UserPreset` (user slider values).

Optionally, the style engine may receive:
- `project_id`
- `analysis_id`
- `variation_seed`

### 3.2 Outputs

The style engine must output `RenderParams`, a deterministic, serializable object containing at least:

- `style_profile_slug`
- `interpretation_profile_slug`
- `preset_id`
- `symmetry_bias`
- `recursion_depth`
- `density_level`
- `noise_level`
- `motion_intensity`
- `palette_id`
- `stochastic_term`
- `layout_macro_shape`
- `texture_complexity`
- `variation_seed`

This object will be stored with `GenerationJob` and used by the poster renderer.

## 4. Entities and configs

### 4.1 StyleProfile

`StyleProfile` is a declarative config describing music style and visual mood.

Fields:
- `slug`
- `music_style`
- `visual_mood`
- `palette`
- `contrast`
- `geometry`
- `density`
- `motion_intensity`
- `noise_level`
- `symmetry_bias`
- `complexity_bias`
- `version`

Implementation:
- YAML/JSON configs in `config/style_profiles/*.yaml`.
- Loader that reads all profiles at startup into a registry keyed by `slug`.

### 4.2 InterpretationProfile

`InterpretationProfile` defines how perceptual axes influence visual controls.

Fields:
- `slug`
- `name`
- `description`
- `axis_weights` (for energy, tension, density, brightness, stability, smoothness, repetition)
- `mapping_rules` describing how axes influence:
  - `symmetry_bias`
  - `recursion_depth`
  - `density_level`
  - `noise_level`
  - `motion_intensity`
  - `palette_id`
  - `stochastic_term`
  - `layout_macro_shape`
  - `texture_complexity`

Implementation:
- YAML/JSON configs in `config/interpretation_profiles/*.yaml`.
- Loader with validation and runtime registry keyed by `slug`.

### 4.3 UserPreset

`UserPreset` holds user slider values.

Fields:
- `id`
- `project_id`
- `style_profile_slug`
- `complexity`
- `symmetry`
- `density`
- `noise`
- `motion`
- `created_at`

Implementation:
- Stored in SQLite.
- Accessible by `preset_id` or by `(project_id, style_profile_slug)`.

### 4.4 RenderParams

`RenderParams` captures all parameters the renderer needs. It is not a DB table by default, but it may be stored as JSON in `GenerationJob`.

Fields:
- `style_profile_slug`
- `interpretation_profile_slug`
- `preset_id`
- `symmetry_bias`
- `recursion_depth`
- `density_level`
- `noise_level`
- `motion_intensity`
- `palette_id`
- `stochastic_term`
- `layout_macro_shape`
- `texture_complexity`
- `variation_seed`

## 5. /resolve-style API

### 5.1 Request

`POST /resolve-style` must accept JSON:

```json
{
  "project_id": "...",
  "analysis_id": "...",
  "style_profile_slug": "techno_futuristic",
  "interpretation_profile_slug": "organic_fluid",
  "preset_id": "...",
  "override_sliders": {
    "complexity": 0.7,
    "symmetry": 0.5,
    "density": 0.8,
    "noise": 0.3,
    "motion": 0.4
  }
}
```

Rules:
- `project_id` and `analysis_id` are required.
- `style_profile_slug` is required unless a default can be derived from `suggested_music_style`.
- `interpretation_profile_slug` is required, but a default (e.g., `organic_fluid`) must exist.
- `preset_id` is optional; if missing, a new `UserPreset` may be created.
- `override_sliders` is optional; values, if present, override stored preset values.

### 5.2 Response

On success, return:

```json
{
  "status": "success",
  "project_id": "...",
  "analysis_id": "...",
  "generation_job_id": "...",
  "style_profile_slug": "techno_futuristic",
  "interpretation_profile_slug": "organic_fluid",
  "render_params": {
    "symmetry_bias": 0.4,
    "recursion_depth": 0.8,
    "density_level": 0.7,
    "noise_level": 0.3,
    "motion_intensity": 0.4,
    "palette_id": "neon_blue",
    "stochastic_term": 0.25,
    "layout_macro_shape": "ABA_like",
    "texture_complexity": 0.6,
    "variation_seed": 123456
  }
}
```

On error, return a structured error with a clear reason (`unknown_style_profile`, `unknown_interpretation_profile`, `missing_analysis`, etc.).

## 6. Style engine behavior

### 6.1 Perceptual resolver

The perceptual resolver is responsible for ensuring that a `PerceptualLatent` exists for the given `analysis_id`:

- If `PerceptualLatent` exists in DB, load it.
- If not, compute it from `AudioAnalysis` via the `build_perceptual_latent` function (as specified in the analysis spec) and store it.

This ensures that older projects can still be upgraded to v0.2.1 behavior.

### 6.2 Visual resolver

Core function:

```python
def resolve_render_params(
    perceptual,
    style_profile,
    interpretation_profile,
    user_preset
) -> RenderParams:
    ...
```

The visual resolver must combine three layers:

1. **Base style layer (StyleProfile)**
   - Initialize default values for:
     - `symmetry_bias`
     - `recursion_depth`
     - `density_level`
     - `noise_level`
     - `motion_intensity`
     - `palette_id`
     - `stochastic_term`
   - These defaults represent the baseline visual mood for the chosen style.

2. **Perceptual interpretation layer (PerceptualLatent + InterpretationProfile)**
   - Use `axis_weights` and `mapping_rules` to adjust base parameters.
   - Example mapping (illustrative):
     - High `energy` and `density` → increase `recursion_depth` and `density_level`.
     - High `tension` → increase `stochastic_term` and reduce `symmetry_bias`.
     - High `brightness` → pick brighter `palette_id` and adjust `contrast`.
     - High `stability` and `smoothness` → increase `symmetry_bias`, decrease `noise_level`.
     - High `repetition` and `section_complexity` → increase `texture_complexity`, choose `layout_macro_shape` reflecting repeated motifs.

   - The implementation should be explicit and readable, not a black-box ML model.

3. **User control layer (UserPreset)**
   - Apply sliders as final adjustments:
     - `complexity` → affects `recursion_depth` and `texture_complexity`.
     - `symmetry` → adjusts `symmetry_bias`.
     - `density` → adjusts `density_level`.
     - `noise` → adjusts `noise_level`.
     - `motion` → adjusts `motion_intensity`.

   - Slider influence should be bounded and predictable (e.g., within a certain range around the base/perceptual values).

### 6.3 Determinism and seeds

- The style engine must be deterministic given the same inputs.
- `variation_seed` should be computed from stable identifiers, for example:

```python
variation_seed = hash((project_id, analysis_id, preset_id,
                       style_profile.slug, interpretation_profile.slug))
```

- No hidden randomness is allowed in this layer.

## 7. Error handling and fallbacks

- If `StyleProfile` is missing → return `error: unknown_style_profile`.
- If `InterpretationProfile` is missing → use a default profile and log a warning.
- If `PerceptualLatent` cannot be created → fall back to a simplified mapping from `AudioAnalysis` only, but clearly mark this in logs and, if possible, in a debug field.
- If `UserPreset` is missing → create a default preset with neutral slider values.

## 8. Logging

The style engine should log:
- input identifiers (`project_id`, `analysis_id`, style/interpretation slugs);
- key perceptual axes used;
- selected profile names;
- summarized `RenderParams` (at least in debug mode);
- any fallbacks or missing configs.

Logs should be concise and useful for debugging calibration of profiles and mappings.

## 9. Test cases

Minimum test scenarios:

1. **Basic flow**
   - Valid project, track, analysis.
   - Known `StyleProfile` and `InterpretationProfile`.
   - Existing preset.
   - `/resolve-style` returns `RenderParams` and creates a `GenerationJob`.

2. **Default interpretation profile**
   - No `interpretation_profile_slug` provided.
   - Default profile is used.

3. **Missing PerceptualLatent**
   - No stored `PerceptualLatent`.
   - Engine computes it on the fly and proceeds.

4. **Different interpretation profiles**
   - Same track and style, two different interpretation profiles.
   - `RenderParams` differ in a way consistent with profile definitions.

5. **Slider influence**
   - Same inputs, different `UserPreset` slider values.
   - `RenderParams` reflect slider changes in a controlled manner.

## 10. Acceptance criteria

The style engine implementation is considered complete when:

- `/resolve-style`:
  - reads `AudioAnalysis` and `PerceptualLatent` for the given `analysis_id`;
  - loads `StyleProfile` and `InterpretationProfile` from configs;
  - applies `UserPreset` sliders;
  - produces a populated `RenderParams` object;
  - creates a `GenerationJob` with `render_params` stored and `status = pending`.

- Different interpretation profiles for the same track and preset produce different `RenderParams` that align with profile descriptions.
- The explainability chain `audio → AudioAnalysis → PerceptualLatent → InterpretationProfile + StyleProfile → RenderParams → Poster` can be reconstructed from logs and stored metadata.
