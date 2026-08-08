"""End-to-end интеграционный тест всей цепочки:
    audio_features → build_perceptual_latent
    → PerceptualLatent / RenderParams / TrackMetadata
    → build_visual_composition_plan
    → execute_plan → PNG

Использует только синтетические признаки — реальный аудио-файл не нужен.

Доступные style_profile_slug (configs/visual_composition_profiles.yaml):
  blues_jazz, electronic, jazz, ambient, classical
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lib.audio_analysis.analysis import build_perceptual_latent
from lib.composition.planner import (
    build_visual_composition_plan,
    PerceptualLatent,
    RenderParams,
    TrackMetadata,
)
from lib.reference_renderer.execute_plan import execute_plan, RenderResult


# ──────────────────────────────────────────────────────────────────────────────
# Синтетические raw audio_features
# ──────────────────────────────────────────────────────────────────────────────

_BASE_AUDIO_FEATURES = {
    "bpm": 120.0,
    "key": "A",
    "energy": 0.15,
    "spectral_centroid": 2200.0,
    "brightness": 0.10,
    "rhythm_density": 0.50,
    "dynamic_range": 14.0,
    "duration_sec": 180.0,
    "repetition_score": 0.80,
    "silence_rate": 0.05,
    "harmonic_stability": 0.75,
    "harmonic_change_rate_hz": 0.3,
    "spectral_flatness": 0.10,
    "high_frequency_energy_ratio": 0.15,
    "suggested_music_style": "blues",
    "sections": [
        {"id": "S1", "label": "Section 1", "start_sec": 0.0,   "end_sec": 30.0},
        {"id": "S2", "label": "Section 2", "start_sec": 30.0,  "end_sec": 60.0},
        {"id": "S3", "label": "Section 3", "start_sec": 60.0,  "end_sec": 90.0},
        {"id": "S4", "label": "Section 4", "start_sec": 90.0,  "end_sec": 120.0},
        {"id": "S5", "label": "Section 5", "start_sec": 120.0, "end_sec": 150.0},
        {"id": "S6", "label": "Section 6", "start_sec": 150.0, "end_sec": 180.0},
    ],
    "recurrence_groups": [
        {"group_id": "G1", "sections": ["S1", "S3"]},
        {"group_id": "G2", "sections": ["S2", "S4"]},
    ],
    "events": [
        {"type": "energy_peak", "time_sec": 15.0,  "description": "High energy frame"},
        {"type": "energy_peak", "time_sec": 75.0,  "description": "High energy frame"},
        {"type": "energy_peak", "time_sec": 135.0, "description": "High energy frame"},
    ],
}

# Маппинг suggested_music_style → style_profile_slug
# Соответствует profiles в configs/visual_composition_profiles.yaml
_SLUG_MAP = {
    "blues":      "blues_jazz",
    "jazz":       "jazz",
    "electronic": "electronic",
    "ambient":    "ambient",
    "classical":  "classical",
    "rock":       "electronic",
    "pop":        "blues_jazz",
    "soundtrack": "classical",
    "mixed":      "blues_jazz",
}
_SLUG_DEFAULT = "blues_jazz"


def _make_audio_features(overrides: dict | None = None) -> dict:
    f = dict(_BASE_AUDIO_FEATURES)
    if overrides:
        f.update(overrides)
    return f


def _latent_from_features(features: dict) -> PerceptualLatent:
    """audio_features dict → PerceptualLatent dataclass."""
    lat = build_perceptual_latent(features)
    max_bpm = 220.0
    return PerceptualLatent(
        energy=float(lat.get("energy", 0.5)),
        tension=float(lat.get("tension", 0.5)),
        repetition=float(lat.get("repetition", 0.5)),
        tempo=float(min(lat.get("tempo_bpm", 120.0) / max_bpm, 1.0)),
        section_complexity=float(lat.get("section_complexity", 0.5)),
        silence_rate=float(lat.get("silence_rate", 0.2)),
        harmonic_stability=float(lat.get("harmonic_stability", 0.5)),
        harmonic_change_rate=float(min(lat.get("harmonic_change_rate_hz", 0.0), 1.0)),
        spectral_flatness=float(lat.get("spectral_flatness", 0.5)),
        high_frequency_energy=float(lat.get("high_frequency_energy_ratio", 0.5)),
    )


def _render_params_from_features(features: dict) -> RenderParams:
    """audio_features dict → RenderParams dataclass."""
    style = features.get("suggested_music_style", "blues")
    profile_slug = _SLUG_MAP.get(style, _SLUG_DEFAULT)
    lat = build_perceptual_latent(features)
    return RenderParams(
        style_profile_slug=profile_slug,
        symmetry_bias=float(lat.get("stability", 0.5)),
        density_level=float(lat.get("density", 0.5)),
        noise_level=float(lat.get("spectral_flatness", 0.1)),
        motion_intensity=float(lat.get("tension", 0.5)),
        texture_complexity=float(lat.get("section_complexity", 0.5)),
        palette_id="",  # берётся из профиля
    )


def _track_meta(audio_hash: str, title: str, artist: str) -> TrackMetadata:
    return TrackMetadata(
        audio_content_hash=audio_hash,
        title=title,
        artist=artist,
        duration_ms=180_000,
    )


def _make_plan(
    features: dict,
    audio_hash: str = "e2e_hash_0000",
    title: str = "E2E Test Track",
    artist: str = "E2E Artist",
    save_artifacts: bool = False,
):
    perceptual = _latent_from_features(features)
    render_p   = _render_params_from_features(features)
    track_meta = _track_meta(audio_hash, title, artist)
    return build_visual_composition_plan(
        perceptual=perceptual,
        render_params=render_p,
        track_metadata=track_meta,
        save_artifacts=save_artifacts,
    )


# ─── 5 стилей, по одному на каждый профиль ────────────────────────────────────

STYLES = [
    ("blues",     {"suggested_music_style": "blues",      "bpm": 110.0, "brightness": 0.08, "repetition_score": 0.90}),
    ("electronic",{"suggested_music_style": "electronic",  "bpm": 145.0, "energy": 0.30,    "brightness": 0.25, "rhythm_density": 0.65}),
    ("jazz",      {"suggested_music_style": "jazz",        "bpm": 115.0, "brightness": 0.12, "energy": 0.14}),
    ("ambient",   {"suggested_music_style": "ambient",     "bpm": 75.0,  "brightness": 0.05, "rhythm_density": 0.35, "energy": 0.08}),
    ("classical", {"suggested_music_style": "classical",   "bpm": 90.0,  "brightness": 0.07, "energy": 0.09,   "repetition_score": 0.60}),
]


# ─── Фикстуры pytest ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def blues_features():
    return _make_audio_features()


@pytest.fixture(scope="module")
def blues_latent_dict(blues_features):
    return build_perceptual_latent(blues_features)


@pytest.fixture(scope="module")
def blues_plan(blues_features):
    return _make_plan(blues_features, audio_hash="e2e_test_blues_0000",
                     title="Blues Test Track", artist="E2E Artist")


# ─── Тесты цепочки ───────────────────────────────────────────────────────────

class TestPipelineStages:
    """E2E — поэтапная проверка выхода каждого этапа."""

    def test_latent_keys(self, blues_latent_dict):
        expected = {
            "energy", "tension", "density", "brightness", "stability",
            "smoothness", "repetition", "section_complexity", "macro_shape_hint",
            "tempo_bpm", "silence_rate", "harmonic_stability",
            "harmonic_change_rate_hz", "spectral_flatness", "high_frequency_energy_ratio",
        }
        assert expected.issubset(set(blues_latent_dict.keys()))

    def test_latent_ranges(self, blues_latent_dict):
        for field in ["energy", "tension", "density", "brightness",
                      "stability", "smoothness", "repetition", "section_complexity"]:
            v = blues_latent_dict[field]
            assert 0.0 <= v <= 1.0, f"{field}={v} out of [0,1]"
        assert blues_latent_dict["tempo_bpm"] > 0.0

    def test_plan_schema_version(self, blues_plan):
        assert blues_plan.schema_version == "visual-composition-plan/v0.3"

    def test_plan_has_layers(self, blues_plan):
        enabled = [l for l in blues_plan.layers if l.enabled]
        assert len(enabled) >= 3, f"only {len(enabled)} enabled layers"

    def test_plan_canvas(self, blues_plan):
        assert blues_plan.canvas.width_px == 1024
        assert blues_plan.canvas.height_px == 1024
        assert blues_plan.canvas.color_space == "sRGB"

    def test_plan_visual_identity(self, blues_plan):
        vi = blues_plan.visual_identity
        palette_id = vi.get("palette_id") if isinstance(vi, dict) else getattr(vi, "palette_id", None)
        assert palette_id, "visual_identity.palette_id is empty"

    def test_render_no_save(self, blues_plan):
        result = execute_plan(blues_plan, save_png=False)
        assert isinstance(result, RenderResult)
        assert result.plan_id == blues_plan.plan_id
        assert result.width == 1024
        assert result.height == 1024
        assert result.layers_rendered >= 3

    def test_render_saves_png(self, blues_plan, tmp_path):
        result = execute_plan(blues_plan, output_dir=tmp_path, save_png=True)
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.output_path.stat().st_size > 10_000


class TestMultiStylePipeline:
    """E2E — все 5 профилей проходят полный цикл перед рендером."""

    @pytest.mark.parametrize("style,overrides", STYLES)
    def test_plan_and_render(self, style, overrides):
        features = _make_audio_features(overrides)
        plan     = _make_plan(features, audio_hash=f"e2e_{style}_0000",
                              title=f"{style.capitalize()} Test Track",
                              artist="E2E Artist")
        result   = execute_plan(plan, save_png=False)
        assert result.layers_rendered >= 1, f"{style}: ни одного отрендеренного слоя"
        assert result.width == 1024 and result.height == 1024


class TestDeterminism:
    """E2E — два последовательных запуска → идентичный plan_id."""

    def test_plan_id_stable(self):
        features = _make_audio_features()
        p1 = _make_plan(features, audio_hash="det_hash", title="Det Track", artist="Det Artist")
        p2 = _make_plan(features, audio_hash="det_hash", title="Det Track", artist="Det Artist")
        assert p1.plan_id == p2.plan_id, "plan_id нестабилен между запусками"

    def test_render_layers_count_stable(self):
        features = _make_audio_features()
        plan = _make_plan(features, audio_hash="det_hash", title="Det Track", artist="Det Artist")
        r1 = execute_plan(plan, save_png=False)
        r2 = execute_plan(plan, save_png=False)
        assert r1.layers_rendered == r2.layers_rendered


class TestEdgeCases:
    """E2E — граничные значения признаков."""

    def test_silence_track(self):
        """energy=0, rhythm_density=0 — пиплайн не падает."""
        features = _make_audio_features({"energy": 0.0, "rhythm_density": 0.0,
                                         "brightness": 0.0, "dynamic_range": 0.0,
                                         "suggested_music_style": "ambient"})
        plan   = _make_plan(features, audio_hash="silence_hash", title="Silence", artist="None")
        result = execute_plan(plan, save_png=False)
        assert result.width == 1024

    def test_extreme_bpm(self):
        """bpm=300 (drum&bass) — планировщик не падает."""
        features = _make_audio_features({"bpm": 300.0, "energy": 0.35,
                                         "rhythm_density": 0.80, "brightness": 0.30,
                                         "suggested_music_style": "electronic"})
        plan   = _make_plan(features, audio_hash="extreme_bpm_hash", title="Extreme BPM", artist="None")
        result = execute_plan(plan, save_png=False)
        assert result.width == 1024

    def test_png_content_not_black(self, tmp_path):
        """PNG не чёрный лист: std пикселей > 0."""
        from PIL import Image
        features = _make_audio_features()
        plan     = _make_plan(features, audio_hash="content_check",
                              title="Content Check", artist="Test")
        result   = execute_plan(plan, output_dir=tmp_path, save_png=True)
        img = np.array(Image.open(result.output_path))
        assert img.std() > 1.0, "PNG выглядит чёрным/однородным"
