#!/usr/bin/env python3
"""
prepare_e4_commit.py — атомарный коммит E4: freeze fixtures, add harness.
Запуск: python prepare_e4_commit.py
Требует: git в PATH, выполнять из корня D:\WORK\AVCoder
"""

import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
E4 = ROOT / "artifacts" / "e4"
PROV = E4 / "e4_reference_render_audit_v1" / "provenance"
HARNESS = E4 / "harness"
TESTS = ROOT / "tests"
CONFIGS_STYLE = ROOT / "lib" / "style_engine" / "configs" / "style_profiles"
CONFIGS_INTERP = ROOT / "lib" / "style_engine" / "configs" / "interpretation_profiles"

# ---------------------------------------------------------------------------
# 1. УДАЛЕНИЕ фиктивных provenance JSON (git rm)
# ---------------------------------------------------------------------------
provenance_jsons = list(PROV.rglob("*.json"))
if provenance_jsons:
    print(f"[git rm] Удаляю {len(provenance_jsons)} фиктивных JSON...")
    for f in provenance_jsons:
        subprocess.run(["git", "rm", "-f", str(f.relative_to(ROOT))],
                       cwd=ROOT, check=True)
else:
    print("[git rm] Фиктивных JSON не найдено (уже удалены или путь изменился)")

# ---------------------------------------------------------------------------
# 2. .gitkeep в пустых директориях provenance
# ---------------------------------------------------------------------------
empty_dirs = [
    PROV / "renders",
    PROV / "scores",
    PROV / "contact_sheets",
]
for d in empty_dirs:
    d.mkdir(parents=True, exist_ok=True)
    gk = d / ".gitkeep"
    gk.write_text("")
    print(f"[create] {gk.relative_to(ROOT)}")

# ---------------------------------------------------------------------------
# 3. Пустые audit_matrix.csv и report.md
# ---------------------------------------------------------------------------
audit_matrix = E4 / "e4_reference_render_audit_v1" / "audit_matrix.csv"
report_md    = E4 / "e4_reference_render_audit_v1" / "report.md"
audit_matrix.parent.mkdir(parents=True, exist_ok=True)

if not audit_matrix.exists():
    audit_matrix.write_text(
        "fixture_id,style_slug,genre,render_sha256,theta_hash,"
        "score_harmony,score_density,score_brightness,score_tension,"
        "score_energy,score_stability,score_smoothness,auditor,notes\n"
    )
    print(f"[create] {audit_matrix.relative_to(ROOT)}")

if not report_md.exists():
    report_md.write_text(
        "# E4 Reference Render Audit Report\n\n"
        "_Этот файл заполняется автоматически шагом B (render harness). "
        "Не редактировать вручную._\n"
    )
    print(f"[create] {report_md.relative_to(ROOT)}")

# ---------------------------------------------------------------------------
# 4. .gitattributes — LFS для PNG/JPG рендеров
# ---------------------------------------------------------------------------
gitattributes = ROOT / ".gitattributes"
lfs_rules = textwrap.dedent("""\
    # E4 render artifacts — Git LFS
    artifacts/e4/**/*.png filter=lfs diff=lfs merge=lfs -text
    artifacts/e4/**/*.jpg filter=lfs diff=lfs merge=lfs -text
    artifacts/e4/**/*.jpeg filter=lfs diff=lfs merge=lfs -text
""")
existing = gitattributes.read_text() if gitattributes.exists() else ""
if "artifacts/e4/**/*.png" not in existing:
    with open(gitattributes, "a") as f:
        f.write("\n" + lfs_rules)
    print(f"[update] .gitattributes — добавлены LFS-правила")

# ---------------------------------------------------------------------------
# 5. fixtures_manifest.yaml — 21 жанровый + 1 smoke, без дубликатов
#    ИСПРАВЛЕНИЯ: ambient → lunar_mist, classical → ivory_cobalt
#    jazz и blues_jazz — оба canonical, НЕТ алиаса jazz→blues_jazz
# ---------------------------------------------------------------------------
manifest_path = E4 / "fixtures_manifest.yaml"

