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
from typing import Any, Dict, List, Tuple

import numpy as np
import yaml
from scipy.stats import bootstrap

ROOT = Path(__file__).resolve().parent
CONFIGS = ROOT / 'configs'
OUT = ROOT / 'output'
BUNDLE = OUT / 'frozen_benchmark_bundle.json'
MANIFEST = OUT / 'manifest_full.json'

LIB_SEARCH_PATHS = [
    Path(r'd:\IFZ\qwen_coder\lib'),
    ROOT / 'lib',
    ROOT,
]

RUN_TABLE_HEADER = [
    'run_id', 'generator', 'experiment', 'class_name', 'instance_id', 'seed',
    'noise_level', 'deformation_step', 'mapping_mode', 'status', 'artifact_stub'
]
TIMING_HEADER = ['run_id', 'generator', 'experiment', 'elapsed_sec']
FAILED_HEADER = ['generator', 'experiment', 'class_name', 'instance_id', 'error']


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


def stable_seed(*parts: Any) -> int:
    s = '|'.join(map(str, parts)).encode('utf-8')
    return int(hashlib.sha256(s).hexdigest()[:16], 16) % (2 ** 32)


def clip01(x: Any) -> np.ndarray:
    return np.clip(np.asarray(x, dtype=float), 0.0, 1.0)


