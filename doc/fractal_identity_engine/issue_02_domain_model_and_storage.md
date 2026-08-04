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
