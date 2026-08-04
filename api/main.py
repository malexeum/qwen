# api/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import os
import shutil
import mimetypes

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# =======================
# DB setup (SQLite)
# =======================

DB_URL = "sqlite:///./data/fractal_identity.db"
os.makedirs("data", exist_ok=True)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# =======================
# ORM models
# =======================

class UserProjectDB(Base):
    __tablename__ = "user_projects"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    name = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    project_state = Column(String)

    tracks = relationship("TrackDB", back_populates="project")


class TrackDB(Base):
    __tablename__ = "tracks"

    id = Column(String, primary_key=True, index=True)
    source_type = Column(String)  # "mic" | "file"
    storage_path = Column(String)
    duration_sec = Column(Float, nullable=True)
    format = Column(String)
    created_at = Column(DateTime)
    project_id = Column(String, ForeignKey("user_projects.id"))

    project = relationship("UserProjectDB", back_populates="tracks")


# TODO: дополнительные таблицы (AudioAnalysisDB, UserPresetDB, GenerationJobDB, PosterAssetDB, ExportJobDB)
# чтобы не перегружать skeleton, пока оставляем их заглушками, добавим на следующих шагах.


def init_db():
    Base.metadata.create_all(bind=engine)


# =======================
# Pydantic schemas
# =======================

class Track(BaseModel):
    id: str
    source_type: str
    storage_path: str
    duration_sec: Optional[float] = None
    format: str
    created_at: datetime
    project_id: str


class UserProject(BaseModel):
    id: str
    user_id: str
    name: str
    tracks: List[Track] = []
    created_at: datetime
    updated_at: datetime
    project_state: str

    class Config:
        orm_mode = True


class CreateProjectRequest(BaseModel):
    user_id: str
    name: str


class ProjectResponse(UserProject):
    pass


# =======================
# Storage utilities
# =======================

AUDIO_ROOT = "storage/audio"
os.makedirs(AUDIO_ROOT, exist_ok=True)

ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/x-mpeg"}


def guess_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def save_uploaded_file(project_id: str, file: UploadFile) -> str:
    """
    Save uploaded audio file under deterministic path:
    storage/audio/<project_id>/<uuid4>.<ext>
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
# FastAPI app
# =======================

app = FastAPI(title="Fractal Identity Engine API v0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # для MVP можно оставить, потом сузить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


# =======================
# Dependency
# =======================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =======================
# Endpoints
# =======================

from fastapi import Depends


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

    # tracks подтянутся через relationship и orm_mode
    return project_db


@app.post("/upload", response_model=Track)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    # проверить наличие проекта
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
        duration_sec=None,  # пока не знаем, заполним после анализа
        format=format_ext,
        created_at=now,
        project_id=project_id,
    )
    db.add(track_db)
    db.commit()
    db.refresh(track_db)

    return Track(
        id=track_db.id,
        source_type=track_db.source_type,
        storage_path=track_db.storage_path,
        duration_sec=track_db.duration_sec,
        format=track_db.format,
        created_at=track_db.created_at,
        project_id=track_db.project_id,
    )


# Заглушки для следующих шагов

@app.post("/capture")
async def capture_audio(project_id: str):
    # TODO: реализовать контракт для микрофона (Issue 3/4)
    return {"status": "capture_not_implemented_yet", "project_id": project_id}


@app.post("/analyze")
async def analyze_audio(project_id: str, track_id: str):
    # TODO: использовать lib/audio_analysis + запись AudioAnalysisDB
    return {"status": "analyze_not_implemented_yet", "project_id": project_id, "track_id": track_id}


@app.post("/resolve-style")
async def resolve_style(project_id: str, analysis_id: str, preset_id: str):
    # TODO: загрузка StyleProfile из YAML + RenderParams
    return {"status": "resolve_style_not_implemented_yet"}


@app.post("/generate/poster")
async def generate_poster(project_id: str, job_id: Optional[str] = None):
    # TODO: использовать lib/fractal_engine.core и создать PosterAssetDB
    return {"status": "generate_poster_not_implemented_yet"}


@app.post("/export")
async def export_asset(asset_id: str, format: str = "png"):
    # TODO: создать ExportJobDB, сгенерировать download_url
    return {"status": "export_not_implemented_yet", "asset_id": asset_id, "format": format}