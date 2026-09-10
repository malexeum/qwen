# AVCoder: pipeline и контракты

## Цель

Воспроизводимо переводить аудиотрек в объяснимую визуальную интерпретацию:

Audio → inventory identity → D1 perceptual extraction → canonical feature artifact → composition mapping → fractal poster output.

Этот документ фиксирует канонический контракт репозитория, различает инженерную диагностику от production pipeline и отделяет v7 baseline от эксперимента v8.

## Единственный пользовательский launcher

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
.\tools\run_four_track_fractal_posters.ps1
```

или напрямую:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_four_track_fractal_posters.ps1
```

## Входы и источник истины

- Inventory: `corpus/inventory/audio_source_inventory.v1.json`
- Canonical source set:
  - `08. Monkberry Moon Delight.mp3`
  - `12 - Sunny Afternoon.mp3`
  - `19 - Picture Book.mp3`
  - `Road_Trip.mp3`
- Decoder: FFmpeg.
- Virtual environment: `.venv\Scripts\python.exe`.

## Каноническая цепочка

```text
MP3
→ inventory resolution (path + byte_size + sha256)
→ D1 feature extraction
→ canonical d1_feature_artifact/v2
→ semantic_payload
→ renderer-specific composition mapping
→ poster.fractal.svg
→ metadata sidecar
→ diagnostics JSON
→ batch_manifest.json
```

## Что нельзя использовать как input постера

`parameters.diagnostic_local.json` и другие инженерные diagnostic JSONs не являются входом для рендерера. Они используются только для локальной диагностики и не проходят strict read_feature_artifact() validation.

Это важно, потому что:

- диагностический JSON имеет другой контракт;
- он не содержит canonical `source_locator` и `feature_sha256` для `d1_feature_artifact/v2`;
- он не проходит validation в `lib.d1_feature_artifact_io.read_feature_artifact()`;
- он не должен быть подменой canonical artifact pipeline.

## Canonical artifact contract

`d1_feature_artifact/v2` remains the only valid canonical artifact for the renderer pipeline.

Canonical artifact includes:

- `schema_version`
- `analysis_id`
- `source_identity`
- `source_locator`
- `perceptual`
- `bridge`
- `encoder`
- `named_theta`
- `canonical_theta_hash`
- `feature_sha256`
- `git_sha`

The exact artifact file is written to each source subfolder under `features/d1_rock_v1.json` and then consumed by the renderer.

## Output contract

For each source:

```text
<output>/<source_slug>/
  features/
    d1_rock_v1.json
  poster.fractal.svg
  poster.fractal.metadata.json
  diagnostics.json
```

At root:

```text
batch_manifest.json
```

## Batch manifest contract

The root manifest must include:

- `schema_version`
- `generated_at_utc`
- `source_count`
- `status`
- per-source entries with source name, registry path, output dir, artifact hashes, svg hashes, and metadata hashes

## Validation checklist

- Exactly four non-empty `poster.fractal.svg` files are created.
- SVG output does not contain `DIAGNOSTIC LOCAL`, `NOT A SPECTROGRAM`, or `eight_axis_scalar_bar_map` markers.
- Every artifact is readable by `read_feature_artifact()`.
- Every source status is `ok`.
- Manifest hashes match the actual files.

## Status of renderer v7

v7 is a valid engineering baseline, not a canonical aesthetic final state.

It is useful because it:

- provides reproducibility and provenance;
- validates the extraction and canonical artifact path;
- helps guard against regressions;
- is an engineering baseline, not the final visual identity target.

The next experimental branch is `rock_visual_identity_v8`.

## Experiment: rock_visual_identity_v8

The v8 experiment must preserve the canonical extraction and artifact contract.

The v8 change is limited to macro-composition mapping and output styling, while keeping:

- `d1_feature_artifact/v2` unchanged;
- the v7 batch canonical pipeline unchanged;
- v7 provenance and hash logic intact.

The experiment should operate as a versioned renderer that consumes the same canonical artifact and resolves a deterministic composition mode from the semantic payload.

Planned mode families:

- `monolithic`
- `kinetic_break`
- `recursive_grove`
- `fragmented_signal`

The selection should be based on semantic indicators such as:

- tension
- harmonic_stability
- harmonic_change_rate
- texture_complexity
- recursion_depth
- section_complexity
- noise_level
- symmetry_bias

The macro mapping should change high-level visual structure only:

- junction position
- flow angle
- visual mass count
- branch count
- recursion levels
- symmetry
- density
- materiality
- palette ratio

This keeps the extraction layer canonical while allowing materially different poster worlds in the v8 rendering layer.