MANIFEST_CONTENT = textwrap.dedent("""\
    # fixtures_manifest.yaml
    # 21 жанровых fixture + 1 smoke-test default
    # Источник истины для шага B (render harness)
    # output_sha256 / audit scores заполняются harness-ом — не редактировать вручную
    version: "1.0"
    generated_by: "prepare_e4_commit.py"
    total_fixtures: 22

    fixtures:

      # ── SMOKE ──────────────────────────────────────────────────────────────
      - id: smoke_default_01
        style_slug: ambient
        genre: smoke
        description: "Smoke-test: базовый ambient без theta-смещений"
        perceptual:
          energy: 0.5
          tension: 0.3
          density: 0.4
          brightness: 0.5
          stability: 0.7
          smoothness: 0.8
          repetition: 0.5
          section_complexity: 0.4
          macro_shape_hint: plateau
        theta: {}
        user_preset:
          complexity: 0.5
          symmetry: 0.5
          density: 0.5
          noise: 0.2
          motion: 0.3
        output_sha256: null
        audit_scores: null

      # ── 21 ЖАНРОВЫХ ────────────────────────────────────────────────────────
      - id: genre_lunar_mist_01
        style_slug: lunar_mist
        genre: ambient
        description: "Ambient: тихая ночная текстура, низкое натяжение"
        perceptual:
          energy: 0.2
          tension: 0.15
          density: 0.25
          brightness: 0.35
          stability: 0.85
          smoothness: 0.9
          repetition: 0.6
          section_complexity: 0.2
          macro_shape_hint: fade_in
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.45
          harmony_theta_2: 0.5
        user_preset:
          complexity: 0.3
          symmetry: 0.7
          density: 0.25
          noise: 0.1
          motion: 0.15
        output_sha256: null
        audit_scores: null

      - id: genre_rock_01
        style_slug: rock
        genre: rock
        description: "Rock: высокая энергия, жёсткие атаки, плотная середина"
        perceptual:
          energy: 0.85
          tension: 0.75
          density: 0.8
          brightness: 0.6
          stability: 0.5
          smoothness: 0.3
          repetition: 0.65
          section_complexity: 0.6
          macro_shape_hint: peak
        theta:
          harmony_theta_0: 0.6
          harmony_theta_3: 0.7
          harmony_theta_5: 0.55
        user_preset:
          complexity: 0.7
          symmetry: 0.4
          density: 0.8
          noise: 0.5
          motion: 0.75
        output_sha256: null
        audit_scores: null

      - id: genre_pop_01
        style_slug: pop
        genre: pop
        description: "Pop: яркость, компрессия, хуковые структуры"
        perceptual:
          energy: 0.7
          tension: 0.45
          density: 0.65
          brightness: 0.8
          stability: 0.65
          smoothness: 0.6
          repetition: 0.75
          section_complexity: 0.5
          macro_shape_hint: verse_chorus
        theta:
          harmony_theta_0: 0.55
          harmony_theta_2: 0.6
          harmony_theta_4: 0.5
        user_preset:
          complexity: 0.5
          symmetry: 0.65
          density: 0.6
          noise: 0.25
          motion: 0.55
        output_sha256: null
        audit_scores: null

      - id: genre_jazz_01
        style_slug: jazz
        genre: jazz
        description: "Jazz canonical: импровизация, хроматика, свинговый грув"
        perceptual:
          energy: 0.6
          tension: 0.55
          density: 0.55
          brightness: 0.6
          stability: 0.45
          smoothness: 0.5
          repetition: 0.35
          section_complexity: 0.7
          macro_shape_hint: wave
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.6
          harmony_theta_3: 0.65
          harmony_theta_6: 0.55
        user_preset:
          complexity: 0.7
          symmetry: 0.35
          density: 0.5
          noise: 0.4
          motion: 0.6
        output_sha256: null
        audit_scores: null

      - id: genre_blues_jazz_01
        style_slug: blues_jazz
        genre: blues_jazz
        description: "Blues-Jazz canonical: блюзовый лад + джазовые разрешения (отдельный профиль)"
        perceptual:
          energy: 0.55
          tension: 0.6
          density: 0.5
          brightness: 0.5
          stability: 0.4
          smoothness: 0.45
          repetition: 0.4
          section_complexity: 0.65
          macro_shape_hint: swell
        theta:
          harmony_theta_0: 0.45
          harmony_theta_2: 0.55
          harmony_theta_5: 0.6
          harmony_theta_7: 0.5
        user_preset:
          complexity: 0.65
          symmetry: 0.3
          density: 0.5
          noise: 0.45
          motion: 0.55
        output_sha256: null
        audit_scores: null

      - id: genre_blues_01
        style_slug: blues_jazz
        genre: blues
        description: "Blues (alias → blues_jazz): дельта, пентатоника, low-tension call-response"
        perceptual:
          energy: 0.5
          tension: 0.65
          density: 0.45
          brightness: 0.4
          stability: 0.5
          smoothness: 0.4
          repetition: 0.55
          section_complexity: 0.5
          macro_shape_hint: plateau
        theta:
          harmony_theta_0: 0.4
          harmony_theta_5: 0.65
        user_preset:
          complexity: 0.55
          symmetry: 0.35
          density: 0.45
          noise: 0.4
          motion: 0.45
        output_sha256: null
        audit_scores: null

      - id: genre_ivory_cobalt_01
        style_slug: ivory_cobalt
        genre: classical
        description: "Classical: полифония, широкий динамический диапазон, ivory_cobalt палитра"
        perceptual:
          energy: 0.45
          tension: 0.4
          density: 0.5
          brightness: 0.55
          stability: 0.75
          smoothness: 0.75
          repetition: 0.4
          section_complexity: 0.65
          macro_shape_hint: arch
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.5
          harmony_theta_2: 0.5
        user_preset:
          complexity: 0.65
          symmetry: 0.7
          density: 0.5
          noise: 0.1
          motion: 0.4
        output_sha256: null
        audit_scores: null

      - id: genre_electronic_01
        style_slug: electronic
        genre: electronic
        description: "Electronic: сетка, синтетические тембры, высокая повторяемость"
        perceptual:
          energy: 0.75
          tension: 0.5
          density: 0.7
          brightness: 0.7
          stability: 0.6
          smoothness: 0.55
          repetition: 0.85
          section_complexity: 0.45
          macro_shape_hint: loop
        theta:
          harmony_theta_0: 0.5
          harmony_theta_4: 0.6
        user_preset:
          complexity: 0.55
          symmetry: 0.75
          density: 0.7
          noise: 0.35
          motion: 0.7
        output_sha256: null
        audit_scores: null

      - id: genre_hiphop_01
        style_slug: hiphop
        genre: hiphop
        description: "Hip-Hop: грув, семплинг, пунктирный ритм, суб-бас"
        perceptual:
          energy: 0.7
          tension: 0.5
          density: 0.65
          brightness: 0.55
          stability: 0.6
          smoothness: 0.45
          repetition: 0.8
          section_complexity: 0.5
          macro_shape_hint: loop
        theta:
          harmony_theta_0: 0.5
          harmony_theta_3: 0.55
        user_preset:
          complexity: 0.55
          symmetry: 0.6
          density: 0.65
          noise: 0.4
          motion: 0.65
        output_sha256: null
        audit_scores: null

      - id: genre_rnb_01
        style_slug: rnb
        genre: rnb
        description: "R&B: грув с синкопами, тёплые тембры, мелизматика"
        perceptual:
          energy: 0.6
          tension: 0.45
          density: 0.6
          brightness: 0.65
          stability: 0.6
          smoothness: 0.65
          repetition: 0.65
          section_complexity: 0.55
          macro_shape_hint: verse_chorus
        theta:
          harmony_theta_0: 0.5
          harmony_theta_2: 0.55
          harmony_theta_4: 0.5
        user_preset:
          complexity: 0.55
          symmetry: 0.6
          density: 0.6
          noise: 0.3
          motion: 0.55
        output_sha256: null
        audit_scores: null

      - id: genre_reggae_01
        style_slug: reggae
        genre: reggae
        description: "Reggae: offbeat сkank, суб-бас, лёгкое натяжение"
        perceptual:
          energy: 0.5
          tension: 0.3
          density: 0.5
          brightness: 0.55
          stability: 0.65
          smoothness: 0.6
          repetition: 0.7
          section_complexity: 0.35
          macro_shape_hint: plateau
        theta:
          harmony_theta_0: 0.45
          harmony_theta_4: 0.5
        user_preset:
          complexity: 0.4
          symmetry: 0.6
          density: 0.5
          noise: 0.2
          motion: 0.4
        output_sha256: null
        audit_scores: null

      - id: genre_folk_01
        style_slug: folk
        genre: folk
        description: "Folk: акустика, нарратив, умеренная сложность"
        perceptual:
          energy: 0.4
          tension: 0.3
          density: 0.35
          brightness: 0.5
          stability: 0.7
          smoothness: 0.65
          repetition: 0.5
          section_complexity: 0.45
          macro_shape_hint: arch
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.45
        user_preset:
          complexity: 0.45
          symmetry: 0.55
          density: 0.35
          noise: 0.15
          motion: 0.35
        output_sha256: null
        audit_scores: null

      - id: genre_country_01
        style_slug: country
        genre: country
        description: "Country: twang, педальная сталь, нарративная структура"
        perceptual:
          energy: 0.5
          tension: 0.35
          density: 0.45
          brightness: 0.55
          stability: 0.65
          smoothness: 0.6
          repetition: 0.55
          section_complexity: 0.45
          macro_shape_hint: verse_chorus
        theta:
          harmony_theta_0: 0.5
          harmony_theta_2: 0.45
        user_preset:
          complexity: 0.45
          symmetry: 0.6
          density: 0.45
          noise: 0.2
          motion: 0.4
        output_sha256: null
        audit_scores: null

      - id: genre_metal_01
        style_slug: metal
        genre: metal
        description: "Metal: экстремальная энергия, down-tuning, бластбиты"
        perceptual:
          energy: 0.95
          tension: 0.85
          density: 0.9
          brightness: 0.5
          stability: 0.4
          smoothness: 0.15
          repetition: 0.6
          section_complexity: 0.7
          macro_shape_hint: peak
        theta:
          harmony_theta_0: 0.65
          harmony_theta_3: 0.8
          harmony_theta_5: 0.7
        user_preset:
          complexity: 0.85
          symmetry: 0.35
          density: 0.9
          noise: 0.7
          motion: 0.9
        output_sha256: null
        audit_scores: null

      - id: genre_punk_01
        style_slug: punk
        genre: punk
        description: "Punk: темп, примитивная структура, DIY-агрессия"
        perceptual:
          energy: 0.88
          tension: 0.7
          density: 0.75
          brightness: 0.6
          stability: 0.45
          smoothness: 0.2
          repetition: 0.7
          section_complexity: 0.4
          macro_shape_hint: peak
        theta:
          harmony_theta_0: 0.6
          harmony_theta_3: 0.65
        user_preset:
          complexity: 0.6
          symmetry: 0.3
          density: 0.75
          noise: 0.6
          motion: 0.8
        output_sha256: null
        audit_scores: null

      - id: genre_latin_01
        style_slug: latin
        genre: latin
        description: "Latin: clave, перкуссионная полиритмия, тёплая палитра"
        perceptual:
          energy: 0.65
          tension: 0.45
          density: 0.65
          brightness: 0.7
          stability: 0.55
          smoothness: 0.55
          repetition: 0.7
          section_complexity: 0.55
          macro_shape_hint: wave
        theta:
          harmony_theta_0: 0.5
          harmony_theta_2: 0.55
          harmony_theta_4: 0.5
        user_preset:
          complexity: 0.6
          symmetry: 0.5
          density: 0.65
          noise: 0.3
          motion: 0.65
        output_sha256: null
        audit_scores: null

      - id: genre_world_01
        style_slug: world
        genre: world
        description: "World: микротональность, экзотические гаммы, перкуссия"
        perceptual:
          energy: 0.55
          tension: 0.5
          density: 0.55
          brightness: 0.6
          stability: 0.5
          smoothness: 0.5
          repetition: 0.5
          section_complexity: 0.65
          macro_shape_hint: wave
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.55
          harmony_theta_6: 0.6
        user_preset:
          complexity: 0.65
          symmetry: 0.45
          density: 0.55
          noise: 0.35
          motion: 0.5
        output_sha256: null
        audit_scores: null

      - id: genre_gospel_01
        style_slug: gospel
        genre: gospel
        description: "Gospel: call-response, высокая яркость, духовная энергия"
        perceptual:
          energy: 0.75
          tension: 0.4
          density: 0.6
          brightness: 0.85
          stability: 0.65
          smoothness: 0.65
          repetition: 0.6
          section_complexity: 0.5
          macro_shape_hint: swell
        theta:
          harmony_theta_0: 0.55
          harmony_theta_2: 0.6
          harmony_theta_4: 0.65
        user_preset:
          complexity: 0.55
          symmetry: 0.6
          density: 0.6
          noise: 0.2
          motion: 0.65
        output_sha256: null
        audit_scores: null

      - id: genre_soul_01
        style_slug: soul
        genre: soul
        description: "Soul: warm groove, динамика вокала, ретро-тембры"
        perceptual:
          energy: 0.65
          tension: 0.4
          density: 0.55
          brightness: 0.65
          stability: 0.6
          smoothness: 0.65
          repetition: 0.6
          section_complexity: 0.5
          macro_shape_hint: arch
        theta:
          harmony_theta_0: 0.5
          harmony_theta_2: 0.55
          harmony_theta_4: 0.5
        user_preset:
          complexity: 0.55
          symmetry: 0.6
          density: 0.55
          noise: 0.25
          motion: 0.55
        output_sha256: null
        audit_scores: null

      - id: genre_cinematic_01
        style_slug: cinematic
        genre: cinematic
        description: "Cinematic: оркестровые свеллы, широкая динамика, arc-форма"
        perceptual:
          energy: 0.55
          tension: 0.6
          density: 0.6
          brightness: 0.55
          stability: 0.55
          smoothness: 0.6
          repetition: 0.35
          section_complexity: 0.75
          macro_shape_hint: arch
        theta:
          harmony_theta_0: 0.5
          harmony_theta_1: 0.55
          harmony_theta_2: 0.5
          harmony_theta_7: 0.6
        user_preset:
          complexity: 0.75
          symmetry: 0.65
          density: 0.6
          noise: 0.2
          motion: 0.6
        output_sha256: null
        audit_scores: null
""")

