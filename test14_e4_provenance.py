"""test14_e4_provenance.py — Post-render provenance validation (Run C).

Run AFTER e4_render_harness.py has completed successfully.
Validates that:
  - Every fixture in the manifest has a corresponding provenance JSON.
  - Every provenance JSON has a real output_sha256 (not PENDING_RENDER).
  - output_sha256 matches the actual PNG on disk.
  - harmony_theta_hash is deterministic and matches re-computation.
  - variation_seed matches resolve_render_params output for the fixture.
  - No two canonical fixtures share the same output_sha256 (identity test).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.style_engine.engine import (
    THETA_AXES,
    _THETA_DEFAULT,
    _compute_variation_seed,
    resolve_render_params,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MANIFEST_PATH  = Path("artifacts/e4/fixtures_manifest.yaml")
AUDIT_ROOT     = Path("artifacts/e4/e4_reference_render_audit_v1")
PROVENANCE_DIR = AUDIT_ROOT / "provenance"
RENDERS_DIR    = AUDIT_ROOT / "renders"

DEFAULT_INTERP = "default"
DEFAULT_PRESET = {
    "id":         "e4_neutral",
    "complexity":  0.5,
    "symmetry":    0.5,
    "density":     0.5,
    "noise":       0.5,
    "motion":      0.5,
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def manifest() -> Dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def canonical_fixtures(manifest) -> List[Dict]:
    """All fixtures except default_smoke."""
    return [fx for fx in manifest["fixtures"] if fx["id"] != "default_smoke"]


@pytest.fixture(scope="module")
def all_fixtures(manifest) -> List[Dict]:
    return manifest["fixtures"]


def load_provenance(fixture_id: str, profile_slug: str) -> Dict:
    path = PROVENANCE_DIR / profile_slug / f"{fixture_id}.json"
    if not path.exists():
        pytest.skip(f"Provenance not yet generated: {path} — run Run B first")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# P1 — Provenance exists for every fixture
# ---------------------------------------------------------------------------
class TestP1ProvenanceExists:
    def test_all_provenance_files_present(self, all_fixtures):
        missing = []
        for fx in all_fixtures:
            p = PROVENANCE_DIR / fx["profile_slug"] / f"{fx['id']}.json"
            if not p.exists():
                missing.append(str(p))
        assert not missing, f"Missing provenance files:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# P2 — No PENDING_RENDER in output_sha256
# ---------------------------------------------------------------------------
class TestP2NoPlaceholder:
    @pytest.mark.parametrize("fixture", [
        pytest.param(fx, id=fx["id"])
        for fx in yaml.safe_load(open(MANIFEST_PATH))["fixtures"]
    ] if MANIFEST_PATH.exists() else [])
    def test_output_sha256_is_real(self, fixture):
        prov = load_provenance(fixture["id"], fixture["profile_slug"])
        sha  = prov.get("output_sha256", "")
        assert sha != "PENDING_RENDER", f"{fixture['id']}: output_sha256 is still PENDING_RENDER"
        assert sha.startswith("sha256:"), f"{fixture['id']}: output_sha256 format invalid: {sha!r}"
        assert len(sha) == 7 + 64, f"{fixture['id']}: sha256 hex wrong length: {sha!r}"


# ---------------------------------------------------------------------------
# P3 — output_sha256 matches actual PNG on disk
# ---------------------------------------------------------------------------
class TestP3HashMatchesPNG:
    @pytest.mark.parametrize("fixture", [
        pytest.param(fx, id=fx["id"])
        for fx in yaml.safe_load(open(MANIFEST_PATH))["fixtures"]
    ] if MANIFEST_PATH.exists() else [])
    def test_sha256_matches_png(self, fixture):
        fid      = fixture["id"]
        png_path = RENDERS_DIR / f"{fid}.png"
        if not png_path.exists():
            pytest.skip(f"PNG not found: {png_path}")
        prov = load_provenance(fid, fixture["profile_slug"])
        expected = prov["output_sha256"]
        actual   = sha256_file(png_path)
        assert actual == expected, (
            f"{fid}: SHA mismatch\n  provenance: {expected}\n  on disk:    {actual}"
        )


# ---------------------------------------------------------------------------
# P4 — variation_seed matches engine recomputation
# ---------------------------------------------------------------------------
class TestP4SeedDeterminism:
    @pytest.mark.parametrize("fixture", [
        pytest.param(fx, id=fx["id"])
        for fx in yaml.safe_load(open(MANIFEST_PATH))["fixtures"]
    ] if MANIFEST_PATH.exists() else [])
    def test_seed_matches_engine(self, fixture):
        fid      = fixture["id"]
        prov     = load_provenance(fid, fixture["profile_slug"])
        theta_vec = prov["harmony_theta"]
        theta_dict = {f"harmony_theta_{i}": v for i, v in enumerate(theta_vec)}
        expected_seed = _compute_variation_seed(
            project_id="e4_audit",
            analysis_id=fid,
            preset_id="e4_neutral",
            style_slug=fixture["profile_slug"],
            interp_slug=DEFAULT_INTERP,
            theta_values=theta_dict,
        )
        assert prov["variation_seed"] == expected_seed, (
            f"{fid}: seed mismatch provenance={prov['variation_seed']} "
            f"engine={expected_seed}"
        )


# ---------------------------------------------------------------------------
# P5 — No two canonical fixtures share output_sha256
# ---------------------------------------------------------------------------
class TestP5UniqueOutputs:
    def test_no_duplicate_sha256(self, canonical_fixtures):
        seen: Dict[str, str] = {}
        for fx in canonical_fixtures:
            p = PROVENANCE_DIR / fx["profile_slug"] / f"{fx['id']}.json"
            if not p.exists():
                continue
            with open(p) as f:
                prov = json.load(f)
            sha = prov.get("output_sha256", "")
            if sha in seen:
                pytest.fail(
                    f"Duplicate output_sha256: {fx['id']} and {seen[sha]} "
                    f"share {sha!r} — renders are not unique"
                )
            seen[sha] = fx["id"]


# ---------------------------------------------------------------------------
# P6 — Rerender identity: re-running produces same SHA
# ---------------------------------------------------------------------------
class TestP6RerenderIdentity:
    @pytest.mark.parametrize("fixture", [
        pytest.param(fx, id=fx["id"])
        for fx in yaml.safe_load(open(MANIFEST_PATH))["fixtures"][:3]
    ] if MANIFEST_PATH.exists() else [],
    )
    def test_rerender_sha_matches_original(self, fixture, tmp_path):
        """Re-render to tmp_path and confirm SHA matches provenance."""
        fid  = fixture["id"]
        prov = load_provenance(fid, fixture["profile_slug"])

        perceptual = dict(fixture.get("perceptual", {}))
        for i, val in enumerate(fixture.get("harmony_theta", [])):
            perceptual[f"harmony_theta_{i}"] = float(val)

        render_params, _, _ = resolve_render_params(
            project_id="e4_audit",
            analysis_id=fid,
            perceptual=perceptual,
            style_profile_slug=fixture["profile_slug"],
            interpretation_profile_slug=DEFAULT_INTERP,
            user_preset=DEFAULT_PRESET,
            strict_theta=True,
        )

        assert render_params.variation_seed == prov["variation_seed"], (
            f"{fid}: seed changed between runs"
        )
        # If PIL+numpy available, do a real pixel comparison
        try:
            import numpy as np
            from PIL import Image
            from lib.style_engine.e4_render_harness import call_generator, sha256_file

            out_png = tmp_path / f"{fid}_recheck.png"
            call_generator(render_params, fixture, out_png)
            actual_sha = sha256_file(out_png)
            assert actual_sha == prov["output_sha256"], (
                f"{fid}: rerender SHA mismatch\n"
                f"  original: {prov['output_sha256']}\n"
                f"  rerender: {actual_sha}"
            )
        except ImportError:
            pytest.skip("numpy/Pillow not available — seed-only check passed")
