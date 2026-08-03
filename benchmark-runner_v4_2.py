from __future__ import annotations

import csv
import hashlib
import importlib.machinery
import importlib.util
import json
import math
import sys
import time
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import yaml
from scipy.stats import bootstrap
import warnings

# Глушим технические предупреждения SciPy для детерминированных (нулевых) дисперсий
warnings.filterwarnings(
    'ignore',
    message='.*The BCa confidence interval cannot be calculated.*'
)
warnings.filterwarnings(
    'ignore',
    category=RuntimeWarning,
    module='scipy.stats._resampling'
)
warnings.filterwarnings(
    'ignore',
    message='.*DegenerateDataWarning.*'
)

ROOT = Path(__file__).resolve().parent
CONFIGS = ROOT / 'configs'
OUT = ROOT / 'output_v4'
BUNDLE = OUT / 'frozen_benchmark_bundle.json'
MANIFEST = OUT / 'manifest_full.json'

LIB_SEARCH_PATHS = [
    Path(r'd:\IFZ\qwen_coder\lib'),
    ROOT / 'lib',
    ROOT,
]

# ---------------------------------------------------------------------------
# Versioning constants (Section 5.2 of TZ). Any change here => new benchmark
# run, never patched silently mid-cycle.
# ---------------------------------------------------------------------------
COMPONENT_VERSIONS = {
    'generator_version': '3.1.0',
    'observer_version': '3.2.0',
    'feature_schema_version': '2.0.0',
    'identity_schema_version': '2.0.0',
    'distance_metric_version': '1.0.0',
    'bifurcation_detector_version': '4.0.0',
}
DISTANCE_METRIC_NAME = 'euclidean'
NORMALIZATION_SCHEME = 'robust_zscore_per_feature'

RUN_TABLE_HEADER = [
    'run_id',
    'generator',
    'experiment',
    'input_class',
    'output_class',
    'transition_type',
    'family_relation',
    'nearest_centroid_class',
    'instance_id',
    'seed',
    'deformation_step',
    'noise_level',
    'mapping_mode',
    'observer_version',
    'feature_schema_version',
    'identity_schema_version',
    'distance_metric_version',
    'status',
    'metric_missing_reason',
    'identity_confidence',
    'identity_breakage_score',
    'centroid_distance',
    'approx_morphology_score',
    'threshold_profile_used',
    'family_continuity_score',
    'breakage_confidence',
    'transition_confidence',
    'class_stability_index',
    'morphology_persistence_score',
    'observer_stability_score',
]
TIMING_HEADER = ['run_id', 'generator', 'experiment', 'elapsed_sec']
FAILED_HEADER = ['run_id', 'generator', 'experiment', 'input_class', 'instance_id',
                  'module_name', 'version', 'input_id', 'failure_stage', 'error']

NON_NUMERIC_FIELDS = {
    'run_id',
    'generator',
    'experiment',
    'input_class',
    'output_class',
    'transition_type',
    'family_relation',
    'nearest_centroid_class',
    'mapping_mode',
    'status',
    'metric_missing_reason',
    'observer_version',
    'feature_schema_version',
    'identity_schema_version',
    'distance_metric_version',
    'threshold_profile_used',
}

MORPHOLOGY_FEATURES = [
    # v4.1 core, retained for continuity
    'symmetry_score',
    'fractal_dim_proxy',
    'basin_entropy',
    'density_variation',
    'edge_density',
    'entropy_orbit',
    'entropy_visit',
    'kurt_orbit',
    'skew_orbit',
    'std_orbit',
    'std_visit',

    # stable field statistics
    'mad_orbit',
    'mad_visit',
    'iqr_orbit',
    'iqr_visit',
    'p90_p10_orbit',
    'p90_p10_visit',

    # multi-scale morphology
    'multi_scale_fractal_dim_s1',
    'multi_scale_fractal_dim_s2',
    'multi_scale_fractal_dim_s4',
    'multi_scale_edge_density_s1',
    'multi_scale_edge_density_s2',
    'multi_scale_edge_density_s4',
    'multi_scale_lacunarity_s1',
    'multi_scale_lacunarity_s2',
    'multi_scale_lacunarity_s4',
    'multi_scale_symmetry_s1',
    'multi_scale_symmetry_s2',
    'multi_scale_symmetry_s4',
    'multi_scale_basin_entropy_s1',
    'multi_scale_basin_entropy_s2',
    'multi_scale_basin_entropy_s4',

    # topology
    'topology_orbit_foreground_fraction',
    'topology_orbit_n_components',
    'topology_orbit_largest_component_fraction',
    'topology_orbit_mean_component_size',
    'topology_orbit_std_component_size',
    'topology_orbit_holes',
    'topology_orbit_euler_number',
    'topology_orbit_component_persistence',
    'topology_visit_foreground_fraction',
    'topology_visit_n_components',
    'topology_visit_largest_component_fraction',
    'topology_visit_mean_component_size',
    'topology_visit_std_component_size',
    'topology_visit_holes',
    'topology_visit_euler_number',
    'topology_visit_component_persistence',

    # boundary complexity
    'boundary_orbit_perimeter_fraction',
    'boundary_orbit_compactness',
    'boundary_orbit_shape_index',
    'boundary_orbit_boundary_density',
    'boundary_orbit_boundary_fractal_dim',
    'boundary_orbit_boundary_curvature_mean',
    'boundary_orbit_boundary_curvature_std',
    'boundary_visit_perimeter_fraction',
    'boundary_visit_compactness',
    'boundary_visit_shape_index',
    'boundary_visit_boundary_density',
    'boundary_visit_boundary_fractal_dim',
    'boundary_visit_boundary_curvature_mean',
    'boundary_visit_boundary_curvature_std',

    # basin geometry
    'basin_geom_orbit_area_mean',
    'basin_geom_orbit_area_std',
    'basin_geom_orbit_elongation_mean',
    'basin_geom_orbit_elongation_std',
    'basin_geom_orbit_bbox_fill_mean',
    'basin_geom_orbit_bbox_fill_std',
    'basin_geom_visit_area_mean',
    'basin_geom_visit_area_std',
    'basin_geom_visit_elongation_mean',
    'basin_geom_visit_elongation_std',
    'basin_geom_visit_bbox_fill_mean',
    'basin_geom_visit_bbox_fill_std',

    # curvature
    'curvature_orbit_mean',
    'curvature_orbit_std',
    'curvature_orbit_p90',
    'curvature_orbit_p50',
    'curvature_orbit_corner_density',
    'curvature_visit_mean',
    'curvature_visit_std',
    'curvature_visit_p90',
    'curvature_visit_p50',
    'curvature_visit_corner_density',

    # persistence / observer stability
    'persistence_scale_consistency',
    'persistence_topology_stability',
    'persistence_boundary_stability',
    'morphology_persistence_score',
    'observer_stability_proxy',
]

GENERATOR_SPECIFIC_FEATURES = {
    'duffing_lyapunov': ['lyapunov_mean', 'lyapunov_std', 'stability_gradient'],
    'chaotic_scattering': ['escape_time_mean', 'escape_time_std', 'basin_count'],
    'orbit_ifs_multi_trap': ['orbit_occupancy', 'trap_interaction_score', 'support_area'],
    'julia_orbit_trap': ['escape_ratio', 'trap_response_mean', 'connected_component_proxy'],
}

STATUS_SUCCESS = 'success'
STATUS_FAILED = 'failed'
STATUS_PARTIAL = 'partial'
STATUS_SKIPPED = 'skipped'


def extract_feature_dict(observe_mod, adapted_result) -> Dict[str, float]:
    proxy = type('ObserveProxy', (), {
        'orbit_map': adapted_result.orbit_map,
        'visit_density': adapted_result.visit_density,
        'orbitmap': adapted_result.orbit_map,
        'visitdensity': adapted_result.visit_density,
        'aux': getattr(adapted_result, 'aux', {}),
    })()

    feats = observe_mod.extract_features(proxy)
    out = {k: float(v) for k, v in feats.items()}

    # -----------------------------------------------------------------------
    # Backward-compatible mandatory keys
    # -----------------------------------------------------------------------
    out['symmetry_score'] = float(out.get('symmetry_score', 0.0))
    out['fractal_dim_proxy'] = float(out.get('fractal_dim_proxy', 0.0))
    out['basin_entropy'] = float(out.get('basin_entropy', 0.0))
    out['density_variation'] = float(
        out.get('density_variation', out.get('std_visit', out.get('std_orbit', 0.0)))
    )
    out['edge_density'] = float(out.get('edge_density', 0.0))
    out['entropy_orbit'] = float(out.get('entropy_orbit', 0.0))
    out['entropy_visit'] = float(out.get('entropy_visit', 0.0))
    out['kurt_orbit'] = float(out.get('kurt_orbit', 0.0))
    out['skew_orbit'] = float(out.get('skew_orbit', 0.0))
    out['std_orbit'] = float(out.get('std_orbit', 0.0))
    out['std_visit'] = float(out.get('std_visit', 0.0))

    # -----------------------------------------------------------------------
    # v4.2 stable field statistics
    # -----------------------------------------------------------------------
    out['mad_orbit'] = float(out.get('mad_orbit', 0.0))
    out['mad_visit'] = float(out.get('mad_visit', 0.0))
    out['iqr_orbit'] = float(out.get('iqr_orbit', 0.0))
    out['iqr_visit'] = float(out.get('iqr_visit', 0.0))
    out['p90_p10_orbit'] = float(out.get('p90_p10_orbit', 0.0))
    out['p90_p10_visit'] = float(out.get('p90_p10_visit', 0.0))

    # -----------------------------------------------------------------------
    # v4.2 multi-scale morphology
    # -----------------------------------------------------------------------
    for key in [
        'multi_scale_fractal_dim_s1',
        'multi_scale_fractal_dim_s2',
        'multi_scale_fractal_dim_s4',
        'multi_scale_edge_density_s1',
        'multi_scale_edge_density_s2',
        'multi_scale_edge_density_s4',
        'multi_scale_lacunarity_s1',
        'multi_scale_lacunarity_s2',
        'multi_scale_lacunarity_s4',
        'multi_scale_symmetry_s1',
        'multi_scale_symmetry_s2',
        'multi_scale_symmetry_s4',
        'multi_scale_basin_entropy_s1',
        'multi_scale_basin_entropy_s2',
        'multi_scale_basin_entropy_s4',
    ]:
        out[key] = float(out.get(key, 0.0))

    # -----------------------------------------------------------------------
    # v4.2 topology
    # -----------------------------------------------------------------------
    for key in [
        'topology_orbit_foreground_fraction',
        'topology_orbit_n_components',
        'topology_orbit_largest_component_fraction',
        'topology_orbit_mean_component_size',
        'topology_orbit_std_component_size',
        'topology_orbit_holes',
        'topology_orbit_euler_number',
        'topology_orbit_component_persistence',
        'topology_visit_foreground_fraction',
        'topology_visit_n_components',
        'topology_visit_largest_component_fraction',
        'topology_visit_mean_component_size',
        'topology_visit_std_component_size',
        'topology_visit_holes',
        'topology_visit_euler_number',
        'topology_visit_component_persistence',
    ]:
        out[key] = float(out.get(key, 0.0))

    # -----------------------------------------------------------------------
    # v4.2 boundary complexity
    # -----------------------------------------------------------------------
    for key in [
        'boundary_orbit_perimeter_fraction',
        'boundary_orbit_compactness',
        'boundary_orbit_shape_index',
        'boundary_orbit_boundary_density',
        'boundary_orbit_boundary_fractal_dim',
        'boundary_orbit_boundary_curvature_mean',
        'boundary_orbit_boundary_curvature_std',
        'boundary_visit_perimeter_fraction',
        'boundary_visit_compactness',
        'boundary_visit_shape_index',
        'boundary_visit_boundary_density',
        'boundary_visit_boundary_fractal_dim',
        'boundary_visit_boundary_curvature_mean',
        'boundary_visit_boundary_curvature_std',
    ]:
        out[key] = float(out.get(key, 0.0))

    # -----------------------------------------------------------------------
    # v4.2 basin geometry
    # -----------------------------------------------------------------------
    for key in [
        'basin_geom_orbit_area_mean',
        'basin_geom_orbit_area_std',
        'basin_geom_orbit_elongation_mean',
        'basin_geom_orbit_elongation_std',
        'basin_geom_orbit_bbox_fill_mean',
        'basin_geom_orbit_bbox_fill_std',
        'basin_geom_visit_area_mean',
        'basin_geom_visit_area_std',
        'basin_geom_visit_elongation_mean',
        'basin_geom_visit_elongation_std',
        'basin_geom_visit_bbox_fill_mean',
        'basin_geom_visit_bbox_fill_std',
    ]:
        out[key] = float(out.get(key, 0.0))

    # -----------------------------------------------------------------------
    # v4.2 curvature descriptors
    # -----------------------------------------------------------------------
    for key in [
        'curvature_orbit_mean',
        'curvature_orbit_std',
        'curvature_orbit_p90',
        'curvature_orbit_p50',
        'curvature_orbit_corner_density',
        'curvature_visit_mean',
        'curvature_visit_std',
        'curvature_visit_p90',
        'curvature_visit_p50',
        'curvature_visit_corner_density',
    ]:
        out[key] = float(out.get(key, 0.0))

    # -----------------------------------------------------------------------
    # v4.2 persistence / observer stability
    # -----------------------------------------------------------------------
    out['persistence_scale_consistency'] = float(out.get('persistence_scale_consistency', 0.0))
    out['persistence_topology_stability'] = float(out.get('persistence_topology_stability', 0.0))
    out['persistence_boundary_stability'] = float(out.get('persistence_boundary_stability', 0.0))
    out['morphology_persistence_score'] = float(out.get('morphology_persistence_score', 0.0))
    out['observer_stability_proxy'] = float(out.get('observer_stability_proxy', 0.0))

    return out


# ---------------------------------------------------------------------------
# Generic IO helpers
# ---------------------------------------------------------------------------
def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}

