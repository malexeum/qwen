# Issue 1 — Freeze MVP scope and API contracts

**Priority:** P0  
**Area:** architecture / product / backend  
**Depends on:** none

## Goal
Freeze the exact MVP scope for Fractal Identity Engine v0.2 and define the API and service boundaries before implementation starts.

## Context
The product is a web-first app with mobile support that turns sound into a fractal poster and GIF preview. Inputs are microphone live capture or MP3/WAV upload. The MVP must include audio analysis, music style suggestion, visual mood selection, 3–5 sliders, preview generation, watermark, project saving, and paid hi-res export. Loop-video, pro mode, text input, batch generation, and social publishing are out of scope for v0.2.

## Requirements
- Confirm the final MVP scenario.
- Lock the list of MVP features.
- Lock the list of post-MVP features.
- Define the exact system boundaries between analysis, style resolution, rendering, preview, export, and project storage.
- Define the API surface for the MVP.
- Define the meaning of preview vs hi-res assets.
- Define the project limit and free vs paid behavior.
- Define which parts are authoritative and which are derived.

## Proposed API surface
- `POST /upload`
- `POST /capture`
- `POST /analyze`
- `POST /resolve-style`
- `POST /generate/poster`
- `POST /export`
- `GET /project/{id}`
- `GET /project/{id}/preview`
- `GET /project/{id}/history`

## Explicit MVP scope
### In scope
- Web app as primary client.
- Mobile wrapper / companion client.
- Microphone live input.
- MP3/WAV upload.
- Server-side audio analysis.
- Auto style suggestion.
- Manual music style selection.
- Visual mood selection.
- 3–5 sliders.
- Poster preview.
- GIF preview.
- Watermarked preview assets.
- Save project.
- Up to 5 projects per user.
- Paid hi-res export.

### Out of scope
- Loop-video.
- Text input.
- Pro mode.
- Batch generation.
- Complex editor.
- Collaborative projects.
- Advanced social publishing.
- Multi-signal fusion beyond audio.

## Deliverables
- Finalized scope document.
- Final API contract.
- MVP / post-MVP split.
- Boundary diagram or short architectural note.

## Acceptance criteria
- The product can be explained in one sentence.
- Every endpoint has a clear responsibility.
- MVP vs post-MVP is unambiguous.
- Loop-video and pro features are explicitly excluded from v0.2.

## Notes
This issue must be completed before any implementation begins. If the scope is still fuzzy, the project will drift into an editor-platform monster.

---

# Issue 2 — Define domain model and storage schema

**Priority:** P0  
**Area:** architecture / backend / storage  
**Depends on:** Issue 1

## Goal
Define the domain model, entity relationships, lifecycle rules, and storage schema for the MVP so backend, renderer, and UI can share a stable data contract.

## Context
The MVP needs a minimal but durable model that separates authoritative data from derived outputs. The system must support repeated generation on the same project, style variation without re-upload, and project history with limited saved slots.

## Core entities
### Track
Authoritative sound source.
Fields:
- `id`
- `source_type` (`mic` | `file`)
- `storage_path`
- `duration_sec`
- `format`
- `created_at`
- `project_id`

### AudioAnalysis
Immutable derived analysis result.
Fields:
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

### UserPreset
User-selected parameter snapshot.
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

### GenerationJob
Stateful rendering job.
Fields:
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
Fields:
- `id`
- `job_id`
- `storage_path`
- `preview_path`
- `width`
- `height`
- `watermarked`
- `is_hi_res`

### ExportJob
Separate export workflow.
Fields:
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
Fields:
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

## Authority vs derived
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
- Preview images.
- GIF previews.
- Hi-res assets.
- Watermarked variants.

## Storage requirements
- Raw audio or file references must be stored separately.
- Derived analysis must be serializable as JSON.
- Style profiles should live in config files, not hardcoded in renderer code.
- Generated assets should be stored as files with stable references in the project model.
- Project metadata must allow reopening the project without recomputing the analysis.

## Lifecycle rules
- A project may contain multiple generations over time.
- A track may be analyzed once and reused.
- A preset may be changed without re-uploading the track.
- A generation job may fail independently of the project.
- Preview assets must not replace masters.

## Deliverables
- Entity diagram or schema sketch.
- Storage layout description.
- Field-by-field model spec.
- Lifecycle/status rules.

## Acceptance criteria
- Each entity has a clear role.
- Authoritative vs derived is unambiguous.
- Storage is sufficient to support replay and history.
- Backend, UI, and renderer can all reference the same model without interpretation drift.

## Notes
This issue should be completed before any implementation work on upload, analysis, or rendering begins. If the model is not stable, everything else will wobble.
