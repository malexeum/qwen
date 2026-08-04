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
