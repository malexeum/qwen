from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class Track(BaseModel):
    id: str
    source_type: str
    storage_path: str
    duration_sec: Optional[float] = None
    format: str
    created_at: datetime
    project_id: str

    model_config = ConfigDict(from_attributes=True)


class AudioAnalysis(BaseModel):
    id: str
    track_id: str
    project_id: str
    bpm: Optional[float] = None
    key: Optional[str] = None
    energy: Optional[float] = None
    spectral_centroid: Optional[float] = None
    brightness: Optional[float] = None
    rhythm_density: Optional[float] = None
    dynamic_range: Optional[float] = None
    duration_sec: Optional[float] = None
    repetition_score: Optional[float] = None
    suggested_music_style: Optional[str] = None
    created_at: datetime

    sections: Optional[List[Dict[str, Any]]] = None
    recurrence_groups: Optional[List[Dict[str, Any]]] = None
    events: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)


class PerceptualLatent(BaseModel):
    id: str
    analysis_id: str
    track_id: str

    energy: Optional[float] = None
    tension: Optional[float] = None
    density: Optional[float] = None
    brightness: Optional[float] = None
    stability: Optional[float] = None
    smoothness: Optional[float] = None
    repetition: Optional[float] = None
    section_complexity: Optional[float] = None
    macro_shape_hint: Optional[str] = None

    tempo_bpm: Optional[float] = None
    silence_rate: Optional[float] = None
    harmonic_stability: Optional[float] = None
    harmonic_change_rate_hz: Optional[float] = None
    spectral_flatness: Optional[float] = None
    high_frequency_energy_ratio: Optional[float] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPreset(BaseModel):
    id: str
    project_id: str
    style_profile_slug: str
    complexity: float
    symmetry: float
    density: float
    noise: float
    motion: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerationJob(BaseModel):
    id: str
    project_id: str
    analysis_id: str
    preset_id: str
    status: str
    output_type: str
    render_params: dict
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PosterAsset(BaseModel):
    id: str
    job_id: str
    project_id: str
    storage_path: str
    preview_path: str
    width: int
    height: int
    watermarked: bool
    is_hi_res: bool

    model_config = ConfigDict(from_attributes=True)


class ExportJob(BaseModel):
    id: str
    asset_id: str
    format: str
    preset: Optional[str] = None
    status: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProject(BaseModel):
    id: str
    user_id: str
    name: str
    tracks: List[Track] = []
    analyses: List[AudioAnalysis] = []
    presets: List[UserPreset] = []
    jobs: List[GenerationJob] = []
    assets: List[PosterAsset] = []
    created_at: datetime
    updated_at: datetime
    project_state: str

    model_config = ConfigDict(from_attributes=True)


class CreateProjectRequest(BaseModel):
    user_id: str
    name: str


class ProjectResponse(UserProject):
    pass


class AnalyzeResponse(BaseModel):
    status: str
    project_id: str
    track_id: str
    analysis_id: str
    features: Dict[str, Any]
    suggested_music_style: str
    perceptual: Optional[Dict[str, Any]] = None