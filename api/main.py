# api/main.py

from lib.audio_analysis.analysis import analyze_audio_file, build_perceptual_latent
from lib.style_engine.engine import resolve_render_params
from lib.fractal_backend.adapter import render_poster as render_poster_adapter, RenderParams
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from uuid import uuid4
import os
import shutil
import mimetypes
import json
import numpy as np
import time
import logging

from .models_db import (
    SessionLocal,
    init_db,
    UserProjectDB,
    TrackDB,
    AudioAnalysisDB,
    UserPresetDB,
    GenerationJobDB,
    PosterAssetDB,
    ExportJobDB,
    PerceptualLatentDB,
)

from .schemas import (
    Track,
    GenerationJob,
    ExportJob,
    CreateProjectRequest,
    ProjectResponse,
    AnalyzeResponse,
)

# Composition pipeline — опциональный импорт
try:
    from lib.composition.composition_adapter import build_planner_input
    from lib.composition.composition_planner import build_composition_plan
    _COMPOSITION_AVAILABLE = True
except ImportError:
    _COMPOSITION_AVAILABLE = False

logger = logging.getLogger(__name__)

# =======================
# Storage utilities
# =======================

AUDIO_ROOT = "storage/audio"
POSTER_ROOT = "storage/posters"
os.makedirs(AUDIO_ROOT, exist_ok=True)
os.makedirs(POSTER_ROOT, exist_ok=True)

ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/x-mpeg"}


def guess_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def save_uploaded_file(project_id: str, file: UploadFile) -> str:
    """
    Save uploaded audio file under deterministic path:
    storage/audio/<project_id>/<uuid4>.<ext>.
    """
    project_dir = os.path.join(AUDIO_ROOT, project_id)
    os.makedirs(project_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] or ".bin"
    file_id = str(uuid4())
    target_name = file_id + ext
    target_path = os.path.join(project_dir, target_name)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return target_path


# =======================
# Helpers
# =======================


def _to_python_scalar(v):
    """
    Приведение значения к чистому Python-типу для безопасной сериализации.
    - np.generic -> .item()
    - np.ndarray -> mean() или 0.0 для пустого
    - иначе возвращаем как есть
    """
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, np.ndarray):
        if v.size == 0:
            return 0.0
        return float(v.mean())
    return v


def derive_style_profile_slug(suggested_music_style: str) -> str:
    """
    Перевод музыкального класса в slug визуального StyleProfile.

    Ожидаемые профили:
    - default
    - rock
    - blues_jazz
    - ambient
    - electronic
    - soundtrack
    """
    music_style = (suggested_music_style or "").strip().lower()

    mapping = {
        "rock": "rock",
        "electronic": "electronic",
        "ambient": "ambient",
        "soundtrack": "soundtrack",
        "jazz": "blues_jazz",
        "blues": "blues_jazz",
        "classical": "soundtrack",
        "pop": "rock",
        "mixed": "default",
    }

    return mapping.get(music_style, "default")


def cleanup_audio_storage(
    max_age_days: int = 7,
    base_dir: str | None = None,
) -> int:
    """
    Удаляет файлы из storage/audio, которые старше max_age_days.
    Возвращает количество удалённых файлов.
    """
    if base_dir is None:
        base_dir = AUDIO_ROOT

    now_ts = time.time()
    max_age_sec = max_age_days * 24 * 3600

    deleted = 0
    for root, _, files in os.walk(base_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            age_sec = now_ts - st.st_mtime
            if age_sec > max_age_sec:
                try:
                    os.remove(path)
                    deleted += 1
                except OSError:
                    continue
    return deleted


def _build_composition_plan_safe(perceptual: dict, features: dict, style_profile_slug: str, seed: int):
    """
    Строит CompositionPlan из доступных данных.
    При любой ошибке возвращает None — рендерер продолжит в legacy-режиме.
    """
    if not _COMPOSITION_AVAILABLE:
        return None
    try:
        planner_input = build_planner_input(
            features=features,
            perceptual=perceptual,
            style_profile_slug=style_profile_slug,
            seed=seed,
        )
        return build_composition_plan(planner_input)
    except Exception as exc:
        logger.warning("CompositionPlan build failed (non-critical): %s", exc)
        return None


# =======================
# DB dependency
# =======================


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =======================
# FastAPI app
# =======================

app = FastAPI(title="Fractal Identity Engine API v0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


# =======================
# Project endpoints
# =======================


@app.post("/project", response_model=ProjectResponse)
def create_project(req: CreateProjectRequest, db=Depends(get_db)):
    project_id = str(uuid4())
    now = datetime.utcnow()
    project_db = UserProjectDB(
        id=project_id,
        user_id=req.user_id,
        name=req.name,
        created_at=now,
        updated_at=now,
        project_state="draft",
    )
    db.add(project_db)
    db.commit()
    db.refresh(project_db)
    return project_db


@app.get("/project/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db=Depends(get_db)):
    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_db


# =======================
# Upload / capture
# =======================


@app.post("/upload", response_model=Track)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")

    mime = file.content_type or guess_mime_type(file.filename)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime}. Only MP3/WAV allowed.",
        )

    storage_path = save_uploaded_file(project_id, file)
    now = datetime.utcnow()

    track_id = str(uuid4())
    format_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")

    track_db = TrackDB(
        id=track_id,
        source_type="file",
        storage_path=storage_path,
        duration_sec=None,
        format=format_ext,
        created_at=now,
        project_id=project_id,
    )
    db.add(track_db)
    db.commit()
    db.refresh(track_db)

    return Track.model_validate(track_db)


@app.post("/capture")
async def capture_audio(project_id: str, db=Depends(get_db)):
    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "capture_not_implemented_yet", "project_id": project_id}