def pairwise_distances_numpy(X: np.ndarray) -> np.ndarray:
    diff = X[:, None, :] - X[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def choose_mode(protocol: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    runtime_cfg = protocol.get('runtime', {}) if isinstance(protocol.get('runtime', {}), dict) else {}
    active_mode = runtime_cfg.get('active_mode') or 'research-fast'
    modes = protocol.get('modes', {})
    if not isinstance(modes, dict) or not modes:
        return 'implicit-default', {'repeats_per_class': 3, 'deformation_steps': 6, 'sensitivity_steps': 15}
    if active_mode in modes and isinstance(modes[active_mode], dict):
        return str(active_mode), modes[active_mode]
    preferred = ['research-fast', 'research', 'publication', 'validation-hires']
    for name in preferred:
        if name in modes and isinstance(modes[name], dict):
            return name, modes[name]
    first_key = next(iter(modes))
    val = modes[first_key]
    return first_key, val if isinstance(val, dict) else {'repeats_per_class': 3, 'deformation_steps': 6, 'sensitivity_steps': 15}


def build_instance_vector(base_vector: List[float], offsets: List[float], expected_len: int) -> np.ndarray:
    base = np.asarray(base_vector, dtype=float)
    off = np.asarray(offsets, dtype=float)
    if len(base) != expected_len:
        raise ValueError(f'base_vector length {len(base)} != dimensions count {expected_len}')
    if len(off) != expected_len:
        raise ValueError(f'offset length {len(off)} != dimensions count {expected_len}')
    return clip01(base + off)


def apply_parameter_noise(vec: np.ndarray, noise_level: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if noise_level <= 0:
        return vec.copy()
    return clip01(vec + rng.normal(0.0, noise_level, size=len(vec)))


def default_seed_list(protocol: Dict[str, Any], repeats_per_class: int) -> List[int]:
    randomness = protocol.get('randomness', {})
    seeds = randomness.get('seeds', []) if isinstance(randomness, dict) else []
    if isinstance(seeds, list) and seeds:
        return [int(s) for s in seeds[:repeats_per_class]]
    return list(range(repeats_per_class))


def default_noise_levels(protocol: Dict[str, Any]) -> List[float]:
    direct = protocol.get('noise_levels', [])
    if isinstance(direct, list) and direct:
        return [float(v) for v in direct]
    noise = protocol.get('noise', {}) if isinstance(protocol.get('noise', {}), dict) else {}
    parameter_noise = noise.get('parameter_noise', {}) if isinstance(noise.get('parameter_noise', {}), dict) else {}
    levels = parameter_noise.get('levels', [0.0])
    if isinstance(levels, list) and levels:
        return [float(v) for v in levels]
    return [0.0]


def default_seed_noise(protocol: Dict[str, Any], generator: str) -> float:
    noise = protocol.get('noise', {}) if isinstance(protocol.get('noise', {}), dict) else {}
    seed_noise = noise.get('seed_noise', {}) if isinstance(noise.get('seed_noise', {}), dict) else {}
    return float(seed_noise.get(generator, 0.0))


def default_mapping_mode(protocol: Dict[str, Any]) -> str:
    mapping_cfg = protocol.get('mapping', {})
    if not isinstance(mapping_cfg, dict):
        return 'rule_based_mapping'
    return str(mapping_cfg.get('default_mapping_mode', 'rule_based_mapping'))


def default_experiments(protocol: Dict[str, Any]) -> List[str]:
    experiments = protocol.get('experiments', [])
    if isinstance(experiments, list) and experiments:
        return [str(e) for e in experiments]
    return ['reproducibility', 'sensitivity', 'separability', 'family_deformation']


def default_generator_registry(protocol: Dict[str, Any]) -> List[Dict[str, Any]]:
    generators_cfg = protocol.get('generators', {})
    nonlinear = generators_cfg.get('nonlinear', []) if isinstance(generators_cfg, dict) else []
    baselines = generators_cfg.get('baselines', []) if isinstance(generators_cfg, dict) else []
    registry = []
    for g in nonlinear:
        registry.append({'name': str(g), 'enabled': True, 'family': 'nonlinear'})
    for g in baselines:
        registry.append({'name': str(g), 'enabled': True, 'family': 'baseline'})
    if registry:
        return registry
    return [
        {'name': 'julia_orbit_trap', 'enabled': True, 'family': 'fallback'},
        {'name': 'orbit_ifs_multi_trap', 'enabled': True, 'family': 'fallback'},
        {'name': 'duffing_lyapunov', 'enabled': True, 'family': 'fallback'},
        {'name': 'chaotic_scattering', 'enabled': True, 'family': 'fallback'},
    ]


def default_benchmark_sets(registry: Dict[str, Any]) -> Dict[str, Any]:
    benchmark_sets = registry.get('benchmark_sets', {}) if isinstance(registry, dict) else {}
    if isinstance(benchmark_sets, dict) and benchmark_sets:
        return benchmark_sets
    classes = registry.get('classes', []) if isinstance(registry, dict) else []
    names = [c.get('name') for c in classes if isinstance(c, dict) and c.get('name')]
    return {
        'reproducibility': {'include_classes': names},
        'sensitivity': {'include_classes': names},
        'separability': {'include_classes': names},
        'family_deformation': {'include_classes': names},
    }


def build_default_manifest() -> Dict[str, str]:
    ensure_dir(OUT)
    return {
        'run_table_path': str(OUT / 'run_table.csv'),
        'timing_profile_path': str(OUT / 'timing_profile.csv'),
        'features_raw_path': str(OUT / 'features_raw.csv'),
        'features_normalized_path': str(OUT / 'features_normalized.csv'),
        'aggregate_by_class_path': str(OUT / 'aggregate_by_class.csv'),
        'aggregate_by_generator_path': str(OUT / 'aggregate_by_generator.csv'),
        'aggregate_by_experiment_path': str(OUT / 'aggregate_by_experiment.csv'),
        'pairwise_distance_matrix_path': str(OUT / 'pairwise_distance_matrix.csv'),
        'retrieval_accuracy_path': str(OUT / 'retrieval_accuracy.csv'),
        'bifurcation_events_path': str(OUT / 'bifurcation_events.csv'),
        'summary_json_path': str(OUT / 'summary.json'),
        'research_report_md_path': str(OUT / 'research_report.md'),
        'failed_runs_path': str(OUT / 'failed_runs.csv'),
        'manifest_full_path': str(MANIFEST),
        'frozen_bundle_path': str(BUNDLE),
        'observations_dir': str(OUT / 'observations'),
        'preview_dir': str(OUT / 'preview_png'),
    }


def build_bundle_from_yaml() -> Dict[str, Any]:
    protocol_path = CONFIGS / 'experiment_protocol.yaml'
    registry_path = CONFIGS / 'input_registry.yaml'
    if not protocol_path.exists():
        raise FileNotFoundError(f'Missing protocol YAML: {protocol_path}')
    if not registry_path.exists():
        raise FileNotFoundError(f'Missing input registry YAML: {registry_path}')
    protocol = load_yaml(protocol_path)
    registry = load_yaml(registry_path)
    mode_name, mode = choose_mode(protocol)
    ctx = {
        'mode_name': mode_name,
        'mode': mode,
        'default_mapping_mode': default_mapping_mode(protocol),
        'benchmark_sets': default_benchmark_sets(registry),
        'generator_registry': default_generator_registry(protocol),
    }
    return {
        'protocol_spec': {'source': str(protocol_path), 'content': protocol},
        'input_registry_spec': {'source': str(registry_path), 'content': registry},
        'benchmark_context': ctx,
        'build_info': {
            'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'builder': 'benchmark-runner_v3 real backend integration',
        },
    }


def prepare_bundle_and_manifest() -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    ensure_dir(OUT)
    source_mode = 'frozen'
    if BUNDLE.exists():
        bundle = load_json(BUNDLE)
    else:
        bundle = build_bundle_from_yaml()
        save_json(BUNDLE, bundle)
        source_mode = 'yaml-fallback'
    if MANIFEST.exists():
        manifest = load_json(MANIFEST)
    else:
        manifest = build_default_manifest()
        save_json(MANIFEST, manifest)
        source_mode = f'{source_mode}+manifest-generated'
    return bundle, manifest, source_mode


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
        if path.exists() and (path / 'core.py').exists() and (path / 'generators.py').exists() and (path / 'observe.py').exists() and (path / 'metrics.py').exists():
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
    rhythmic_period = float(max(1e-3, v[2]))
    repetition_coeff = float(v[6])
    tension = float(v[4])
    symmetry = float(2.0 * v[5] - 1.0)
    density = float(v[3])
    contrast = float(v[7])
    return core_mod.Harmony(
        spectral_profile=spectral_profile,
        freq_ratios=freq_ratios,
        rhythmic_period=rhythmic_period,
        repetition_coeff=repetition_coeff,
        tension=tension,
        symmetry=symmetry,
        density=density,
        contrast=contrast,
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
    extra = {}
    gen_name = generator
    if generator == 'orbit_ifs_multi_trap':
        extra['npoints'] = int(mode.get('ifs_points', 50000))
    elif generator == 'duffing_lyapunov':
        extra['nsteps'] = int(mode.get('duffing_steps', 400))
        max_iter = int(mode.get('duffing_steps', 400))
    elif generator == 'chaotic_scattering':
        max_iter = int(mode.get('duffing_steps', 400))
    return core_mod.SimState(
        generator_name=gen_name,
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


def robust_zscore(rows: List[Dict[str, Any]], feature_names: List[str]) -> List[Dict[str, Any]]:
    vals = {f: [] for f in feature_names}
    for r in rows:
        for f in feature_names:
            vals[f].append(float(r.get(f, np.nan)))
    stats = {}
    for f in feature_names:
        arr = np.array(vals[f], dtype=float)
        med = np.nanmedian(arr)
        mad = np.nanmedian(np.abs(arr - med))
        scale = 1.4826 * mad if mad > 1e-12 else (np.nanstd(arr) if np.nanstd(arr) > 1e-12 else 1.0)
        stats[f] = (med, scale)
    norm_rows = []
    for r in rows:
        nr = dict(r)
        for f in feature_names:
            val = float(r.get(f, np.nan))
            med, scale = stats[f]
            nr[f] = float((val - med) / scale) if not np.isnan(val) else np.nan
        norm_rows.append(nr)
    return norm_rows


def write_csv_with_header(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    ensure_dir(path.parent)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def write_feature_csv(path: Path, rows: List[Dict[str, Any]], feature_names: List[str]) -> None:
    header = ['run_id', 'generator', 'experiment', 'class_name', 'instance_id', 'seed', 'noise_level', 'deformation_step'] + feature_names
    csv_rows = []
    for r in rows:
        row = [r['run_id'], r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'], r['deformation_step']]
        row.extend([r.get(f, '') for f in feature_names])
        csv_rows.append(row)
    write_csv_with_header(path, header, csv_rows)


def summarize(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    by_gen = {}
    generators = sorted(set(r['generator'] for r in rows)) if rows else []
    for g in generators:
        sub = [r for r in rows if r['generator'] == g]
        by_gen[g] = {
            'n_runs': len(sub),
            'features_mean': {f: float(np.nanmean([r[f] for r in sub if f in r])) for f in feature_names if any(f in r for r in sub)},
        }
    return {'n_total_runs': len(rows), 'generators': by_gen}


def compute_within_class_variance(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_class[r['class_name']].append(r)
    within_vars = {}
    for cls, cls_rows in by_class.items():
        cls_vars = []
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r and not np.isnan(r[f])]
            if len(vals) > 1:
                cls_vars.append(np.var(vals, ddof=1))
        within_vars[cls] = float(np.mean(cls_vars)) if cls_vars else 0.0
    overall_within_mean = float(np.mean(list(within_vars.values()))) if within_vars else 0.0
    return {'within_class_variances': within_vars, 'within_mean': overall_within_mean}


def compute_between_class_variance(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_class[r['class_name']].append(r)
    class_means: Dict[str, Dict[str, float]] = {}
    for cls, cls_rows in by_class.items():
        class_means[cls] = {}
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r and not np.isnan(r[f])]
            if vals:
                class_means[cls][f] = float(np.mean(vals))
    between_vars = []
    for f in feature_names:
        means_for_f = [class_means[cls][f] for cls in class_means if f in class_means[cls]]
        if len(means_for_f) > 1:
            between_vars.append(np.var(means_for_f, ddof=1))
    between_mean = float(np.mean(between_vars)) if between_vars else 0.0
    return {'between_mean': between_mean, 'class_means': class_means}


def compute_separability(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    within = compute_within_class_variance(rows, feature_names)
    between = compute_between_class_variance(rows, feature_names)
    separability_score = between['between_mean'] / (within['within_mean'] + 1e-8)
    return {
        'separability_score': float(separability_score),
        'within_mean': within['within_mean'],
        'between_mean': between['between_mean'],
        'within_by_class': within['within_class_variances'],
        'class_means': between['class_means'],
    }


def compute_retrieval_metrics(rows: List[Dict[str, Any]], feature_names: List[str], sample_size: int = 500):
    data = []
    for r in rows:
        feat_vec = [r[f] for f in feature_names if f in r and not np.isnan(r[f])]
        if len(feat_vec) == len(feature_names):
            data.append({'class_name': r['class_name'], 'features': np.array(feat_vec, dtype=float)})
    if len(data) < 2:
        return {'top1_accuracy': 0.0, 'top3_accuracy': 0.0, 'n_queries': 0}, None, []
    if len(data) > sample_size:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(data), sample_size, replace=False)
        data = [data[i] for i in sorted(idx)]
    X = np.vstack([d['features'] for d in data])
    labels = [d['class_name'] for d in data]
    dist_matrix = pairwise_distances_numpy(X)
    top1_correct = 0
    top3_correct = 0
    n_queries = len(data)
    for i in range(n_queries):
        distances = dist_matrix[i].copy()
        distances[i] = np.inf
        sorted_idx = np.argsort(distances)
        if labels[sorted_idx[0]] == labels[i]:
            top1_correct += 1
        nearest_3 = [labels[j] for j in sorted_idx[:3]]
        if labels[i] in nearest_3:
            top3_correct += 1
    return {
        'top1_accuracy': float(top1_correct / n_queries),
        'top3_accuracy': float(top3_correct / n_queries),
        'n_queries': n_queries,
    }, dist_matrix, labels


def compute_bootstrap_ci(rows: List[Dict[str, Any]], feature_names: List[str], n_bootstrap: int = 300, confidence_level: float = 0.95) -> Dict[str, Any]:
    by_gen: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_gen[r['generator']].append(r)
    out = {}
    for gen, gen_rows in by_gen.items():
        stats_by_feature = {}
        for f in feature_names:
            vals = np.array([r[f] for r in gen_rows if f in r and not np.isnan(r[f])], dtype=float)
            if len(vals) >= 2:
                try:
                    res = bootstrap((vals,), np.mean, confidence_level=confidence_level, n_resamples=n_bootstrap, random_state=42)
                    stats_by_feature[f] = {'mean': float(np.mean(vals)), 'ci_lower': float(res.confidence_interval.low), 'ci_upper': float(res.confidence_interval.high)}
                except Exception:
                    stderr = np.std(vals, ddof=1) / np.sqrt(len(vals))
                    stats_by_feature[f] = {'mean': float(np.mean(vals)), 'ci_lower': float(np.mean(vals) - 1.96 * stderr), 'ci_upper': float(np.mean(vals) + 1.96 * stderr)}
        out[gen] = stats_by_feature
    return out


def moving_average(arr: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(arr) < window:
        return arr.copy()
    kernel = np.ones(window, dtype=float) / window
    pad_left = window // 2
    pad_right = window - 1 - pad_left
    padded = np.pad(arr, (pad_left, pad_right), mode='edge')
    return np.convolve(padded, kernel, mode='valid')


def detect_bifurcation_events(rows: List[Dict[str, Any]], feature_names: List[str], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    trajectories: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'])
        trajectories[key].append(r)
    smoothing_window = int(config.get('smoothing_window', 3)) if isinstance(config, dict) else 3
    z_threshold = float(config.get('z_threshold', 2.5)) if isinstance(config, dict) else 2.5
    persistence_points = int(config.get('persistence_points', 2)) if isinstance(config, dict) else 2
    min_jump_norm = float(config.get('min_jump_norm', 0.15)) if isinstance(config, dict) else 0.15
    out = []
    for key, traj in trajectories.items():
        traj = sorted(traj, key=lambda x: int(x.get('deformation_step', 0)))
        if len(traj) < max(3, persistence_points + 1):
            continue
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
                    out.append({'generator': key[0], 'class_name': key[2], 'parameter_name': 'deformation_step', 'parameter_value': int(i + 1), 'feature': f, 'gradient_norm': float(np.mean(np.abs(local_jump))), 'zscore': float(np.max(local_z)), 'confirmed_event': True})
                    break
    return out


def save_run_observation(manifest: Dict[str, Any], run_id: str, adapted_result) -> str:
    runtime_cfg = manifest.get('_runtime', {}) if isinstance(manifest.get('_runtime', {}), dict) else {}
    if not bool(runtime_cfg.get('save_observation_arrays', True)):
        return ''
    obs_dir = Path(manifest['observations_dir'])
    ensure_dir(obs_dir)
    base = obs_dir / run_id
    np.save(base.with_suffix('.orbit.npy'), np.asarray(adapted_result.orbit_map, dtype=np.float32))
    np.save(base.with_suffix('.visit.npy'), np.asarray(adapted_result.visit_density, dtype=np.float32))
    return str(base)


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


def generate_research_report(source_mode: str, rows: List[Dict[str, Any]], feature_names: List[str], summary: Dict[str, Any], separability_results: Dict[str, Any], retrieval_results: Dict[str, Any], bootstrap_results: Dict[str, Any], bifurcations: List[Dict[str, Any]], stage2_metrics: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append('# Benchmark Research Report\n\n')
    lines.append(f'- Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
    lines.append(f'- Config source: {source_mode}\n')
    lines.append(f'- Total runs: {len(rows)}\n')
    lines.append(f'- Number of normalized features: {len(feature_names)}\n\n')
    lines.append('## Executive Summary\n\n')
    lines.append(f'- Separability score: {separability_results.get("separability_score", 0.0):.6f}\n')
    lines.append(f'- Within mean: {separability_results.get("within_mean", 0.0):.6f}\n')
    lines.append(f'- Between mean: {separability_results.get("between_mean", 0.0):.6f}\n')
    lines.append(f'- Top-1 retrieval: {retrieval_results.get("top1_accuracy", 0.0):.6f}\n')
    lines.append(f'- Top-3 retrieval: {retrieval_results.get("top3_accuracy", 0.0):.6f}\n')
    lines.append(f'- Confirmed bifurcation events: {len(bifurcations)}\n\n')
    lines.append('## Generator Means\n\n')
    lines.append('| Generator | N runs | Mean symmetry | Mean fractal dim | Mean basin entropy |\n')
    lines.append('|---|---:|---:|---:|---:|\n')
    for gen, data in sorted(summary.get('generators', {}).items()):
        fm = data.get('features_mean', {})
        lines.append(f'| {gen} | {data.get("n_runs", 0)} | {fm.get("symmetry_score", 0.0):.4f} | {fm.get("fractal_dim_proxy", 0.0):.4f} | {fm.get("basin_entropy", 0.0):.4f} |\n')
    lines.append('\n')
    lines.append('## Stage-2 Metrics\n\n')
    for k, v in sorted(stage2_metrics.items()):
        lines.append(f'- {k}: {v}\n')
    lines.append('\n')
    lines.append('## Bootstrap CI\n\n')
    for gen, gen_data in sorted(bootstrap_results.items()):
        lines.append(f'### {gen}\n\n')
        lines.append('| Feature | Mean | CI lower | CI upper |\n')
        lines.append('|---|---:|---:|---:|\n')
        for feat, stats in sorted(gen_data.items()):
            lines.append(f'| {feat} | {stats["mean"]:.4f} | {stats["ci_lower"]:.4f} | {stats["ci_upper"]:.4f} |\n')
        lines.append('\n')
    lines.append('## Bifurcation Events\n\n')
    if bifurcations:
        lines.append('| Generator | Class | Feature | Parameter value | Gradient norm | Z-score |\n')
        lines.append('|---|---|---|---:|---:|---:|\n')
        for b in bifurcations[:20]:
            lines.append(f'| {b["generator"]} | {b["class_name"]} | {b["feature"]} | {b["parameter_value"]} | {b["gradient_norm"]:.4f} | {b["zscore"]:.4f} |\n')
    else:
        lines.append('No confirmed bifurcation events detected.\n')
    lines.append('\n')
    return ''.join(lines)


def compute_stage2_metrics(norm_rows: List[Dict[str, Any]], feature_names: List[str], metrics_mod) -> Dict[str, Any]:
    if not norm_rows or not feature_names:
        return {}
    X = np.array([[r[f] for f in feature_names] for r in norm_rows], dtype=float)
    labels = np.array([r['class_name'] for r in norm_rows])
    class_stats = metrics_mod.class_distances(X, labels)
    out = {
        'within_mean_metrics_module': float(class_stats.get('within_mean', 0.0)),
        'between_mean_metrics_module': float(class_stats.get('between_mean', 0.0)),
        'separability_metrics_module': float(class_stats.get('separability', 0.0)),
    }

    repro_rows = [r for r in norm_rows if r['experiment'] == 'reproducibility']
    if len(repro_rows) >= 2:
        XR = np.array([[r[f] for f in feature_names] for r in repro_rows], dtype=float)
        rep = metrics_mod.reproducibility_score(XR)
        out['mean_cv'] = float(rep.get('mean_cv', 0.0))
        out['max_cv'] = float(rep.get('max_cv', 0.0))

    fam_rows = [r for r in norm_rows if r['experiment'] == 'family_deformation']
    if len(fam_rows) >= 3:
        fam_grouped: Dict[Tuple[str, str, int, int, float], List[Dict[str, Any]]] = defaultdict(list)
        for r in fam_rows:
            key = (r['generator'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'])
            fam_grouped[key].append(r)
        cohesion_vals = []
        for seq in fam_grouped.values():
            seq = sorted(seq, key=lambda z: z['deformation_step'])
            if len(seq) >= 3:
                XS = np.array([[s[f] for f in feature_names] for s in seq], dtype=float)
                coh = metrics_mod.family_cohesion(XS)
                cohesion_vals.append(coh.get('cohesion_ratio', np.nan))
        if cohesion_vals:
            out['family_continuity_score'] = float(np.nanmean(cohesion_vals))
            out['cohesion_ratio'] = float(np.nanmean(cohesion_vals))

    sens_rows = [r for r in norm_rows if r['experiment'] == 'sensitivity']
    if len(sens_rows) >= 3:
        sens_grouped: Dict[Tuple[str, str, int, int, float], List[Dict[str, Any]]] = defaultdict(list)
        for r in sens_rows:
            key = (r['generator'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'])
            sens_grouped[key].append(r)
        grads = []
        for seq in sens_grouped.values():
            seq = sorted(seq, key=lambda z: z['deformation_step'])
            if len(seq) >= 3:
                XS = np.array([[s[f] for f in feature_names] for s in seq], dtype=float)
                ps = np.array([s['deformation_step'] for s in seq], dtype=float)
                sens = metrics_mod.sensitivity_curve(XS, ps)
                grads.append(sens.get('max_gradient', np.nan))
        if grads:
            out['input_perturbation_sensitivity'] = float(np.nanmean(grads))
    return out


def build_run_jobs(protocol: Dict[str, Any], registry: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    mode = ctx.get('mode', {})
    repeats_per_class = int(mode.get('repeats_per_class', 3))
    deformation_steps = int(mode.get('deformation_steps', 6))
    sensitivity_steps = int(mode.get('sensitivity_steps', 15))
    mapping_mode = str(ctx.get('default_mapping_mode', 'rule_based_mapping'))
    generators = [g['name'] for g in ctx.get('generator_registry', []) if g.get('enabled', True)]

    dimensions = registry.get('dimensions', []) if isinstance(registry.get('dimensions', []), list) else []
    expected_len = len(dimensions) if dimensions else 8
    class_defs = registry.get('classes', []) if isinstance(registry.get('classes', []), list) else []
    class_map = {c['name']: c for c in class_defs if isinstance(c, dict) and c.get('name')}
    benchmark_sets = ctx.get('benchmark_sets', {}) if isinstance(ctx.get('benchmark_sets', {}), dict) else {}
    seeds = default_seed_list(protocol, repeats_per_class)
    noise_levels = default_noise_levels(protocol)
    experiments = default_experiments(protocol)

    jobs: List[Dict[str, Any]] = []
    failed_rows: List[Dict[str, Any]] = []

    for generator in generators:
        gen_seed_noise = default_seed_noise(protocol, generator)
        for experiment in experiments:
            selected_classes = benchmark_sets.get(experiment, {}).get('include_classes', list(class_map.keys()))
            for class_name in selected_classes:
                if class_name not in class_map:
                    failed_rows.append({'generator': generator, 'experiment': experiment, 'class_name': class_name, 'instance_id': -1, 'error': f'class_not_found_in_registry: {class_name}'})
                    continue
                cdef = class_map[class_name]
                base_vector = cdef.get('base_vector', [0.5] * expected_len)
                n_inst = int(cdef.get('n_instances', 1))
                offsets = cdef.get('instance_generation', {}).get('offsets', [])
                if not isinstance(offsets, list) or len(offsets) < n_inst:
                    failed_rows.append({'generator': generator, 'experiment': experiment, 'class_name': class_name, 'instance_id': -1, 'error': 'missing_or_incomplete_offsets'})
                    continue
                local_pert_scales = cdef.get('perturbation_scales', registry.get('perturbation_policy', {}).get('default_scales', [0.01, 0.03, 0.05]))
                for instance_id in range(n_inst):
                    try:
                        instance_vec = build_instance_vector(base_vector, offsets[instance_id], expected_len)
                    except Exception as exc:
                        failed_rows.append({'generator': generator, 'experiment': experiment, 'class_name': class_name, 'instance_id': instance_id, 'error': repr(exc)})
                        continue
                    if experiment == 'family_deformation':
                        step_count = deformation_steps
                    elif experiment == 'sensitivity':
                        step_count = sensitivity_steps
                    else:
                        step_count = 1
                    experiment_noise_levels = local_pert_scales if experiment in {'family_deformation', 'sensitivity'} else noise_levels
                    for deformation_step in range(step_count):
                        for noise_level in experiment_noise_levels:
                            for seed in seeds:
                                run_id = f'{generator}__{experiment}__{class_name}__i{instance_id:02d}__s{seed:02d}__n{float(noise_level):.3f}__d{deformation_step:02d}__{mapping_mode}'
                                jobs.append({
                                    'run_id': run_id,
                                    'generator': generator,
                                    'experiment': experiment,
                                    'class_name': class_name,
                                    'instance_id': instance_id,
                                    'seed': seed,
                                    'noise_level': float(noise_level),
                                    'deformation_step': deformation_step,
                                    'mapping_mode': mapping_mode,
                                    'instance_vec': instance_vec.tolist(),
                                    'gen_seed_noise': float(gen_seed_noise),
                                })
    return jobs, failed_rows


def execute_single_job(job: Dict[str, Any], mode: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    lib_dir = resolve_lib_dir()
    core_mod, generators_mod, observe_mod, _metrics_mod = import_backend_modules(lib_dir)
    generator_dispatch = get_generator_dispatch(generators_mod)

    mapping_mode = str(job['mapping_mode'])
    encoder = core_mod.HarmonyEncoder(seed=12345) if mapping_mode == 'frozen_encoder_mapping' else None

    run_id = str(job['run_id'])
    generator = str(job['generator'])
    experiment = str(job['experiment'])
    vec = np.asarray(job['instance_vec'], dtype=float)
    noise_level = float(job['noise_level'])
    deformation_step = int(job['deformation_step'])

    step_count = 1
    if experiment == 'family_deformation':
        step_count = int(mode.get('deformation_steps', 6))
    elif experiment == 'sensitivity':
        step_count = int(mode.get('sensitivity_steps', 15))

    if experiment == 'family_deformation' and step_count > 1:
        alpha = deformation_step / max(1, step_count - 1)
        direction = np.array([1, -1, 1, -1, 1, -1, 1, -1], dtype=float)
        vec = clip01(vec + alpha * noise_level * direction)
    elif experiment == 'sensitivity' and step_count > 1:
        alpha = deformation_step / max(1, step_count - 1)
        vec = vec.copy()
        vec[4] = np.clip(alpha, 0.0, 1.0)
    else:
        vec = apply_parameter_noise(vec, noise_level, stable_seed(run_id, 'parameter_noise'))

    harmony = vector_to_harmony(core_mod, vec)
    theta = encoder.encode(harmony, dim_out=6) if encoder is not None else rule_based_theta(harmony, dim_out=6)
    sim_state = make_sim_state(core_mod, generator, theta, mode, stable_seed(run_id, 'sim_seed'), float(job['gen_seed_noise']))

    if generator in generator_dispatch:
        result = generator_dispatch[generator](sim_state)
    else:
        result = run_baseline(generator, theta, mode, stable_seed(run_id, 'baseline_seed'))

    adapted = adapt_result_fields(result)
    artifact_stub = save_run_observation(manifest, run_id, adapted)
    feats = extract_feature_dict(observe_mod, adapted)
    feats.update(compute_generator_specific_metrics(adapted, generator))

    row = {
        'run_id': run_id,
        'generator': generator,
        'experiment': experiment,
        'class_name': str(job['class_name']),
        'instance_id': int(job['instance_id']),
        'seed': int(job['seed']),
        'noise_level': noise_level,
        'deformation_step': deformation_step,
        'mapping_mode': mapping_mode,
        'status': 'completed',
        'artifact_stub': artifact_stub,
        **feats,
    }
    return {
        'row': row,
        'timing': {
            'run_id': run_id,
            'generator': generator,
            'experiment': experiment,
            'elapsed_sec': time.time() - t0,
        }
    }
def format_hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:02d}'


def render_progress_bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return '[' + ('-' * width) + ']'
    ratio = max(0.0, min(1.0, done / total))
    filled = int(round(ratio * width))
    filled = min(filled, width)
    return '[' + ('#' * filled) + ('-' * (width - filled)) + ']'


def print_stage(stage_idx: int, stage_total: int, title: str) -> None:
    print(f'[Stage {stage_idx}/{stage_total}] {title}', flush=True)


def print_job_breakdown(jobs: List[Dict[str, Any]]) -> None:
    exp_counts = Counter(str(j['experiment']) for j in jobs)
    gen_counts = Counter(str(j['generator']) for j in jobs)

    print('[INFO] Jobs by experiment:', flush=True)
    for name, count in sorted(exp_counts.items()):
        print(f'  - {name}: {count}', flush=True)

    print('[INFO] Jobs by generator:', flush=True)
    for name, count in sorted(gen_counts.items()):
        print(f'  - {name}: {count}', flush=True)


class ProgressReporter:
    def __init__(self, total: int, update_interval_sec: float = 60.0, bar_width: int = 28) -> None:
        self.total = max(0, int(total))
        self.update_interval_sec = max(1.0, float(update_interval_sec))
        self.bar_width = int(bar_width)
        self.start_time = time.time()
        self.last_print_time = 0.0
        self.done = 0
        self.failed = 0
        self.last_label = ''

    def set_failed(self, failed: int) -> None:
        self.failed = max(0, int(failed))

    def step(self, n: int = 1, failed: int | None = None, label: str = '', force: bool = False) -> None:
        self.done += int(n)
        if failed is not None:
            self.failed = max(0, int(failed))
        if label:
            self.last_label = str(label)
        self.maybe_print(force=force)

    def maybe_print(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self.last_print_time) < self.update_interval_sec:
            return
        self.last_print_time = now

        elapsed = now - self.start_time
        pct = (100.0 * self.done / self.total) if self.total > 0 else 100.0
        avg_sec = (elapsed / self.done) if self.done > 0 else 0.0
        remain = max(0, self.total - self.done)
        eta = avg_sec * remain if self.done > 0 else 0.0
        rate_per_min = (self.done / elapsed * 60.0) if elapsed > 0 else 0.0
        bar = render_progress_bar(self.done, self.total, width=self.bar_width)

        tail = f' | last: {self.last_label}' if self.last_label else ''
        print(
            f'[PROGRESS] {bar} {self.done}/{self.total} ({pct:6.2f}%)'
            f' | failed: {self.failed}'
            f' | elapsed: {format_hms(elapsed)}'
            f' | eta: {format_hms(eta)}'
            f' | rate: {rate_per_min:5.2f} jobs/min'
            f'{tail}',
            flush=True,
        )

    def finish(self, failed: int | None = None, label: str = '') -> None:
        if failed is not None:
            self.failed = max(0, int(failed))
        if label:
            self.last_label = str(label)
        self.done = self.total
        self.maybe_print(force=True)

def main() -> None:
    STAGE_TOTAL = 6

    print_stage(1, STAGE_TOTAL, 'Prepare bundle and manifest...')
    t_stage_1 = time.time()
    bundle, manifest, source_mode = prepare_bundle_and_manifest()
    protocol = bundle.get('protocol_spec', {}).get('content', {})
    registry = bundle.get('input_registry_spec', {}).get('content', {})
    ctx = bundle.get('benchmark_context', {})

    mode = ctx.get('mode', {})
    runtime_cfg = protocol.get('runtime', {}) if isinstance(protocol.get('runtime', {}), dict) else {}
    if not runtime_cfg.get('active_mode'):
        runtime_cfg['active_mode'] = 'research-fast'
    protocol['runtime'] = runtime_cfg

    workers = int(runtime_cfg.get('n_workers', 8) or 8)

    manifest = dict(manifest)
    manifest['_runtime'] = {
        'save_observation_arrays': False,  # для массового прогона
    }

    lib_dir = resolve_lib_dir()
    _core_mod, _generators_mod, _observe_mod, metrics_mod = import_backend_modules(lib_dir)

    print(
        f'[INFO] Config source: {source_mode} | mode: {ctx.get("mode_name", "unknown")} | '
        f'workers: {workers} | lib_dir: {lib_dir}',
        flush=True,
    )
    print(f'[INFO] Stage 1 done in {format_hms(time.time() - t_stage_1)}', flush=True)

    print_stage(2, STAGE_TOTAL, 'Build run list...')
    t_stage_2 = time.time()
    jobs, pre_failed_rows = build_run_jobs(protocol, registry, ctx)
    print(f'[INFO] Total jobs: {len(jobs)}', flush=True)
    print(f'[INFO] Preflight failed rows: {len(pre_failed_rows)}', flush=True)
    print_job_breakdown(jobs)
    print(f'[INFO] Stage 2 done in {format_hms(time.time() - t_stage_2)}', flush=True)

    print_stage(3, STAGE_TOTAL, 'Execute jobs...')
    t_stage_3 = time.time()

    all_run_rows: List[Dict[str, Any]] = []
    raw_feature_rows: List[Dict[str, Any]] = []
    timing_rows: List[Dict[str, Any]] = []
    failed_rows: List[Dict[str, Any]] = list(pre_failed_rows)

    reporter = ProgressReporter(
        total=len(jobs),
        update_interval_sec=60.0,
        bar_width=30,
    )
    reporter.set_failed(len(failed_rows))

    if len(jobs) == 0:
        reporter.maybe_print(force=True)
    else:
        reporter.maybe_print(force=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        future_to_job = {
            ex.submit(execute_single_job, job, mode, manifest): job
            for job in jobs
        }

        printed_failures = 0
        max_failure_prints = 10

        for fut in as_completed(future_to_job):
            job = future_to_job[fut]
            try:
                payload = fut.result()
                row = payload['row']
                raw_feature_rows.append(row)
                all_run_rows.append({k: row[k] for k in RUN_TABLE_HEADER})
                timing_rows.append(payload['timing'])

                reporter.step(
                    n=1,
                    failed=len(failed_rows),
                    label=str(row.get('run_id', 'completed')),
                    force=False,
                )

            except Exception as exc:
                failed_rows.append({
                    'generator': str(job.get('generator', 'unknown')),
                    'experiment': str(job.get('experiment', 'unknown')),
                    'class_name': str(job.get('class_name', 'unknown')),
                    'instance_id': int(job.get('instance_id', -1)),
                    'error': repr(exc),
                })

                if printed_failures < max_failure_prints:
                    print(
                        '[ERROR] '
                        f"generator={job.get('generator')} | "
                        f"experiment={job.get('experiment')} | "
                        f"class={job.get('class_name')} | "
                        f"instance={job.get('instance_id')} | "
                        f"seed={job.get('seed')} | "
                        f"noise={job.get('noise_level')} | "
                        f"step={job.get('deformation_step')} | "
                        f"run_id={job.get('run_id')} | "
                        f"exc={repr(exc)}",
                        flush=True,
                    )
                    printed_failures += 1

                reporter.step(
                    n=1,
                    failed=len(failed_rows),
                    label=f"FAILED:{job.get('generator')}:{job.get('experiment')}",
                    force=False,
                )

        reporter.finish(failed=len(failed_rows), label='all-jobs-finished')

    print(
        f'[INFO] Stage 3 done in {format_hms(time.time() - t_stage_3)} | '
        f'completed rows: {len(all_run_rows)} | feature rows: {len(raw_feature_rows)} | failed: {len(failed_rows)}',
        flush=True,
    )

    print_stage(4, STAGE_TOTAL, 'Normalize features and compute metrics...')
    t_stage_4 = time.time()

    meta_fields = set(RUN_TABLE_HEADER)
    feature_names = sorted({k for r in raw_feature_rows for k in r.keys()} - meta_fields)
    norm_rows = robust_zscore(raw_feature_rows, feature_names) if raw_feature_rows else []

    summary = summarize(norm_rows, feature_names)
    separability = compute_separability(norm_rows, feature_names) if norm_rows else {
        'separability_score': 0.0,
        'within_mean': 0.0,
        'between_mean': 0.0,
        'within_by_class': {},
        'class_means': {},
    }
    retrieval, dist_matrix, retrieval_labels = compute_retrieval_metrics(norm_rows, feature_names) if norm_rows else (
        {'top1_accuracy': 0.0, 'top3_accuracy': 0.0, 'n_queries': 0},
        None,
        [],
    )
    bootstrap_stats = compute_bootstrap_ci(norm_rows, feature_names) if norm_rows else {}
    bifurcations = detect_bifurcation_events(
        norm_rows,
        feature_names,
        protocol.get('bifurcation_detection', {}),
    ) if norm_rows else []
    stage2_metrics = compute_stage2_metrics(norm_rows, feature_names, metrics_mod) if norm_rows else {}
    report = generate_research_report(
        source_mode,
        norm_rows,
        feature_names,
        summary,
        separability,
        retrieval,
        bootstrap_stats,
        bifurcations,
        stage2_metrics,
    )

    print(
        f'[INFO] Stage 4 done in {format_hms(time.time() - t_stage_4)} | '
        f'normalized rows: {len(norm_rows)} | features: {len(feature_names)} | '
        f'bifurcations: {len(bifurcations)}',
        flush=True,
    )

    print_stage(5, STAGE_TOTAL, 'Write CSV/JSON/report artifacts...')
    t_stage_5 = time.time()

    write_csv_with_header(
        Path(manifest['run_table_path']),
        RUN_TABLE_HEADER,
        [[r[h] for h in RUN_TABLE_HEADER] for r in all_run_rows]
    )
    write_csv_with_header(
        Path(manifest['timing_profile_path']),
        TIMING_HEADER,
        [[r['run_id'], r['generator'], r['experiment'], f"{r['elapsed_sec']:.6f}"] for r in timing_rows]
    )
    write_csv_with_header(
        Path(manifest['failed_runs_path']),
        FAILED_HEADER,
        [[r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['error']] for r in failed_rows]
    )
    write_feature_csv(Path(manifest['features_raw_path']), raw_feature_rows, feature_names)
    write_feature_csv(Path(manifest['features_normalized_path']), norm_rows, feature_names)

    by_class = defaultdict(list)
    by_experiment = defaultdict(list)
    for r in norm_rows:
        by_class[r['class_name']].append(r)
        by_experiment[r['experiment']].append(r)

    agg_gen_rows = []
    for gen, data in sorted(summary.get('generators', {}).items()):
        row = [gen, data.get('n_runs', 0)]
        row.extend([data.get('features_mean', {}).get(f, '') for f in feature_names])
        agg_gen_rows.append(row)
    write_csv_with_header(
        Path(manifest['aggregate_by_generator_path']),
        ['generator', 'n_runs'] + feature_names,
        agg_gen_rows
    )

    agg_class_rows = []
    for cls, cls_rows in sorted(by_class.items()):
        row = [cls, len(cls_rows)]
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r and not np.isnan(r[f])]
            row.append(float(np.mean(vals)) if vals else '')
        agg_class_rows.append(row)
    write_csv_with_header(
        Path(manifest['aggregate_by_class_path']),
        ['class_name', 'n_runs'] + feature_names,
        agg_class_rows
    )

    agg_exp_rows = []
    for exp, exp_rows in sorted(by_experiment.items()):
        row = [exp, len(exp_rows)]
        for f in feature_names:
            vals = [r[f] for r in exp_rows if f in r and not np.isnan(r[f])]
            row.append(float(np.mean(vals)) if vals else '')
        agg_exp_rows.append(row)
    write_csv_with_header(
        Path(manifest['aggregate_by_experiment_path']),
        ['experiment', 'n_runs'] + feature_names,
        agg_exp_rows
    )

    write_csv_with_header(
        Path(manifest['retrieval_accuracy_path']),
        ['n_queries', 'top1_accuracy', 'top3_accuracy'],
        [[retrieval['n_queries'], retrieval['top1_accuracy'], retrieval['top3_accuracy']]]
    )

    bif_rows = [
        [
            b['generator'],
            b['class_name'],
            b['parameter_name'],
            b['parameter_value'],
            b['gradient_norm'],
            b['zscore'],
            b['confirmed_event'],
        ]
        for b in bifurcations
    ]
    write_csv_with_header(
        Path(manifest['bifurcation_events_path']),
        ['generator', 'class_name', 'parameter_name', 'parameter_value', 'gradient_norm', 'zscore', 'confirmed_event'],
        bif_rows
    )

    if dist_matrix is not None:
        dist_rows = [[retrieval_labels[i]] + [float(v) for v in dist_matrix[i]] for i in range(dist_matrix.shape[0])]
        write_csv_with_header(
            Path(manifest['pairwise_distance_matrix_path']),
            ['class_name'] + [f'd{i}' for i in range(dist_matrix.shape[1])],
            dist_rows
        )
    else:
        write_csv_with_header(Path(manifest['pairwise_distance_matrix_path']), ['class_name'], [])

    save_json(Path(manifest['summary_json_path']), {
        'config_source': source_mode,
        'lib_dir': str(lib_dir),
        'summary': summary,
        'separability': separability,
        'retrieval': retrieval,
        'stage2_metrics': stage2_metrics,
        'n_bifurcations': len(bifurcations),
        'n_failed_runs': len(failed_rows),
        'stage2_decision': {
            'recommended_generators': sorted(summary.get('generators', {}).keys()),
            'rejected_generators': [],
            'decision_reason': 'provisional ranking from integrated backend; inspect report and failed_runs before final scientific conclusion',
        },
    })

    with Path(manifest['research_report_md_path']).open('w', encoding='utf-8') as f:
        f.write(report)

    print(f'[INFO] Stage 5 done in {format_hms(time.time() - t_stage_5)}', flush=True)

    print_stage(6, STAGE_TOTAL, 'Done.')
    print(json.dumps({
        'config_source': source_mode,
        'mode_name': ctx.get('mode_name', 'unknown'),
        'lib_dir': str(lib_dir),
        'n_jobs': len(jobs),
        'n_runs': len(all_run_rows),
        'n_feature_rows': len(raw_feature_rows),
        'n_feature_names': len(feature_names),
        'n_failed_runs': len(failed_rows),
        'workers': workers,
        'output_dir': str(OUT),
    }, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()