# RFC_0.2 — Fractal Identity Engine MVP

## 1. Purpose
Build a playful but mathematically honest web+mobile product that turns sound into a unique fractal visual identity: a poster plus a GIF preview. The product must feel simple to use, support both live microphone input and uploaded audio files, and leave room for future expansion into text and other signal types.

## 2. Product goal
The MVP must let any user get a beautiful, unique fractal visual from sound in a few minutes, then optionally save the project and buy a hi-res export. The core value is not “generic AI art”, but a stable mapping from audio structure to a visually coherent fractal identity.

## 3. User flow
1. User opens the app.
2. User chooses sound input: microphone live or audio file upload.
3. Server analyzes the audio and produces `AudioAnalysis`.
4. App suggests a music style or lets the user choose it manually.
5. User selects a visual mood.
6. User adjusts 3–5 sliders.
7. App renders a low-res preview poster and a short GIF preview.
8. User can save the project, share it, or buy hi-res export.

## 4. Scope of MVP
### In scope
- Web app as the primary client.
- Mobile app as a thin wrapper / companion client.
- Microphone live input using Web Audio API.
- Audio upload for MP3 and WAV.
- Server-side audio analysis in Python.
- Fractal poster generation.
- GIF preview generation.
- Watermark on preview assets.
- Up to 5 saved projects per user.
- Paid hi-res export.

### Out of scope
- Text-to-fractal input.
- Full pro mode for studios.
- Batch processing.
- Complex editor.
- Collaborative projects.
- Advanced social publishing tools.
- Deep multi-signal fusion beyond audio for the MVP.

## 5. Target audience
- Casual users who have sound and want a visual artifact.
- Musicians, DJs, podcasters, and streamers.
- People who want an avatar, poster, cover, or visual to share.

The product positioning for v0.2 is “toy for everyone”: easy, playful, and a little magical, but still grounded in clear signal-to-visual logic.

## 6. Product principles
- Keep the first flow simple.
- Preserve a mathematically traceable relationship between sound and visual output.
- Make the visual result feel unique per input.
- Keep style controls understandable for non-experts.
- Separate analysis, rendering, and export.
- Make preview first, hi-res later.
- Design for a path from MVP to pro mode without rewriting the core.

## 7. Functional requirements
### 7.1 Input
The system must accept:
- Live microphone stream.
- Uploaded MP3/WAV files.

### 7.2 Audio analysis
The backend must compute an `AudioAnalysis` JSON object with at least:
- BPM.
- Key / mode.
- Energy.
- Spectral centroid / brightness.
- Rhythm density.
- Dynamic range.
- Duration.
- Repetition / structure score.

### 7.3 Style selection
The user must be able to:
- Accept an auto-suggested musical style.
- Or choose a style manually.
- Then select a visual mood.

### 7.4 Sliders
The MVP must support 3–5 visible controls:
- Complexity.
- Symmetry.
- Density.
- Noise.
- Motion.

### 7.5 Output
The system must generate:
- Poster preview in PNG/JPG low-res.
- GIF preview loop.
- Watermarked preview versions.
- Optional hi-res poster export.

### 7.6 Project history
The user must be able to save and revisit up to 5 projects in the MVP.

## 8. Domain model
### Track
Authoritative source of the uploaded or live sound.
- `id`
- `source_type` (`mic` | `file`)
- `storage_path`
- `duration_sec`
- `format`
- `created_at`
- `project_id`

### AudioAnalysis
Derived immutable analysis result.
- `id`
- `track_id`
- `bpm`
- `key`
- `energy`
- `spectral_centroid`
- `brightness`
- `rhythm_density`
- `dynamic_range`
- `duration_sec`
- `repetition_score`
- `suggested_music_style`
- `created_at`

### StyleProfile
Declarative style config.
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

### UserPreset
User-adjustable parameter snapshot.
- `id`
- `project_id`
- `style_profile_slug`
- `complexity`
- `symmetry`
- `density`
- `noise`
- `motion`
- `created_at`

### GenerationJob
Stateful generation process.
- `id`
- `project_id`
- `analysis_id`
- `preset_id`
- `status`
- `output_type`
- `render_params`
- `created_at`
- `completed_at`
- `error_message`