# ---------------------------------------------------------------------------
# Feature schema loader (v4.2)
# ---------------------------------------------------------------------------
def load_feature_schema(
    configs_dir: Path,
    fallback_features: List[str],
    filename: str = 'feature_schema_v2.yaml',
) -> Dict[str, Any]:
    """
    Загружает feature schema из YAML и возвращает нормализованную структуру:
      {
        'schema_name': str,
        'schema_version': str,
        'observer_version': str,
        'morphology_features': List[str],
        'generator_specific_features': Dict[str, List[str]],
        'raw': Dict[str, Any],
        'source_path': str,
        'loaded': bool,
        'error': str,
      }

    Если YAML отсутствует или некорректен, возвращает fallback-конфигурацию
    на основе встроенных MORPHOLOGY_FEATURES / GENERATOR_SPECIFIC_FEATURES.
    """
    out: Dict[str, Any] = {
        'schema_name': 'feature_schema_fallback',
        'schema_version': str(COMPONENT_VERSIONS.get('feature_schema_version', 'unknown')),
        'observer_version': str(COMPONENT_VERSIONS.get('observer_version', 'unknown')),
        'morphology_features': list(fallback_features),
        'generator_specific_features': dict(GENERATOR_SPECIFIC_FEATURES),
        'raw': {},
        'source_path': str(configs_dir / filename),
        'loaded': False,
        'error': '',
    }

    path = configs_dir / filename
    if not path.exists():
        out['error'] = f'feature_schema_file_not_found: {path}'
        return out

    try:
        data = load_yaml(path)
        if not isinstance(data, dict) or not data:
            out['error'] = f'feature_schema_invalid_or_empty: {path}'
            return out

        morphology_features: List[str] = []
        generator_specific_features: Dict[str, List[str]] = {}

        recommended_sets = data.get('recommended_sets', {})
        if isinstance(recommended_sets, dict):
            morph_block = recommended_sets.get('morphology_core_v42', {})
            if isinstance(morph_block, dict):
                fields = morph_block.get('fields', [])
                if isinstance(fields, list):
                    morphology_features = [str(x) for x in fields if str(x).strip()]

            gspec_block = recommended_sets.get('generator_specific_v42', {})
            if isinstance(gspec_block, dict):
                by_gen = gspec_block.get('fields_by_generator', {})
                if isinstance(by_gen, dict):
                    for gen, feats in by_gen.items():
                        if isinstance(feats, list):
                            generator_specific_features[str(gen)] = [
                                str(x) for x in feats if str(x).strip()
                            ]

        # Fallback: if recommended_sets missing, try to infer from groups
        if not morphology_features:
            groups = data.get('groups', {})
            if isinstance(groups, dict):
                for group_name, group_cfg in groups.items():
                    if str(group_name) == 'generator_specific':
                        continue
                    if not isinstance(group_cfg, dict):
                        continue
                    fields = group_cfg.get('fields', [])
                    if not isinstance(fields, list):
                        continue
                    for item in fields:
                        if not isinstance(item, dict):
                            continue
                        if bool(item.get('include_in_morphology', False)) and item.get('name'):
                            morphology_features.append(str(item['name']))

        if not generator_specific_features:
            groups = data.get('groups', {})
            gblock = groups.get('generator_specific', {}) if isinstance(groups, dict) else {}
            if isinstance(gblock, dict):
                by_gen = gblock.get('by_generator', {})
                if isinstance(by_gen, dict):
                    for gen, items in by_gen.items():
                        if not isinstance(items, list):
                            continue
                        feats = []
                        for item in items:
                            if isinstance(item, dict) and item.get('name'):
                                feats.append(str(item['name']))
                        if feats:
                            generator_specific_features[str(gen)] = feats

        # Final cleanup and deduplication preserving order
        seen = set()
        morphology_features_clean: List[str] = []
        for f in morphology_features:
            if f not in seen:
                morphology_features_clean.append(f)
                seen.add(f)

        if not morphology_features_clean:
            out['error'] = f'feature_schema_no_morphology_features: {path}'
            return out

        generator_specific_clean: Dict[str, List[str]] = {}
        for gen, feats in generator_specific_features.items():
            seen_local = set()
            clean_feats: List[str] = []
            for f in feats:
                if f not in seen_local:
                    clean_feats.append(f)
                    seen_local.add(f)
            generator_specific_clean[str(gen)] = clean_feats

        out.update({
            'schema_name': str(data.get('schema_name', 'feature_schema_v2')),
            'schema_version': str(data.get('schema_version', out['schema_version'])),
            'observer_version': str(data.get('observer_version', out['observer_version'])),
            'morphology_features': morphology_features_clean,
            'generator_specific_features': generator_specific_clean or dict(GENERATOR_SPECIFIC_FEATURES),
            'raw': data,
            'source_path': str(path),
            'loaded': True,
            'error': '',
        })
        return out

    except Exception as exc:
        out['error'] = f'feature_schema_load_failed: {repr(exc)}'
        return out

# ---------------------------------------------------------------------------
# Identity schema loader (v4.2)
# ---------------------------------------------------------------------------
def load_identity_schema(
    configs_dir: Path,
    run_table_header: List[str],
    filename: str = 'identity_schema_v2.yaml',
) -> Dict[str, Any]:
    """
    Загружает identity schema из YAML и возвращает нормализованную структуру:
      {
        'schema_name': str,
        'schema_version': str,
        'observer_version': str,
        'feature_schema_version': str,
        'expected_run_table_fields': List[str],
        'transition_types': Dict[str, Any],
        'raw': Dict[str, Any],
        'source_path': str,
        'loaded': bool,
        'valid_run_table': bool,
        'missing_run_table_fields': List[str],
        'error': str,
      }

    Если YAML отсутствует или некорректен, возвращает fallback-конфигурацию,
    согласованную с текущим classify_identity(...) и RUN_TABLE_HEADER.
    """
    fallback_expected_fields = [
        'output_class',
        'transition_type',
        'family_relation',
        'nearest_centroid_class',
        'identity_confidence',
        'identity_breakage_score',
        'centroid_distance',
        'approx_morphology_score',
        'threshold_profile_used',
        'family_continuity_score',
        'breakage_confidence',
        'transition_confidence',
        'class_stability_index',
        'observer_stability_score',
    ]

    fallback_transition_types = {
        'preserved': {
            'description': 'Identity preserved.',
            'output_class_pattern': 'preserved_{input_class}',
        },
        'transformed': {
            'description': 'Identity preserved but morphologically transformed.',
            'output_class_pattern': 'transformed_{input_class}',
        },
        'broken': {
            'description': 'Identity broken.',
            'output_class_pattern': 'broken_{input_class}',
        },
        'emergent': {
            'description': 'Emergent morphology, possibly linked to nearest centroid.',
            'output_class_pattern': {
                'unknown': 'emergent_unknown',
                'with_nearest': 'emergent_{nearest_centroid_class}',
            },
        },
        'unresolved': {
            'description': 'Identity unresolved because of missing data or failed run.',
            'output_class_pattern': 'unresolved_{input_class}',
        },
    }

    out: Dict[str, Any] = {
        'schema_name': 'identity_schema_fallback',
        'schema_version': str(COMPONENT_VERSIONS.get('identity_schema_version', 'unknown')),
        'observer_version': str(COMPONENT_VERSIONS.get('observer_version', 'unknown')),
        'feature_schema_version': str(COMPONENT_VERSIONS.get('feature_schema_version', 'unknown')),
        'expected_run_table_fields': list(fallback_expected_fields),
        'transition_types': dict(fallback_transition_types),
        'raw': {},
        'source_path': str(configs_dir / filename),
        'loaded': False,
        'valid_run_table': True,
        'missing_run_table_fields': [],
        'error': '',
    }

    path = configs_dir / filename
    if not path.exists():
        missing = [f for f in fallback_expected_fields if f not in run_table_header]
        out['valid_run_table'] = len(missing) == 0
        out['missing_run_table_fields'] = missing
        out['error'] = f'identity_schema_file_not_found: {path}'
        return out

    try:
        data = load_yaml(path)
        if not isinstance(data, dict) or not data:
            missing = [f for f in fallback_expected_fields if f not in run_table_header]
            out['valid_run_table'] = len(missing) == 0
            out['missing_run_table_fields'] = missing
            out['error'] = f'identity_schema_invalid_or_empty: {path}'
            return out

        expected_fields = data.get('expected_run_table_fields', fallback_expected_fields)
        if not isinstance(expected_fields, list) or not expected_fields:
            expected_fields = list(fallback_expected_fields)
        expected_fields = [str(x) for x in expected_fields if str(x).strip()]

        transition_types = data.get('transition_types', fallback_transition_types)
        if not isinstance(transition_types, dict) or not transition_types:
            transition_types = dict(fallback_transition_types)

        missing = [f for f in expected_fields if f not in run_table_header]

        out.update({
            'schema_name': str(data.get('schema_name', 'identity_schema_v2')),
            'schema_version': str(data.get('schema_version', out['schema_version'])),
            'observer_version': str(data.get('observer_version', out['observer_version'])),
            'feature_schema_version': str(data.get('feature_schema_version', out['feature_schema_version'])),
            'expected_run_table_fields': expected_fields,
            'transition_types': transition_types,
            'raw': data,
            'source_path': str(path),
            'loaded': True,
            'valid_run_table': len(missing) == 0,
            'missing_run_table_fields': missing,
            'error': '',
        })
        return out

    except Exception as exc:
        missing = [f for f in fallback_expected_fields if f not in run_table_header]
        out['valid_run_table'] = len(missing) == 0
        out['missing_run_table_fields'] = missing
        out['error'] = f'identity_schema_load_failed: {repr(exc)}'
        return out

def validate_schema_versions(
    feature_schema: Dict[str, Any],
    identity_schema: Dict[str, Any],
    taxonomy: Dict[str, Any],
    component_versions: Dict[str, str],
) -> None:
    """
    Сравнивает версии feature/identity schema из YAML, taxonomy и COMPONENT_VERSIONS
    и печатает предупреждения, если что-то разъехалось. Не бросает исключений.
    """
    fv_code = str(component_versions.get('feature_schema_version', 'unknown'))
    iv_code = str(component_versions.get('identity_schema_version', 'unknown'))
    ov_code = str(component_versions.get('observer_version', 'unknown'))

    fv_yaml = str(feature_schema.get('schema_version', 'unknown'))
    fv_yaml_name = str(feature_schema.get('schema_name', 'feature_schema'))
    fv_yaml_obs = str(feature_schema.get('observer_version', ov_code))

    iv_yaml = str(identity_schema.get('schema_version', 'unknown'))
    iv_yaml_name = str(identity_schema.get('schema_name', 'identity_schema'))
    iv_yaml_obs = str(identity_schema.get('observer_version', ov_code))
    iv_yaml_feat = str(identity_schema.get('feature_schema_version', fv_yaml))

    fv_tax = str(taxonomy.get('feature_schema_version', fv_code))
    iv_tax = str(taxonomy.get('identity_schema_version', iv_code))

    # Feature schema: code vs YAML vs taxonomy
    if fv_code != fv_yaml:
        print(
            f'[WARN] feature_schema_version mismatch: code={fv_code}, '
            f'{fv_yaml_name}={fv_yaml}',
            flush=True,
        )
    if fv_code != fv_tax:
        print(
            f'[WARN] feature_schema_version mismatch: code={fv_code}, '
            f'taxonomy={fv_tax}',
            flush=True,
        )
    if fv_yaml != fv_tax:
        print(
            f'[WARN] feature_schema_version mismatch: YAML={fv_yaml}, '
            f'taxonomy={fv_tax}',
            flush=True,
        )

    # Identity schema: code vs YAML vs taxonomy
    if iv_code != iv_yaml:
        print(
            f'[WARN] identity_schema_version mismatch: code={iv_code}, '
            f'{iv_yaml_name}={iv_yaml}',
            flush=True,
        )
    if iv_code != iv_tax:
        print(
            f'[WARN] identity_schema_version mismatch: code={iv_code}, '
            f'taxonomy={iv_tax}',
            flush=True,
        )
    if iv_yaml != iv_tax:
        print(
            f'[WARN] identity_schema_version mismatch: YAML={iv_yaml}, '
            f'taxonomy={iv_tax}',
            flush=True,
        )

    # Проверка согласованности observer_version
    if ov_code != fv_yaml_obs:
        print(
            f'[WARN] observer_version mismatch (feature schema): code={ov_code}, '
            f'feature_schema={fv_yaml_obs}',
            flush=True,
        )
    if ov_code != iv_yaml_obs:
        print(
            f'[WARN] observer_version mismatch (identity schema): code={ov_code}, '
            f'identity_schema={iv_yaml_obs}',
            flush=True,
        )

    # Identity schema должна ссылаться на ту же feature schema
    if fv_yaml != iv_yaml_feat:
        print(
            f'[WARN] identity_schema feature_schema_version mismatch: '
            f'feature_schema_yaml={fv_yaml}, identity_schema_yaml={iv_yaml_feat}',
            flush=True,
        )

def stable_seed(*parts: Any) -> int:
    s = '|'.join(map(str, parts)).encode('utf-8')
    return int(hashlib.sha256(s).hexdigest()[:16], 16) % (2 ** 32)


