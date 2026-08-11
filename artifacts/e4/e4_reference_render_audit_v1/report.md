# E4 Reference Render Audit — Run Report

**experiment_id:** `e4_reference_render_audit_v1`  
**status:** PENDING — Run B not yet executed  
**fixtures:** 21 canonical + 1 default smoke  

---

## How to Run

```bash
python -m lib.style_engine.e4_render_harness \
  --manifest artifacts/e4/fixtures_manifest.yaml \
  --output artifacts/e4/e4_reference_render_audit_v1
```

Optional flags:
- `--dry-run` — resolve RenderParams only, no PNG output
- `--rerender` — force re-render even if PNG exists
- `--generators lib.generators` — use real generator module

## Validate After Run B

```bash
python -m pytest test14_e4_provenance.py -v
```

---

## Results

> _This section is populated by Commit C after Run B completes._

| Fixture | Profile | Seed | SHA-256 (short) | Elapsed |
|---------|---------|------|------------------|---------|
| — | — | — | — | — |

## Rerender Identity Check

> _3 fixtures re-rendered post-Run B to verify determinism._

| Fixture | Original SHA | Rerender SHA | Match |
|---------|-------------|--------------|-------|
| — | — | — | — |

---

*Commit A: fixtures frozen. Commit B: renders + provenance. Commit C: this report filled in.*
