# D1 render-seed contract

`lib.style_engine.seed_policy.compute_render_variation_seed` is the public API for the StyleEngine render variation seed.

## Source of truth

The adapter delegates directly to `lib.style_engine.engine._compute_variation_seed`. It must not implement an independent hash, truncation rule, random-number generator seed policy, or field-ordering policy.

## Render identity

The public API accepts exactly these explicit identity components:

- `project_id`
- `analysis_id`
- `preset_id`
- `style_slug`
- `interpretation_slug`
- `theta_values`

`theta_values` is copied at the adapter boundary so the production call receives an ordinary mapping detached from caller-side mutation. The production engine owns validation and canonical treatment of its values.

## Output

The production contract returns a deterministic unsigned 32-bit Python integer, suitable for the render variation path.

## Separation from provenance

`feature_hash` and file hashes belong to provenance identity. They are intentionally not parameters of this render-seed API unless the production engine contract itself changes. This prevents a provenance extension from silently changing the visual-variation seed.

## Compatibility

The former `compute_variation_seed(profile_slug, feature_sha256, canonical_theta_hash)` function was removed because it encoded a separate 64-bit SHA-256 policy and did not match the production StyleEngine contract. New callers must use `compute_render_variation_seed`.