# =======================
# Audio analysis v0.2.1
# =======================


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_audio(project_id: str, track_id: str, db=Depends(get_db)):
    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")

    track_db = db.query(TrackDB).filter(TrackDB.id == track_id).first()
    if not track_db:
        raise HTTPException(status_code=404, detail="Track not found")

    storage_path = track_db.storage_path
    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=400, detail="Audio file not found on storage")

    try:
        features = analyze_audio_file(storage_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    now = datetime.utcnow()
    analysis_id = str(uuid4())

    sections_json = json.dumps(features.get("sections", []), ensure_ascii=False)
    recurrence_json = json.dumps(features.get("recurrence_groups", []), ensure_ascii=False)
    events_json = json.dumps(features.get("events", []), ensure_ascii=False)

    analysis_db = AudioAnalysisDB(
        id=analysis_id,
        track_id=track_id,
        project_id=project_id,
        bpm=_to_python_scalar(features["bpm"]),
        key=str(features["key"]),
        energy=_to_python_scalar(features["energy"]),
        spectral_centroid=_to_python_scalar(features["spectral_centroid"]),
        brightness=_to_python_scalar(features["brightness"]),
        rhythm_density=_to_python_scalar(features["rhythm_density"]),
        dynamic_range=_to_python_scalar(features["dynamic_range"]),
        duration_sec=_to_python_scalar(features["duration_sec"]),
        repetition_score=_to_python_scalar(features["repetition_score"]),
        suggested_music_style=str(features["suggested_music_style"]),
        created_at=now,
        sections=sections_json,
        recurrence_groups=recurrence_json,
        events=events_json,
    )
    db.add(analysis_db)
    db.commit()
    db.refresh(analysis_db)

    perceptual_vector = build_perceptual_latent(features)
    perceptual_id = str(uuid4())

    perceptual_db = PerceptualLatentDB(
        id=perceptual_id,
        analysis_id=analysis_id,
        track_id=track_id,
        energy=_to_python_scalar(perceptual_vector["energy"]),
        tension=_to_python_scalar(perceptual_vector["tension"]),
        density=_to_python_scalar(perceptual_vector["density"]),
        brightness=_to_python_scalar(perceptual_vector["brightness"]),
        stability=_to_python_scalar(perceptual_vector["stability"]),
        smoothness=_to_python_scalar(perceptual_vector["smoothness"]),
        repetition=_to_python_scalar(perceptual_vector["repetition"]),
        section_complexity=_to_python_scalar(perceptual_vector["section_complexity"]),
        macro_shape_hint=str(perceptual_vector["macro_shape_hint"]),
        created_at=now,
    )
    db.add(perceptual_db)
    db.commit()

    clean_features = {k: _to_python_scalar(v) for k, v in features.items()}
    clean_perceptual = {k: _to_python_scalar(v) for k, v in perceptual_vector.items()}

    api_feature_keys = [
        "bpm", "key", "energy", "spectral_centroid", "brightness",
        "onset_rate_hz", "onset_count", "beat_regularity", "beat_count",
        "dynamic_range", "duration_sec", "repetition_score", "silence_rate",
        "harmonic_stability", "harmonic_change_rate_hz", "spectral_flatness",
        "high_frequency_energy_ratio", "band_energy_0_250_hz",
        "band_energy_250_2000_hz", "band_energy_2000_6000_hz",
        "band_energy_6000_nyquist",
    ]

    api_features = {
        key: clean_features[key]
        for key in api_feature_keys
        if key in clean_features
    }

    return AnalyzeResponse(
        status="success",
        project_id=project_id,
        track_id=track_id,
        analysis_id=analysis_id,
        features=api_features,
        suggested_music_style=str(clean_features["suggested_music_style"]),
        perceptual=clean_perceptual,
    )


# =======================
# Style resolution v0.2.1
# =======================


@app.post("/resolve-style")
async def resolve_style(
    payload: dict = Body(...),
    db=Depends(get_db),
):
    """
    Style engine endpoint v0.2.1.

    style_profile_slug может быть передан явно,
    а если не передан - выводится из analysis_db.suggested_music_style.
    """

    project_id = payload.get("project_id")
    analysis_id = payload.get("analysis_id")
    style_profile_slug = payload.get("style_profile_slug")
    interpretation_profile_slug = payload.get("interpretation_profile_slug", "default")
    preset_id = payload.get("preset_id")
    override_sliders = payload.get("override_sliders", {}) or {}

    if not project_id or not analysis_id:
        raise HTTPException(status_code=400, detail="project_id and analysis_id are required")

    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")

    analysis_db = db.query(AudioAnalysisDB).filter(AudioAnalysisDB.id == analysis_id).first()
    if not analysis_db:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not style_profile_slug:
        style_profile_slug = derive_style_profile_slug(analysis_db.suggested_music_style)

    perceptual_db = (
        db.query(PerceptualLatentDB)
        .filter(PerceptualLatentDB.analysis_id == analysis_id)
        .first()
    )

    if not perceptual_db:
        features = {
            "energy": analysis_db.energy or 0.0,
            "rhythm_density": analysis_db.rhythm_density or 0.0,
            "brightness": analysis_db.brightness or 0.0,
            "repetition_score": analysis_db.repetition_score or 0.0,
            "dynamic_range": analysis_db.dynamic_range or 0.0,
            "duration_sec": analysis_db.duration_sec or 0.0,
            "sections": [],
            "events": [],
        }
        perceptual_vector = build_perceptual_latent(features)
        perceptual_db = PerceptualLatentDB(
            id=str(uuid4()),
            analysis_id=analysis_id,
            track_id=analysis_db.track_id,
            energy=_to_python_scalar(perceptual_vector["energy"]),
            tension=_to_python_scalar(perceptual_vector["tension"]),
            density=_to_python_scalar(perceptual_vector["density"]),
            brightness=_to_python_scalar(perceptual_vector["brightness"]),
            stability=_to_python_scalar(perceptual_vector["stability"]),
            smoothness=_to_python_scalar(perceptual_vector["smoothness"]),
            repetition=_to_python_scalar(perceptual_vector["repetition"]),
            section_complexity=_to_python_scalar(perceptual_vector["section_complexity"]),
            macro_shape_hint=str(perceptual_vector["macro_shape_hint"]),
            created_at=datetime.utcnow(),
        )
        db.add(perceptual_db)
        db.commit()
        db.refresh(perceptual_db)

    perceptual = {
        "energy": perceptual_db.energy or 0.0,
        "tension": perceptual_db.tension or 0.0,
        "density": perceptual_db.density or 0.0,
        "brightness": perceptual_db.brightness or 0.0,
        "stability": perceptual_db.stability or 0.0,
        "smoothness": perceptual_db.smoothness or 0.0,
        "repetition": perceptual_db.repetition or 0.0,
        "section_complexity": perceptual_db.section_complexity or 0.0,
        "macro_shape_hint": perceptual_db.macro_shape_hint or "unknown",
    }

    if preset_id:
        preset_db = db.query(UserPresetDB).filter(UserPresetDB.id == preset_id).first()
    else:
        preset_db = (
            db.query(UserPresetDB)
            .filter(
                UserPresetDB.project_id == project_id,
                UserPresetDB.style_profile_slug == style_profile_slug,
            )
            .first()
        )

    if not preset_db:
        preset_db = UserPresetDB(
            id=str(uuid4()),
            project_id=project_id,
            style_profile_slug=style_profile_slug,
            complexity=0.5,
            symmetry=0.5,
            density=0.5,
            noise=0.5,
            motion=0.5,
            created_at=datetime.utcnow(),
        )
        db.add(preset_db)
        db.commit()
        db.refresh(preset_db)

    user_preset = {
        "id": preset_db.id,
        "complexity": override_sliders.get("complexity", preset_db.complexity),
        "symmetry": override_sliders.get("symmetry", preset_db.symmetry),
        "density": override_sliders.get("density", preset_db.density),
        "noise": override_sliders.get("noise", preset_db.noise),
        "motion": override_sliders.get("motion", preset_db.motion),
    }

    try:
        render_params_obj, style_profile, interp_profile = resolve_render_params(
            project_id=project_id,
            analysis_id=analysis_id,
            perceptual=perceptual,
            style_profile_slug=style_profile_slug,
            interpretation_profile_slug=interpretation_profile_slug,
            user_preset=user_preset,
        )
    except ValueError as e:
        msg = str(e)
        if msg.startswith("unknown_style_profile"):
            raise HTTPException(status_code=400, detail=msg)
        if msg.startswith("unknown_interpretation_profile"):
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=500, detail=msg)

    job_id = str(uuid4())
    now = datetime.utcnow()
    render_params_json = json.dumps(render_params_obj.__dict__, ensure_ascii=False)

    job_db = GenerationJobDB(
        id=job_id,
        project_id=project_id,
        analysis_id=analysis_id,
        preset_id=preset_db.id,
        status="pending",
        output_type="poster_preview",
        render_params=render_params_json,
        created_at=now,
        completed_at=None,
        error_message=None,
    )
    db.add(job_db)
    db.commit()
    db.refresh(job_db)

    return {
        "status": "success",
        "project_id": project_id,
        "analysis_id": analysis_id,
        "generation_job_id": job_id,
        "preset_id": preset_db.id,
        "style_profile_slug": style_profile.slug,
        "interpretation_profile_slug": interp_profile.slug,
        "render_params": render_params_obj.__dict__,
    }