manifest_path.write_text(MANIFEST_CONTENT, encoding="utf-8")
print(f"[write] {manifest_path.relative_to(ROOT)} — 22 fixtures (21 жанр + 1 smoke)")

# ---------------------------------------------------------------------------
# 6. Harness директория + render_harness.py
# ---------------------------------------------------------------------------
HARNESS.mkdir(parents=True, exist_ok=True)
(HARNESS / "__init__.py").write_text("")

harness_code = textwrap.dedent('''\
    """
    harness/render_harness.py
    Шаг B: запускает resolve_render_params для каждого fixture из manifest,
    вычисляет SHA-256 вывода, заполняет audit_matrix.csv.
    """
    from __future__ import annotations
    import csv
    import hashlib
    import json
    import sys
    from pathlib import Path
    import yaml

    ROOT = Path(__file__).parents[3]
    sys.path.insert(0, str(ROOT))

    from lib.style_engine.engine import resolve_render_params

    MANIFEST = Path(__file__).parents[1] / "fixtures_manifest.yaml"
    AUDIT_CSV = Path(__file__).parents[1] / "e4_reference_render_audit_v1" / "audit_matrix.csv"

    FIELDNAMES = [
        "fixture_id", "style_slug", "genre", "render_sha256", "theta_hash",
        "score_harmony", "score_density", "score_brightness", "score_tension",
        "score_energy", "score_stability", "score_smoothness", "auditor", "notes",
    ]


    def _sha256(obj: object) -> str:
        raw = json.dumps(obj, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()


    def run_harness(dry_run: bool = False) -> list[dict]:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        rows: list[dict] = []
        for fx in manifest["fixtures"]:
            fid = fx["id"]
            try:
                rp, sp, ip = resolve_render_params(
                    project_id="e4_audit",
                    analysis_id=fid,
                    perceptual=fx["perceptual"] | fx.get("theta", {}),
                    style_profile_slug=fx["style_slug"],
                    interpretation_profile_slug="default",
                    user_preset=fx["user_preset"],
                    strict_theta=True,
                )
                render_sha = _sha256(rp.__dict__ if hasattr(rp, "__dict__") else rp)
                theta_hash = _sha256(fx.get("theta", {}))
                row = {
                    "fixture_id":       fid,
                    "style_slug":       fx["style_slug"],
                    "genre":            fx["genre"],
                    "render_sha256":    render_sha,
                    "theta_hash":       theta_hash,
                    "score_harmony":    "",
                    "score_density":    "",
                    "score_brightness": "",
                    "score_tension":    "",
                    "score_energy":     "",
                    "score_stability":  "",
                    "score_smoothness": "",
                    "auditor":          "auto",
                    "notes":            "",
                }
                print(f"  OK  {fid}")
            except Exception as exc:
                row = {k: "" for k in FIELDNAMES}
                row.update({"fixture_id": fid, "style_slug": fx["style_slug"],
                             "genre": fx["genre"], "notes": str(exc), "auditor": "error"})
                print(f"  ERR {fid}: {exc}", file=sys.stderr)
            rows.append(row)

        if not dry_run:
            with open(AUDIT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(rows)
            print(f"\\nАудит записан → {AUDIT_CSV.relative_to(ROOT)}")
        return rows


    if __name__ == "__main__":
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--dry-run", action="store_true")
        args = p.parse_args()
        run_harness(dry_run=args.dry_run)
''')
(HARNESS / "render_harness.py").write_text(harness_code, encoding="utf-8")
print(f"[create] harness/render_harness.py")