def clip01(x: Any) -> np.ndarray:
    return np.clip(np.asarray(x, dtype=float), 0.0, 1.0)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def write_csv_with_header(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    ensure_dir(path.parent)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Backend resolution (reused from v3.1)
# ---------------------------------------------------------------------------
def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load module {module_name} from {file_path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_lib_dir() -> Path:
    for path in LIB_SEARCH_PATHS:
        if path.exists() and (path / 'core.py').exists() and (path / 'generators.py').exists() \
                and (path / 'observe.py').exists() and (path / 'metrics.py').exists():
            return path
    raise FileNotFoundError('Could not resolve lib directory containing core.py, generators.py, observe.py, metrics.py')


def import_backend_modules(lib_dir: Path):
    package_name = 'fractal_backend_lib'
    if package_name not in sys.modules:
        pkg = importlib.util.module_from_spec(importlib.machinery.ModuleSpec(package_name, loader=None))
        pkg.__path__ = [str(lib_dir)]
        sys.modules[package_name] = pkg
    core_mod = load_module(f'{package_name}.core', lib_dir / 'core.py')
    generators_mod = load_module(f'{package_name}.generators', lib_dir / 'generators.py')
    observe_mod = load_module(f'{package_name}.observe', lib_dir / 'observe.py')
    metrics_mod = load_module(f'{package_name}.metrics', lib_dir / 'metrics.py')
    return core_mod, generators_mod, observe_mod, metrics_mod


def vector_to_harmony(core_mod, vec: np.ndarray):
    v = np.asarray(vec, dtype=float)
    if len(v) != 8:
        raise ValueError(f'Expected 8-dimensional input vector, got {len(v)}')
    spectral_profile = np.array([v[0], 0.5 * (v[0] + v[7]), v[3], v[6]], dtype=float)
    freq_ratios = np.array([v[1], 0.5 * (v[1] + v[2]), v[2]], dtype=float)
    return core_mod.Harmony(
        spectral_profile=spectral_profile,
        freq_ratios=freq_ratios,
        rhythmic_period=float(max(1e-3, v[2])),
        repetition_coeff=float(v[6]),
        tension=float(v[4]),
        symmetry=float(2.0 * v[5] - 1.0),
        density=float(v[3]),
        contrast=float(v[7]),
    )


def rule_based_theta(harmony, dim_out: int = 6) -> np.ndarray:
    vec = harmony.as_vector()
    chunks = np.array_split(vec, dim_out)
    theta = []
    for i, chunk in enumerate(chunks):
        val = np.mean(chunk) if len(chunk) else 0.0
        theta.append(np.tanh(1.5 * (val - 0.5) + 0.1 * math.sin(i + 1)))
    return np.array(theta, dtype=float)


def get_resolution_for_generator(mode: Dict[str, Any], generator: str) -> Tuple[int, int]:
    if generator == 'duffing_lyapunov':
        return tuple(mode.get('resolution_duffing', mode.get('resolution_default', [128, 128])))
    if generator == 'chaotic_scattering':
        return tuple(mode.get('resolution_scattering', mode.get('resolution_default', [128, 128])))
    return tuple(mode.get('resolution_default', [128, 128]))


def get_domain_for_generator(generator: str) -> Tuple[float, float, float, float]:
    if generator in {'julia_orbit_trap', 'orbit_ifs_multi_trap', 'chaotic_scattering'}:
        return (-2.0, 2.0, -2.0, 2.0)
    return (-1.0, 1.0, -1.0, 1.0)


def make_sim_state(core_mod, generator: str, theta: np.ndarray, mode: Dict[str, Any], seed: int, stochastic_scale: float):
    resolution = get_resolution_for_generator(mode, generator)
    max_iter = 200
    extra: Dict[str, Any] = {}
    if generator == 'orbit_ifs_multi_trap':
        extra['n_points'] = int(mode.get('ifs_points', 50000))
    elif generator == 'duffing_lyapunov':
        extra['n_steps'] = int(mode.get('duffing_steps', 400))
        max_iter = int(mode.get('duffing_steps', 400))
    elif generator == 'chaotic_scattering':
        max_iter = int(mode.get('duffing_steps', 400))
    return core_mod.SimState(
        generator_name=generator,
        theta=np.asarray(theta, dtype=float),
        resolution=tuple(map(int, resolution)),
        domain=get_domain_for_generator(generator),
        max_iter=max_iter,
        escape_radius=4.0,
        trap_kind='point',
        seed=int(seed),
        stochastic_scale=float(stochastic_scale),
        extra=extra,
    )


def get_generator_dispatch(generators_mod):
    return {
        'julia_orbit_trap': generators_mod.julia_orbit_trap,
        'orbit_ifs_multi_trap': generators_mod.orbit_ifs_multi_trap,
        'duffing_lyapunov': generators_mod.duffing_lyapunov_map,
        'chaotic_scattering': generators_mod.chaotic_scattering_basins,
    }


def run_baseline(generator: str, theta: np.ndarray, mode: Dict[str, Any], seed: int):
    rng = np.random.default_rng(seed)
    h, w = tuple(map(int, mode.get('resolution_default', [128, 128])))
    yy, xx = np.mgrid[0:h, 0:w]
    xx = (xx / max(w - 1, 1) - 0.5) * 2
    yy = (yy / max(h - 1, 1) - 0.5) * 2
    if generator == 'random_baseline':
        orbit = rng.random((h, w))
        visit = rng.poisson(1.0, size=(h, w)).astype(float)
    elif generator == 'smooth_geometric_baseline':
        orbit = np.exp(-3 * (xx ** 2 + yy ** 2)) * (1 + 0.2 * theta[0])
        visit = np.exp(-2 * ((xx - 0.2 * theta[1]) ** 2 + (yy + 0.2 * theta[2]) ** 2))
    else:
        orbit = 0.5 + 0.5 * np.sin((2 + abs(theta[0])) * np.pi * xx + theta[1])
        orbit *= 0.5 + 0.5 * np.cos((2 + abs(theta[2])) * np.pi * yy + theta[3])
        visit = np.abs(np.gradient(orbit)[0]) + np.abs(np.gradient(orbit)[1])
    return type('BaselineRunResult', (), {'orbit_map': orbit, 'visit_density': visit, 'aux': {'baseline': generator}})()


def adapt_result_fields(result):
    if hasattr(result, 'orbit_map') and hasattr(result, 'visit_density'):
        return result
    if hasattr(result, 'orbitmap') and hasattr(result, 'visitdensity'):
        return type('AdaptedRunResult', (), {
            'orbit_map': result.orbitmap,
            'visit_density': result.visitdensity,
            'aux': getattr(result, 'aux', {}),
        })()
    raise AttributeError('Result object does not expose orbit map / visit density fields')


def extract_feature_dict(observe_mod, adapted_result) -> Dict[str, float]:
    proxy = type('ObserveProxy', (), {
        'orbit_map': adapted_result.orbit_map,
        'visit_density': adapted_result.visit_density,
        'orbitmap': adapted_result.orbit_map,
        'visitdensity': adapted_result.visit_density,
        'aux': getattr(adapted_result, 'aux', {}),
    })()
    feats = observe_mod.extract_features(proxy)
    out = {k: float(v) for k, v in feats.items()}
    out['symmetry_score'] = float(out.get('symmetry_score', 0.0))
    out['fractal_dim_proxy'] = float(out.get('fractal_dim_proxy', 0.0))
    out['basin_entropy'] = float(out.get('basin_entropy', 0.0))
    out['density_variation'] = float(out.get('std_visit', out.get('std_orbit', 0.0)))
    return out


def compute_generator_specific_metrics(adapted_result: Any, generator: str) -> Dict[str, float]:
    orbit = np.asarray(adapted_result.orbit_map, dtype=float)
    visit = np.asarray(adapted_result.visit_density, dtype=float)
    out: Dict[str, float] = {}
    if generator == 'duffing_lyapunov':
        out['lyapunov_mean'] = float(np.mean(orbit))
        out['lyapunov_std'] = float(np.std(orbit))
        out['stability_gradient'] = float(np.mean(np.abs(np.gradient(orbit)[0])) + np.mean(np.abs(np.gradient(orbit)[1])))
    elif generator == 'chaotic_scattering':
        vals, counts = np.unique(orbit.astype(int), return_counts=True)
        out['escape_time_mean'] = float(np.mean(visit))
        out['escape_time_std'] = float(np.std(visit))
        out['basin_count'] = float(np.sum(vals >= 0))
    elif generator == 'orbit_ifs_multi_trap':
        out['orbit_occupancy'] = float(np.mean(visit > np.percentile(visit, 75)))
        out['trap_interaction_score'] = float(np.mean(np.log1p(visit)))
        out['support_area'] = float(np.mean(orbit > np.percentile(orbit, 60)))
    elif generator == 'julia_orbit_trap':
        out['escape_ratio'] = float(np.mean(orbit < np.median(orbit)))
        out['trap_response_mean'] = float(np.mean(visit))
        out['connected_component_proxy'] = float(np.sum(orbit > np.percentile(orbit, 80)))
    return out


# ---------------------------------------------------------------------------
# Config bundle (protocol + input_registry + output_taxonomy), frozen
# ---------------------------------------------------------------------------
def default_mapping_mode(protocol: Dict[str, Any]) -> str:
    mapping_cfg = protocol.get('mapping', {})
    if not isinstance(mapping_cfg, dict):
        return 'rule_based_mapping'
    return str(mapping_cfg.get('default_mapping_mode', 'rule_based_mapping'))


def default_generator_registry(protocol: Dict[str, Any], registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(registry.get('generators'), dict) and isinstance(registry['generators'].get('registry'), list):
        return registry['generators']['registry']
    generators_cfg = protocol.get('generators', {})
    nonlinear = generators_cfg.get('nonlinear', []) if isinstance(generators_cfg, dict) else []
    baselines = generators_cfg.get('baselines', []) if isinstance(generators_cfg, dict) else []
    out = [{'name': str(g), 'enabled': True, 'family': 'nonlinear', 'baseline': False} for g in nonlinear]
    out += [{'name': str(g), 'enabled': True, 'family': 'baseline', 'baseline': True} for g in baselines]
    if out:
        return out
    return [
        {'name': 'julia_orbit_trap', 'enabled': True, 'family': 'nonlinear', 'baseline': False},
        {'name': 'orbit_ifs_multi_trap', 'enabled': True, 'family': 'nonlinear', 'baseline': False},
        {'name': 'duffing_lyapunov', 'enabled': True, 'family': 'nonlinear', 'baseline': False},
        {'name': 'chaotic_scattering', 'enabled': True, 'family': 'nonlinear', 'baseline': False},
    ]


def choose_mode(protocol: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    runtime_cfg = protocol.get('runtime', {}) if isinstance(protocol.get('runtime', {}), dict) else {}
    active_mode = runtime_cfg.get('active_mode') or 'research-fast'
    modes = protocol.get('modes', {})

    default_mode = {
        'repeats_per_class': 3,
        'deformation_steps': 6,
        'sensitivity_steps': 15,
        'resolution_default': [128, 128],
        'resolution_duffing': [128, 128],
        'resolution_scattering': [128, 128],
    }

    if not isinstance(modes, dict) or not modes:
        mode_name = 'implicit-default'
        mode = dict(default_mode)
    elif active_mode in modes and isinstance(modes[active_mode], dict):
        mode_name = str(active_mode)
        mode = dict(modes[active_mode])
    else:
        first_key = next(iter(modes))
        val = modes[first_key]
        mode_name = str(first_key)
        mode = dict(val) if isinstance(val, dict) else dict(default_mode)

    noise_cfg = protocol.get('noise', {}) if isinstance(protocol.get('noise', {}), dict) else {}
    deformation_amp_cfg = noise_cfg.get('deformation_amplitude', {}) if isinstance(noise_cfg.get('deformation_amplitude', {}), dict) else {}

    if deformation_amp_cfg:
        mode['deformation_amplitude'] = {
            k: float(v) for k, v in deformation_amp_cfg.items()
        }
    else:
        mode['deformation_amplitude'] = {
            'julia_orbit_trap': 0.25,
            'orbit_ifs_multi_trap': 0.25,
            'duffing_lyapunov': 0.80,
            'chaotic_scattering': 0.25,
            'default': 0.25,
        }

    return mode_name, mode


def build_bundle() -> Dict[str, Any]:
    protocol_path = CONFIGS / 'experiment_protocol.yaml'
    registry_path = CONFIGS / 'input_registry.yaml'
    taxonomy_path = CONFIGS / 'output_taxonomy.yaml'
    for p in (protocol_path, registry_path, taxonomy_path):
        if not p.exists():
            raise FileNotFoundError(f'Missing required config: {p}')
    protocol = load_yaml(protocol_path)
    registry = load_yaml(registry_path)
    taxonomy = load_yaml(taxonomy_path)
    mode_name, mode = choose_mode(protocol)
    ctx = {
        'mode_name': mode_name,
        'mode': mode,
        'default_mapping_mode': default_mapping_mode(protocol),
        'generator_registry': default_generator_registry(protocol, registry),
        'benchmark_sets': registry.get('benchmark_sets', {}),
        'component_versions': COMPONENT_VERSIONS,
        'distance_metric_name': DISTANCE_METRIC_NAME,
        'normalization_scheme': NORMALIZATION_SCHEME,
    }
    return {
        'protocol_spec': {'source': str(protocol_path), 'sha256': sha256_file(protocol_path), 'content': protocol},
        'input_registry_spec': {'source': str(registry_path), 'sha256': sha256_file(registry_path), 'content': registry},
        'output_taxonomy_spec': {'source': str(taxonomy_path), 'sha256': sha256_file(taxonomy_path), 'content': taxonomy},
        'benchmark_context': ctx,
        'build_info': {'built_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'builder': 'benchmark-runner_v4'},
    }


def build_manifest() -> Dict[str, str]:
    ensure_dir(OUT)
    return {
        'run_table_path': str(OUT / 'run_table.csv'),
        'timing_profile_path': str(OUT / 'timing_profile.csv'),
        'features_raw_path': str(OUT / 'features_raw.csv'),
        'features_normalized_path': str(OUT / 'features_normalized.csv'),
        'aggregate_by_generator_path': str(OUT / 'aggregate_by_generator.csv'),
        'aggregate_by_class_path': str(OUT / 'aggregate_by_class.csv'),
        'aggregate_by_transition_path': str(OUT / 'aggregate_by_transition.csv'),
        'pairwise_distance_matrix_path': str(OUT / 'pairwise_distance_matrix.csv'),
        'bifurcation_events_path': str(OUT / 'bifurcation_events.csv'),
        'failed_runs_path': str(OUT / 'failed_runs.csv'),
        'summary_json_path': str(OUT / 'summary.json'),
        'research_report_md_path': str(OUT / 'research_report.md'),
        'manifest_full_path': str(MANIFEST),
        'frozen_bundle_path': str(BUNDLE),
        'observations_dir': str(OUT / 'observations'),
        'centroids_path': str(OUT / 'frozen_centroids.json'),
    }


def prepare_bundle_and_manifest() -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    ensure_dir(OUT)
    if BUNDLE.exists():
        bundle = load_json(BUNDLE)
        source_mode = 'frozen'
    else:
        bundle = build_bundle()
        save_json(BUNDLE, bundle)
        source_mode = 'yaml-fallback'
    if MANIFEST.exists():
        manifest = load_json(MANIFEST)
    else:
        manifest = build_manifest()
        save_json(MANIFEST, manifest)
        source_mode += '+manifest-generated'
    return bundle, manifest, source_mode


# ---------------------------------------------------------------------------
# Job matrix (Section 10, Step 3)
# ---------------------------------------------------------------------------
def build_run_jobs(
    protocol: Dict[str, Any],
    registry: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    mode = ctx.get('mode', {})
    repeats_per_class = int(mode.get('repeats_per_class', 3))
    deformation_steps = int(mode.get('deformation_steps', 6))
    sensitivity_steps = int(mode.get('sensitivity_steps', 15))
    mapping_mode = str(ctx.get('default_mapping_mode', 'rule_based_mapping'))
    generators = [
        str(g['name'])
        for g in ctx.get('generator_registry', [])
        if isinstance(g, dict) and g.get('enabled', True) and g.get('name')
    ]

    dimensions = registry.get('vector_definition', {}).get('dimensions', []) or registry.get('dimensions', [])
    expected_len = len(dimensions) if dimensions else 8

    class_defs = registry.get('classes', []) if isinstance(registry.get('classes', []), list) else []
    class_map = {
        str(c['name']): c
        for c in class_defs
        if isinstance(c, dict) and c.get('name')
    }

    benchmark_sets = ctx.get('benchmark_sets', {}) if isinstance(ctx.get('benchmark_sets', {}), dict) else {}

    randomness = protocol.get('randomness', {})
    seeds_all = randomness.get('seeds', []) if isinstance(randomness, dict) else []
    seeds = [int(s) for s in seeds_all[:repeats_per_class]] if seeds_all else list(range(repeats_per_class))

    noise_cfg = protocol.get('noise', {}) if isinstance(protocol.get('noise', {}), dict) else {}
    parameter_noise = noise_cfg.get('parameter_noise', {}) if isinstance(noise_cfg.get('parameter_noise', {}), dict) else {}
    noise_levels = [float(v) for v in parameter_noise.get('levels', [0.0])] or [0.0]
    seed_noise_cfg = noise_cfg.get('seed_noise', {}) if isinstance(noise_cfg.get('seed_noise', {}), dict) else {}

    experiments = protocol.get('experiments', []) or [
        'reproducibility',
        'sensitivity',
        'separability',
        'family_deformation',
    ]
    experiments = [str(e) for e in experiments]

    jobs: List[Dict[str, Any]] = []
    failed_rows: List[Dict[str, Any]] = []

    for generator in generators:
        gen_seed_noise = float(seed_noise_cfg.get(generator, 0.0))

        for experiment in experiments:
            selected_classes = benchmark_sets.get(experiment, {}).get('include_classes', list(class_map.keys()))
            if not isinstance(selected_classes, list):
                selected_classes = list(class_map.keys())

            for class_name in selected_classes:
                class_name = str(class_name)

                if class_name not in class_map:
                    failed_rows.append({
                        'run_id': f'preflight__{generator}__{experiment}__{class_name}',
                        'generator': generator,
                        'experiment': experiment,
                        'input_class': class_name,
                        'instance_id': -1,
                        'module_name': 'build_run_jobs',
                        'version': COMPONENT_VERSIONS['feature_schema_version'],
                        'input_id': class_name,
                        'failure_stage': 'job_matrix_construction',
                        'error': f'class_not_found_in_registry: {class_name}',
                    })
                    continue

                cdef = class_map[class_name]

                base_vector = cdef.get('base_vector', [0.5] * expected_len)
                if not isinstance(base_vector, (list, tuple)):
                    failed_rows.append({
                        'run_id': f'preflight__{generator}__{experiment}__{class_name}',
                        'generator': generator,
                        'experiment': experiment,
                        'input_class': class_name,
                        'instance_id': -1,
                        'module_name': 'build_run_jobs',
                        'version': COMPONENT_VERSIONS['feature_schema_version'],
                        'input_id': class_name,
                        'failure_stage': 'job_matrix_construction',
                        'error': 'base_vector_is_not_sequence',
                    })
                    continue

                if len(base_vector) != expected_len:
                    failed_rows.append({
                        'run_id': f'preflight__{generator}__{experiment}__{class_name}',
                        'generator': generator,
                        'experiment': experiment,
                        'input_class': class_name,
                        'instance_id': -1,
                        'module_name': 'build_run_jobs',
                        'version': COMPONENT_VERSIONS['feature_schema_version'],
                        'input_id': class_name,
                        'failure_stage': 'job_matrix_construction',
                        'error': f'base_vector_length_mismatch: expected={expected_len}, got={len(base_vector)}',
                    })
                    continue

                n_inst = int(cdef.get('n_instances', 1))
                instance_generation = cdef.get('instance_generation', {})
                offsets = instance_generation.get('offsets', []) if isinstance(instance_generation, dict) else []

                if not isinstance(offsets, list) or len(offsets) < n_inst:
                    failed_rows.append({
                        'run_id': f'preflight__{generator}__{experiment}__{class_name}',
                        'generator': generator,
                        'experiment': experiment,
                        'input_class': class_name,
                        'instance_id': -1,
                        'module_name': 'build_run_jobs',
                        'version': COMPONENT_VERSIONS['feature_schema_version'],
                        'input_id': class_name,
                        'failure_stage': 'job_matrix_construction',
                        'error': 'missing_or_incomplete_offsets',
                    })
                    continue

                local_pert_scales = cdef.get('perturbation_scales', [0.01, 0.03, 0.05])
                if not isinstance(local_pert_scales, list) or not local_pert_scales:
                    local_pert_scales = [0.01, 0.03, 0.05]

                try:
                    local_pert_scales = [float(v) for v in local_pert_scales]
                except Exception:
                    failed_rows.append({
                        'run_id': f'preflight__{generator}__{experiment}__{class_name}',
                        'generator': generator,
                        'experiment': experiment,
                        'input_class': class_name,
                        'instance_id': -1,
                        'module_name': 'build_run_jobs',
                        'version': COMPONENT_VERSIONS['feature_schema_version'],
                        'input_id': class_name,
                        'failure_stage': 'job_matrix_construction',
                        'error': 'perturbation_scales_not_numeric',
                    })
                    continue

                for instance_id in range(n_inst):
                    try:
                        base = np.asarray(base_vector, dtype=float)
                        off = np.asarray(offsets[instance_id], dtype=float)

                        if len(off) != expected_len:
                            raise ValueError(
                                f'offset_length_mismatch: expected={expected_len}, got={len(off)}'
                            )

                        instance_vec = clip01(base + off)
                    except Exception as exc:
                        failed_rows.append({
                            'run_id': f'preflight__{generator}__{experiment}__{class_name}__{instance_id}',
                            'generator': generator,
                            'experiment': experiment,
                            'input_class': class_name,
                            'instance_id': instance_id,
                            'module_name': 'build_run_jobs',
                            'version': COMPONENT_VERSIONS['feature_schema_version'],
                            'input_id': class_name,
                            'failure_stage': 'instance_vector_construction',
                            'error': repr(exc),
                        })
                        continue

                    if experiment == 'family_deformation':
                        step_count = max(1, deformation_steps)
                    elif experiment == 'sensitivity':
                        step_count = max(1, sensitivity_steps)
                    else:
                        step_count = 1

                    if experiment in {'family_deformation', 'sensitivity'}:
                        experiment_noise_levels = local_pert_scales
                    else:
                        experiment_noise_levels = noise_levels

                    for deformation_step in range(step_count):
                        for noise_level in experiment_noise_levels:
                            noise_level = float(noise_level)

                            for seed in seeds:
                                seed = int(seed)

                                run_id = (
                                    f'{generator}__{experiment}__{class_name}__i{instance_id:02d}'
                                    f'__s{seed:02d}__n{noise_level:.3f}__d{deformation_step:02d}__{mapping_mode}'
                                )

                                jobs.append({
                                    'run_id': run_id,
                                    'generator': generator,
                                    'experiment': experiment,
                                    'input_class': class_name,
                                    'instance_id': instance_id,
                                    'seed': seed,
                                    'noise_level': noise_level,
                                    'deformation_step': deformation_step,
                                    'mapping_mode': mapping_mode,
                                    'instance_vec': instance_vec.tolist(),
                                    'gen_seed_noise': gen_seed_noise,
                                })

    return jobs, failed_rows
    
# ---------------------------------------------------------------------------
# Job execution: generator -> observer -> raw features (Steps 4-5)
# ---------------------------------------------------------------------------
def apply_parameter_noise(vec: np.ndarray, noise_level: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if noise_level <= 0:
        return vec.copy()
    return clip01(vec + rng.normal(0.0, noise_level, size=len(vec)))


def execute_single_job(job: Dict[str, Any], mode: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    run_id = str(job['run_id'])
    generator = str(job['generator'])
    experiment = str(job['experiment'])
    input_class = str(job['input_class'])
    instance_id = int(job['instance_id'])

    try:
        lib_dir = resolve_lib_dir()
        core_mod, generators_mod, observe_mod, _metrics_mod = import_backend_modules(lib_dir)
        generator_dispatch = get_generator_dispatch(generators_mod)
    except Exception as exc:
        return {
            'status': STATUS_FAILED,
            'run_id': run_id,
            'generator': generator,
            'experiment': experiment,
            'input_class': input_class,
            'instance_id': instance_id,
            'module_name': 'import_backend_modules',
            'version': COMPONENT_VERSIONS['generator_version'],
            'input_id': run_id,
            'failure_stage': 'backend_resolution',
            'error': repr(exc),
        }

    mapping_mode = str(job['mapping_mode'])
    encoder = core_mod.HarmonyEncoder(seed=12345) if mapping_mode == 'frozen_encoder_mapping' else None

    vec = np.asarray(job['instance_vec'], dtype=float)
    noise_level = float(job['noise_level'])
    deformation_step = int(job['deformation_step'])

    step_count = 1
    if experiment == 'family_deformation':
        step_count = int(mode.get('deformation_steps', 6))
    elif experiment == 'sensitivity':
        step_count = int(mode.get('sensitivity_steps', 15))

    try:
        if experiment == 'family_deformation' and step_count > 1:
            alpha = deformation_step / max(1, step_count - 1)
            direction = np.array([1, -1, 1, -1, 1, -1, 1, -1], dtype=float)

            deformation_amp_cfg = mode.get(
                'deformation_amplitude',
                {
                    'julia_orbit_trap': 0.10,
                    'orbit_ifs_multi_trap': 0.25,
                    'duffing_lyapunov': 0.80,
                    'chaotic_scattering': 0.30,
                    'default': 0.20,
                }
            )
            if not isinstance(deformation_amp_cfg, dict):
                deformation_amp_cfg = {
                    'julia_orbit_trap': 0.10,
                    'orbit_ifs_multi_trap': 0.25,
                    'duffing_lyapunov': 0.80,
                    'chaotic_scattering': 0.30,
                    'default': 0.20,
                }

            base_amp = float(deformation_amp_cfg.get(generator, deformation_amp_cfg.get('default', 0.20)))
            amp = base_amp + noise_level
            vec = clip01(vec + alpha * amp * direction)

        elif experiment == 'sensitivity' and step_count > 1:
            alpha = deformation_step / max(1, step_count - 1)
            delta = alpha - 0.5
            vec = vec.copy()
            vec[4] = np.clip(vec[4] + 0.80 * delta, 0.0, 1.0)  # tension
            vec[5] = np.clip(vec[5] - 0.60 * delta, 0.0, 1.0)  # symmetry/asymmetry
            vec[7] = np.clip(vec[7] + 0.50 * delta, 0.0, 1.0)  # contrast
        else:
            vec = apply_parameter_noise(vec, noise_level, stable_seed(run_id, 'parameter_noise'))

        harmony = vector_to_harmony(core_mod, vec)
        theta = encoder.encode(harmony, dim_out=6) if encoder is not None else rule_based_theta(harmony, dim_out=6)
        sim_state = make_sim_state(
            core_mod,
            generator,
            theta,
            mode,
            stable_seed(run_id, 'sim_seed'),
            float(job['gen_seed_noise'])
        )

        if generator in generator_dispatch:
            result = generator_dispatch[generator](sim_state)
        else:
            result = run_baseline(generator, theta, mode, stable_seed(run_id, 'baseline_seed'))

        adapted = adapt_result_fields(result)
    except Exception as exc:
        return {
            'status': STATUS_FAILED,
            'run_id': run_id,
            'generator': generator,
            'experiment': experiment,
            'input_class': input_class,
            'instance_id': instance_id,
            'module_name': 'generator_layer',
            'version': COMPONENT_VERSIONS['generator_version'],
            'input_id': run_id,
            'failure_stage': 'generation',
            'error': repr(exc),
        }

    try:
        feats = extract_feature_dict(observe_mod, adapted)
    except Exception as exc:
        return {
            'status': STATUS_FAILED,
            'run_id': run_id,
            'generator': generator,
            'experiment': experiment,
            'input_class': input_class,
            'instance_id': instance_id,
            'module_name': 'observer_layer',
            'version': COMPONENT_VERSIONS['observer_version'],
            'input_id': run_id,
            'failure_stage': 'observation',
            'error': repr(exc),
        }

    gen_specific_status = STATUS_SUCCESS
    gen_specific_reason = ''
    try:
        gen_feats = compute_generator_specific_metrics(adapted, generator)
        feats.update(gen_feats)
    except Exception as exc:
        gen_specific_status = STATUS_PARTIAL
        gen_specific_reason = f'generator_specific_metrics_failed: {repr(exc)}'

    missing_morphology = [
        f for f in MORPHOLOGY_FEATURES
        if f not in feats or (isinstance(feats.get(f), float) and np.isnan(feats[f]))
    ]

    status = STATUS_SUCCESS if not missing_morphology else STATUS_PARTIAL
    metric_missing_reason = '' if not missing_morphology else f'missing_morphology_features: {missing_morphology}'

    if gen_specific_status == STATUS_PARTIAL and status == STATUS_SUCCESS:
        status = STATUS_PARTIAL
        metric_missing_reason = gen_specific_reason
    elif gen_specific_status == STATUS_PARTIAL:
        metric_missing_reason = f'{metric_missing_reason}; {gen_specific_reason}'

    row = {
        'run_id': run_id,
        'generator': generator,
        'experiment': experiment,
        'input_class': input_class,
        'instance_id': instance_id,
        'seed': int(job['seed']),
        'noise_level': noise_level,
        'deformation_step': deformation_step,
        'mapping_mode': mapping_mode,
        'observer_version': COMPONENT_VERSIONS['observer_version'],
        'feature_schema_version': COMPONENT_VERSIONS['feature_schema_version'],
        'identity_schema_version': COMPONENT_VERSIONS['identity_schema_version'],
        'distance_metric_version': COMPONENT_VERSIONS['distance_metric_version'],
        'status': status,
        'metric_missing_reason': metric_missing_reason,
        **feats,
    }

    return {
        'status': status,
        'row': row,
        'timing': {
            'run_id': run_id,
            'generator': generator,
            'experiment': experiment,
            'elapsed_sec': time.time() - t0,
        }
    }

# ---------------------------------------------------------------------------
# Morphology normalization (Section 9.1)
# ---------------------------------------------------------------------------
def robust_zscore(rows: List[Dict[str, Any]], feature_names: List[str]) -> List[Dict[str, Any]]:
    vals = {f: [] for f in feature_names}

    for r in rows:
        for f in feature_names:
            v = r.get(f, np.nan)
            if isinstance(v, (int, float, np.integer, np.floating)):
                vals[f].append(float(v))
            else:
                vals[f].append(np.nan)

    stats = {}
    for f in feature_names:
        arr = np.array(vals[f], dtype=float)
        med = np.nanmedian(arr)
        mad = np.nanmedian(np.abs(arr - med))
        std = np.nanstd(arr)
        scale = 1.4826 * mad if mad > 1e-12 else (std if std > 1e-12 else 1.0)
        stats[f] = (med, scale)

    norm_rows = []
    for r in rows:
        nr = dict(r)
        for f in feature_names:
            v = r.get(f, np.nan)
            if isinstance(v, (int, float, np.integer, np.floating)):
                val = float(v)
                med, scale = stats[f]
                nr[f] = float((val - med) / scale) if not np.isnan(val) else np.nan
            else:
                nr[f] = np.nan
        norm_rows.append(nr)

    return norm_rows


# ---------------------------------------------------------------------------
# Identity layer (Section 7, 12): frozen centroid classification
# ---------------------------------------------------------------------------
def euclidean(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.sum((a - b) ** 2)))

# ---------------------------------------------------------------------------
# Identity layer: frozen centroids + generator-specific output_class classifier
# ---------------------------------------------------------------------------

def build_frozen_centroids(
    norm_rows: List[Dict[str, Any]],
    morph_features: List[str],
) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Строит frozen-centroids отдельно по (generator x input_class).
    Это важнее, чем один centroid на input_class, потому что у генераторов
    разные геометрии признаков даже для одного и того же класса.
    """
    ref_rows = [
        r for r in norm_rows
        if r.get('experiment') == 'reproducibility'
        and int(r.get('deformation_step', 0)) == 0
        and float(r.get('noise_level', 0.0)) == 0.0
        and r.get('status') == STATUS_SUCCESS
    ]

    by_gen_class: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for r in ref_rows:
        gen = str(r.get('generator', 'unknown'))
        cls = str(r.get('input_class', 'unknown'))
        by_gen_class[gen][cls].append(r)

    centroids: Dict[str, Dict[str, np.ndarray]] = {}
    for gen, class_map in by_gen_class.items():
        centroids[gen] = {}
        for cls, rows in class_map.items():
            vecs: List[np.ndarray] = []
            for r in rows:
                vals = [r.get(f, np.nan) for f in morph_features]
                if all(not np.isnan(v) for v in vals):
                    vecs.append(np.array(vals, dtype=float))
            if vecs:
                centroids[gen][cls] = np.mean(np.vstack(vecs), axis=0)

    return centroids


def _get_identity_threshold_profile(
    generator: str,
    taxonomy: Dict[str, Any],
) -> Tuple[Dict[str, float], str]:
    """
    Возвращает профиль порогов для конкретного генератора.

    Поддерживает новую YAML-структуру:
      generator_specific_thresholds:
        enabled: true
        fallback_profile: global_default
        profiles:
          global_default: {...}
          julia_orbit_trap: {...}
          orbit_ifs_multi_trap: {...}
          duffing_lyapunov: {...}
          chaotic_scattering: {...}

    И fallback на глобальный блок thresholds.
    """
    generator = str(generator)

    defaults = {
        'centroid_distance_preserved': 1.5,
        'centroid_distance_transformed': 3.5,
        'family_affinity_min': 0.35,
        'breakage_score_min': 0.65,
        'emergent_min_distance_to_any_centroid': 3.5,
        'emergent_min_internal_cohesion': 0.5,
    }

    thresholds = taxonomy.get('thresholds', {})
    global_profile = {
        'centroid_distance_preserved': float(
            thresholds.get('centroid_distance_preserved', defaults['centroid_distance_preserved'])
        ),
        'centroid_distance_transformed': float(
            thresholds.get('centroid_distance_transformed', defaults['centroid_distance_transformed'])
        ),
        'family_affinity_min': float(
            thresholds.get('family_affinity_min', defaults['family_affinity_min'])
        ),
        'breakage_score_min': float(
            thresholds.get('breakage_score_min', defaults['breakage_score_min'])
        ),
        'emergent_min_distance_to_any_centroid': float(
            thresholds.get(
                'emergent_min_distance_to_any_centroid',
                defaults['emergent_min_distance_to_any_centroid']
            )
        ),
        'emergent_min_internal_cohesion': float(
            thresholds.get(
                'emergent_min_internal_cohesion',
                defaults['emergent_min_internal_cohesion']
            )
        ),
    }

    gcfg = taxonomy.get('generator_specific_thresholds', {})
    if not isinstance(gcfg, dict) or not gcfg.get('enabled', False):
        return global_profile, 'global_thresholds'

    profiles = gcfg.get('profiles', {})
    if not isinstance(profiles, dict):
        return global_profile, 'global_thresholds'

    fallback_profile_name = str(gcfg.get('fallback_profile', 'global_default'))
    fallback_raw = profiles.get(fallback_profile_name, {})
    if not isinstance(fallback_raw, dict):
        fallback_raw = {}

    fallback_profile = {
        'centroid_distance_preserved': float(
            fallback_raw.get(
                'centroid_distance_preserved',
                global_profile['centroid_distance_preserved']
            )
        ),
        'centroid_distance_transformed': float(
            fallback_raw.get(
                'centroid_distance_transformed',
                global_profile['centroid_distance_transformed']
            )
        ),
        'family_affinity_min': float(
            fallback_raw.get(
                'family_affinity_min',
                global_profile['family_affinity_min']
            )
        ),
        'breakage_score_min': float(
            fallback_raw.get(
                'breakage_score_min',
                global_profile['breakage_score_min']
            )
        ),
        'emergent_min_distance_to_any_centroid': float(
            fallback_raw.get(
                'emergent_min_distance_to_any_centroid',
                global_profile['emergent_min_distance_to_any_centroid']
            )
        ),
        'emergent_min_internal_cohesion': float(
            fallback_raw.get(
                'emergent_min_internal_cohesion',
                global_profile['emergent_min_internal_cohesion']
            )
        ),
    }

    raw = profiles.get(generator, {})
    if not isinstance(raw, dict):
        return fallback_profile, fallback_profile_name

    resolved = {
        'centroid_distance_preserved': float(
            raw.get(
                'centroid_distance_preserved',
                fallback_profile['centroid_distance_preserved']
            )
        ),
        'centroid_distance_transformed': float(
            raw.get(
                'centroid_distance_transformed',
                fallback_profile['centroid_distance_transformed']
            )
        ),
        'family_affinity_min': float(
            raw.get(
                'family_affinity_min',
                fallback_profile['family_affinity_min']
            )
        ),
        'breakage_score_min': float(
            raw.get(
                'breakage_score_min',
                fallback_profile['breakage_score_min']
            )
        ),
        'emergent_min_distance_to_any_centroid': float(
            raw.get(
                'emergent_min_distance_to_any_centroid',
                fallback_profile['emergent_min_distance_to_any_centroid']
            )
        ),
        'emergent_min_internal_cohesion': float(
            raw.get(
                'emergent_min_internal_cohesion',
                fallback_profile['emergent_min_internal_cohesion']
            )
        ),
    }

    return resolved, generator


def _safe_inverse_distance_weights(dists: Dict[str, float]) -> Dict[str, float]:
    eps = 1e-8
    return {cls: 1.0 / max(eps, float(dist)) for cls, dist in dists.items()}


def classify_identity(
    vec: np.ndarray,
    input_class: str,
    generator: str,
    centroids: Dict[str, Dict[str, np.ndarray]],
    taxonomy: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Классифицирует выход в:
      preserved / transformed / broken / emergent
    отдельно для каждого генератора.

    Возвращает:
      output_class
      transition_type
      family_relation
      identity_confidence
      identity_breakage_score
      centroid_distance
      nearest_centroid_class
      approx_morphology_score
      threshold_profile_used
      family_continuity_score
      breakage_confidence
      transition_confidence
      class_stability_index
      observer_stability_score
    """
    input_class = str(input_class)
    generator = str(generator)
    vec = np.asarray(vec, dtype=float)

    thr, profile_name = _get_identity_threshold_profile(generator, taxonomy)
    preserved_thr = float(thr['centroid_distance_preserved'])
    transformed_thr = float(thr['centroid_distance_transformed'])
    affinity_min = float(thr['family_affinity_min'])
    breakage_min = float(thr['breakage_score_min'])
    emergent_dist_min = float(thr['emergent_min_distance_to_any_centroid'])
    emergent_cohesion_min = float(thr.get('emergent_min_internal_cohesion', 0.5))

    gen_centroids = centroids.get(generator, {})
    if not gen_centroids or input_class not in gen_centroids:
        return {
            'output_class': f'unresolved_{input_class}',
            'transition_type': 'unresolved',
            'family_relation': input_class,
            'identity_confidence': 0.0,
            'identity_breakage_score': 1.0,
            'centroid_distance': float('nan'),
            'nearest_centroid_class': 'unknown',
            'approx_morphology_score': float('nan'),
            'threshold_profile_used': profile_name,
            'family_continuity_score': 0.0,
            'breakage_confidence': 0.0,
            'transition_confidence': 0.0,
            'class_stability_index': 0.0,
            'observer_stability_score': 0.0,
        }

    dists = {
        cls: euclidean(vec, np.asarray(c, dtype=float))
        for cls, c in gen_centroids.items()
    }
    own_dist = float(dists[input_class])

    nearest_cls, nearest_dist = min(dists.items(), key=lambda kv: kv[1])
    nearest_cls = str(nearest_cls)
    nearest_dist = float(nearest_dist)
    min_dist_all = float(min(dists.values()))

    weights = _safe_inverse_distance_weights(dists)
    weight_sum = float(sum(weights.values())) if weights else 1.0
    family_affinity = float(weights.get(input_class, 0.0) / max(weight_sum, 1e-8))
    nearest_affinity = float(weights.get(nearest_cls, 0.0) / max(weight_sum, 1e-8))

    approx_morphology_score = float(own_dist)

    excess = max(0.0, own_dist - transformed_thr)
    breakage_score = float(
        min(
            1.0,
            0.5 * (1.0 - family_affinity)
            + 0.5 * (excess / max(transformed_thr, 1e-8)),
        )
    )

    local_cohesion = float(1.0 / (1.0 + min_dist_all))

    if own_dist <= preserved_thr:
        identity_confidence = float(
            max(0.0, 1.0 - 0.35 * (own_dist / max(preserved_thr, 1e-8)))
        )
    elif own_dist <= transformed_thr:
        frac = (own_dist - preserved_thr) / max(transformed_thr - preserved_thr, 1e-8)
        identity_confidence = float(max(0.0, 0.75 - 0.50 * frac))
    else:
        frac = (own_dist - transformed_thr) / max(transformed_thr, 1e-8)
        identity_confidence = float(max(0.0, 0.25 - 0.25 * min(1.0, frac)))

    # -----------------------------------------------------------------------
    # v4.2 diagnostic scores
    # -----------------------------------------------------------------------
    family_continuity_score = float(
        max(0.0, min(1.0, family_affinity * (1.0 / (1.0 + own_dist))))
    )
    breakage_confidence = float(
        max(0.0, min(1.0, breakage_score * (1.0 + max(0.0, own_dist - transformed_thr) / max(transformed_thr, 1e-8))))
    )
    transition_confidence = float(
        max(
            0.0,
            min(
                1.0,
                (nearest_affinity * (own_dist / max(transformed_thr, 1e-8)))
            ),
        )
    )
    class_stability_index = float(
        max(0.0, min(1.0, 1.0 / (1.0 + min_dist_all)))
    )

    # observer_stability_score остаётся proxy-фичей, здесь просто дубль для удобства
    observer_stability_score = float(0.0)
    # Значение будет проставлено в apply_identity_layer из rr['observer_stability_proxy'].

    # -----------------------------------------------------------------------
    # Emergent branch
    # -----------------------------------------------------------------------
    is_emergent = (
        min_dist_all >= emergent_dist_min
        and local_cohesion >= emergent_cohesion_min
    )
    if is_emergent:
        emergent_label = 'emergent_unknown'
        if nearest_affinity >= affinity_min:
            emergent_label = f'emergent_{nearest_cls}'

        return {
            'output_class': emergent_label,
            'transition_type': 'emergent',
            'family_relation': nearest_cls if emergent_label != 'emergent_unknown' else 'unknown',
            'identity_confidence': identity_confidence,
            'identity_breakage_score': breakage_score,
            'centroid_distance': own_dist,
            'nearest_centroid_class': nearest_cls,
            'approx_morphology_score': approx_morphology_score,
            'threshold_profile_used': profile_name,
            'family_continuity_score': family_continuity_score,
            'breakage_confidence': breakage_confidence,
            'transition_confidence': transition_confidence,
            'class_stability_index': class_stability_index,
            'observer_stability_score': observer_stability_score,
        }

    # -----------------------------------------------------------------------
    # Broken branch
    # -----------------------------------------------------------------------
    is_broken = (
        breakage_score >= breakage_min
        or (own_dist > transformed_thr and family_affinity < affinity_min)
    )
    if is_broken:
        return {
            'output_class': f'broken_{input_class}',
            'transition_type': 'broken',
            'family_relation': nearest_cls,
            'identity_confidence': identity_confidence,
            'identity_breakage_score': breakage_score,
            'centroid_distance': own_dist,
            'nearest_centroid_class': nearest_cls,
            'approx_morphology_score': approx_morphology_score,
            'threshold_profile_used': profile_name,
            'family_continuity_score': family_continuity_score,
            'breakage_confidence': breakage_confidence,
            'transition_confidence': transition_confidence,
            'class_stability_index': class_stability_index,
            'observer_stability_score': observer_stability_score,
        }

    # -----------------------------------------------------------------------
    # Preserved branch
    # -----------------------------------------------------------------------
    is_preserved = (
        own_dist <= preserved_thr
        and family_affinity >= affinity_min
    )
    if is_preserved:
        return {
            'output_class': f'preserved_{input_class}',
            'transition_type': 'preserved',
            'family_relation': input_class,
            'identity_confidence': identity_confidence,
            'identity_breakage_score': breakage_score,
            'centroid_distance': own_dist,
            'nearest_centroid_class': nearest_cls,
            'approx_morphology_score': approx_morphology_score,
            'threshold_profile_used': profile_name,
            'family_continuity_score': family_continuity_score,
            'breakage_confidence': breakage_confidence,
            'transition_confidence': transition_confidence,
            'class_stability_index': class_stability_index,
            'observer_stability_score': observer_stability_score,
        }

    # -----------------------------------------------------------------------
    # Transformed branch
    # -----------------------------------------------------------------------
    is_transformed = (
        own_dist <= transformed_thr
        and family_affinity >= affinity_min
    )
    if is_transformed:
        return {
            'output_class': f'transformed_{input_class}',
            'transition_type': 'transformed',
            'family_relation': input_class,
            'identity_confidence': identity_confidence,
            'identity_breakage_score': breakage_score,
            'centroid_distance': own_dist,
            'nearest_centroid_class': nearest_cls,
            'approx_morphology_score': approx_morphology_score,
            'threshold_profile_used': profile_name,
            'family_continuity_score': family_continuity_score,
            'breakage_confidence': breakage_confidence,
            'transition_confidence': transition_confidence,
            'class_stability_index': class_stability_index,
            'observer_stability_score': observer_stability_score,
        }

    # -----------------------------------------------------------------------
    # Fallback: broken
    # -----------------------------------------------------------------------
    return {
        'output_class': f'broken_{input_class}',
        'transition_type': 'broken',
        'family_relation': nearest_cls,
        'identity_confidence': identity_confidence,
        'identity_breakage_score': breakage_score,
        'centroid_distance': own_dist,
        'nearest_centroid_class': nearest_cls,
        'approx_morphology_score': approx_morphology_score,
        'threshold_profile_used': profile_name,
        'family_continuity_score': family_continuity_score,
        'breakage_confidence': breakage_confidence,
        'transition_confidence': transition_confidence,
        'class_stability_index': class_stability_index,
        'observer_stability_score': observer_stability_score,
    }


def apply_identity_layer(
    norm_rows: List[Dict[str, Any]],
    morph_features: List[str],
    taxonomy: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, List[float]]]]:
    """
    Применяет generator-specific identity classifier ко всем строкам.
    """
    centroids = build_frozen_centroids(norm_rows, morph_features)

    out_rows: List[Dict[str, Any]] = []
    for r in norm_rows:
        rr = dict(r)

        generator = str(rr.get('generator', 'unknown'))
        input_class = str(rr.get('input_class', 'unknown'))
        _, profile_name = _get_identity_threshold_profile(generator, taxonomy)

        feature_values = []
        features_ok = True
        for f in morph_features:
            if f not in rr:
                features_ok = False
                break
            try:
                val = float(rr[f])
            except Exception:
                features_ok = False
                break
            if np.isnan(val):
                features_ok = False
                break
            feature_values.append(val)

        observer_stability_score = float(rr.get('observer_stability_proxy', 0.0))

        if rr.get('status') != STATUS_SUCCESS or not features_ok:
            rr['output_class'] = f'unresolved_{input_class}'
            rr['transition_type'] = 'unresolved'
            rr['family_relation'] = input_class
            rr['identity_confidence'] = 0.0
            rr['identity_breakage_score'] = float('nan')
            rr['centroid_distance'] = float('nan')
            rr['nearest_centroid_class'] = 'unknown'
            rr['approx_morphology_score'] = float('nan')
            rr['threshold_profile_used'] = profile_name
            rr['family_continuity_score'] = 0.0
            rr['breakage_confidence'] = 0.0
            rr['transition_confidence'] = 0.0
            rr['class_stability_index'] = 0.0
            rr['observer_stability_score'] = observer_stability_score
            out_rows.append(rr)
            continue

        vec = np.asarray(feature_values, dtype=float)
        identity = classify_identity(
            vec=vec,
            input_class=input_class,
            generator=generator,
            centroids=centroids,
            taxonomy=taxonomy,
        )

        identity['observer_stability_score'] = observer_stability_score
        rr.update(identity)
        out_rows.append(rr)

    centroids_serializable: Dict[str, Dict[str, List[float]]] = {
        gen: {cls: c.tolist() for cls, c in class_map.items()}
        for gen, class_map in centroids.items()
    }
    return out_rows, centroids_serializable

# ---------------------------------------------------------------------------
# Metrics layer (Section 9.3-9.4)
# ---------------------------------------------------------------------------
def pairwise_distances_numpy(X: np.ndarray) -> np.ndarray:
    diff = X[:, None, :] - X[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def compute_within_between(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    label_key: str,
) -> Dict[str, Any]:
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        label = r.get(label_key, 'unknown')
        by_class[str(label)].append(r)

    within_vars: Dict[str, float] = {}
    class_means: Dict[str, Dict[str, float]] = {}

    for cls, cls_rows in by_class.items():
        cls_vars: List[float] = []
        class_means[cls] = {}
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r and not np.isnan(r[f])]
            if len(vals) > 1:
                cls_vars.append(float(np.var(vals, ddof=1)))
            if vals:
                class_means[cls][f] = float(np.mean(vals))
        within_vars[cls] = float(np.mean(cls_vars)) if cls_vars else 0.0

    within_mean = float(np.mean(list(within_vars.values()))) if within_vars else 0.0

    between_vars: List[float] = []
    for f in feature_names:
        means_for_f = [class_means[cls][f] for cls in class_means if f in class_means[cls]]
        if len(means_for_f) > 1:
            between_vars.append(float(np.var(means_for_f, ddof=1)))

    between_mean = float(np.mean(between_vars)) if between_vars else 0.0
    separability = between_mean / (within_mean + 1e-8)

    return {
        'within_mean': within_mean,
        'between_mean': between_mean,
        'separability': float(separability),
        'within_by_class': within_vars,
        'class_means': class_means,
    }


def compute_retrieval_metrics(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    label_key: str,
    sample_size: int = 500,
) -> Tuple[Dict[str, Any], Optional[np.ndarray], List[str]]:
    data: List[Dict[str, Any]] = []
    for r in rows:
        vec = [r[f] for f in feature_names if f in r and not np.isnan(r[f])]
        if len(vec) == len(feature_names):
            data.append({
                'label': r.get(label_key, 'unknown'),
                'features': np.array(vec, dtype=float),
            })

    if len(data) < 2:
        return {'top1_accuracy': 0.0, 'top3_accuracy': 0.0, 'n_queries': 0}, None, []

    if len(data) > sample_size:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(data), sample_size, replace=False)
        data = [data[i] for i in sorted(idx)]

    X = np.vstack([d['features'] for d in data])
    labels = [str(d['label']) for d in data]
    dist_matrix = pairwise_distances_numpy(X)

    top1 = 0
    top3 = 0
    n = len(data)

    for i in range(n):
        d = dist_matrix[i].copy()
        d[i] = np.inf
        order = np.argsort(d)
        if labels[order[0]] == labels[i]:
            top1 += 1
        if labels[i] in [labels[j] for j in order[:3]]:
            top3 += 1

    return {
        'top1_accuracy': float(top1 / n),
        'top3_accuracy': float(top3 / n),
        'n_queries': n,
    }, dist_matrix, labels


def compute_transition_rates(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(str(r.get('transition_type', 'unresolved')) for r in rows)
    total = len(rows) or 1
    rates = {k: float(v / total) for k, v in counts.items()}
    return {
        'counts': dict(counts),
        'rates': rates,
        'class_preservation_rate': rates.get('preserved', 0.0),
        'class_transition_rate': rates.get('transformed', 0.0),
        'class_breakage_rate': rates.get('broken', 0.0),
        'emergent_rate': rates.get('emergent', 0.0),
    }


def compute_sensitivity_metrics(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
) -> Dict[str, Any]:
    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get('experiment') != 'sensitivity':
            continue
        key = (
            r.get('generator'),
            r.get('input_class'),
            r.get('instance_id'),
            r.get('seed'),
            r.get('noise_level'),
        )
        grouped[key].append(r)

    grads: List[float] = []
    for seq in grouped.values():
        seq = sorted(seq, key=lambda z: int(z.get('deformation_step', 0)))
        if len(seq) < 3:
            continue
        X = np.array([[s[f] for f in feature_names] for s in seq], dtype=float)
        diffs = np.diff(X, axis=0)
        norms = np.sqrt(np.sum(diffs ** 2, axis=1))
        if len(norms):
            grads.append(float(np.max(norms)))

    return {'input_perturbation_sensitivity': float(np.mean(grads)) if grads else 0.0}


def compute_seed_sensitivity(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
) -> Dict[str, Any]:
    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get('experiment') != 'reproducibility':
            continue
        key = (
            r.get('generator'),
            r.get('input_class'),
            r.get('instance_id'),
            r.get('noise_level'),
            r.get('deformation_step'),
        )
        grouped[key].append(r)

    cvs: List[float] = []
    for seq in grouped.values():
        if len(seq) < 2:
            continue
        for f in feature_names:
            vals = np.array([s[f] for s in seq if f in s and not np.isnan(s[f])], dtype=float)
            if len(vals) >= 2 and abs(np.mean(vals)) > 1e-8:
                cvs.append(float(np.std(vals, ddof=1) / abs(np.mean(vals))))

    return {'seed_sensitivity': float(np.mean(cvs)) if cvs else 0.0}


def compute_observer_variance(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
) -> Dict[str, Any]:
    variances: List[float] = []
    for f in feature_names:
        vals = np.array([r[f] for r in rows if f in r and not np.isnan(r[f])], dtype=float)
        if len(vals) > 1:
            variances.append(float(np.var(vals, ddof=1)))
    return {'observer_variance': float(np.mean(variances)) if variances else 0.0}


def compute_bootstrap_ci(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    group_key: str,
    n_bootstrap: int = 300,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    by_group: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        label = r.get(group_key, 'unknown')
        by_group[str(label)].append(r)

    out: Dict[str, Dict[str, Any]] = {}

    for g, g_rows in by_group.items():
        stats_by_feature: Dict[str, Any] = {}

        for f in feature_names:
            vals = np.array(
                [r[f] for r in g_rows if f in r and not np.isnan(r[f])],
                dtype=float,
            )

            if len(vals) < 2:
                continue

            mean_val = float(np.mean(vals))
            std_val = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            median_val = float(np.median(vals))
            iqr_val = float(np.percentile(vals, 75) - np.percentile(vals, 25))
            min_val = float(np.min(vals))
            max_val = float(np.max(vals))
            n_val = int(len(vals))

            # Вырожденный случай: все значения одинаковы или дисперсия практически нулевая
            if std_val < 1e-12 or np.allclose(vals, vals[0], atol=1e-12, rtol=0.0):
                stats_by_feature[f] = {
                    'mean': mean_val,
                    'std': std_val,
                    'median': median_val,
                    'iqr': iqr_val,
                    'min': min_val,
                    'max': max_val,
                    'n': n_val,
                    'ci_lower': mean_val,
                    'ci_upper': mean_val,
                }
                continue

            try:
                res = bootstrap(
                    (vals,),
                    np.mean,
                    confidence_level=confidence_level,
                    n_resamples=n_bootstrap,
                    random_state=42,
                )

                ci_low = float(res.confidence_interval.low)
                ci_high = float(res.confidence_interval.high)

                if np.isnan(ci_low) or np.isnan(ci_high):
                    raise ValueError('bootstrap returned NaN confidence interval')

                stats_by_feature[f] = {
                    'mean': mean_val,
                    'std': std_val,
                    'median': median_val,
                    'iqr': iqr_val,
                    'min': min_val,
                    'max': max_val,
                    'n': n_val,
                    'ci_lower': ci_low,
                    'ci_upper': ci_high,
                }

            except Exception:
                se = std_val / np.sqrt(len(vals))
                ci_low = float(mean_val - 1.96 * se)
                ci_high = float(mean_val + 1.96 * se)

                stats_by_feature[f] = {
                    'mean': mean_val,
                    'std': std_val,
                    'median': median_val,
                    'iqr': iqr_val,
                    'min': min_val,
                    'max': max_val,
                    'n': n_val,
                    'ci_lower': ci_low,
                    'ci_upper': ci_high,
                }

        out[g] = stats_by_feature

    return out


# ---------------------------------------------------------------------------
# Bifurcation detector v4 (Section 13)
# ---------------------------------------------------------------------------
def moving_average(arr: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(arr) < window:
        return arr.copy()
    kernel = np.ones(window, dtype=float) / window
    pad_left = window // 2
    pad_right = window - 1 - pad_left
    padded = np.pad(arr, (pad_left, pad_right), mode='edge')
    return np.convolve(padded, kernel, mode='valid')


def detect_bifurcation_events(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    trajectories: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (
            r.get('generator'),
            r.get('experiment'),
            r.get('input_class'),
            r.get('instance_id'),
            r.get('seed'),
            r.get('noise_level'),
        )
        trajectories[key].append(r)

    smoothing_window = int(config.get('smoothing_window', 3)) if isinstance(config, dict) else 3
    z_threshold = float(config.get('z_threshold', 2.5)) if isinstance(config, dict) else 2.5
    persistence_points = int(config.get('persistence_points', 2)) if isinstance(config, dict) else 2
    min_jump_norm = float(config.get('min_jump_norm', 0.15)) if isinstance(config, dict) else 0.15

    out: List[Dict[str, Any]] = []

    for key, traj in trajectories.items():
        traj = sorted(traj, key=lambda x: int(x.get('deformation_step', 0)))
        if len(traj) < max(3, persistence_points + 1):
            continue

        output_classes = [t.get('output_class', '') for t in traj]

        for f in feature_names:
            vals = np.array([r[f] for r in traj if f in r and not np.isnan(r[f])], dtype=float)
            if len(vals) < max(3, persistence_points + 1):
                continue

            smooth = moving_average(vals, smoothing_window)
            diffs = np.diff(smooth)
            if len(diffs) < persistence_points:
                continue

            mean_diff = np.mean(diffs)
            std_diff = np.std(diffs, ddof=1) if len(diffs) > 1 else 1.0
            std_diff = std_diff if std_diff > 1e-10 else 1.0

            z = np.abs((diffs - mean_diff) / std_diff)

            for i in range(len(diffs) - persistence_points + 1):
                local_z = z[i:i + persistence_points]
                local_jump = diffs[i:i + persistence_points]
                if np.all(local_z > z_threshold) and np.all(np.abs(local_jump) > min_jump_norm):
                    out.append({
                        'generator': key[0],
                        'input_class': key[2],
                        'output_class': output_classes[min(i + 1, len(output_classes) - 1)],
                        'parameter_name': 'deformation_step',
                        'parameter_value': int(i + 1),
                        'feature_name': f,
                        'gradient_norm': float(np.mean(np.abs(local_jump))),
                        'zscore': float(np.max(local_z)),
                        'confirmed_event': True,
                    })
                    break

    return out

# ---------------------------------------------------------------------------
# Reporting layer (Section 15)
# ---------------------------------------------------------------------------
def build_summary(
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    separability: Dict[str, Any],
    retrieval: Dict[str, Any],
    transitions: Dict[str, Any],
    failed_rows: List[Dict[str, Any]],
    n_bifurcations: int,
) -> Dict[str, Any]:
    by_gen = Counter(str(r.get('generator', 'unknown')) for r in rows)
    by_class = Counter(str(r.get('input_class', 'unknown')) for r in rows)

    by_gen_preservation: Dict[str, List[float]] = defaultdict(list)
    by_gen_family_continuity: Dict[str, List[float]] = defaultdict(list)
    by_gen_class_stability: Dict[str, List[float]] = defaultdict(list)
    by_gen_observer_stability: Dict[str, List[float]] = defaultdict(list)

    for r in rows:
        gen = str(r.get('generator', 'unknown'))
        by_gen_preservation[gen].append(
            1.0 if r.get('transition_type') == 'preserved' else 0.0
        )
        if 'family_continuity_score' in r and isinstance(r['family_continuity_score'], (int, float)):
            by_gen_family_continuity[gen].append(float(r['family_continuity_score']))
        if 'class_stability_index' in r and isinstance(r['class_stability_index'], (int, float)):
            by_gen_class_stability[gen].append(float(r['class_stability_index']))
        if 'observer_stability_score' in r and isinstance(r['observer_stability_score'], (int, float)):
            by_gen_observer_stability[gen].append(float(r['observer_stability_score']))

    best_generators = sorted(
        by_gen_preservation.items(),
        key=lambda kv: -np.mean(kv[1]) if kv[1] else 0.0,
    )

    class_preservation: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        cls = str(r.get('input_class', 'unknown'))
        class_preservation[cls].append(
            1.0 if r.get('transition_type') == 'preserved' else 0.0
        )
    best_classes_preservation = sorted(
        class_preservation.items(),
        key=lambda kv: -np.mean(kv[1]) if kv[1] else 0.0,
    )

    # Глобальные средние по новым скалам v4.2
    family_continuity_vals = [
        float(r.get('family_continuity_score', np.nan))
        for r in rows
        if isinstance(r.get('family_continuity_score', np.nan), (int, float))
        and not np.isnan(r.get('family_continuity_score', np.nan))
    ]
    class_stability_vals = [
        float(r.get('class_stability_index', np.nan))
        for r in rows
        if isinstance(r.get('class_stability_index', np.nan), (int, float))
        and not np.isnan(r.get('class_stability_index', np.nan))
    ]
    morphology_persistence_vals = [
        float(r.get('morphology_persistence_score', np.nan))
        for r in rows
        if isinstance(r.get('morphology_persistence_score', np.nan), (int, float))
        and not np.isnan(r.get('morphology_persistence_score', np.nan))
    ]
    observer_stability_vals = [
        float(r.get('observer_stability_score', np.nan))
        for r in rows
        if isinstance(r.get('observer_stability_score', np.nan), (int, float))
        and not np.isnan(r.get('observer_stability_score', np.nan))
    ]

    mean_family_continuity = float(np.mean(family_continuity_vals)) if family_continuity_vals else 0.0
    mean_class_stability = float(np.mean(class_stability_vals)) if class_stability_vals else 0.0
    mean_morphology_persistence = float(np.mean(morphology_persistence_vals)) if morphology_persistence_vals else 0.0
    mean_observer_stability = float(np.mean(observer_stability_vals)) if observer_stability_vals else 0.0

    return {
        'n_total_runs': len(rows),
        'n_runs_by_generator': dict(by_gen),
        'n_runs_by_class': dict(by_class),
        'n_transitions': dict(Counter(str(r.get('transition_type', 'unresolved')) for r in rows)),
        'separability': separability.get('separability', 0.0),
        'retrieval_top1': retrieval.get('top1_accuracy', 0.0),
        'retrieval_top3': retrieval.get('top3_accuracy', 0.0),
        'best_generators_by_preservation': [g for g, _ in best_generators[:5]],
        'problematic_modules': sorted({str(f.get('module_name', 'unknown')) for f in failed_rows}),
        'best_classes_by_preservation': [c for c, _ in best_classes_preservation[:5]],
        'n_bifurcations': n_bifurcations,
        'n_failed_runs': len(failed_rows),

        # Новые агрегаты v4.2
        'mean_family_continuity_score': mean_family_continuity,
        'mean_class_stability_index': mean_class_stability,
        'mean_morphology_persistence_score': mean_morphology_persistence,
        'mean_observer_stability_score': mean_observer_stability,
        'by_generator_family_continuity': {
            gen: float(np.mean(vals)) if vals else 0.0
            for gen, vals in by_gen_family_continuity.items()
        },
        'by_generator_class_stability_index': {
            gen: float(np.mean(vals)) if vals else 0.0
            for gen, vals in by_gen_class_stability.items()
        },
        'by_generator_observer_stability_score': {
            gen: float(np.mean(vals)) if vals else 0.0
            for gen, vals in by_gen_observer_stability.items()
        },
    }

def generate_research_report(
    component_versions: Dict[str, str],
    source_mode: str,
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    summary: Dict[str, Any],
    separability: Dict[str, Any],
    retrieval: Dict[str, Any],
    transitions: Dict[str, Any],
    bootstrap_by_gen: Dict[str, Any],
    bifurcations: List[Dict[str, Any]],
    sensitivity: Dict[str, Any],
    seed_sensitivity: Dict[str, Any],
    observer_variance: Dict[str, Any],
) -> str:
    L: List[str] = []
    L.append('# Benchmark v4 Research Report\n\n')
    L.append(f'- Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
    L.append(f'- Config source: {source_mode}\n')
    for k, v in component_versions.items():
        L.append(f'- {k}: {v}\n')
    L.append(f'- Distance metric: {DISTANCE_METRIC_NAME}\n')
    L.append(f'- Normalization scheme: {NORMALIZATION_SCHEME}\n\n')

    L.append('## 1. Purpose of Benchmark v4\n\n')
    L.append(
        'Benchmark v4 separates morphology (form/structure descriptors) from identity '
        '(output class assignment, transition type, confidence, breakage), enforces component '
        'versioning, and forbids silent NaNs across the pipeline.\n\n'
    )

    L.append('## 2. Pipeline Architecture\n\n')
    L.append(
        'Generator layer -> Observer layer -> Morphology layer -> Identity layer -> '
        'Metrics layer -> Reporting layer, executed per job in the factorial run matrix.\n\n'
    )

    L.append('## 3. Class Structure\n\n')
    L.append(f'- Total runs: {len(rows)}\n')
    L.append(
        f'- Runs by input class: {json.dumps(summary.get("n_runs_by_class", {}), ensure_ascii=False)}\n\n'
    )

    L.append('## 4. Morphology Layer\n\n')
    L.append(f'- Morphology feature set: {", ".join(MORPHOLOGY_FEATURES)}\n')
    L.append(f'- Separability (between/within): {separability.get("separability", 0.0):.6f}\n')
    L.append(f'- Within-class mean variance: {separability.get("within_mean", 0.0):.6f}\n')
    L.append(f'- Between-class mean variance: {separability.get("between_mean", 0.0):.6f}\n')
    L.append(
        f'- Mean morphology persistence score: {summary.get("mean_morphology_persistence_score", 0.0):.4f}\n'
    )
    L.append(
        f'- Mean observer stability score: {summary.get("mean_observer_stability_score", 0.0):.4f}\n\n'
    )

    L.append('## 5. Identity Layer\n\n')
    L.append(
        f'- Transition counts: {json.dumps(summary.get("n_transitions", {}), ensure_ascii=False)}\n'
    )
    L.append(f'- Class preservation rate: {transitions.get("class_preservation_rate", 0.0):.4f}\n')
    L.append(f'- Class transition rate: {transitions.get("class_transition_rate", 0.0):.4f}\n')
    L.append(f'- Class breakage rate: {transitions.get("class_breakage_rate", 0.0):.4f}\n')
    L.append(f'- Emergent rate: {transitions.get("emergent_rate", 0.0):.4f}\n')
    L.append(
        f'- Mean family continuity score: {summary.get("mean_family_continuity_score", 0.0):.4f}\n'
    )
    L.append(
        f'- Mean class stability index: {summary.get("mean_class_stability_index", 0.0):.4f}\n\n'
    )

    L.append('## 6. Metrics Summary\n\n')
    L.append(f'- Top-1 retrieval accuracy: {retrieval.get("top1_accuracy", 0.0):.4f}\n')
    L.append(f'- Top-3 retrieval accuracy: {retrieval.get("top3_accuracy", 0.0):.4f}\n')
    L.append(f'- N retrieval queries: {retrieval.get("n_queries", 0)}\n')
    L.append(
        f'- Input perturbation sensitivity: {sensitivity.get("input_perturbation_sensitivity", 0.0):.4f}\n'
    )
    L.append(
        f'- Seed sensitivity (mean CV): {seed_sensitivity.get("seed_sensitivity", 0.0):.4f}\n'
    )
    L.append(f'- Observer variance: {observer_variance.get("observer_variance", 0.0):.4f}\n\n')

    L.append('## 7. Transition Analysis\n\n')
    L.append('| Generator | N runs | Mean family continuity | Mean class stability |\n')
    L.append('|---|---:|---:|---:|\n')
    by_gen_runs = summary.get('n_runs_by_generator', {})
    by_gen_family = summary.get('by_generator_family_continuity', {})
    by_gen_stability = summary.get('by_generator_class_stability_index', {})
    for gen in sorted(by_gen_runs.keys()):
        n = by_gen_runs.get(gen, 0)
        fam = by_gen_family.get(gen, 0.0)
        stab = by_gen_stability.get(gen, 0.0)
        L.append(f'| {gen} | {n} | {fam:.3f} | {stab:.3f} |\n')
    L.append('\n')

    L.append('## 8. Bifurcation Analysis\n\n')
    L.append(f'- Confirmed bifurcation events: {len(bifurcations)}\n')
    if bifurcations:
        L.append('| Generator | Input class | Output class | Feature | Step | Gradient | Z-score |\n')
        L.append('|---|---|---|---|---:|---:|---:|\n')
        for b in bifurcations[:20]:
            L.append(
                f"| {b['generator']} | {b['input_class']} | {b['output_class']} | {b['feature_name']} | "
                f"{b['parameter_value']} | {b['gradient_norm']:.4f} | {b['zscore']:.4f} |\n"
            )
    L.append('\n')

    L.append('## 9. Generator Recommendations\n\n')
    L.append(
        f"- Best generators by preservation: {', '.join(summary.get('best_generators_by_preservation', []))}\n"
    )
    L.append(
        f"- Best classes by preservation: {', '.join(summary.get('best_classes_by_preservation', []))}\n\n"
    )

    L.append('## 10. Recommendations for Next Stage\n\n')
    L.append(
        '- Replace stub generator-specific analysis with deeper morphology descriptors '
        '(multi-scale, topological connectivity) once v4 stabilizes.\n'
    )
    L.append('- Recompute frozen centroids only when identity_schema_version changes.\n')
    L.append('- Expand validation-hires mode once separability and retrieval metrics stabilize.\n\n')

    return ''.join(L)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def format_hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f'{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}'


def main() -> None:
    STAGE_TOTAL = 10

    print(f'[Stage 1/{STAGE_TOTAL}] Load frozen config and check component versions...', flush=True)
    t0 = time.time()
    bundle, manifest, source_mode = prepare_bundle_and_manifest()
    protocol = bundle['protocol_spec']['content']
    registry = bundle['input_registry_spec']['content']
    taxonomy = bundle['output_taxonomy_spec']['content']
    ctx = bundle['benchmark_context']
    mode = ctx.get('mode', {})
    versions = ctx.get('component_versions', COMPONENT_VERSIONS)
    runtime_cfg = protocol.get('runtime', {}) if isinstance(protocol.get('runtime', {}), dict) else {}
    workers = int(runtime_cfg.get('n_workers', 8) or 8)
    print(f'[INFO] source={source_mode} mode={ctx.get("mode_name")} versions={versions}', flush=True)
    print(f'[Stage 1 done in {format_hms(time.time() - t0)}]', flush=True)

    print(f'[Stage 2/{STAGE_TOTAL}] Load registries (input, output taxonomy, distance config)...', flush=True)
    t1 = time.time()

    feature_schema = load_feature_schema(CONFIGS, MORPHOLOGY_FEATURES)
    morph_features = feature_schema.get('morphology_features', MORPHOLOGY_FEATURES)

    generator_specific_from_schema = feature_schema.get('generator_specific_features', {})
    if isinstance(generator_specific_from_schema, dict) and generator_specific_from_schema:
        active_generator_specific_features = generator_specific_from_schema
    else:
        active_generator_specific_features = GENERATOR_SPECIFIC_FEATURES

    identity_schema = load_identity_schema(CONFIGS, RUN_TABLE_HEADER)

    validate_schema_versions(feature_schema, identity_schema, taxonomy, versions)

    print(
        f'[INFO] morphology_feature_set n={len(morph_features)}, '
        f'taxonomy_identity_schema_version={taxonomy.get("identity_schema_version")}, '
        f'feature_schema_loaded={feature_schema.get("loaded")}, '
        f'feature_schema_version={feature_schema.get("schema_version")}, '
        f'identity_schema_loaded={identity_schema.get("loaded")}, '
        f'identity_schema_version={identity_schema.get("schema_version")}, '
        f'identity_run_table_valid={identity_schema.get("valid_run_table")}',
        flush=True
    )

    if feature_schema.get('error'):
        print(f'[WARN] feature schema fallback active: {feature_schema["error"]}', flush=True)

    if identity_schema.get('error'):
        print(f'[WARN] identity schema fallback active: {identity_schema["error"]}', flush=True)

    if not identity_schema.get('valid_run_table', True):
        print(
            f'[WARN] identity schema expects missing RUN_TABLE_HEADER fields: '
            f'{identity_schema.get("missing_run_table_fields", [])}',
            flush=True
        )

    print(f'[Stage 2 done in {format_hms(time.time() - t1)}]', flush=True)

    print(f'[Stage 3/{STAGE_TOTAL}] Build run matrix (factorial)...', flush=True)
    t2 = time.time()
    jobs, pre_failed_rows = build_run_jobs(protocol, registry, ctx)
    print(f'[INFO] n_jobs={len(jobs)} n_preflight_failed={len(pre_failed_rows)}', flush=True)
    print(f'[Stage 3 done in {format_hms(time.time() - t2)}]', flush=True)

    print(f'[Stage 4/{STAGE_TOTAL}] Generation + Observer (parallel execution)...', flush=True)
    t3 = time.time()
    raw_rows: List[Dict[str, Any]] = []
    timing_rows: List[Dict[str, Any]] = []
    failed_rows: List[Dict[str, Any]] = list(pre_failed_rows)

    if jobs:
        total_jobs = len(jobs)
        completed_count = 0
        last_print_time = time.time()

        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(execute_single_job, job, mode, manifest): job for job in jobs}
            for fut in as_completed(futures):
                completed_count += 1

                curr_time = time.time()
                if curr_time - last_print_time >= 60.0 or completed_count == total_jobs:
                    percent = (completed_count / total_jobs) * 100.0
                    elapsed = curr_time - t3
                    speed = completed_count / elapsed if elapsed > 0 else 0.0
                    eta_sec = (total_jobs - completed_count) / speed if speed > 0 else 0.0

                    print(
                        f'  [Progress] {completed_count}/{total_jobs} ({percent:.1f}%) '
                        f'| Elapsed: {format_hms(elapsed)} | ETA: {format_hms(eta_sec)} '
                        f'| Speed: {speed:.1f} it/s',
                        flush=True
                    )
                    last_print_time = curr_time

                job = futures[fut]
                try:
                    payload = fut.result()
                except Exception as exc:
                    failed_rows.append({
                        'run_id': job['run_id'],
                        'generator': job['generator'],
                        'experiment': job['experiment'],
                        'input_class': job['input_class'],
                        'instance_id': job['instance_id'],
                        'module_name': 'execute_single_job',
                        'version': versions['generator_version'],
                        'input_id': job['run_id'],
                        'failure_stage': 'process_pool',
                        'error': repr(exc),
                    })
                    continue

                if payload.get('status') == STATUS_FAILED and 'row' not in payload:
                    failed_rows.append({k: payload.get(k, '') for k in FAILED_HEADER})
                    continue

                raw_rows.append(payload['row'])
                timing_rows.append(payload['timing'])

    print(f'[INFO] n_completed={len(raw_rows)} n_failed={len(failed_rows)}', flush=True)
    print(f'[Stage 4 done in {format_hms(time.time() - t3)}]', flush=True)

    print(f'[Stage 5/{STAGE_TOTAL}] Morphology classification (normalization)...', flush=True)
    t4 = time.time()

    meta_fields = set(RUN_TABLE_HEADER) | NON_NUMERIC_FIELDS
    feature_names = sorted(
        k for k in {kk for r in raw_rows for kk in r.keys()}
        if k not in meta_fields
    )

    generator_specific_fields = sorted(
        {f for feats in active_generator_specific_features.values() for f in feats}
    ) if isinstance(active_generator_specific_features, dict) else []

    for f in generator_specific_fields:
        if f not in feature_names:
            feature_names.append(f)

    feature_names = sorted(feature_names)

    norm_rows = robust_zscore(raw_rows, feature_names) if raw_rows else []
    print(f'[INFO] n_features={len(feature_names)} (including generator-specific)', flush=True)
    print(f'[Stage 5 done in {format_hms(time.time() - t4)}]', flush=True)

    print(f'[Stage 6/{STAGE_TOTAL}] Identity classification (output_class, transition_type)...', flush=True)
    t5 = time.time()
    identity_rows, centroids = apply_identity_layer(norm_rows, morph_features, taxonomy) if norm_rows else ([], {})
    print(f'[INFO] n_centroids={len(centroids)}', flush=True)
    print(f'[Stage 6 done in {format_hms(time.time() - t5)}]', flush=True)

    print(f'[Stage 7/{STAGE_TOTAL}] Distance computation (within/between/pairwise)...', flush=True)
    t6 = time.time()
    separability = compute_within_between(identity_rows, morph_features, 'input_class') if identity_rows else {
        'within_mean': 0.0,
        'between_mean': 0.0,
        'separability': 0.0,
        'within_by_class': {},
        'class_means': {},
    }
    retrieval, dist_matrix, retrieval_labels = compute_retrieval_metrics(
        identity_rows, morph_features, 'input_class'
    ) if identity_rows else (
        {'top1_accuracy': 0.0, 'top3_accuracy': 0.0, 'n_queries': 0},
        None,
        [],
    )
    print(f'[Stage 7 done in {format_hms(time.time() - t6)}]', flush=True)

    print(f'[Stage 8/{STAGE_TOTAL}] Bifurcation scan...', flush=True)
    t7 = time.time()
    bifurcations = detect_bifurcation_events(
        identity_rows,
        morph_features,
        protocol.get('bifurcation_detection', {}),
    ) if identity_rows else []
    print(f'[INFO] n_bifurcations={len(bifurcations)}', flush=True)
    print(f'[Stage 8 done in {format_hms(time.time() - t7)}]', flush=True)

    print(f'[Stage 9/{STAGE_TOTAL}] Aggregation (transitions, sensitivity, bootstrap CI)...', flush=True)
    t8 = time.time()
    transitions = compute_transition_rates(identity_rows) if identity_rows else {}
    sensitivity = compute_sensitivity_metrics(identity_rows, morph_features) if identity_rows else {}
    seed_sensitivity = compute_seed_sensitivity(identity_rows, morph_features) if identity_rows else {}
    observer_variance = compute_observer_variance(identity_rows, morph_features) if identity_rows else {}
    bootstrap_by_gen = compute_bootstrap_ci(identity_rows, morph_features, 'generator') if identity_rows else {}

    summary = build_summary(
        identity_rows,
        feature_names,
        separability,
        retrieval,
        transitions,
        failed_rows,
        len(bifurcations),
    )
    report = generate_research_report(
        versions,
        source_mode,
        identity_rows,
        feature_names,
        summary,
        separability,
        retrieval,
        transitions,
        bootstrap_by_gen,
        bifurcations,
        sensitivity,
        seed_sensitivity,
        observer_variance,
    )
    print(f'[Stage 9 done in {format_hms(time.time() - t8)}]', flush=True)

    print(f'[Stage 10/{STAGE_TOTAL}] Write artifacts...', flush=True)
    t9 = time.time()

    write_csv_with_header(
        Path(manifest['run_table_path']),
        RUN_TABLE_HEADER,
        [[r.get(h, '') for h in RUN_TABLE_HEADER] for r in identity_rows],
    )
    write_csv_with_header(
        Path(manifest['timing_profile_path']),
        TIMING_HEADER,
        [[r['run_id'], r['generator'], r['experiment'], f"{r['elapsed_sec']:.6f}"] for r in timing_rows],
    )
    write_csv_with_header(
        Path(manifest['failed_runs_path']),
        FAILED_HEADER,
        [[r.get(h, '') for h in FAILED_HEADER] for r in failed_rows],
    )

    feat_header = [
        'run_id',
        'generator',
        'input_class',
        'output_class',
        'transition_type',
        'instance_id',
        'seed',
        'noise_level',
        'deformation_step',
    ] + feature_names

    write_csv_with_header(
        Path(manifest['features_raw_path']),
        feat_header,
        [[r.get(h, '') for h in feat_header] for r in raw_rows],
    )
    write_csv_with_header(
        Path(manifest['features_normalized_path']),
        feat_header,
        [[r.get(h, '') for h in feat_header] for r in identity_rows],
    )

    by_gen: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_transition: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for r in identity_rows:
        by_gen[str(r['generator'])].append(r)
        by_class[str(r['input_class'])].append(r)
        by_transition[str(r.get('transition_type', 'unresolved'))].append(r)

    def agg_rows(
        groups: Dict[str, List[Dict[str, Any]]],
        key_name: str,
        morph_features_local: List[str],
        generator_specific_features_local: Dict[str, List[str]],
    ) -> Tuple[List[str], List[List[Any]]]:
        gen_spec_fields = sorted(
            {f for feats in generator_specific_features_local.values() for f in feats}
        ) if isinstance(generator_specific_features_local, dict) else []

        all_features = list(morph_features_local) + [
            f for f in gen_spec_fields if f not in morph_features_local
        ]

        header = [key_name, 'n_runs'] + all_features
        rows_out: List[List[Any]] = []

        for k, grows in sorted(groups.items()):
            row: List[Any] = [k, len(grows)]
            for f in all_features:
                vals = [
                    float(r[f])
                    for r in grows
                    if f in r and isinstance(r[f], (int, float)) and not np.isnan(r[f])
                ]
                row.append(float(np.mean(vals)) if vals else '')
            rows_out.append(row)

        return header, rows_out

    h, r_ = agg_rows(by_gen, 'generator', morph_features, active_generator_specific_features)
    write_csv_with_header(Path(manifest['aggregate_by_generator_path']), h, r_)

    h, r_ = agg_rows(by_class, 'input_class', morph_features, active_generator_specific_features)
    write_csv_with_header(Path(manifest['aggregate_by_class_path']), h, r_)

    h, r_ = agg_rows(by_transition, 'transition_type', morph_features, active_generator_specific_features)
    write_csv_with_header(Path(manifest['aggregate_by_transition_path']), h, r_)

    bif_rows = [
        [
            b['generator'],
            b['input_class'],
            b['parameter_name'],
            b['parameter_value'],
            b['feature_name'],
            b['gradient_norm'],
            b['zscore'],
            b['confirmed_event'],
        ]
        for b in bifurcations
    ]
    write_csv_with_header(
        Path(manifest['bifurcation_events_path']),
        [
            'generator',
            'input_class',
            'parameter_name',
            'parameter_value',
            'feature_name',
            'gradient_norm',
            'zscore',
            'confirmed_event',
        ],
        bif_rows,
    )

    if dist_matrix is not None:
        dist_rows = [
            [retrieval_labels[i]] + [float(v) for v in dist_matrix[i]]
            for i in range(dist_matrix.shape[0])
        ]
        write_csv_with_header(
            Path(manifest['pairwise_distance_matrix_path']),
            ['input_class'] + [f'd{i}' for i in range(dist_matrix.shape[1])],
            dist_rows,
        )
    else:
        write_csv_with_header(
            Path(manifest['pairwise_distance_matrix_path']),
            ['input_class'],
            [],
        )

    save_json(
        Path(manifest['centroids_path']),
        {
            'identity_schema_version': versions['identity_schema_version'],
            'centroids': centroids,
        }
    )

    save_json(
        Path(manifest['summary_json_path']),
        {
            'config_source': source_mode,
            'component_versions': versions,
            'distance_metric': DISTANCE_METRIC_NAME,
            'normalization_scheme': NORMALIZATION_SCHEME,
            'feature_schema': {
                'schema_name': feature_schema.get('schema_name'),
                'schema_version': feature_schema.get('schema_version'),
                'observer_version': feature_schema.get('observer_version'),
                'source_path': feature_schema.get('source_path'),
                'loaded': feature_schema.get('loaded'),
                'error': feature_schema.get('error'),
                'n_morphology_features': len(morph_features),
            },
            'identity_schema': {
                'schema_name': identity_schema.get('schema_name'),
                'schema_version': identity_schema.get('schema_version'),
                'observer_version': identity_schema.get('observer_version'),
                'feature_schema_version': identity_schema.get('feature_schema_version'),
                'source_path': identity_schema.get('source_path'),
                'loaded': identity_schema.get('loaded'),
                'valid_run_table': identity_schema.get('valid_run_table'),
                'missing_run_table_fields': identity_schema.get('missing_run_table_fields'),
                'error': identity_schema.get('error'),
            },
            'summary': summary,
            'separability': separability,
            'retrieval': retrieval,
            'transitions': transitions,
            'sensitivity': sensitivity,
            'seed_sensitivity': seed_sensitivity,
            'observer_variance': observer_variance,
            'n_bifurcations': len(bifurcations),
            'n_failed_runs': len(failed_rows),
        }
    )

    with Path(manifest['research_report_md_path']).open('w', encoding='utf-8') as f:
        f.write(report)

    print(f'[Stage 10 done in {format_hms(time.time() - t9)}]', flush=True)

    print(
        json.dumps(
            {
                'config_source': source_mode,
                'n_jobs': len(jobs),
                'n_runs': len(identity_rows),
                'n_failed_runs': len(failed_rows),
                'n_bifurcations': len(bifurcations),
                'output_dir': str(OUT),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == '__main__':
    main()