# =======================
# Poster generation (через fractal backend adapter)
# =======================


@app.post("/generate/poster", response_model=GenerationJob)
async def generate_poster(project_id: str, analysis_id: str, preset_id: str, db=Depends(get_db)):
    project_db = db.query(UserProjectDB).filter(UserProjectDB.id == project_id).first()
    if not project_db:
        raise HTTPException(status_code=404, detail="Project not found")

    analysis_db = db.query(AudioAnalysisDB).filter(AudioAnalysisDB.id == analysis_id).first()
    if not analysis_db:
        raise HTTPException(status_code=404, detail="Analysis not found")

    preset_db = db.query(UserPresetDB).filter(UserPresetDB.id == preset_id).first()
    if not preset_db:
        raise HTTPException(status_code=404, detail="Preset not found")

    perceptual_db = (
        db.query(PerceptualLatentDB)
        .filter(PerceptualLatentDB.analysis_id == analysis_id)
        .first()
    )
    if not perceptual_db:
        raise HTTPException(status_code=400, detail="PerceptualLatent not found for analysis")

    perceptual = {
        "energy": perceptual_db.energy or 0.0,
        "tension": perceptual_db.tension or 0.0,
        "density": perceptual_db.density or 0.0,
        "brightness": perceptual_db.brightness or 0.0,
        "stability": perceptual_db.stability or 0.0,
        "smoothness": perceptual_db.smoothness or 0.0,
        "repetition": perceptual_db.repetition or 0.0,
        "section_complexity": perceptual_db.section_complexity or 0.0,
        "macro_shape_hint": perceptual_db.macro_shape_hint or "unknown",
    }

    job_db = (
        db.query(GenerationJobDB)
        .filter(
            GenerationJobDB.project_id == project_id,
            GenerationJobDB.analysis_id == analysis_id,
            GenerationJobDB.preset_id == preset_id,
        )
        .order_by(GenerationJobDB.created_at.desc())
        .first()
    )
    if not job_db:
        raise HTTPException(status_code=404, detail="GenerationJob not found for given preset")

    try:
        render_params_dict = json.loads(job_db.render_params)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse render_params JSON")

    render_params = RenderParams(
        style_profile_slug=render_params_dict.get("style_profile_slug"),
        interpretation_profile_slug=render_params_dict.get("interpretation_profile_slug"),
        preset_id=render_params_dict.get("preset_id"),
        symmetry_bias=float(render_params_dict.get("symmetry_bias", 0.5)),
        recursion_depth=float(render_params_dict.get("recursion_depth", 0.5)),
        density_level=float(render_params_dict.get("density_level", 0.5)),
        noise_level=float(render_params_dict.get("noise_level", 0.5)),
        motion_intensity=float(render_params_dict.get("motion_intensity", 0.5)),
        palette_id=render_params_dict.get("palette_id"),
        stochastic_term=float(render_params_dict.get("stochastic_term", 0.25)),
        layout_macro_shape=render_params_dict.get("layout_macro_shape", "ABA_like"),
        texture_complexity=float(render_params_dict.get("texture_complexity", 0.5)),
        variation_seed=int(render_params_dict.get("variation_seed", 0)),
    )

    # --- Строим CompositionPlan ---
    # Собираем features из analysis_db для planner (только устойчивые поля)
    analysis_features_for_planner = {
        "bpm": analysis_db.bpm or 120.0,
        "energy": analysis_db.energy or 0.1,
        "repetition_score": analysis_db.repetition_score or 0.5,
        # band_energy полей нет в AudioAnalysisDB — берём из perceptual или 0
        # (planner использует дефолты если ключей нет)
    }
    style_slug_for_planner = render_params_dict.get("style_profile_slug", "default")
    seed_for_planner = int(render_params_dict.get("variation_seed", 0))

    composition_plan = _build_composition_plan_safe(
        perceptual=perceptual,
        features=analysis_features_for_planner,
        style_profile_slug=style_slug_for_planner,
        seed=seed_for_planner,
    )

    if composition_plan is not None:
        logger.info(
            "CompositionPlan built: archetype=%s density=%.3f motifs=%d",
            composition_plan.archetype,
            composition_plan.density,
            composition_plan.motif.count if composition_plan.motif else 0,
        )

    poster_id = str(uuid4())
    poster_filename = f"{poster_id}.png"
    poster_path = os.path.join(POSTER_ROOT, poster_filename)

    poster_meta = render_poster_adapter(
        render_params=render_params,
        perceptual=perceptual,
        output_path=poster_path,
        composition_plan=composition_plan,
    )

    now = datetime.utcnow()
    job_db.status = "completed"
    job_db.completed_at = now
    db.add(job_db)

    asset_db = PosterAssetDB(
        id=poster_id,
        job_id=job_db.id,
        storage_path=poster_path,
        preview_path=poster_path,
        width=poster_meta.get("width", 1200),
        height=poster_meta.get("height", 1200),
        watermarked=False,
        is_hi_res=False,
        project_id=project_id,
    )
    db.add(asset_db)
    db.commit()
    db.refresh(job_db)

    render_params_dict["generator_name"] = poster_meta.get("generator_name")
    render_params_dict["composition_archetype"] = poster_meta.get("composition_archetype")

    return GenerationJob(
        id=job_db.id,
        project_id=job_db.project_id,
        analysis_id=job_db.analysis_id,
        preset_id=job_db.preset_id,
        status=job_db.status,
        output_type=job_db.output_type,
        render_params=render_params_dict,
        created_at=job_db.created_at,
        completed_at=job_db.completed_at,
        error_message=job_db.error_message,
        output_path=poster_path,
    )


# =======================
# Maintenance endpoints
# =======================


@app.post("/maintenance/cleanup-audio")
async def maintenance_cleanup_audio(
    max_age_days: int = 7,
):
    deleted = cleanup_audio_storage(max_age_days=max_age_days)
    return {
        "status": "success",
        "max_age_days": max_age_days,
        "deleted_files": deleted,
    }


# =======================
# Export (заглушка)
# =======================


@app.post("/export", response_model=ExportJob)
async def export_asset(asset_id: str, format: str = "png", db=Depends(get_db)):
    asset_db = db.query(PosterAssetDB).filter(PosterAssetDB.id == asset_id).first()
    if not asset_db:
        raise HTTPException(status_code=404, detail="Asset not found")

    export_id = str(uuid4())
    now = datetime.utcnow()
    download_url = f"https://example.com/download/{export_id}"

    export_db = ExportJobDB(
        id=export_id,
        asset_id=asset_id,
        format=format,
        preset=None,
        status="pending",
        output_path="",
        download_url=download_url,
        created_at=now,
        completed_at=None,
    )
    db.add(export_db)
    db.commit()
    db.refresh(export_db)

    return ExportJob.model_validate(export_db)
