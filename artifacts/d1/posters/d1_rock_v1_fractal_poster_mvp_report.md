# D1 Rock Polaroid Poster MVP Report

## Status

Canonical poster MVP materialized from the approved D1 Rock Polaroid visual contract.

## Validated D1 provenance

- Analysis ID: d1_rock_v1.
- Source registry path: tests/audio/Rock.mp3.
- Canonical theta hash: sha256:5e2ac5e7a4c1151d.
- Feature SHA-256: sha256:814b21fcdf5ae5a1e11172aa2301cd781f2d76446c436e27498902a9cebe81b4.
- Seed SHA-256: sha256:b5c1931e5db5b59dc358db78076f273e2c7c05c2fd79cafa4dfd23f73479a625.
- Canonical SVG SHA-256: sha256:6c419e76b497bd3678a418e6250fb998f1500fcdb3020e620612fcc1ce4673a3.

## Artistic interpretation

The poster is a deterministic artistic interpretation bound to the validated D1 identity. It is not an audio spectrogram, a measured fractal property, a Lyapunov measurement, or a scientific visualization of the track.

The approved composition consists of a literal hexagon junction at (540, 360) px; incoming cyan, gold and magenta branches; theta trajectories originating at the junction; a layered fading cyan after-trace; one subtle split-drift-return-fade accent in the secondary materiality layer; and deterministic quiet-space materiality.

## Output contract

- SVG is canonical: storage/posters/d1_rock_v1_fractal_poster.svg.
- Sidecar metadata contains the SVG SHA-256; the SVG does not self-contain its own derived hash.
- PNG files are local immutable raster derivatives generated through the explicit local rsvg-convert executable. Their bytes are not asserted cross-platform byte-canonical.
- Preview raster: PNG, 1080x1260 px.
- Final raster: PNG, 1528x1783 px, preserving the rounded 6:7 full-canvas ratio.

## SHA-256 inventory

- storage/posters/d1_rock_v1_fractal_poster.svg | sha256:6c419e76b497bd3678a418e6250fb998f1500fcdb3020e620612fcc1ce4673a3 | 20933 bytes.
- storage/posters/d1_rock_v1_fractal_poster.metadata.json | sha256:64ff3374bc6e20cb4f1b160f2bc1c50d134f549396b48e6f2d06663c2f429e01 | 2653 bytes.
- storage/posters/d1_rock_v1_fractal_poster_preview_1080.png | sha256:86946683fe42025ffb93a79fd0b252ba41c1267fb4a2de24d5fe575c53ae333f | 200634 bytes.
- storage/posters/d1_rock_v1_fractal_poster_final_1528.png | sha256:c347afa3489f4fe4838f1d46461bfa7d0f674c480e58e345b90ba10c4a43f3ab | 328138 bytes.

## Verification

- SVG viewBox verified as 0 0 1080 1260.
- SVG to sidecar SHA-256 linkage verified.
- SVG does not self-contain its derived SHA-256.
- Preview and final PNG format/dimensions verified locally.
