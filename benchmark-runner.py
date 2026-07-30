from __future__ import annotations
import csv, json, time, hashlib
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

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
    rng = np.random.default_rng(seed)
    x = vec
    base = {
        'symmetry_score': float(0.6*x[5] + 0.15*x[1] - 0.2*x[7] + rng.normal(0, seed_noise)),
        'fractal_dim_proxy': float(1.1 + 0.7*x[6] + 0.3*x[4] + rng.normal(0, seed_noise)),
        'basin_entropy': float(0.3 + 0.9*x[4] + 0.4*x[7] - 0.2*x[5] + rng.normal(0, seed_noise)),
        'density_variation': float(0.2 + 0.8*x[6] + 0.2*abs(x[7]-x[0]) + rng.normal(0, seed_noise)),
    }
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
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for r in rows:
            for feat in feature_names:
                if feat in r:
                    w.writerow([r['run_id'], r['generator'], r['experiment'], r['class_name'], r['instance_id'], r['seed'], feat, r[feat]])


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

    with open(manifest['research_report_md_path'], 'w', encoding='utf-8') as f:
        f.write('# Benchmark runner report\n\n')
        f.write('This is an auto-generated placeholder report from the factorized benchmark orchestrator.\n')

    for extra in [manifest['aggregate_by_class_path'], manifest['aggregate_by_generator_path'], manifest['aggregate_by_experiment_path'], manifest['pairwise_distance_matrix_path'], manifest['retrieval_accuracy_path'], manifest['bifurcation_events_path']]:
        with open(extra, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(['placeholder'])

    print(json.dumps({'n_runs': len(all_run_rows), 'n_feature_rows': len(raw_feature_rows), 'n_feature_names': len(feature_names)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
