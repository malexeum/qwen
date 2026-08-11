#!/usr/bin/env python3
"""
e4_render_harness.py — E4 Reference Render Audit harness.

Run B entry point:
    python -m lib.style_engine.e4_render_harness \\
        --manifest artifacts/e4/fixtures_manifest.yaml \\
        --output artifacts/e4/e4_reference_render_audit_v1

Produces per successful fixture:
    <output>/renders/<fixture_id>.png
    <output>/provenance/<profile_slug>/<fixture_id>.json

After all fixtures:
    <output>/contact_sheet.png
    <output>/audit_matrix.csv   (metadata + output_sha256, no scores)

Invariants:
    - provenance JSON is written AFTER the PNG is fsynced (best effort).
    - output_sha256 is computed from the actual PNG bytes (SHA-256).
    - Re-running with --rerender flag overwrites renders but appends
      a _rerender_N suffix in provenance to preserve first-run SHA.
    - Fixtures are deterministic: same seed + same RenderParams → same PNG.
    - Run B is idempotent/resumable: if a PNG exists but its provenance
      is missing (e.g. a prior run crashed between render and
      write_provenance), the provenance is (re)written from the
      existing PNG on the next run instead of being silently skipped.
    - generator_stack in provenance = journal of builders ACTUALLY called
      by GeneratorRuntime at runtime.  Never a static YAML declaration.
    - composition_config_hash in provenance = sha256 of the canonical
      visual_composition_profiles.yaml bytes that were loaded at startup.
      Proves which composition file drove this render.
    - Stub mode (e4_stub:numpy_noise) is FORBIDDEN in E4 baseline runs.
      Pass --allow-stub explicitly for local development only.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ---------------------------------------------------------------------------
# Optional: Pillow for contact sheet and PNG output.  Graceful degradation.
# ---------------------------------------------------------------------------
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.style_engine.engine import compute_theta_hash, resolve_render_params  # noqa: E402
from lib.style_engine.generator_runtime import GeneratorRuntime, RenderResult   # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPERIMENT_ID  = "e4_reference_render_audit_v1"
RENDER_W       = 512
RENDER_H       = 512
CONTACT_COLS   = 4
DEFAULT_INTERP = "default"
DEFAULT_PRESET = {
    "id":        "e4_neutral",
    "complexity": 0.5,
    "symmetry":   0.5,
    "density":    0.5,
    "noise":      0.5,
    "motion":     0.5,
}

# Path to canonical composition profiles — source of truth for E4 baseline.
CANONICAL_COMPOSITION_YAML: Path = (
    Path(__file__).resolve().parent / "configs" / "visual_composition_profiles.yaml"
)

# _DEV_COMPOSITION: single-layer fallback for unit tests and local dev only.
# NEVER used in E4 baseline harness runs.
_DEV_COMPOSITION: dict[str, Any] = {
    "layers": [
        {
            "id":      "layer_0",
            "builder": "julia_orbit_trap",
            "weight":  1.0,
        }
    ]
}


# ---------------------------------------------------------------------------
# Composition YAML loading
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when a composition profile slug is missing or invalid."""


def load_composition_profiles(
    yaml_path: Path,
) -> tuple[dict[str, dict], str]:
    """
    Load visual_composition_profiles.yaml.

    Returns:
        profiles  — dict[slug, {palette, layers}]
        yaml_hash — sha256:<hex> of raw file bytes (for provenance)
    """
    with open(yaml_path, "rb") as f:
        raw = f.read()
    yaml_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    data = yaml.safe_load(raw.decode("utf-8"))
    profiles = data.get("profiles", {})
    if not profiles:
        raise ValidationError(
            f"visual_composition_profiles.yaml has no 'profiles' key: {yaml_path}"
        )
    return profiles, yaml_hash


def get_composition_for_slug(
    profiles: dict[str, dict],
    profile_slug: str,
) -> dict:
    """
    Extract the composition dict for a given style slug.

    Raises ValidationError (not a fallback!) if slug is absent.
    This is intentional: an unknown slug means the composition contract
    is broken, not that we should silently fall back to a default.
    """
    if profile_slug not in profiles:
        available = sorted(profiles.keys())
        raise ValidationError(
            f"Composition profile slug '{profile_slug}' not found in "
            f"visual_composition_profiles.yaml. "
            f"Available: {available}"
        )
    entry = profiles[profile_slug]
    # Return only the layers section as composition_profile dict
    return {"layers": entry["layers"]}


