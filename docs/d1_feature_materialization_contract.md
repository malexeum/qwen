# D1 feature-artifact materialization contract

## Scope

D1-D.2 materializes previously validated in-memory `D1FeatureArtifact` objects. It does not create official fixture artifacts in the repository, generate PNG, modify E4, or alter feature semantic identity.

## Layout

A caller-controlled existing root may contain:

```text
<root>/
  manifest.json
  features/<analysis_id>.json
```

Feature paths are derived only as `features/<analysis_id>.json`. `analysis_id` must match `^[A-Za-z0-9][A-Za-z0-9_-]*$`. Absolute paths, dot components, slash, backslash, Unicode filename components, and traversal are rejected. The resolved target must remain below the resolved root.

## Feature envelope

Each feature object contains only:

```text
semantic_payload
feature_sha256
git_sha
```

Before writing, the writer recomputes `feature_sha256` from the canonical semantic payload and rejects forged or mutated artifacts. Existing feature objects are immutable: a write to an existing target raises `FileExistsError`.

## Atomicity and durability

Writes use a unique temporary sibling file, file flush and `fsync`, then `os.replace`. This keeps replacement on one filesystem boundary. The temporary file is removed after any failure.

On POSIX, the writer additionally fsyncs the parent directory after replacement, providing durable directory metadata. On Windows, the writer provides file fsync plus atomic `os.replace`; directory metadata fsync is unavailable through this portable stdlib path, so post-replace durability is best effort.

All writer-produced JSON bytes use LF; writers reject output containing carriage returns.

## Manifest

`manifest.json` is a mutable deployment index, not a feature object. It is rebuilt completely from a validated full sequence of artifacts, sorted by `analysis_id`, then atomically replaced. It is never appended or partially edited.

Each manifest entry has `analysis_id`, a relative POSIX `relative_path`, and `feature_sha256`. Duplicate analysis IDs, paths, or hashes are rejected. The manifest is excluded from feature semantic hash preimages.