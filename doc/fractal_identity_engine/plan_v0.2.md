# plan_v0.2 — Fractal Identity Engine MVP

## 0. Purpose
This plan translates `RFC_0.2.md` into an implementation roadmap. The MVP is a web-first product with mobile support that turns sound into a fractal poster and GIF preview, with microphone live input, file upload, style selection, sliders, watermark, and paid hi-res export.

## 1. Delivery strategy
We should build the MVP in thin vertical slices. Each slice must produce something visible and testable, so we can verify the user flow early and avoid spending weeks on invisible infrastructure.

### Core rule
Do not build the loop-video pipeline in v0.2. Keep the first release focused on poster + GIF preview only.

## 2. Milestones
### Milestone A — Product and architecture freeze
Goal: lock the MVP scope, data contracts, and service boundaries.

Deliverables:
- Finalized RFC.
- Domain model.
- API contract.
- Storage contract.
- Style engine contract.
- MVP / post-MVP split.

Exit criteria:
- Team can describe the product in one sentence.
- No feature outside RFC_0.2 is required to start implementation.

### Milestone B — Backend skeleton
Goal: create the minimal backend foundation.

Deliverables:
- Project creation.
- File upload endpoint.
- Audio capture ingestion endpoint placeholder.
- Project retrieval endpoint.
- Preview metadata endpoint.
- Storage structure for raw audio and generated assets.

Exit criteria:
- A project can be created and retrieved.
- Uploaded audio is persisted.

### Milestone C — Audio analysis
Goal: extract stable audio features from file or capture input.

Deliverables:
- BPM extraction.
- Key / mode extraction.
- Energy.
- Spectral centroid / brightness.
- Rhythm density.
- Dynamic range.
- Duration.
- Repetition / structure score.
- Suggested music style.

Exit criteria:
- Analysis JSON is deterministic enough for repeated runs on the same input.
- Analysis is stored as derived immutable data.

### Milestone D — Style engine
Goal: connect audio analysis, visual mood, and user sliders into render parameters.

Deliverables:
- Style profile configs.
- Music style and visual mood mapping.
- Slider-to-parameter mapping.
- Render parameter resolver.
- Auto style suggestion logic.

Exit criteria:
- Same analysis can produce different render params depending on style and sliders.
- Styles remain config-driven.

### Milestone E — Poster renderer
Goal: render a low-res poster preview and hi-res export master.

Deliverables:
- Fractal rendering core.
- Browser or server preview rendering path.
- Poster preview asset generation.
- Watermark overlay on preview.
- Hi-res poster master export path.

Exit criteria:
- A user can generate a poster preview for at least one style.
- Poster output visibly changes with parameters.

### Milestone F — Preview UI
Goal: deliver the first complete product loop.

Deliverables:
- Upload / capture screen.
- Style selection screen.
- Mood selection screen.
- Sliders panel.
- Preview screen.
- Save project action.
- Export action.

Exit criteria:
- A user can go from input to preview without developer intervention.

### Milestone G — Export and monetization
Goal: enable paid hi-res export and basic project limits.

Deliverables:
- Export job pipeline.
- Download URLs.
- Watermarked free preview exports.
- Paid hi-res export gate.
- Free project limit.

Exit criteria:
- User can pay to unlock hi-res export.
- Free-tier limits are enforced.

### Milestone H — Mobile support
Goal: wrap the web product for mobile and ensure microphone access works well.

Deliverables:
- Mobile shell / wrapper.
- Native microphone access if needed.
- Shared backend integration.
- Mobile preview flow.

Exit criteria:
- Mobile client can complete the same core flow.

## 3. Workstreams
### 3.1 Product / UX
Responsibilities:
- Define the user flow.
- Simplify language on screens.
- Ensure the interface stays playful and not technical.
- Decide which controls are visible first.

### 3.2 Backend
Responsibilities:
- Upload and capture ingestion.
- Audio analysis.
- Style resolution.
- Rendering orchestration.
- Storage and project history.
- Export jobs.

### 3.3 Renderer
Responsibilities:
- Fractal parameterization.
- Poster rendering.
- GIF preview generation.
- Watermark pipeline.
- Deterministic render contract.

### 3.4 Mobile
Responsibilities:
- Mic access.
- Input capture.
- Upload flow.
- Preview experience.
- Native wrapper integration.

## 4. Feature breakdown
### MVP features
- Microphone live input.
- MP3/WAV upload.
- Server-side audio analysis.
- Auto style suggestion.
- Manual music style selection.
- Visual mood selection.
- 3–5 sliders.
- Low-res poster preview.
- GIF preview.
- Watermark on free preview.
- Project saving.
- Up to 5 projects per user.
- Paid hi-res export.

### Post-MVP features
- Text input.
- Loop video.
- Pro mode.
- Batch generation.
- Collaborative projects.
- Multi-signal fusion.
- Social publishing tools.

## 5. Sequencing
### Phase 1
- Freeze RFC.
- Finalize contracts.
- Define style profiles.
- Confirm storage model.

### Phase 2
- Build backend skeleton.
- Add upload and capture ingestion.
- Add project storage.

### Phase 3
- Implement audio analysis.
- Validate analysis JSON.
- Add suggested style logic.

### Phase 4
- Build style resolver.
- Add slider mapping.
- Test style variation behavior.

### Phase 5
- Implement poster renderer.
- Add watermark.
- Generate preview assets.

### Phase 6
- Build preview UI.
- Connect save project flow.
- Connect export flow.

### Phase 7
- Add paid hi-res export.
- Enforce free-tier limits.
- Harden project history.

### Phase 8
- Wrap for mobile.
- Validate microphone behavior.
- Polish responsive UX.

## 6. Dependencies
### Hard dependencies
- Audio analysis before style resolution.
- Style resolution before rendering.
- Rendering before preview/export.
- Preview before paid hi-res conversion.
- Project storage before history UI.

### Soft dependencies
- Watermarking can be integrated during renderer or export.
- Mobile wrapper can start after web preview is stable.

## 7. Risks
### Product risks
- Too many controls make the MVP feel technical.
- Too few controls make it feel shallow.
- If the preview is weak, the product loses the "wow" moment.

### Technical risks
- Browser preview rendering may be slower than expected.
- Audio analysis may vary too much across different inputs.
- Fractal rendering may need optimization for mobile devices.
- Hi-res export can become a bottleneck if not isolated.

### Scope risks
- Loop-video can easily sneak back into v0.2.
- Pro mode can distract from the first release.
- Text-to-fractal can pull the team into a second product.

## 8. Time estimate
### Minimal MVP
- RFC and contracts: 1–2 days.
- Backend skeleton: 2–4 days.
- Audio analysis: 3–7 days.
- Style engine: 4–8 days.
- Poster renderer: 4–8 days.
- Preview UI: 3–6 days.
- Export / monetization: 2–5 days.
- Project history: 1–3 days.
- QA / fixes: 3–6 days.

### Total
- Fast but realistic: 3–5 weeks.
- Safe and polished: 5–7 weeks.

## 9. Definition of done
The MVP is done when a non-technical user can:
1. Open the app.
2. Capture sound or upload a file.
3. Get a style suggestion.
4. Adjust a few sliders.
5. See a compelling poster preview.
6. Save the project.
7. Pay for hi-res export.

## 10. Immediate next tasks
1. Confirm final MVP scope.
2. Freeze style profile list.
3. Decide on browser preview renderer.
4. Define storage layout.
5. Break work into GitHub Issues.
6. Start with backend skeleton and audio analysis.
