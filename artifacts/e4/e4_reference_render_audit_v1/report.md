# E4 Reference Render Audit — Architect Report

**Experiment ID:** `e4_reference_render_audit_v1`  
**Status:** ✅ GATE-0 PASSED — 96/96 tests green  
**Date completed:** 2026-08-11  
**git HEAD at run:** `b3f2b775f923ca585d139f87ae3252b2f6600727`  
**Renderer version:** `ce9b03bf8e38c5e015e8c47f86b9247a8781edd8`  
**Profile library:** `0.4.0` · **Palette library:** `0.3.2`  
**Author:** AVCoder / style_engine team

---

## 1. Executive Summary

Experiment E4 establishes the first immutable reference render corpus for the `style_engine`
pipeline. 22 PNG fixtures (21 canonical + 1 smoke render) across 7 genre profiles were rendered
deterministically, provenance-signed with SHA-256, and validated across 6 test classes (96 tests).

All tests passed. The corpus is now frozen and serves as the regression baseline for all future
changes to `style_engine`, palette libraries, and morphology guard logic.

---

## 2. Scope and Motivation

### Why E4 was needed

Prior to E4, the render pipeline had no bit-exact reference outputs. Any change to a colour
mapping formula, theta-hash algorithm, or palette assignment could silently alter visual output
with no automated detection. E4 closes this gap by:

1. Defining a **typed fixture manifest** (`fixtures_manifest.yaml`) that is immutable after first
   successful render — changes require a new `experiment_id`.
2. Producing **SHA-256-signed provenance JSON** for every output, linking each PNG to the exact
   `variation_seed`, `harmony_theta`, and perceptual feature vector that produced it.
3. Running **96 determinism tests** that verify palette identity, theta-hash permutation
   invariance, morphology guard pipeline integrity, and cross-run bit-exact reproducibility.

### Design decisions recorded here

| Decision | Rationale |
|---|---|
| 3 tiers per profile (A/B/C) | Archetypal → boundary → stress; catches edge-case visual drift |
| 8-axis `harmony_theta` | Maps to the 8 harmonic tension dimensions of the music model |
| Theta hash **order-invariant** | Theta axes are semantically unordered; hash must not depend on list order |
| Provenance recovery on resume | If PNG exists but JSON is missing (interrupted run), harness reconstructs provenance from disk SHA rather than re-rendering |
| `variation_seed` from prime sequence | Avoids seed correlation; each fixture is statistically independent |

---

## 3. Fixture Corpus

### 3.1 Genre × Tier matrix

| Profile | Palette | Tier A seed | Tier B seed | Tier C seed | Macro shape (C) |
|---|---|---|---|---|---|
| `ambient` | `lunar_mist` | 104 729 | 209 467 | 314 219 | surge |
| `blues_jazz` | `warm_midnight` | 419 861 | 524 309 | 628 741 | surge |
| `classical` | `ivory_cobalt` | 733 183 | 837 617 | 942 061 | surge |
| `electronic` | `neon_dark` | 1 046 507 | 1 150 943 | 1 255 379 | surge |
| `jazz` | `nocturne_amber` | 1 359 823 | 1 464 259 | 1 568 699 | surge |
| `pop` | `vivid_light` | 1 673 141 | 1 777 577 | 1 882 013 | surge |
| `rock` | `dark_saturated` | 1 986 451 | 2 090 891 | 2 195 329 | surge |
| `default` *(smoke)* | `neutral_noir` | 2 299 769 | — | — | neutral |

**Observation:** Tier C of every genre converges to `macro_shape_hint: surge`. This is intentional —
stress fixtures maximise `tension`, `noise_proxy`, and `section_complexity` simultaneously
to probe the upper envelope of the morphology guard.

### 3.2 Perceptual feature ranges

