# Technical Specification — Fractal Identity Engine MVP v0.2

## 1. Goal
Build a web-first MVP with mobile support that turns sound into a fractal poster and GIF preview. The first release must support microphone live input and MP3/WAV upload, audio analysis, style selection, 3–5 sliders, watermark preview, project saving, and paid hi-res export. Loop-video is explicitly excluded from v0.2.

## 2. Existing materials
- RFC_0.2.md defines product direction and scope.
- plan_v0_2.md defines implementation roadmap and milestones.
- issue_01_scope_and_api.md and issue_02_domain_model_and_storage.md define scope, API surface, domain model and storage contracts.
- The repository has a research-oriented core under `lib/`.

## 3. Architecture boundaries

### Separate subsystems
- Input ingestion (file upload, microphone capture).
- Audio analysis.
- Style resolution.
- Rendering.
- Watermarking.
- Export.
- Project persistence.

### Core rule
Do not mix research logic with product logic. Research concepts may inform style profiles and engine configs, but production code must consume only explicit configs and contracts.

## 4. Development strategy

Implement a vertical slice:

1. Upload / capture sound.
2. Analyze audio.
3. Resolve style.
4. Render poster preview.
5. Apply watermark.
6. Save project.
7. Export hi-res.

Loop-video, editor mode, text input, collaboration and multi-signal fusion are out of scope for v0.2.

## 5. Technology expectations

- Backend and orchestration: Python (FastAPI-style API layer, `lib/` core modules).
- Audio analysis: ready-made libraries (e.g. librosa, Essentia) wrapped in `lib/audio_analysis`.
- Style system: config-driven, with profiles in YAML/JSON under `config/style_profiles`.
- Preview rendering: browser-first, using WebGL or Canvas via `web/src/renderer/webgl_canvas.ts`.
- Hi-res rendering and export: backend-driven, deterministic.

## 6. Data contracts

All IDs are UUID v4 strings unless otherwise specified.

### Track
Authoritative sound source.

Fields:
- `id: string`
- `source_type: "mic" | "file"`
- `storage_path: string`
- `duration_sec: number`
- `format: string`
- `created_at: datetime`
- `project_id: string`

### AudioAnalysis
Immutable derived analysis.

Fields:
- `id: string`
- `track_id: string`
- `bpm: number`
- `key: string`
- `energy: number`
- `spectral_centroid: number`
- `brightness: number`
- `rhythm_density: number`
- `dynamic_range: number`
- `duration_sec: number`
- `repetition_score: number`
- `suggested_music_style: string`
- `created_at: datetime`

### StyleProfile
Declarative style config (from YAML/JSON).

Fields:
- `slug: string`
- `music_style: string`
- `visual_mood: string`
- `palette: string[]`
- `contrast: number`
- `geometry: string`
- `density: number`
- `motion_intensity: number`
- `noise_level: number`
- `symmetry_bias: number`
- `complexity_bias: number`
- `version: number`

### UserPreset
User-adjusted parameter snapshot.

Fields:
- `id: string`
- `project_id: string`
- `style_profile_slug: string`
- `complexity: number`
- `symmetry: number`
- `density: number`
- `noise: number`
- `motion: number`
- `created_at: datetime`

### GenerationJob
Rendering process state.

Fields:
- `id: string`
- `project_id: string`
- `analysis_id: string`
- `preset_id: string`
- `status: "pending" | "running" | "failed" | "completed"`
- `output_type: "poster_preview" | "poster_master" | "gif_preview"`
- `render_params: RenderParams`
- `created_at: datetime`
- `completed_at: datetime | null`
- `error_message: string | null`

### PosterAsset
Generated poster artifact.

Fields:
- `id: string`
- `job_id: string`
- `storage_path: string`
- `preview_path: string`
- `width: number`
- `height: number`
- `watermarked: boolean`
- `is_hi_res: boolean`

### ExportJob
Export process state.

Fields:
- `id: string`
- `asset_id: string`
- `format: "png" | "jpg"`
- `preset: string | null`
- `status: "pending" | "running" | "failed" | "completed"`
- `output_path: string | null`
- `download_url: string | null`
- `created_at: datetime`
- `completed_at: datetime | null`

### UserProject
Aggregate root.

Fields:
- `id: string`
- `user_id: string`
- `name: string`
- `tracks: Track[]`
- `analysis: AudioAnalysis[]`
- `presets: UserPreset[]`
- `jobs: GenerationJob[]`
- `assets: PosterAsset[]`
- `created_at: datetime`
- `updated_at: datetime`
- `project_state: string`

### RenderParams

Backend → renderer contract.

Minimal fields (can evolve, but must remain explicit):

- `seed: number`
- `iterations: number`
- `scale: number`
- `color_palette_slug: string`
- `symmetry_mode: "none" | "radial" | "mirror"`
- `noise_intensity: number`
- `density: number`
- `motion_phase: number`
- `brightness_bias: number`
- `contrast_bias: number`

RenderParams are produced by style resolution and consumed by both:

- server-side poster generator, and
- browser WebGL/Canvas preview adapter.

## 7. Backend tasks

(далее как в твоём ТЗ: 7.1–7.8: project foundation, /upload, /capture contract, /analyze, /resolve-style, /generate/poster, watermark pipeline, /export, без изменений по смыслу, но с отсылкой к файловой структуре `lib/` и `config/style_profiles`.)

## 8. Frontend tasks

(8.1–8.5 как в исходном ТЗ: первые экраны, style/mood, slider panel, preview screen, project history, с уточнением, что превью использует WebGL/Canvas и RenderParams.)

## 9. Mobile tasks

Mobile wrapper, shared backend contracts, mic access и тот же user journey.

## 10. Non-functional requirements

- Preview fast enough for playful UX.
- Styles config-driven.
- Analysis and rendering logic separable.
- Repeated generation on one project possible.
- Codebase ready for post-MVP features.



## 11. Explicit exclusions
Do not implement in v0.2:
- loop-video;
- text input;
- pro mode;
- batch generation;
- collaboration;
- advanced social publishing;
- multi-signal fusion beyond audio.

## 12. Milestone order
1. Backend skeleton and storage.
2. Upload and capture ingestion.
3. Audio analysis.
4. Style profiles and style resolver.
5. Poster renderer.
6. Watermarking.
7. Preview UI.
8. Export and monetization.
9. Project history.
10. Mobile wrapper.
11. QA and visual sanity-check.

## 13. Definition of done
The work is done when a non-technical user can:
1. Open the app.
2. Capture sound or upload a file.
3. Receive a meaningful style suggestion.
4. Adjust a few sliders.
5. See a compelling poster preview with a watermark.
6. Save the project.
7. Pay for hi-res export.

## 14. Acceptance criteria for the developer
- The implementation respects the RFC_0.2 scope.
- Issue 1 and Issue 2 are reflected in the code structure.
- No loop-video or editor logic is introduced.
- Data contracts are stable and explicit.
- The first vertical slice works end-to-end.
