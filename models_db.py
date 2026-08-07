# api/models_db.py

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

# =======================
# DB setup (SQLite)
# =======================

DB_URL = "sqlite:///./data/fractal_identity.db"
os.makedirs("data", exist_ok=True)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =======================
# ORM models (Issue 2 + v0.2.1)
# =======================


class UserProjectDB(Base):
    __tablename__ = "user_projects"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    project_state = Column(String)

    tracks = relationship(
        "TrackDB",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    analyses = relationship(
        "AudioAnalysisDB",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    presets = relationship(
        "UserPresetDB",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    jobs = relationship(
        "GenerationJobDB",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    assets = relationship(
        "PosterAssetDB",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class TrackDB(Base):
    __tablename__ = "tracks"

    id = Column(String, primary_key=True, index=True)
    source_type = Column(String)  # "mic" | "file"
    storage_path = Column(String)
    duration_sec = Column(Float, nullable=True)
    format = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    project_id = Column(String, ForeignKey("user_projects.id"))
    project = relationship("UserProjectDB", back_populates="tracks")

    analyses = relationship(
        "AudioAnalysisDB",
        back_populates="track",
        cascade="all, delete-orphan",
    )


class AudioAnalysisDB(Base):
    __tablename__ = "audio_analyses"

    id = Column(String, primary_key=True, index=True)
    track_id = Column(String, ForeignKey("tracks.id"))
    project_id = Column(String, ForeignKey("user_projects.id"))

    bpm = Column(Float, nullable=True)
    key = Column(String, nullable=True)
    energy = Column(Float, nullable=True)
    spectral_centroid = Column(Float, nullable=True)
    brightness = Column(Float, nullable=True)
    rhythm_density = Column(Float, nullable=True)
    dynamic_range = Column(Float, nullable=True)
    duration_sec = Column(Float, nullable=True)
    repetition_score = Column(Float, nullable=True)
    suggested_music_style = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Структурные поля (храним как JSON-строки для MVP)
    sections = Column(Text, nullable=True)           # JSON: [{id, label, start_sec, end_sec}, ...]
    recurrence_groups = Column(Text, nullable=True)  # JSON: [{group_id, sections: [...]}, ...]
    events = Column(Text, nullable=True)             # JSON: [{type, time_sec, description}, ...]

    track = relationship("TrackDB", back_populates="analyses")
    project = relationship("UserProjectDB", back_populates="analyses")


class PerceptualLatentDB(Base):
    __tablename__ = "perceptual_latents"

    id = Column(String, primary_key=True, index=True)
    analysis_id = Column(String, ForeignKey("audio_analyses.id"))
    track_id = Column(String, ForeignKey("tracks.id"))

    energy = Column(Float, nullable=True)
    tension = Column(Float, nullable=True)
    density = Column(Float, nullable=True)
    brightness = Column(Float, nullable=True)
    stability = Column(Float, nullable=True)
    smoothness = Column(Float, nullable=True)
    repetition = Column(Float, nullable=True)
    section_complexity = Column(Float, nullable=True)
    macro_shape_hint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("AudioAnalysisDB")
    track = relationship("TrackDB")


class UserPresetDB(Base):
    __tablename__ = "user_presets"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("user_projects.id"))
    style_profile_slug = Column(String)
    complexity = Column(Float)
    symmetry = Column(Float)
    density = Column(Float)
    noise = Column(Float)
    motion = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("UserProjectDB", back_populates="presets")


class GenerationJobDB(Base):
    __tablename__ = "generation_jobs"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("user_projects.id"))
    analysis_id = Column(String, ForeignKey("audio_analyses.id"))
    preset_id = Column(String, ForeignKey("user_presets.id"))

    status = Column(String)  # "pending" | "running" | "failed" | "completed"
    output_type = Column(String)  # "poster_preview" | "poster_master" | "gif_preview"
    render_params = Column(Text)  # JSON-строка с RenderParams
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    project = relationship("UserProjectDB", back_populates="jobs")
    analysis = relationship("AudioAnalysisDB")
    preset = relationship("UserPresetDB")
    assets = relationship(
        "PosterAssetDB",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class PosterAssetDB(Base):
    __tablename__ = "poster_assets"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("generation_jobs.id"))

    storage_path = Column(String)
    preview_path = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    watermarked = Column(Boolean, default=False)
    is_hi_res = Column(Boolean, default=False)

    job = relationship("GenerationJobDB", back_populates="assets")
    project_id = Column(String, ForeignKey("user_projects.id"))
    project = relationship("UserProjectDB", back_populates="assets")


class ExportJobDB(Base):
    __tablename__ = "export_jobs"

    id = Column(String, primary_key=True, index=True)
    asset_id = Column(String, ForeignKey("poster_assets.id"))

    format = Column(String)  # "png" | "jpg"
    preset = Column(String, nullable=True)
    status = Column(String)  # "pending" | "running" | "failed" | "completed"
    output_path = Column(String, nullable=True)
    download_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    asset = relationship("PosterAssetDB")


def init_db():
    Base.metadata.create_all(bind=engine)