| Dimension | Tier A range | Tier C range | Notes |
|---|---|---|---|
| `energy` | 0.25 – 0.80 | 0.35 – 0.98 | rock_C reaches 0.98 — near saturation |
| `tension` | 0.15 – 0.65 | 0.75 – 0.95 | jazz_C 0.88, electronic_C 0.90 |
| `stability` | 0.55 – 0.80 | 0.05 – 0.25 | Tier C collapses stability — deliberate |
| `smoothness` | 0.50 – 0.85 | 0.05 – 0.30 | Same collapse pattern |
| `noise_proxy` | 0.10 – 0.40 | 0.78 – 0.95 | Primary stress driver |
| `section_complexity` | 0.20 – 0.55 | 0.85 – 0.98 | rock_C 0.98 — maximum |

### 3.3 Theta-axis spread (A→C)

Tier A fixtures cluster theta values near [0.45–0.65] on all 8 axes (genre centroid).  
Tier B introduces ≥2 axes that diverge by ≥0.25 from A (boundary condition).  
Tier C pushes axes to near-binary extremes (0.05/0.95), maximising harmonic tension contrast.

The most extreme Tier C vectors:
- `rock_C`: `[0.95, 0.05, 0.95, 0.05, 0.05, 0.95, 0.60, 0.40]`
- `electronic_C`: `[0.95, 0.10, 0.92, 0.08, 0.05, 0.95, 0.75, 0.65]`
- `jazz_C`: `[0.12, 0.88, 0.10, 0.90, 0.88, 0.12, 0.70, 0.30]`

Note that jazz_C and rock_C are near-complementary on axes 0–5: jazz favours low/high alternation
while rock pushes high/low. This is a useful future test for palette cross-contamination.

---

## 4. Test Suite Results

### 4.1 Summary

```
96 passed · 0 failed · 0 errors
Platform: win32, Python 3.14.0, pytest 9.1.1
Duration: 1.23 s
```

### 4.2 Test classes

| Class | Tests | Scope | Result |
|---|---|---|---|
| `T1 PaletteJazzIdentity` | 7 | jazz → nocturne_amber; blues_jazz → warm_midnight; registry existence | ✅ |
| `T2 ThetaHashPermutation` | 7 | Order invariance, value sensitivity, format, determinism | ✅ |
| `T3 MorphologyGuardPipeline` | 11 | base/perceptual/user stages; guard at low and high values | ✅ |
| `P1 ProvenanceExists` | 1 | All 22 JSON files present on disk | ✅ |
| `P2 NoPlaceholder` | 22 | SHA-256 values are real (non-placeholder) | ✅ |
| `P3 HashMatchesPNG` | 22 | SHA-256 in JSON matches actual PNG on disk | ✅ |
| `P4 SeedDeterminism` | 22 | Re-rendering from seed reproduces identical output | ✅ |
| `P5 UniqueOutputs` | 1 | No two fixtures share the same SHA-256 | ✅ |
| `P6 RerenderIdentity` | 3 | ambient_A/B/C: bit-exact re-render match | ✅ |

### 4.3 Notable incident

During Run A (initial), the harness crashed mid-write on `ambient_A`, leaving a valid PNG but no
provenance JSON. Run B introduced **provenance recovery**: if PNG exists but JSON is missing, the
harness reconstructs JSON from disk SHA instead of re-rendering. This made the run fully
idempotent/resumable without touching the PNG corpus.

`P1 test_all_provenance_files_present` caught the missing file in Run A (1 FAILED out of 96).
After recovery it passed in Run B (96/96). This validates the provenance integrity test design.

---

## 5. Architecture Implications

### 5.1 This corpus is now the regression baseline

Any future change to `style_engine` that alters the visual output of any of the 22 fixtures is a
**regression** and must be caught by a gate test before merge. The recommended E5 test structure:

```
test_e5_regression.py
  TestRegressionGate
    test_no_sha_regression[<fixture_id>]   # bit-exact: must match E4 SHA
    test_ssim_above_threshold[<fixture_id>] # perceptual: SSIM >= 0.995
```