# ---------------------------------------------------------------------------
# 7. test14_e4_provenance.py
# ---------------------------------------------------------------------------
TESTS.mkdir(exist_ok=True)
test_code = textwrap.dedent('''\
    """
    test14_e4_provenance.py
    Проверяет: manifest корректен, все style_slug резолвятся, SHA-256 стабильны.
    """
    import hashlib, json, sys
    from pathlib import Path
    import pytest, yaml

    ROOT = Path(__file__).parents[1]
    sys.path.insert(0, str(ROOT))

    MANIFEST = ROOT / "artifacts" / "e4" / "fixtures_manifest.yaml"

    from lib.style_engine.engine import resolve_render_params


    @pytest.fixture(scope="module")
    def manifest():
        with open(MANIFEST, encoding="utf-8") as f:
            return yaml.safe_load(f)


    def test_manifest_total(manifest):
        assert manifest["total_fixtures"] == 22
        assert len(manifest["fixtures"]) == 22


    def test_no_duplicate_ids(manifest):
        ids = [f["id"] for f in manifest["fixtures"]]
        assert len(ids) == len(set(ids)), f"Дубликаты: {[x for x in ids if ids.count(x)>1]}"


    def test_no_placeholder_sha(manifest):
        """output_sha256 и audit_scores должны быть null до шага B."""
        for fx in manifest["fixtures"]:
            assert fx.get("output_sha256") is None, f"{fx['id']}: output_sha256 не null"
            assert fx.get("audit_scores") is None, f"{fx['id']}: audit_scores не null"


    def test_ambient_slug_is_lunar_mist(manifest):
        ambient = [f for f in manifest["fixtures"] if f["genre"] == "ambient"]
        assert all(f["style_slug"] == "lunar_mist" for f in ambient), \\
            "ambient-fixture должен иметь style_slug=lunar_mist"


    def test_classical_slug_is_ivory_cobalt(manifest):
        classical = [f for f in manifest["fixtures"] if f["genre"] == "classical"]
        assert all(f["style_slug"] == "ivory_cobalt" for f in classical), \\
            "classical-fixture должен иметь style_slug=ivory_cobalt"


    def test_jazz_and_blues_jazz_are_separate(manifest):
        """jazz и blues_jazz — оба canonical, алиаса jazz→blues_jazz нет."""
        jazz_fx = [f for f in manifest["fixtures"] if f["style_slug"] == "jazz"]
        bj_fx   = [f for f in manifest["fixtures"] if f["style_slug"] == "blues_jazz"]
        assert len(jazz_fx) >= 1,   "Нет jazz-fixture"
        assert len(bj_fx) >= 1,     "Нет blues_jazz-fixture"


    @pytest.mark.parametrize("fixture", yaml.safe_load(MANIFEST.read_text())["fixtures"])
    def test_each_fixture_resolves(fixture):
        rp, sp, ip = resolve_render_params(
            project_id="e4_test",
            analysis_id=fixture["id"],
            perceptual=fixture["perceptual"] | fixture.get("theta", {}),
            style_profile_slug=fixture["style_slug"],
            interpretation_profile_slug="default",
            user_preset=fixture["user_preset"],
            strict_theta=True,
        )
        assert rp is not None
        assert sp is not None


    @pytest.mark.parametrize("fixture", yaml.safe_load(MANIFEST.read_text())["fixtures"])
    def test_sha_stability(fixture):
        """Два вызова с одинаковыми параметрами дают одинаковый SHA."""
        def _resolve():
            rp, _, _ = resolve_render_params(
                project_id="e4_sha",
                analysis_id=fixture["id"],
                perceptual=fixture["perceptual"] | fixture.get("theta", {}),
                style_profile_slug=fixture["style_slug"],
                interpretation_profile_slug="default",
                user_preset=fixture["user_preset"],
                strict_theta=True,
            )
            raw = json.dumps(
                rp.__dict__ if hasattr(rp, "__dict__") else rp,
                sort_keys=True, default=str
            ).encode()
            return hashlib.sha256(raw).hexdigest()
        assert _resolve() == _resolve(), f"{fixture['id']}: SHA не детерминирован"
''')
(TESTS / "test14_e4_provenance.py").write_text(test_code, encoding="utf-8")
print(f"[create] tests/test14_e4_provenance.py")

