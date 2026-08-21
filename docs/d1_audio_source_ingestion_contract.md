# D1 reproducible audio-source ingestion contract

**Status:** design policy proposed by Issue #15.
**Scope:** source provenance before D1 extraction. This document does not ingest audio, change inventory, materialize a D1 artifact, update a manifest, or generate a poster.

## 1. Purpose and non-negotiable invariant

D1 source provenance begins with raw source bytes, not with a local command transcript. A source identity assertion is CI-verifiable only when the GitHub Actions runner can obtain the same approved immutable byte sequence and independently compute its identity.

For every approved audio source, the eventual machine-readable source record must specify:

| Field | Contract |
| --- | --- |
| `source_locator` | Repository-relative tracked path, or registry object locator without embedded credentials |
| `source_version` | Immutable Git commit/blob or Git LFS object identity; or immutable registry generation/version ID |
| `content_sha256` | Lower-case hexadecimal SHA-256 of raw source bytes, represented as `sha256:<64-hex>` |
| `byte_size_octets` | Exact raw-source length in octets (8-bit bytes) |
| `media_type` | Declared media type, e.g. `audio/mpeg`; format metadata does not replace byte identity |
| `verification_mode` | CI procedure that obtains bytes and recomputes SHA-256 and byte size |

The verifier must fail closed: an unavailable source, non-immutable reference, missing field, byte-size mismatch, digest mismatch, unsupported media type, or retrieval/authentication failure is a validation failure. CI must not substitute local paths, cached personal files, a previously copied hash, or an unverified mirror.

## 2. Candidate source modes

### A. Git-tracked source file or Git LFS object

**Locator and immutable reference.** The locator is a repository-relative path. The immutable reference is the commit SHA used by the workflow plus the Git blob identity for ordinary Git files, or the resolved Git LFS object ID for LFS-managed files. A source record binds the expected raw-byte `content_sha256` and `byte_size_octets` to that path and immutable revision.

**CI access.** GitHub Actions checks out the exact commit, including LFS objects when the source is LFS-managed, then recomputes SHA-256 and byte size from the checked-out raw file. The workflow must fail if checkout cannot resolve the object or if the file is represented only by an LFS pointer. No credentials beyond repository/LFS access available to the workflow should be required for approved public or repository-authorized sources.

**Failure behavior.** Missing path, unresolved LFS object, pointer in place of content, read error, hash mismatch, or size mismatch fails the source verification job and blocks any inventory or downstream D1 materialization dependent on that source.

**Licensing and privacy boundary.** This mode is allowed only for audio that the repository is authorized to store and distribute under the repository's licensing and access policy. Personal collections, third-party files without redistribution permission, and sources requiring private local access are excluded.

**Benefits, risks, and operational cost.** Git/Git LFS gives the shortest audit path: checkout → raw bytes → digest/size verification. It is straightforward for the first small approved corpus and supports repeatable extraction. Costs are repository/LFS quota, bandwidth, retention, access-control administration, and a one-time policy decision to store the media. Ordinary Git is appropriate only for small source files; Git LFS is the normal option for approved MP3-sized media.

### B. Immutable external object registry

**Locator and immutable reference.** The locator identifies an object in a managed registry or object store and contains no secret. The immutable reference must be an object generation/version ID, content-addressed object key, or equivalent immutable provider identifier; a mutable name such as `latest.mp3` is insufficient. The record also stores the expected raw-byte `content_sha256`, `byte_size_octets`, and `media_type`.

**CI access.** GitHub Actions obtains the immutable object with a dedicated least-privilege credential or workload identity whose read scope is limited to the approved registry namespace. Retrieval must target the immutable version directly, not a mutable alias. Credentials belong in GitHub-managed secrets or an approved identity mechanism, never in the repository, source locator, issue, PR, or artifact.

**Failure behavior.** Authorization failure, unavailable object, expired or mutable version reference, redirect to an unpinned object, digest mismatch, size mismatch, or media-type mismatch fails closed. CI logs must identify the failed contract field but must not reveal credentials or private URLs.