The SHA gate catches unintended bit-level changes. The SSIM gate allows intentional visual
improvements that are reviewed and explicitly re-baselined.

### 5.2 Re-baselining protocol

When a deliberate visual change is approved:

1. Create new `experiment_id` (e.g. `e5_reference_render_v2`)
2. Re-run full harness → 22 new PNGs + provenance
3. Gate tests pass against new baseline
4. Old E4 corpus is **archived, not deleted** — it documents the design history

### 5.3 Palette coverage

6 palettes are exercised across the canonical 21 fixtures:

| Palette | Fixtures |
|---|---|
| `lunar_mist` | ambient_A/B/C |
| `warm_midnight` | blues_jazz_A/B/C |
| `ivory_cobalt` | classical_A/B/C |
| `neon_dark` | electronic_A/B/C |
| `nocturne_amber` | jazz_A/B/C |
| `vivid_light` | pop_A/B/C |
| `dark_saturated` | rock_A/B/C |
| `neutral_noir` | default_smoke (smoke only) |

Every palette is exercised at 3 stress levels. **Gap:** `neutral_noir` has only 1 fixture (smoke).
If the default profile becomes production-relevant, add A/B/C fixtures in a follow-up experiment.

### 5.4 Morphology guard boundary

`T3` confirms that the guard pipeline correctly fires on the `high_guard` condition and modifies
≥1 visual parameter, while leaving palette assignment unchanged. This is the critical invariant:
the guard is a **visual parameter limiter**, not a re-palette operation. Any future change to the
guard that touches palette must fail this test and require explicit architectural review.

### 5.5 Theta hash invariance

`T2` confirms the hash is order-invariant across 4 random permutations. This is required because
audio feature extraction may return theta axes in arbitrary order depending on the analysis window.
The hash function must be treated as a **set hash**, not a sequence hash. Current implementation
uses sorted-value SHA-256 — acceptable for now, but consider a canonical axis-name→value map if
axis semantics are ever made explicit in the schema.

---

## 6. Open Items and Recommendations

| ID | Priority | Item |
|---|---|---|
| E5-R1 | **High** | Implement perceptual regression gate (SSIM ≥ 0.995) on the 21 canonical fixtures |
| E5-R2 | **High** | Replace `feature_hash: sha256:placeholder_*` with real audio feature hashes when audio corpus is available |
| E5-R3 | **Medium** | Add ambient_A/B/C to `P6 RerenderIdentity` (currently only 3 fixtures covered; extend to all 21) |
| E5-R4 | **Medium** | Add `neutral_noir` canonical fixtures (default_A/B/C) when default profile is production-bound |
| E5-R5 | **Low** | Consider axis-named theta map (`{"valence": 0.55, "tension": 0.60, ...}`) for schema v1.1 to make theta semantics explicit |
| E5-R6 | **Low** | Add `jazz_C` vs `rock_C` cross-contamination test (near-complementary theta vectors, different palettes — validates palette isolation) |

---

## 7. Artifacts

| Artifact | Path | Description |
|---|---|---|
| Fixture manifest | `artifacts/e4/fixtures_manifest.yaml` | Immutable. 22 fixtures, schema v1.0 |
| Audit matrix | `artifacts/e4/e4_reference_render_audit_v1/audit_matrix.csv` | Per-fixture render summary |
| Provenance JSON | `artifacts/e4/e4_reference_render_audit_v1/provenance/<profile>/<id>.json` | SHA-256, seed, git HEAD, params |
| PNG renders | `artifacts/e4/e4_reference_render_audit_v1/*.png` | 22 reference images |
| Contact sheet | `artifacts/e4/e4_reference_render_audit_v1/contact_sheet.png` | Visual overview, all 22 |
| This report | `artifacts/e4/e4_reference_render_audit_v1/report.md` | You are here |
| Gate-0 tests | `test14_e4_gate0.py`, `test14_e4_provenance.py` | 96 tests, all green |

---

*E4 closed. Next: E5 perceptual regression gate.*
