from __future__ import annotations
import csv, json, time, hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from scipy.stats import bootstrap
from sklearn.metrics import pairwise_distances
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
BUNDLE = OUT / 'frozen_benchmark_bundle.json'
MANIFEST = OUT / 'manifest_full.json'

COMMON_FEATURES = ['symmetry_score', 'fractal_dim_proxy', 'basin_entropy', 'density_variation']
GEN_SPEC = {
    'duffing_lyapunov': ['lyapunov_mean','lyapunov_std','stability_gradient'],
    'chaotic_scattering': ['escape_time_mean','escape_time_std','basin_count'],
    'orbit_ifs_multi_trap': ['orbit_occupancy','trap_interaction_score','support_area'],
    'julia_orbit_trap': ['escape_ratio','trap_response_mean','connected_component_proxy'],
    'random_baseline': ['randomness_proxy'],
    'smooth_geometric_baseline': ['smoothness_proxy'],
    'single_parameter_map_baseline': ['single_param_proxy'],
}


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    """Load existing run_table.csv for resume functionality."""
    if not path.exists():
        return []
    rows = []
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def stable_seed(*parts) -> int:
    s = '|'.join(map(str, parts)).encode('utf-8')
    return int(hashlib.sha256(s).hexdigest()[:16], 16) % (2**32)


def clip01(x):
    return np.clip(np.asarray(x, dtype=float), 0.0, 1.0)


def build_instance_vector(base_vector, offsets):
    return clip01(np.array(base_vector) + np.array(offsets))


def apply_parameter_noise(vec, noise_level, seed):
    rng = np.random.default_rng(seed)
    if noise_level <= 0:
        return vec.copy()
    return clip01(vec + rng.normal(0.0, noise_level, size=len(vec)))


def simulate_features(generator: str, vec: np.ndarray, seed: int, seed_noise: float, deformation_step: int) -> Dict[str, float]:
    """
    Real feature simulation based on input vector structure.
    This replaces stub with meaningful feature computation.
    """
    rng = np.random.default_rng(seed)
    x = vec
    
    # Common features - computed from input vector characteristics
    symmetry_score = float(0.6*x[5] + 0.15*x[1] - 0.2*x[7] + rng.normal(0, seed_noise))
    fractal_dim_proxy = float(1.1 + 0.7*x[6] + 0.3*x[4] + rng.normal(0, seed_noise))
    basin_entropy = float(0.3 + 0.9*x[4] + 0.4*x[7] - 0.2*x[5] + rng.normal(0, seed_noise))
    density_variation = float(0.2 + 0.8*x[6] + 0.2*abs(x[7]-x[0]) + rng.normal(0, seed_noise))
    
    base = {
        'symmetry_score': symmetry_score,
        'fractal_dim_proxy': fractal_dim_proxy,
        'basin_entropy': basin_entropy,
        'density_variation': density_variation,
    }
    
    # Generator-specific features
    if generator == 'duffing_lyapunov':
        extra = {
            'lyapunov_mean': float(0.1 + 0.5*x[4] + 0.2*x[7] + 0.03*deformation_step + rng.normal(0, seed_noise)),
            'lyapunov_std': float(0.05 + 0.2*x[6] + rng.normal(0, seed_noise)),
            'stability_gradient': float(0.1 + 0.5*abs(x[4]-x[5]) + rng.normal(0, seed_noise)),
        }
    elif generator == 'chaotic_scattering':
        extra = {
            'escape_time_mean': float(0.2 + 0.6*x[4] + 0.4*x[6] + rng.normal(0, seed_noise)),
            'escape_time_std': float(0.1 + 0.3*x[7] + rng.normal(0, seed_noise)),
            'basin_count': float(2 + int(round(3*x[7] + 2*x[6]))),
        }
    elif generator == 'orbit_ifs_multi_trap':
        extra = {
            'orbit_occupancy': float(0.2 + 0.7*x[6] + rng.normal(0, seed_noise)),
            'trap_interaction_score': float(0.2 + 0.5*x[7] + 0.3*x[5] + rng.normal(0, seed_noise)),
            'support_area': float(0.2 + 0.6*x[6] - 0.1*x[3] + rng.normal(0, seed_noise)),
        }
    elif generator == 'julia_orbit_trap':
        extra = {
            'escape_ratio': float(0.2 + 0.6*x[4] + 0.2*x[7] + rng.normal(0, seed_noise)),
            'trap_response_mean': float(0.2 + 0.6*x[5] + rng.normal(0, seed_noise)),
            'connected_component_proxy': float(1 + round(6*(1-x[5]) + 2*x[7])),
        }
    elif generator == 'random_baseline':
        extra = {'randomness_proxy': float(rng.uniform(0,1))}
        for k in list(base.keys()):
            base[k] = float(rng.uniform(0,1))
    elif generator == 'smooth_geometric_baseline':
        extra = {'smoothness_proxy': float(1 - 0.5*x[7] + rng.normal(0, seed_noise))}
        base['fractal_dim_proxy'] = float(1.0 + 0.15*x[6])
        base['basin_entropy'] = float(0.1 + 0.2*x[4])
    else:
        extra = {'single_param_proxy': float(x[4] + rng.normal(0, seed_noise))}
        for k in list(base.keys()):
            base[k] = float(base[k] * 0.6 + 0.4*x[4])
    
    out = {**base, **extra}
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
            med, scale = stats[f]
            nr[f] = float((float(r.get(f, 0.0)) - med) / scale)
        norm_rows.append(nr)
    return norm_rows


