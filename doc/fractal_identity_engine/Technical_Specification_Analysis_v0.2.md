# Technical Specification — Audio Analysis Layer v0.2

## 1. Goal
Implement a real audio analysis layer for the Fractal Identity Engine MVP so `POST /analyze` stops being a stub and produces a meaningful `AudioAnalysis` object from uploaded audio or microphone-derived input.

## 2. Context
The backend skeleton is already available:
- FastAPI server is running.
- SQLite database is available at `data/fractal_identity.db`.
- Core project endpoints already exist.
- `POST /upload` exists.
- `POST /analyze` currently creates an empty `AudioAnalysis` placeholder.
- Stub endpoints exist for `/capture`, `/resolve-style`, `/generate/poster`, and `/export`.

This task is to replace the analysis stub with a real, deterministic, production-shaped audio feature extraction pipeline.

## 3. Scope
### In scope
- Audio feature extraction from uploaded MP3/WAV files.
- Optional support for microphone-derived analysis input through the same contract.
- Creation and persistence of `AudioAnalysis`.
- Suggested music style output.
- Status handling and error reporting for analysis jobs.
- Basic validation of input audio.

### Out of scope
- Style resolution.
- Poster rendering.
- GIF generation.
- Loop-video.
- Advanced multi-signal fusion.
- Text input.
- Pro mode.

## 4. Inputs
`POST /analyze` must accept at minimum:
- `project_id`
- `track_id`

Optional fields:
- `force_recompute`
- `analysis_mode`
- `source_hint`

The service must be able to analyze:
- uploaded audio files stored in the backend;
- microphone-derived input if available through the same project/track contract.

## 5. Required outputs
The analysis layer must create and persist an `AudioAnalysis` record with at least the following fields:
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

The endpoint response should return:
- analysis id;
- project id;
- track id;
- computed features;
- suggested style;
- status.

## 6. Feature definitions
### 6.1 BPM
Estimate tempo from onset structure or equivalent method. The implementation does not need studio-grade accuracy, but it must be stable and useful for style suggestion.

### 6.2 Key / mode
Estimate tonal center and mode if possible. If key detection is uncertain, return a clearly labeled fallback value instead of inventing precision.

### 6.3 Energy
Compute a normalized energy score from signal power or loudness-related features.

### 6.4 Spectral centroid / brightness
Compute spectral centroid and convert it into a brightness-related descriptor if needed.

### 6.5 Rhythm density
Estimate how event-dense or pulse-dense the audio is over time.

### 6.6 Dynamic range
Estimate the spread between quieter and louder segments.

### 6.7 Duration
Use file metadata or sample count / sample rate.

### 6.8 Repetition / structure score
Approximate structural repetition using simple pattern similarity, onset repetition, or frame similarity. The purpose is to support the MVP’s identity-like visual mapping, not to produce a full musicology system.

## 7. Style suggestion rules
The analysis layer must output one `suggested_music_style` based on the computed features.

Initial MVP suggestion space:
- techno
- classical
- ambient
- cinematic

The suggestion logic may be rule-based for v0.2. The rules must be explicit and maintainable.

Recommended mapping behavior:
- high BPM + high rhythm density + high energy -> techno
- low energy + high smoothness + lower rhythm density -> ambient
- wider dynamic range + moderate tempo + richer tonal variation -> cinematic
- stable tonal behavior + lower motion signature + more harmonic continuity -> classical

If the mapping is uncertain, the system may return a ranked suggestion list, but it must still produce one primary suggested style.

## 8. Determinism requirements
The same input track should produce the same analysis values within a small tolerance.

Requirements:
- no silent randomness;
- no hidden state from previous jobs;
- no data-dependent mutation of the stored track;
- any approximation or fallback must be explicit in the output.

## 9. Validation and failure handling
The layer must validate:
- project existence;
- track existence;
- supported file type;
- readable audio payload;
- minimum viable duration or sample availability.

Failure behavior:
- return a clear error response;
- persist failure state if a job record exists;
- never create a successful AudioAnalysis with empty numeric fields unless the field is explicitly marked as fallback.

## 10. Persistence rules
- `AudioAnalysis` must be stored in SQLite.
- Re-running analysis should either update through a new versioned record or replace only if `force_recompute=true` is explicitly used.
- The design should support future analysis versioning, even if v0.2 only keeps one active record per track.

## 11. Suggested implementation approach
The developer may use Python audio libraries such as:
- librosa;
- mutagen;
- pydub;
- soundfile;
- numpy/scipy.

The exact library choice is flexible, but the resulting code must remain readable and portable.

## 12. API behavior
### `POST /analyze`
Expected behavior:
1. Load the track by `track_id`.
2. Read audio from storage.
3. Extract features.
4. Compute suggested music style.
5. Save `AudioAnalysis`.
6. Return structured JSON.

Example response shape:
```json
{
  "status": "success",
  "project_id": "...",
  "track_id": "...",
  "analysis_id": "...",
  "features": {
    "bpm": 128.4,
    "key": "A minor",
    "energy": 0.82,
    "spectral_centroid": 2450.1,
    "brightness": 0.76,
    "rhythm_density": 0.71,
    "dynamic_range": 12.4,
    "duration_sec": 183.2,
    "repetition_score": 0.63
  },
  "suggested_music_style": "techno"
}
```

## 13. Architecture constraints
- Analysis must not know anything about rendering internals.
- Analysis must not create poster assets.
- Analysis must not resolve visual mood or slider values.
- The layer must only produce audio-derived facts and a style suggestion.

## 14. Logging requirements
The implementation should log:
- analysis start;
- track identifier;
- analysis duration;
- success or failure;
- fallback use if any.

Logging should be concise and suitable for debugging in command-line and server logs.

## 15. Test cases
The developer must cover at least:
- valid MP3 analysis;
- valid WAV analysis;
- unsupported file rejection;
- missing track rejection;
- repeated analysis consistency;
- suggested style output for distinct audio profiles.

## 16. Acceptance criteria
The task is complete when:
- `POST /analyze` returns a real populated `AudioAnalysis` object;
- the result is stored in SQLite;
- the suggested style is computed and returned;
- invalid input fails clearly;
- the endpoint can serve as the foundation for style resolution.

## 17. Definition of done
A non-empty analysis record must exist for a valid uploaded audio file, and the returned features must be sufficient to drive the next pipeline step: `resolve-style`.

## 18. Next dependency
This layer blocks:
- style resolver implementation;
- poster generation parameterization;
- project-level preview flow.