### PosterAsset
Generated poster artifact.
- `id`
- `job_id`
- `storage_path`
- `preview_path`
- `width`
- `height`
- `watermarked`
- `is_hi_res`

### ExportJob
Separate export process for shareable assets.
- `id`
- `asset_id`
- `format`
- `preset`
- `status`
- `output_path`
- `download_url`
- `created_at`
- `completed_at`

### UserProject
Aggregate root.
- `id`
- `user_id`
- `name`
- `tracks[]`
- `analysis[]`
- `presets[]`
- `jobs[]`
- `assets[]`
- `created_at`
- `updated_at`
- `project_state`

## 9. Authority vs derived
### Authoritative
- UserProject.
- Track metadata.
- StyleProfile.
- UserPreset.
- GenerationJob status.
- ExportJob status.

### Derived
- AudioAnalysis.
- Render params.
- Poster previews.
- GIF previews.
- Hi-res assets.
- Watermarked variants.

The system must never treat derived results as if they were primary truth.

## 10. Architecture overview
### Server side
Python backend must handle:
- upload and project creation;
- audio analysis;
- style resolution;
- poster generation;
- export;
- project storage.

### Client side
Web app must handle:
- microphone capture;
- live preview flow;
- file upload;
- style and mood selection;
- sliders;
- preview screen;
- project history;
- paid export interaction.

### Mobile
Mobile app should be a thin client on top of the same backend and the same product logic. It may use native mic access and local caching, but it must not fork the core rendering logic.

## 11. Pipeline
`Upload / Mic Capture → Validate → Analyze → Suggest Style → Choose Mood → Adjust Sliders → Resolve Render Params → Generate Poster Preview → Apply Watermark → Export / Save Project`

The pipeline must remain linear in MVP and must not turn into an editor graph.

## 12. API surface
- `POST /upload`
- `POST /capture`
- `POST /analyze`
- `POST /resolve-style`
- `POST /generate/poster`
- `POST /export`
- `GET /project/{id}`
- `GET /project/{id}/preview`
- `GET /project/{id}/history`

## 13. Style engine
The style engine must treat style as a config, not as a hardcoded branch. Each style profile combines a music style hint and a visual mood profile. The final render parameters must be a blend of:
- audio-derived features,
- selected style profile,
- user sliders.

## 14. Rendering model
The MVP rendering core should be a fractal renderer capable of producing poster images from parameterized fractal logic such as Mandelbrot, Julia, IFS-like structures, or other mathematically coherent families. The renderer may run in the browser for preview and on the server for export, but both must use the same parameter contract.

## 15. Watermark and monetization
Preview assets must include a watermark. Hi-res export must be a paid action in the MVP. The free tier may allow a limited number of daily or monthly generations and up to 5 projects.

## 16. Data storage
The system must store:
- raw audio or file references;
- audio analysis JSON;
- style profiles;
- user presets;
- generation jobs;
- poster assets;
- preview images;
- export jobs;
- project metadata.

## 17. Non-functional requirements
- Fast preview generation.
- Clear and simple UX.
- Deterministic behavior for the same input and same preset where possible.
- Separate concerns between analysis, rendering, and export.
- Future compatibility with text inputs and pro mode.
- Stable low-friction mobile support.

## 18. Success criteria
The MVP is successful if a user can:
1. Open the app.
2. Load sound from microphone or file.
3. Get a meaningful style suggestion.
4. Adjust a few sliders without confusion.
5. Receive a visually coherent poster preview and GIF preview.
6. Save a project.
7. Pay for hi-res export.

If the user wants to share the result, the visual should be compelling enough to do that without explanation.

## 19. Future extensions
After MVP, the system may add:
- text input;
- richer pro mode;
- batch generation;
- more advanced mobile features;
- expanded visual families;
- multi-signal support beyond audio.

## 20. Open questions
- Which preview renderer is fastest and most stable for browser use?
- Should microphone live mode be fully local or partly server-assisted?
- Which output formats are best for v0.2 preview and share?
- What is the minimal set of styles that still feels playful and useful?
- Should hi-res export happen synchronously or via background job?