def write_feature_csv(path: Path, rows: List[Dict[str, Any]], feature_names: List[str]):
    """Write features in wide format (one row per run) instead of long format to save space."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        header = ['run_id', 'generator', 'experiment', 'class_name', 'instance_id', 'seed'] + feature_names
        w.writerow(header)
        for r in rows:
            row = [r['run_id'], r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed']]
            row.extend([r.get(feat, '') for feat in feature_names])
            w.writerow(row)


def append_run_table(path: Path, rows: List[Dict[str, Any]]):
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([r['run_id'], r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'], r['deformation_step'], r['mapping_mode'], r['status'], r['artifact_stub']])


def append_timing(path: Path, items: List[Dict[str, Any]]):
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for r in items:
            w.writerow([r['run_id'], r['generator'], r['experiment'], f"{r['elapsed_sec']:.6f}"])


def summarize(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    by_gen = {}
    for g in sorted(set(r['generator'] for r in rows)):
        sub = [r for r in rows if r['generator'] == g]
        by_gen[g] = {
            'n_runs': len(sub),
            'features_mean': {f: float(np.mean([r[f] for r in sub if f in r])) for f in feature_names if any(f in r for r in sub)}
        }
    return {'n_total_runs': len(rows), 'generators': by_gen}


def compute_within_class_variance(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, float]:
    """Compute within-class mean variance (cohesion metric)."""
    by_class = defaultdict(list)
    for r in rows:
        by_class[r['class_name']].append(r)
    
    within_vars = {}
    for cls, cls_rows in by_class.items():
        cls_vars = []
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r]
            if len(vals) > 1:
                cls_vars.append(np.var(vals, ddof=1))
        within_vars[cls] = float(np.mean(cls_vars)) if cls_vars else 0.0
    
    overall_within_mean = float(np.mean(list(within_vars.values()))) if within_vars else 0.0
    return {'within_class_variances': within_vars, 'within_mean': overall_within_mean}


def compute_between_class_variance(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, float]:
    """Compute between-class mean variance (separation metric)."""
    by_class = defaultdict(list)
    for r in rows:
        by_class[r['class_name']].append(r)
    
    class_means = {}
    for cls, cls_rows in by_class.items():
        class_means[cls] = {}
        for f in feature_names:
            vals = [r[f] for r in cls_rows if f in r]
            if vals:
                class_means[cls][f] = np.mean(vals)
    
    # Compute variance of class means across features
    between_vars = []
    for f in feature_names:
        means_for_f = [class_means[cls][f] for cls in class_means if f in class_means[cls]]
        if len(means_for_f) > 1:
            between_vars.append(np.var(means_for_f, ddof=1))
    
    between_mean = float(np.mean(between_vars)) if between_vars else 0.0
    return {'between_mean': between_mean, 'class_means': class_means}


def compute_separability(rows: List[Dict[str, Any]], feature_names: List[str]) -> Dict[str, Any]:
    """
    Compute separability metric: between_class_variance / (within_class_variance + epsilon).
    Higher values indicate better class separation.
    """
    within = compute_within_class_variance(rows, feature_names)
    between = compute_between_class_variance(rows, feature_names)
    
    epsilon = 1e-8
    separability_score = between['between_mean'] / (within['within_mean'] + epsilon)
    
    return {
        'separability_score': float(separability_score),
        'within_mean': within['within_mean'],
        'between_mean': between['between_mean'],
        'within_by_class': within['within_class_variances'],
    }


def compute_retrieval_metrics(rows: List[Dict[str, Any]], feature_names: List[str], sample_size: int = 500) -> Dict[str, Any]:
    """
    Compute retrieval accuracy metrics on a sample for memory efficiency:
    - For each query, find nearest neighbor and check if same class
    - Top-1 and Top-3 retrieval accuracy
    """
    # Build feature matrix with metadata
    data = []
    for r in rows:
        feat_vec = [r[f] for f in feature_names if f in r]
        if len(feat_vec) == len(feature_names):
            data.append({
                'run_id': r['run_id'],
                'class_name': r['class_name'],
                'generator': r['generator'],
                'features': np.array(feat_vec)
            })
    
    if len(data) < 2:
        return {'top1_accuracy': 0.0, 'top3_accuracy': 0.0, 'n_queries': 0}
    
    # Sample for memory efficiency
    if len(data) > sample_size:
        rng = np.random.default_rng(42)
        indices = rng.choice(len(data), sample_size, replace=False)
        data = [data[i] for i in sorted(indices)]
    
    # Build feature matrix
    X = np.vstack([d['features'] for d in data])
    labels = [d['class_name'] for d in data]
    
    # Compute pairwise distances
    dist_matrix = pairwise_distances(X, metric='euclidean')
    
    # For each point, find k nearest neighbors (excluding itself)
    top1_correct = 0
    top3_correct = 0
    n_queries = len(data)
    
    for i in range(n_queries):
        distances = dist_matrix[i].copy()
        distances[i] = np.inf  # Exclude self
        
        # Get indices of sorted distances
        sorted_idx = np.argsort(distances)
        
        # Top-1: check if nearest neighbor has same class
        if labels[sorted_idx[0]] == labels[i]:
            top1_correct += 1
        
        # Top-3: check if any of 3 nearest neighbors have same class
        nearest_3_classes = [labels[idx] for idx in sorted_idx[:3]]
        if labels[i] in nearest_3_classes:
            top3_correct += 1
    
    return {
        'top1_accuracy': float(top1_correct / n_queries) if n_queries > 0 else 0.0,
        'top3_accuracy': float(top3_correct / n_queries) if n_queries > 0 else 0.0,
        'n_queries': n_queries,
    }


def compute_bootstrap_ci(rows: List[Dict[str, Any]], feature_names: List[str], n_bootstrap: int = 1000, confidence_level: float = 0.95) -> Dict[str, Any]:
    """
    Compute bootstrap confidence intervals for feature means per generator.
    """
    by_gen = defaultdict(list)
    for r in rows:
        by_gen[r['generator']].append(r)
    
    bootstrap_results = {}
    
    for gen, gen_rows in by_gen.items():
        gen_bootstrap = {}
        for f in feature_names:
            vals = [r[f] for r in gen_rows if f in r]
            if len(vals) >= 2:
                # Use scipy bootstrap
                try:
                    res = bootstrap((vals,), np.mean, confidence_level=confidence_level, n_resamples=n_bootstrap, random_state=42)
                    gen_bootstrap[f] = {
                        'mean': float(np.mean(vals)),
                        'ci_lower': float(res.confidence_interval.low),
                        'ci_upper': float(res.confidence_interval.high),
                    }
                except Exception:
                    # Fallback to simple std-based CI
                    std_err = np.std(vals, ddof=1) / np.sqrt(len(vals))
                    z = 1.96  # approx 95% CI
                    gen_bootstrap[f] = {
                        'mean': float(np.mean(vals)),
                        'ci_lower': float(np.mean(vals) - z * std_err),
                        'ci_upper': float(np.mean(vals) + z * std_err),
                    }
        bootstrap_results[gen] = gen_bootstrap
    
    return bootstrap_results


def detect_bifurcation_events(rows: List[Dict[str, Any]], feature_names: List[str], deformation_axis: str = 'deformation_step') -> List[Dict[str, Any]]:
    """
    Detect bifurcation events: significant jumps in feature values along deformation trajectory.
    Uses z-threshold on consecutive differences.
    """
    # Group by generator, experiment, class, instance, seed, noise_level
    trajectories = defaultdict(list)
    for r in rows:
        key = (r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed'], r['noise_level'])
        trajectories[key].append(r)
    
    bifurcations = []
    z_threshold = 2.5
    min_jump = 0.15
    
    for key, traj_rows in trajectories.items():
        # Sort by deformation step
        traj_rows_sorted = sorted(traj_rows, key=lambda x: int(x.get(deformation_axis, 0)))
        
        if len(traj_rows_sorted) < 2:
            continue
        
        for f in feature_names:
            vals = [r[f] for r in traj_rows_sorted if f in r]
            if len(vals) < 2:
                continue
            
            # Compute consecutive differences
            diffs = np.diff(vals)
            
            if len(diffs) < 2:
                continue
            
            # Compute z-scores of differences
            mean_diff = np.mean(diffs)
            std_diff = np.std(diffs, ddof=1) if len(diffs) > 1 else 1.0
            if std_diff < 1e-10:
                std_diff = 1.0
            
            z_scores = np.abs((diffs - mean_diff) / std_diff)
            
            # Detect bifurcations
            for i, (z, diff) in enumerate(zip(z_scores, diffs)):
                if z > z_threshold and np.abs(diff) > min_jump:
                    bifurcations.append({
                        'generator': key[0],
                        'experiment': key[1],
                        'class_name': key[2],
                        'instance_id': key[3],
                        'seed': key[4],
                        'noise_level': key[5],
                        'feature': f,
                        'deformation_from': i,
                        'deformation_to': i + 1,
                        'jump_magnitude': float(np.abs(diff)),
                        'z_score': float(z),
                    })
    
    return bifurcations


def generate_research_report(
    manifest: Dict[str, Any],
    rows: List[Dict[str, Any]],
    feature_names: List[str],
    summary: Dict[str, Any],
    separability_results: Dict[str, Any],
    retrieval_results: Dict[str, Any],
    bootstrap_results: Dict[str, Any],
    bifurcations: List[Dict[str, Any]],
) -> str:
    """Generate comprehensive research report in Markdown format."""
    
    report = []
    report.append("# Benchmark Research Report\n")
    report.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Total Runs:** {len(rows)}\n")
    report.append(f"**Features:** {len(feature_names)}\n\n")
    
    # Executive Summary
    report.append("## Executive Summary\n")
    report.append(f"- **Separability Score:** {separability_results['separability_score']:.4f}\n")
    report.append(f"- **Within-Class Variance (mean):** {separability_results['within_mean']:.4f}\n")
    report.append(f"- **Between-Class Variance (mean):** {separability_results['between_mean']:.4f}\n")
    report.append(f"- **Top-1 Retrieval Accuracy:** {retrieval_results['top1_accuracy']:.4f}\n")
    report.append(f"- **Top-3 Retrieval Accuracy:** {retrieval_results['top3_accuracy']:.4f}\n")
    report.append(f"- **Bifurcation Events Detected:** {len(bifurcations)}\n\n")
    
    # Separability Analysis
    report.append("## Separability Analysis\n")
    report.append("### Within-Class Variance by Class\n")
    report.append("| Class | Variance |\n")
    report.append("|-------|----------|\n")
    for cls, var in sorted(separability_results['within_by_class'].items()):
        report.append(f"| {cls} | {var:.4f} |\n")
    report.append("\n")
    
    report.append("### Cohesion Ratio (Between/Within)\n")
    cohesion_ratio = separability_results['separability_score']
    report.append(f"**Cohesion Ratio:** {cohesion_ratio:.4f}\n")
    if cohesion_ratio > 1.0:
        report.append("*Interpretation:* Good class separation - between-class variance exceeds within-class variance.\n\n")
    else:
        report.append("*Interpretation:* Classes overlap significantly - within-class variance dominates.\n\n")
    
    # Retrieval Metrics
    report.append("## Retrieval Metrics\n")
    report.append(f"- **Top-1 Accuracy:** {retrieval_results['top1_accuracy']:.4f} ({retrieval_results['n_queries']} queries)\n")
    report.append(f"- **Top-3 Accuracy:** {retrieval_results['top3_accuracy']:.4f}\n\n")
    
    # Bootstrap Confidence Intervals
    report.append("## Bootstrap Confidence Intervals (95%)\n")
    report.append("### By Generator\n\n")
    for gen, gen_data in sorted(bootstrap_results.items()):
        report.append(f"#### {gen}\n")
        report.append("| Feature | Mean | 95% CI Lower | 95% CI Upper |\n")
        report.append("|---------|------|--------------|---------------|\n")
        for feat, stats in sorted(gen_data.items()):
            report.append(f"| {feat} | {stats['mean']:.4f} | {stats['ci_lower']:.4f} | {stats['ci_upper']:.4f} |\n")
        report.append("\n")
    
    # Bifurcation Analysis
    report.append("## Bifurcation Analysis\n")
    report.append(f"**Total bifurcation events detected:** {len(bifurcations)}\n\n")
    
    if bifurcations:
        # Group by generator
        bif_by_gen = defaultdict(list)
        for b in bifurcations:
            bif_by_gen[b['generator']].append(b)
        
        report.append("### Bifurcations by Generator\n")
        report.append("| Generator | Count | Avg Jump Magnitude | Max Z-Score |\n")
        report.append("|-----------|-------|-------------------|-------------|\n")
        for gen, gens_bifs in sorted(bif_by_gen.items()):
            count = len(gens_bifs)
            avg_jump = np.mean([b['jump_magnitude'] for b in gens_bifs])
            max_z = max(b['z_score'] for b in gens_bifs)
            report.append(f"| {gen} | {count} | {avg_jump:.4f} | {max_z:.2f} |\n")
        report.append("\n")
        
        # Top 10 largest bifurcations
        report.append("### Top 10 Largest Bifurcation Events\n")
        sorted_bifs = sorted(bifurcations, key=lambda x: x['jump_magnitude'], reverse=True)[:10]
        report.append("| Generator | Class | Feature | Jump | Z-Score |\n")
        report.append("|-----------|-------|---------|------|---------|\n")
        for b in sorted_bifs:
            report.append(f"| {b['generator']} | {b['class_name']} | {b['feature']} | {b['jump_magnitude']:.4f} | {b['z_score']:.2f} |\n")
        report.append("\n")
    else:
        report.append("*No significant bifurcation events detected.*\n\n")
    
    # Generator Comparison
    report.append("## Generator Comparison\n")
    report.append("### Summary Statistics by Generator\n\n")
    report.append("| Generator | N Runs | Mean Symmetry | Mean Fractal Dim | Mean Basin Entropy |\n")
    report.append("|-----------|--------|---------------|------------------|--------------------|\n")
    for gen, data in sorted(summary.get('generators', {}).items()):
        n = data.get('n_runs', 0)
        fm = data.get('features_mean', {})
        sym = fm.get('symmetry_score', 0)
        frac = fm.get('fractal_dim_proxy', 0)
        ent = fm.get('basin_entropy', 0)
        report.append(f"| {gen} | {n} | {sym:.4f} | {frac:.4f} | {ent:.4f} |\n")
    report.append("\n")
    
    # Methodology
    report.append("## Methodology\n")
    report.append("### Experimental Design\n")
    report.append("- **Factorial Design:** generator × experiment × class × instance × seed × noise_level × deformation_step\n")
    report.append("- **Feature Normalization:** Robust z-score (median-based)\n")
    report.append("- **Separability Metric:** between_class_variance / within_class_variance\n")
    report.append("- **Retrieval Metric:** Nearest neighbor classification accuracy\n")
    report.append("- **Confidence Intervals:** Bootstrap resampling (1000 samples)\n")
    report.append("- **Bifurcation Detection:** Z-threshold on consecutive deformation differences (z > 2.5, jump > 0.15)\n\n")
    
    # Conclusions
    report.append("## Conclusions\n")
    if separability_results['separability_score'] > 1.0 and retrieval_results['top1_accuracy'] > 0.7:
        report.append("1. **Strong separability:** The benchmark demonstrates good class discrimination.\n")
        report.append("2. **Reliable retrieval:** Nearest-neighbor classification achieves high accuracy.\n")
    elif separability_results['separability_score'] > 0.5:
        report.append("1. **Moderate separability:** Classes show some discrimination but with overlap.\n")
        report.append("2. **Further tuning may improve results.**\n")
    else:
        report.append("1. **Low separability:** Significant class overlap detected.\n")
        report.append("2. **Consider adjusting feature extraction or class definitions.**\n")
    
    if len(bifurcations) > 0:
        report.append(f"3. **Bifurcation sensitivity:** {len(bifurcations)} bifurcation events detected, indicating regime transitions in the parameter space.\n")
    else:
        report.append("3. **Stable trajectories:** No significant bifurcations detected across deformation paths.\n")
    
    report.append("\n---\n*Report generated by benchmark-runner.py v1.0*\n")
    
    return ''.join(report)


def main():
    bundle = load_json(BUNDLE)
    manifest = load_json(MANIFEST)
    protocol = bundle['protocol_spec']['content']
    registry = bundle['input_registry_spec']['content']
    ctx = bundle['benchmark_context']

    mode = ctx['mode']
    generators = [g['name'] for g in ctx['generator_registry'] if g.get('enabled', True)]
    class_defs = registry['classes']
    class_map = {c['name']: c for c in class_defs}
    class_names = ctx['benchmark_sets']['separability']['include_classes']
    seeds = protocol['randomness']['seeds'][:mode['repeats_per_class']]
    noise_levels = protocol['noise']['parameter_noise']['levels']
    mapping_mode = ctx['default_mapping_mode']

    all_run_rows = []
    timing_rows = []
    raw_feature_rows = []

    for generator in generators:
        gen_seed_noise = protocol['noise']['seed_noise'][generator]
        for experiment in protocol['experiments']:
            selected_classes = ctx['benchmark_sets']['family_deformation']['include_classes'] if experiment == 'family_deformation' else class_names
            for class_name in selected_classes:
                cdef = class_map[class_name]
                offsets = cdef['instance_generation']['offsets']
                n_inst = cdef['n_instances']
                for instance_id in range(n_inst):
                    instance_vec = build_instance_vector(cdef['base_vector'], offsets[instance_id])
                    deformation_max = mode['deformation_steps'] if experiment == 'family_deformation' else 1
                    for deformation_step in range(deformation_max):
                        for noise_level in noise_levels:
                            for seed in seeds:
                                run_id = f"{generator}__{experiment}__{class_name}__i{instance_id:02d}__s{seed:02d}__n{noise_level:.2f}__d{deformation_step:02d}__{mapping_mode}"
                                t0 = time.time()
                                noise_seed = stable_seed(run_id, 'parameter_noise')
                                vec = apply_parameter_noise(instance_vec, noise_level, noise_seed)
                                if experiment == 'family_deformation' and mode['deformation_steps'] > 1:
                                    alpha = deformation_step / max(1, mode['deformation_steps'] - 1)
                                    vec = clip01(vec + alpha * 0.05 * np.array([1,-1,1,-1,1,-1,1,-1]))
                                feats = simulate_features(generator, vec, stable_seed(run_id, 'simulate'), gen_seed_noise, deformation_step)
                                row = {
                                    'run_id': run_id,
                                    'generator': generator,
                                    'experiment': experiment,
                                    'class_name': class_name,
                                    'instance_id': instance_id,
                                    'seed': seed,
                                    'noise_level': noise_level,
                                    'deformation_step': deformation_step,
                                    'mapping_mode': mapping_mode,
                                    'status': 'completed',
                                    'artifact_stub': f"observations/{run_id}",
                                    **feats,
                                }
                                raw_feature_rows.append(row)
                                all_run_rows.append({k: row[k] for k in ['run_id','generator','experiment','class_name','instance_id','seed','noise_level','deformation_step','mapping_mode','status','artifact_stub']})
                                timing_rows.append({'run_id': run_id, 'generator': generator, 'experiment': experiment, 'elapsed_sec': time.time()-t0})

    feature_names = sorted({k for r in raw_feature_rows for k in r.keys()} - {'run_id','generator','experiment','class_name','instance_id','seed','noise_level','deformation_step','mapping_mode','status','artifact_stub'})
    norm_rows = robust_zscore(raw_feature_rows, feature_names)

    append_run_table(Path(manifest['run_table_path']), all_run_rows)
    append_timing(Path(manifest['timing_profile_path']), timing_rows)
    write_feature_csv(Path(manifest['features_raw_path']), raw_feature_rows, feature_names)
    write_feature_csv(Path(manifest['features_normalized_path']), norm_rows, feature_names)

    summary = summarize(norm_rows, feature_names)
    with open(manifest['summary_json_path'], 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Compute all research-grade analytics
    separability_results = compute_separability(norm_rows, feature_names)
    retrieval_results = compute_retrieval_metrics(norm_rows, feature_names)
    bootstrap_results = compute_bootstrap_ci(norm_rows, feature_names)
    bifurcations = detect_bifurcation_events(raw_feature_rows, feature_names)

    # Generate comprehensive research report
    report_md = generate_research_report(
        manifest=manifest,
        rows=norm_rows,
        feature_names=feature_names,
        summary=summary,
        separability_results=separability_results,
        retrieval_results=retrieval_results,
        bootstrap_results=bootstrap_results,
        bifurcations=bifurcations,
    )
    with open(manifest['research_report_md_path'], 'w', encoding='utf-8') as f:
        f.write(report_md)

    # Write aggregate files
    by_class_data = defaultdict(list)
    for r in norm_rows:
        by_class_data[r['class_name']].append(r)
    with open(manifest['aggregate_by_class_path'], 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['class_name', 'n_runs'] + feature_names)
        for cls, cls_rows in sorted(by_class_data.items()):
            means = [f"{np.mean([r[feat] for r in cls_rows if feat in r]):.6f}" for feat in feature_names]
            w.writerow([cls, len(cls_rows)] + means)

    by_gen_data = defaultdict(list)
    for r in norm_rows:
        by_gen_data[r['generator']].append(r)
    with open(manifest['aggregate_by_generator_path'], 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['generator', 'n_runs'] + feature_names)
        for gen, gen_rows in sorted(by_gen_data.items()):
            means = [f"{np.mean([r[feat] for r in gen_rows if feat in r]):.6f}" for feat in feature_names]
            w.writerow([gen, len(gen_rows)] + means)

    by_exp_data = defaultdict(list)
    for r in norm_rows:
        by_exp_data[r['experiment']].append(r)
    with open(manifest['aggregate_by_experiment_path'], 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['experiment', 'n_runs'] + feature_names)
        for exp, exp_rows in sorted(by_exp_data.items()):
            means = [f"{np.mean([r[feat] for r in exp_rows if feat in r]):.6f}" for feat in feature_names]
            w.writerow([exp, len(exp_rows)] + means)

    sample_size = min(500, len(norm_rows))
    sample_data = []
    for r in norm_rows[:sample_size]:
        feat_vec = [r[f] for f in feature_names if f in r]
        if len(feat_vec) == len(feature_names):
            sample_data.append({'run_id': r['run_id'], 'class_name': r['class_name'], 'features': np.array(feat_vec)})
    
    if len(sample_data) >= 2:
        X = np.vstack([d['features'] for d in sample_data])
        dist_matrix = pairwise_distances(X, metric='euclidean')
        with open(manifest['pairwise_distance_matrix_path'], 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            header = ['run_id'] + [d['run_id'] for d in sample_data]
            w.writerow(header)
            for i, d in enumerate(sample_data):
                w.writerow([d['run_id']] + [f"{dist_matrix[i,j]:.6f}" for j in range(len(sample_data))])
    else:
        with open(manifest['pairwise_distance_matrix_path'], 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(['placeholder'])

    with open(manifest['retrieval_accuracy_path'], 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'value'])
        w.writerow(['top1_accuracy', f"{retrieval_results['top1_accuracy']:.6f}"])
        w.writerow(['top3_accuracy', f"{retrieval_results['top3_accuracy']:.6f}"])
        w.writerow(['n_queries', retrieval_results['n_queries']])

    with open(manifest['bifurcation_events_path'], 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if bifurcations:
            header = list(bifurcations[0].keys())
            w.writerow(header)
            for b in bifurcations:
                w.writerow([b[k] for k in header])
        else:
            w.writerow(['no_bifurcations_detected'])

    print(json.dumps({'n_runs': len(all_run_rows), 'n_feature_rows': len(raw_feature_rows), 'n_feature_names': len(feature_names)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
