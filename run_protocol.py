from __future__ import annotations
import os, json, csv, shutil, hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List
import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
PROTOCOL_PATH = ROOT / 'configs' / 'experiment_protocol.yaml'
REGISTRY_PATH = ROOT / 'configs' / 'input_registry.yaml'

@dataclass
class RunMode:
    resolution_default: tuple
    resolution_duffing: tuple
    resolution_scattering: tuple
    repeats_per_class: int
    sensitivity_steps: int
    deformation_steps: int
    duffing_steps: int
    ifs_points: int
    skip_completed: bool
    resume: bool


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_mode(protocol: Dict[str, Any], mode_name: str) -> RunMode:
    m = protocol['modes'][mode_name]
    return RunMode(
        resolution_default=tuple(m['resolution_default']),
        resolution_duffing=tuple(m['resolution_duffing']),
        resolution_scattering=tuple(m['resolution_scattering']),
        repeats_per_class=int(m['repeats_per_class']),
        sensitivity_steps=int(m['sensitivity_steps']),
        deformation_steps=int(m['deformation_steps']),
        duffing_steps=int(m['duffing_steps']),
        ifs_points=int(m['ifs_points']),
        skip_completed=bool(m['skip_completed']),
        resume=bool(m['resume']),
    )


def build_generator_registry(protocol: Dict[str, Any], registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    if 'generators' in registry and 'registry' in registry['generators']:
        return registry['generators']['registry']
    nonlinear = protocol.get('generators', {}).get('nonlinear', [])
    baselines = protocol.get('generators', {}).get('baselines', [])
    items = []
    for name in nonlinear:
        items.append({'name': name, 'family': 'nonlinear', 'baseline': False, 'enabled': True})
    for name in baselines:
        items.append({'name': name, 'family': 'baseline', 'baseline': True, 'enabled': True})
    return items


def freeze_specs(mode_name: str = 'research-final') -> Dict[str, Any]:
    protocol = load_yaml(PROTOCOL_PATH)
    registry = load_yaml(REGISTRY_PATH)
    mode = get_mode(protocol, mode_name)
    generator_registry = build_generator_registry(protocol, registry)

    frozen = {
        'protocol_spec': {
            'source_path': str(PROTOCOL_PATH),
            'sha256': sha256_file(PROTOCOL_PATH),
            'content': protocol,
        },
        'input_registry_spec': {
            'source_path': str(REGISTRY_PATH),
            'sha256': sha256_file(REGISTRY_PATH),
            'content': registry,
        },
        'benchmark_context': {
            'mode_name': mode_name,
            'mode': asdict(mode),
            'default_mapping_mode': protocol['mapping']['default_mapping_mode'],
            'allowed_mapping_modes': protocol['mapping']['allowed_mapping_modes'],
            'generator_registry': generator_registry,
            'class_names': [c['name'] for c in registry['classes']],
            'benchmark_sets': registry['benchmark_sets'],
            'feature_normalization': protocol['feature_processing']['feature_normalization'],
        }
    }
    return frozen


def write_json(obj: Dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def write_csv_header(path: Path, header: List[str]) -> Path:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
    return path


def prepare_output_layout() -> Dict[str, Path]:
    dirs = {
        'root': OUT,
        'runs': OUT / 'runs',
        'observations': OUT / 'observations',
        'features': OUT / 'features',
        'reports': OUT / 'reports',
        'aggregates': OUT / 'aggregates',
        'logs': OUT / 'logs',
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def build_manifest(frozen: Dict[str, Any], dirs: Dict[str, Path]) -> Dict[str, Any]:
    required_files = frozen['protocol_spec']['content']['outputs']['required_files']
    optional_files = frozen['protocol_spec']['content']['outputs']['optional_files']
    manifest = {
        'manifest_version': '1.0',
        'benchmark_runner_target': 'benchmark-runner.py',
        'frozen_protocol_path': str(dirs['root'] / 'frozen_protocol_spec.json'),
        'frozen_input_registry_path': str(dirs['root'] / 'frozen_input_registry_spec.json'),
        'frozen_bundle_path': str(dirs['root'] / 'frozen_benchmark_bundle.json'),
        'run_table_path': str(dirs['runs'] / 'run_table.csv'),
        'failed_runs_path': str(dirs['logs'] / 'failed_runs.csv'),
        'timing_profile_path': str(dirs['logs'] / 'timing_profile.csv'),
        'features_raw_path': str(dirs['features'] / 'features_raw.csv'),
        'features_normalized_path': str(dirs['features'] / 'features_normalized.csv'),
        'pairwise_distance_matrix_path': str(dirs['aggregates'] / 'pairwise_distance_matrix.csv'),
        'bifurcation_events_path': str(dirs['aggregates'] / 'bifurcation_events.csv'),
        'aggregate_by_class_path': str(dirs['aggregates'] / 'aggregate_by_class.csv'),
        'aggregate_by_generator_path': str(dirs['aggregates'] / 'aggregate_by_generator.csv'),
        'aggregate_by_experiment_path': str(dirs['aggregates'] / 'aggregate_by_experiment.csv'),
        'retrieval_accuracy_path': str(dirs['aggregates'] / 'retrieval_accuracy.csv'),
        'summary_json_path': str(dirs['reports'] / 'summary.json'),
        'research_report_md_path': str(dirs['reports'] / 'research_report.md'),
        'required_files': required_files,
        'optional_files': optional_files,
    }
    return manifest


def prepare_run(mode_name: str = 'research-final') -> Dict[str, Any]:
    dirs = prepare_output_layout()
    frozen = freeze_specs(mode_name)

    protocol_only = frozen['protocol_spec']
    registry_only = frozen['input_registry_spec']

    write_json(protocol_only, dirs['root'] / 'frozen_protocol_spec.json')
    write_json(registry_only, dirs['root'] / 'frozen_input_registry_spec.json')
    write_json(frozen, dirs['root'] / 'frozen_benchmark_bundle.json')

    shutil.copy2(PROTOCOL_PATH, dirs['root'] / 'experiment_protocol_copy.yaml')
    shutil.copy2(REGISTRY_PATH, dirs['root'] / 'input_registry_copy.yaml')

    write_csv_header(dirs['runs'] / 'run_table.csv', [
        'run_id','generator','experiment','class_name','instance_id','seed','noise_level','deformation_step','mapping_mode','status','artifact_stub'
    ])
    write_csv_header(dirs['logs'] / 'failed_runs.csv', [
        'run_id','generator','experiment','class_name','instance_id','seed','error_type','error_message'
    ])
    write_csv_header(dirs['logs'] / 'timing_profile.csv', [
        'run_id','generator','experiment','elapsed_sec'
    ])
    write_csv_header(dirs['features'] / 'features_raw.csv', [
        'run_id','generator','experiment','class_name','instance_id','seed','feature_name','value'
    ])
    write_csv_header(dirs['features'] / 'features_normalized.csv', [
        'run_id','generator','experiment','class_name','instance_id','seed','feature_name','value'
    ])

    manifest = build_manifest(frozen, dirs)
    write_json(manifest, dirs['root'] / 'manifest_full.json')
    return manifest


if __name__ == '__main__':
    manifest = prepare_run('research-final')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