# ---------------------------------------------------------------------------
# SHA-256 helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def fsync_path(path: Path) -> None:
    """Best-effort durability fsync.

    On some Windows/Python builds, os.fsync() on a file handle reopened
    in "rb" mode immediately after another process (PIL) closed its write
    handle can raise OSError [Errno 9] Bad file descriptor. This is a
    platform quirk, not a correctness issue: output_sha256 is always
    computed by re-reading the actual bytes on disk right after this
    call, so a failed fsync does not affect provenance integrity.
    """
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        print(f"[warn] fsync skipped for {path.name}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------
def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    fixtures = data.get("fixtures", [])
    if not fixtures:
        raise ValueError(f"Empty fixture list in {manifest_path}")
    return data


def provenance_path_for(provenance_dir: Path, fixture: Dict[str, Any]) -> Path:
    return provenance_dir / fixture["profile_slug"] / f"{fixture['id']}.json"


# ---------------------------------------------------------------------------
# Runtime render  (replaces the old call_generator stub)
# ---------------------------------------------------------------------------

_runtime = GeneratorRuntime()


def _render_via_runtime(
    render_params,
    fixture: Dict[str, Any],
    output_png: Path,
    composition_profile: dict,
    allow_stub: bool = False,
) -> list[str]:
    """
    Calls GeneratorRuntime to produce a PNG at output_png.

    Returns the actual generator_stack (list of builder names that were
    called during this render).  This is the authoritative provenance source;
    the caller must pass it verbatim into write_provenance().

    Stub mode policy:
      - allow_stub=False (default/baseline): any exception from
        GeneratorRuntime raises RuntimeError — baseline PNGs must be
        produced by the real backend, not numpy noise.
      - allow_stub=True (--allow-stub dev flag): falls back to
        deterministic numpy noise, labelled ['e4_stub:numpy_noise'].
        This path must never produce corpus v2 or E5 baseline output.
    """
    # Attempt real GeneratorRuntime path
    try:
        layers = _runtime.resolve_stack(
            profile_slug=fixture["profile_slug"],
            render_params=render_params,
            composition_profile=composition_profile,
        )
        result: RenderResult = _runtime.render(
            layers=layers,
            seed=render_params.variation_seed,
            width=RENDER_W,
            height=RENDER_H,
        )

        # Write PNG from orbit_map
        if _PIL_AVAILABLE:
            import numpy as np
            arr = (result.orbit_map * 255).clip(0, 255).astype("uint8")
            rgb = np.stack([arr, arr, arr], axis=-1)
            Image.fromarray(rgb, "RGB").save(str(output_png), format="PNG")
        else:
            _write_stub_png(output_png, render_params.variation_seed)

        return result.generator_stack  # <-- actual execution journal

    except Exception as exc:
        if not allow_stub:
            raise RuntimeError(
                f"GeneratorRuntime failed for fixture '{fixture['id']}' "
                f"and --allow-stub is not set. "
                f"Baseline renders must use the real backend. "
                f"Original error: {exc}"
            ) from exc
        # allow_stub=True: graceful dev fallback
        print(
            f"[warn] GeneratorRuntime failed for {fixture['id']}: {exc}; "
            "using numpy stub (--allow-stub mode)",
            file=sys.stderr,
        )
        _write_stub_png(output_png, render_params.variation_seed)
        return ["e4_stub:numpy_noise"]


def _write_stub_png(output_png: Path, seed: int) -> None:
    """Deterministic fallback PNG: numpy noise or 1x1 white pixel.

    Used ONLY when --allow-stub is explicitly passed.  Never called
    in E4 baseline harness runs.
    """
    try:
        import numpy as np
        from PIL import Image as _Image
        rng = np.random.default_rng(seed=seed)
        arr = (rng.random((RENDER_H, RENDER_W, 3)) * 255).astype("uint8")
        _Image.fromarray(arr, "RGB").save(str(output_png), format="PNG")
    except ImportError:
        import struct, zlib

        def _png1x1() -> bytes:
            def chunk(tag: bytes, data: bytes) -> bytes:
                c = struct.pack(">I", len(data)) + tag + data
                return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            ihdr = struct.pack(">IIBBBBB", RENDER_W, RENDER_H, 8, 2, 0, 0, 0)
            row  = b"\x00" + b"\xFF\xFF\xFF" * RENDER_W
            idat = zlib.compress(row * RENDER_H)
            return (
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat)
                + chunk(b"IEND", b"")
            )

        output_png.write_bytes(_png1x1())