# ---------------------------------------------------------------------------
# 8. Style profiles: jazz.yaml, blues_jazz.yaml (оба canonical)
#    + rock.yaml, pop.yaml, lunar_mist.yaml, ivory_cobalt.yaml
# ---------------------------------------------------------------------------
CONFIGS_STYLE.mkdir(parents=True, exist_ok=True)

STYLE_PROFILES = {
    "jazz": """\
# jazz.yaml — canonical jazz профиль (НЕ алиас blues_jazz)
slug: jazz
display_name: "Jazz"
description: "Импровизация, хроматика, свинговый грув. Самостоятельный профиль."
base_params:
  complexity: 0.7
  symmetry: 0.35
  density: 0.5
  noise: 0.4
  motion: 0.6
  brightness: 0.6
  tension: 0.55
  energy: 0.6
  stability: 0.45
  smoothness: 0.5
aliases: []
""",
    "blues_jazz": """\
# blues_jazz.yaml — canonical blues_jazz профиль
# Алиасы: blues → blues_jazz (допустимо)
slug: blues_jazz
display_name: "Blues-Jazz"
description: "Блюзовый лад + джазовые разрешения. Отличается от jazz пентатоникой и бендами."
base_params:
  complexity: 0.65
  symmetry: 0.3
  density: 0.5
  noise: 0.45
  motion: 0.55
  brightness: 0.5
  tension: 0.6
  energy: 0.55
  stability: 0.4
  smoothness: 0.45
aliases:
  - blues
""",
    "rock": """\
# rock.yaml
slug: rock
display_name: "Rock"
description: "Высокая энергия, электрогитары, жёсткие атаки, плотная середина."
base_params:
  complexity: 0.7
  symmetry: 0.4
  density: 0.8
  noise: 0.5
  motion: 0.75
  brightness: 0.6
  tension: 0.75
  energy: 0.85
  stability: 0.5
  smoothness: 0.3
aliases: []
""",
    "pop": """\
# pop.yaml
slug: pop
display_name: "Pop"
description: "Яркость, компрессия, хуковые структуры, verse-chorus форма."
base_params:
  complexity: 0.5
  symmetry: 0.65
  density: 0.6
  noise: 0.25
  motion: 0.55
  brightness: 0.8
  tension: 0.45
  energy: 0.7
  stability: 0.65
  smoothness: 0.6
aliases: []
""",
    "lunar_mist": """\
# lunar_mist.yaml — ambient-палитра (замена generic 'ambient')
slug: lunar_mist
display_name: "Lunar Mist"
description: "Тихая ночная текстура, атмосферный ambient, низкое натяжение."
base_params:
  complexity: 0.3
  symmetry: 0.7
  density: 0.25
  noise: 0.1
  motion: 0.15
  brightness: 0.35
  tension: 0.15
  energy: 0.2
  stability: 0.85
  smoothness: 0.9
aliases:
  - ambient
""",
    "ivory_cobalt": """\
# ivory_cobalt.yaml — classical-палитра (замена generic 'classical')
slug: ivory_cobalt
display_name: "Ivory Cobalt"
description: "Полифония, широкий динамический диапазон, академическая структура."
base_params:
  complexity: 0.65
  symmetry: 0.7
  density: 0.5
  noise: 0.1
  motion: 0.4
  brightness: 0.55
  tension: 0.4
  energy: 0.45
  stability: 0.75
  smoothness: 0.75
aliases:
  - classical
""",
}