**Licensing and privacy boundary.** This mode is suitable for authorized sources that should not be redistributed through Git or Git LFS, including approved private/proprietary collections. Access rules, retention, deletion, jurisdiction, and licensing evidence are controlled by the registry policy. A private registry does not waive the requirement for CI to read the exact immutable bytes.

**Benefits, risks, and operational cost.** The repository remains lightweight and can scale to a large or restricted library. Operational cost is higher: storage governance, immutable-version enforcement, credential rotation, availability monitoring, egress/bandwidth control, and a robust CI access policy must exist before a source can enter a hash-verifying inventory.

## 3. Recommendation

For the first 3–4 approved audio tracks, use **Git LFS-backed repository tracking**, provided that storage size, copyright/licensing, and access policy explicitly permit it. This is the most direct reproducibility path because CI can check out exact source bytes and recompute SHA-256 and byte size without external credentials.

For a larger, private, or redistribution-restricted library, adopt an **immutable external object registry** later. Do so only after an implementation-reviewed registry contract provides version-pinned object retrieval, least-privilege CI authentication, immutable retention semantics, and fail-closed validation.

## 4. Migration path for a local-only MP3

1. **Local-only source:** keep the MP3 outside the repository; its locally observed hash is evidence for selection, not a CI-verifiable inventory assertion.
2. **Approved source registration:** confirm licensing/privacy eligibility and choose Git LFS or an immutable external registry. Register a repository-relative locator or credential-free registry locator together with an immutable reference.
3. **CI-verifiable identity:** configure the approved source location so GitHub Actions can retrieve the exact raw bytes. CI computes `sha256:<64-hex>` and `byte_size_octets` and fails closed on any discrepancy.
4. **Inventory-only PR:** only after the source verification path exists, add the source record to audio inventory and direct tests. This PR changes neither extraction nor D1 artifacts.
5. **Validated D1 artifact:** run the approved D1 extraction procedure against the CI-verifiable source and validate the resulting feature artifact.
6. **Manifest:** rebuild the canonical D1 manifest from validated feature artifacts and require byte-for-byte equality with `artifacts/d1/manifest.json`.
7. **Poster:** after explicit human visual approval, materialize the renderer-derived poster and its provenance sidecar in a separate PR when required.

## 5. Current Sunny Afternoon boundary

`tests/audio/12 - Sunny Afternoon.mp3` is absent from GitHub `main`. Consequently, GitHub Actions cannot obtain its raw bytes and cannot independently verify its SHA-256 or byte size.

Therefore, **no hash-verifying inventory-only PR is valid at this stage** for this source. Adding an inventory entry that presents a local hash as CI-verified would violate this contract. The next repository change for this track must be an approved source-ingestion PR implementing one of the source modes above; only then may an inventory-only PR register the source identity.

## 6. Definition of Done: future source-ingestion PR

A source-ingestion PR is complete only when all of the following are true:

- Licensing, redistribution, privacy, and retention eligibility is documented and approved for the source mode.
- The source has a credential-free locator and a pinned immutable version/reference.
- The source contract declares `content_sha256`, `byte_size_octets`, and `media_type`; no local filesystem assumption appears in repository content or validation.
- GitHub Actions retrieves the exact raw source bytes using repository/LFS access or a least-privilege external-registry identity.
- CI recomputes and matches SHA-256 and byte size, validates required fields, and fails closed on retrieval or identity failure.
- The PR contains no audio inventory update, D1 feature artifact, manifest update, poster, schema change, requirements change, unrelated CI change, or unrelated refactor unless a separate approved task explicitly permits it.
- A follow-up inventory-only PR is planned only after the CI-visible source identity gate is green.
- Required checks are green, the PR diff is limited to the approved ingestion contract, and architectural review accepts the provenance boundary.

## 7. Operational sequence

```text
local-only MP3
  → source-policy and eligibility approval
  → source-ingestion PR
  → CI-verifiable source identity
  → inventory-only PR
  → validated D1 feature artifact
  → canonical manifest
  → human-approved poster materialization
```

This ordering prevents a local-only fact from being promoted to a repository provenance claim before an independent CI verifier can reproduce it.