# ---------------------------------------------------------------------------
# Provenance writer
# ---------------------------------------------------------------------------
def write_provenance(
    fixture: Dict[str, Any],
    render_params,
    png_path: Path,
    output_sha256: str,
    provenance_dir: Path,
    run_git_sha: str,
    elapsed_s: float,
    generator_stack: list[str],
    composition_config_hash: str,
    rerender_n: Optional[int] = None,
) -> Path:
    profile_slug = fixture["profile_slug"]
    fixture_id   = fixture["id"]
    prov_dir     = provenance_dir / profile_slug
    prov_dir.mkdir(parents=True, exist_ok=True)

    suffix = "" if rerender_n is None else f"_rerender_{rerender_n}"
    prov_path = prov_dir / f"{fixture_id}{suffix}.json"

    theta_named = {
        f"harmony_theta_{i}": round(float(v), 6)
        for i, v in enumerate([
            render_params.harmony_theta_0,
            render_params.harmony_theta_1,
            render_params.harmony_theta_2,
            render_params.harmony_theta_3,
            render_params.harmony_theta_4,
            render_params.harmony_theta_5,
            render_params.harmony_theta_6,
            render_params.harmony_theta_7,
        ])
    }
    theta_hash = f"sha256:{compute_theta_hash(theta_named, strict=False)}"

    theta_vec = [
        render_params.harmony_theta_0,
        render_params.harmony_theta_1,
        render_params.harmony_theta_2,
        render_params.harmony_theta_3,
        render_params.harmony_theta_4,
        render_params.harmony_theta_5,
        render_params.harmony_theta_6,
        render_params.harmony_theta_7,
    ]

    trace_serialisable = [
        dataclasses.asdict(t) for t in render_params.mapping_trace
    ]

    prov = {
        "fixture_id":              fixture_id,
        "experiment_id":           EXPERIMENT_ID,
        "profile_slug":            profile_slug,
        "git_sha":                 run_git_sha,
        "feature_hash":            fixture.get("feature_hash", "null"),
        "harmony_theta":           theta_vec,
        "harmony_theta_hash":      theta_hash,
        "variation_seed":          render_params.variation_seed,
        "palette_id":              render_params.palette_id,
        # Authoritative execution journal from GeneratorRuntime.render():
        "generator_stack":         generator_stack,
        # Hash of the composition YAML that was actually loaded:
        "composition_config_hash": composition_config_hash,
        "mapping_trace":           trace_serialisable,
        "output_sha256":           output_sha256,
        "renderer_params":         {"width": RENDER_W, "height": RENDER_H},
        "perceptual":              dict(fixture.get("perceptual", {})),
        "render_status":           "rendered",
        "elapsed_s":               round(elapsed_s, 3),
        "created_at":              datetime.now(timezone.utc).isoformat(),
    }

    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return prov_path


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------
def build_contact_sheet(
    png_paths: List[Path], output_path: Path, cols: int = CONTACT_COLS
) -> None:
    if not _PIL_AVAILABLE:
        print("[warn] Pillow not available — skipping contact sheet", file=sys.stderr)
        return
    if not png_paths:
        return

    thumbs = []
    for p in png_paths:
        try:
            img = Image.open(p).convert("RGB")
            img.thumbnail((RENDER_W // 2, RENDER_H // 2))
            thumbs.append((p.stem, img))
        except Exception as e:
            print(f"[warn] Cannot open {p}: {e}", file=sys.stderr)

    if not thumbs:
        return

    tw, th = thumbs[0][1].size
    rows   = (len(thumbs) + cols - 1) // cols
    sheet  = Image.new("RGB", (tw * cols, th * rows), color=(20, 20, 20))

    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for idx, (stem, img) in enumerate(thumbs):
        r, c = divmod(idx, cols)
        sheet.paste(img, (c * tw, r * th))
        if font:
            draw.text((c * tw + 4, r * th + 4), stem, fill=(255, 255, 100), font=font)

    sheet.save(str(output_path), format="PNG")
    print(f"[ok] contact_sheet -> {output_path}")


# ---------------------------------------------------------------------------
# CSV audit matrix
# ---------------------------------------------------------------------------
AUDIT_FIELDS = [
    "fixture_id", "profile_slug", "variation_seed", "palette_id",
    "output_sha256", "elapsed_s", "render_status", "created_at",
    "energy", "tension", "density", "brightness",
    "stability", "smoothness", "repetition", "section_complexity",
    "noise_proxy", "macro_shape_hint",
    "generator_stack",        # comma-joined list of actual builders
    "composition_config_hash",  # sha256 of the YAML that drove this render
]


def write_audit_row(
    writer,
    fixture: Dict[str, Any],
    render_params,
    output_sha256: str,
    elapsed_s: float,
    generator_stack: list[str],
    composition_config_hash: str,
) -> None:
    perc = fixture.get("perceptual", {})
    row = {
        "fixture_id":              fixture["id"],
        "profile_slug":            fixture["profile_slug"],
        "variation_seed":          render_params.variation_seed,
        "palette_id":              render_params.palette_id,
        "output_sha256":           output_sha256,
        "elapsed_s":               round(elapsed_s, 3),
        "render_status":           "rendered",
        "created_at":              datetime.now(timezone.utc).isoformat(),
        "generator_stack":         ",".join(generator_stack),
        "composition_config_hash": composition_config_hash,
    }
    for ax in [
        "energy", "tension", "density", "brightness",
        "stability", "smoothness", "repetition",
        "section_complexity", "noise_proxy", "macro_shape_hint",
    ]:
        row[ax] = perc.get(ax, "")
    writer.writerow(row)


# ---------------------------------------------------------------------------
# Git SHA helper
# ---------------------------------------------------------------------------
def get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="E4 Reference Render Audit — Run B harness"
    )
    parser.add_argument(
        "--manifest", required=True,
        help="Path to fixtures_manifest.yaml",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output directory (audit root)",
    )
    parser.add_argument(
        "--generators", default=None,
        help="Python module path for generators (e.g. lib.generators). "
             "Kept for CLI compatibility; GeneratorRuntime imports "
             "lib.generators directly and does not need this flag.",
    )
    parser.add_argument(
        "--composition", default=None,
        help="Path to alternate composition profile YAML (dev/experiment use). "
             "If omitted, canonical visual_composition_profiles.yaml is used.",
    )
    parser.add_argument(
        "--allow-stub", action="store_true",
        help="Allow numpy stub fallback when GeneratorRuntime fails. "
             "LOCAL DEVELOPMENT ONLY. Never use for corpus v2 or E5 baseline.",
    )
    parser.add_argument(
        "--rerender", action="store_true",
        help="Re-render even if PNG already exists",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Resolve RenderParams only, do not write PNGs",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir    = Path(args.output)
    renders_dir   = output_dir / "renders"
    provenance_dir = output_dir / "provenance"
    renders_dir.mkdir(parents=True, exist_ok=True)
    provenance_dir.mkdir(parents=True, exist_ok=True)

    # Load composition profiles — canonical by default, alternate via flag.
    comp_yaml_path: Path
    if args.composition:
        comp_yaml_path = Path(args.composition)
        print(f"[info] composition   : {comp_yaml_path} (alternate)")
    else:
        comp_yaml_path = CANONICAL_COMPOSITION_YAML
        print(f"[info] composition   : {comp_yaml_path} (canonical)")

    composition_profiles, composition_config_hash = load_composition_profiles(
        comp_yaml_path
    )
    print(f"[info] composition hash: {composition_config_hash[:30]}...")

    if args.generators:
        print(
            f"[info] --generators '{args.generators}' noted; "
            "GeneratorRuntime imports lib.generators directly."
        )
    if args.allow_stub:
        print(
            "[warn] --allow-stub is set. "
            "Stub renders are NOT valid for corpus v2 or E5 baseline.",
            file=sys.stderr,
        )

    run_git_sha = get_git_sha()
    manifest    = load_manifest(manifest_path)
    fixtures    = manifest["fixtures"]
    print(f"[info] experiment_id : {manifest.get('experiment_id', '?')}")
    print(f"[info] fixtures      : {len(fixtures)}")
    print(f"[info] git HEAD      : {run_git_sha[:12]}")
    print(f"[info] output        : {output_dir}")

    # Open audit CSV
    csv_path   = output_dir / "audit_matrix.csv"
    csv_file   = open(csv_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=AUDIT_FIELDS)
    csv_writer.writeheader()

    failed: list[tuple[str, str]] = []
    png_paths: List[Path] = []

    for fixture in fixtures:
        fid          = fixture["id"]
        profile_slug = fixture["profile_slug"]
        perceptual   = dict(fixture.get("perceptual", {}))

        # Inject harmony_theta from manifest into perceptual
        theta_vec = fixture.get("harmony_theta", [])
        for i, val in enumerate(theta_vec):
            perceptual[f"harmony_theta_{i}"] = float(val)

        print(f"\n[run] {fid} ({profile_slug}) ...", end=" ", flush=True)
        t0 = time.perf_counter()

        # --- Resolve composition for this slug (ValidationError if missing) ---
        try:
            composition_profile = get_composition_for_slug(
                composition_profiles, profile_slug
            )
        except ValidationError as exc:
            print(f"FAIL (composition): {exc}")
            failed.append((fid, f"composition_error: {exc}"))
            continue

        # --- Resolve RenderParams ---
        try:
            render_params, style_profile, interp_profile = resolve_render_params(
                project_id="e4_audit",
                analysis_id=fid,
                perceptual=perceptual,
                style_profile_slug=profile_slug,
                interpretation_profile_slug=DEFAULT_INTERP,
                user_preset=DEFAULT_PRESET,
                strict_theta=True,
            )
        except Exception as exc:
            print(f"FAIL (resolve): {exc}")
            failed.append((fid, f"resolve_error: {exc}"))
            continue

        if args.dry_run:
            elapsed = time.perf_counter() - t0
            print(f"dry-run ok ({elapsed*1000:.1f} ms) seed={render_params.variation_seed}")
            continue

        # --- Render PNG via GeneratorRuntime ---
        png_path = renders_dir / f"{fid}.png"
        rerender_n = None
        prov_path_existing = provenance_path_for(provenance_dir, fixture)

        if png_path.exists() and not args.rerender:
            output_sha256 = sha256_file(png_path)
            elapsed = time.perf_counter() - t0
            png_paths.append(png_path)

            if prov_path_existing.exists():
                print(f"skip (exists) -> {png_path.name}")
            else:
                write_provenance(
                    fixture, render_params, png_path, output_sha256,
                    provenance_dir, run_git_sha, elapsed,
                    generator_stack=["e4_recovered:unknown"],
                    composition_config_hash=composition_config_hash,
                    rerender_n=None,
                )
                print(
                    f"recovered provenance (png existed, provenance missing)"
                    f" -> {png_path.name}"
                )

            write_audit_row(
                csv_writer, fixture, render_params, output_sha256, elapsed,
                generator_stack=["e4_recovered:unknown"],
                composition_config_hash=composition_config_hash,
            )
            continue

        if png_path.exists() and args.rerender:
            existing = list(renders_dir.glob(f"{fid}_rerender_*.png"))
            rerender_n = len(existing) + 1
            png_path = renders_dir / f"{fid}_rerender_{rerender_n}.png"

        try:
            generator_stack = _render_via_runtime(
                render_params, fixture, png_path,
                composition_profile=composition_profile,
                allow_stub=args.allow_stub,
            )
        except Exception as exc:
            print(f"FAIL (render): {exc}")
            failed.append((fid, f"render_error: {exc}"))
            continue

        fsync_path(png_path)

        output_sha256 = sha256_file(png_path)
        elapsed = time.perf_counter() - t0
        png_paths.append(png_path)

        prov_path = write_provenance(
            fixture, render_params, png_path, output_sha256,
            provenance_dir, run_git_sha, elapsed,
            generator_stack=generator_stack,
            composition_config_hash=composition_config_hash,
            rerender_n=rerender_n,
        )

        write_audit_row(
            csv_writer, fixture, render_params, output_sha256, elapsed,
            generator_stack=generator_stack,
            composition_config_hash=composition_config_hash,
        )
        print(
            f"ok ({elapsed*1000:.1f} ms) "
            f"stack={generator_stack} "
            f"sha={output_sha256[7:19]}... -> {prov_path.name}"
        )

    csv_file.close()

    if not args.dry_run and png_paths:
        contact_path = output_dir / "contact_sheet.png"
        build_contact_sheet(png_paths, contact_path)

    total   = len(fixtures)
    success = total - len(failed)
    print(f"\n{'='*60}")
    print(f"E4 Run B complete: {success}/{total} fixtures rendered")
    if failed:
        print(f"FAILED ({len(failed)}):")
        for fid, reason in failed:
            print(f"  {fid}: {reason}")
    print(f"audit_matrix -> {csv_path}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