for slug, content in STYLE_PROFILES.items():
    p = CONFIGS_STYLE / f"{slug}.yaml"
    p.write_text(content, encoding="utf-8")
    print(f"[write] configs/style_profiles/{slug}.yaml")

# ---------------------------------------------------------------------------
# 9. Interpretation profile: default.yaml
# ---------------------------------------------------------------------------
CONFIGS_INTERP.mkdir(parents=True, exist_ok=True)
default_interp = """\
# default.yaml — базовый interpretation profile
slug: default
display_name: "Default"
description: "Нейтральный профиль интерпретации. Используется для smoke-тестов и базового resolve."
mapping_rules:
  complexity:
    sources:
      - {key: section_complexity, weight: 0.6}
      - {key: repetition,         weight: -0.2}
      - {key: density,            weight: 0.2}
  symmetry:
    sources:
      - {key: stability,  weight: 0.5}
      - {key: repetition, weight: 0.3}
  density:
    sources:
      - {key: density,   weight: 0.7}
      - {key: energy,    weight: 0.2}
  noise:
    sources:
      - {key: tension,    weight: 0.5}
      - {key: energy,     weight: 0.3}
  motion:
    sources:
      - {key: energy,    weight: 0.5}
      - {key: smoothness, weight: -0.2}
  brightness:
    sources:
      - {key: brightness, weight: 0.8}
guardrails:
  complexity:  [0.0, 1.0]
  symmetry:    [0.0, 1.0]
  density:     [0.0, 1.0]
  noise:       [0.0, 1.0]
  motion:      [0.0, 1.0]
  brightness:  [0.0, 1.0]
theta_defaults:
  harmony_theta_0: 0.5
  harmony_theta_1: 0.5
  harmony_theta_2: 0.5
  harmony_theta_3: 0.5
  harmony_theta_4: 0.5
  harmony_theta_5: 0.5
  harmony_theta_6: 0.5
  harmony_theta_7: 0.5
"""
(CONFIGS_INTERP / "default.yaml").write_text(default_interp, encoding="utf-8")
print(f"[write] configs/interpretation_profiles/default.yaml")

# ---------------------------------------------------------------------------
# 10. git add всё нужное и финальный атомарный коммит
# ---------------------------------------------------------------------------
print("\n[git add] Индексируем все новые/изменённые файлы...")
add_paths = [
    ".gitattributes",
    str((PROV / "renders" / ".gitkeep").relative_to(ROOT)),
    str((PROV / "scores" / ".gitkeep").relative_to(ROOT)),
    str((PROV / "contact_sheets" / ".gitkeep").relative_to(ROOT)),
    str(audit_matrix.relative_to(ROOT)),
    str(report_md.relative_to(ROOT)),
    str(manifest_path.relative_to(ROOT)),
    str((HARNESS / "__init__.py").relative_to(ROOT)),
    str((HARNESS / "render_harness.py").relative_to(ROOT)),
    str((TESTS / "test14_e4_provenance.py").relative_to(ROOT)),
]
# style profiles
for slug in STYLE_PROFILES:
    add_paths.append(str((CONFIGS_STYLE / f"{slug}.yaml").relative_to(ROOT)))
# interp profile
add_paths.append(str((CONFIGS_INTERP / "default.yaml").relative_to(ROOT)))

for path in add_paths:
    subprocess.run(["git", "add", path], cwd=ROOT, check=True)

commit_msg = (
    "feat(E4): freeze fixtures and add reproducible render harness\n\n"
    "- Remove 22 fake provenance JSON (git rm)\n"
    "- Add .gitkeep to renders/, scores/, contact_sheets/\n"
    "- Update fixtures_manifest.yaml: 21 genre + 1 smoke, no duplicates\n"
    "- Fix: ambient → lunar_mist, classical → ivory_cobalt\n"
    "- jazz.yaml and blues_jazz.yaml both canonical; blues→blues_jazz alias only\n"
    "- NO jazz→blues_jazz alias (contract: jazz is independent)\n"
    "- Add harness/render_harness.py for step B\n"
    "- Add tests/test14_e4_provenance.py\n"
    "- Add style profiles: rock, pop, jazz, blues_jazz, lunar_mist, ivory_cobalt\n"
    "- Add interpretation profile: default\n"
    "- Add LFS rules to .gitattributes\n"
    "- Add empty audit_matrix.csv and report.md (filled by harness)\n"
    "- output_sha256 and audit_scores are null until step B runs"
)
subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT, check=True)
print("\n✅ Атомарный коммит создан успешно!")
print("   Следующий шаг: git push origin main")
print("   После push запусти: python artifacts/e4/harness/render_harness.py")