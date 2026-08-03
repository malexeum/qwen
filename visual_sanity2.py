import sys
import math
import csv
import json
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import importlib.util
import importlib.machinery

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Backend import resolution
# ---------------------------------------------------------------------------
LIB_SEARCH_PATHS = [
    ROOT / "rdcoder",
    ROOT / "lib",
    ROOT,
]

lib_dir = None
for path in LIB_SEARCH_PATHS:
    if (path / "core.py").exists() and (path / "generators.py").exists():
        lib_dir = path
        break

if lib_dir is None:
    print("Ошибка: не могу найти core.py и generators.py. Проверь пути!")
    sys.exit(1)

package_name = "fractal_backend_lib"
if package_name not in sys.modules:
    pkg = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec(package_name, loader=None)
    )
    pkg.__path__ = [str(lib_dir)]
    sys.modules[package_name] = pkg


def load_mod(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = load_mod(f"{package_name}.core", lib_dir / "core.py")
generators = load_mod(f"{package_name}.generators", lib_dir / "generators.py")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INPUT_CLASS = "harmonic_symmetric"

BASE_VEC = np.array([0.8, 0.6, 0.5, 0.7, 0.1, 0.9, 0.8, 0.3], dtype=float)

SEEDS = [42, 101, 999]

STEPS_MAP = {
    "julia_orbit_trap": [1, 3, 5, 7],
    "orbit_ifs_multi_trap": [1, 5, 9, 12, 16, 20],
    "duffing_lyapunov": [1, 5, 9, 12, 15],
}

GENERATOR_AMPLITUDES = {
    "julia_orbit_trap": 0.25,
    "orbit_ifs_multi_trap": 0.25,
    "duffing_lyapunov": 0.80,
}

THRESHOLDS = {
    "julia_orbit_trap": {
        "preserved": 0.05,
        "transformed": 0.35,
        "broken": 0.80,
    },
    "orbit_ifs_multi_trap": {
        "preserved": 0.20,
        "transformed": 0.70,
        "broken": 1.50,
    },
    "duffing_lyapunov": {
        "preserved": 0.15,
        "transformed": 0.50,
        "broken": 0.90,
    },
}

OBSERVER_VERSION = "3.1.0"
FEATURE_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rule_based_theta(vec, dim_out=6) -> np.ndarray:
    chunks = np.array_split(vec, dim_out)
    theta = []
    for i, chunk in enumerate(chunks):
        val = np.mean(chunk) if len(chunk) else 0.0
        theta.append(np.tanh((1.5 * val - 0.5) + 0.1 * math.sin(i + 1)))
    return np.array(theta, dtype=float)


def get_deformed_vec(base_vec, step, generator, max_steps):
    if step <= 1:
        return base_vec.copy()

    alpha = (step - 1) / max(1, max_steps - 1)
    direction = np.array([1, -1, 1, -1, 1, -1, 1, -1], dtype=float)
    amp = GENERATOR_AMPLITUDES.get(generator, 0.25)

    return np.clip(base_vec + alpha * amp * direction, 0.0, 1.0)


def vector_to_harmony(vec):
    spectral = np.array([vec[0], 0.5 * (vec[0] + vec[7]), vec[3], vec[6]])
    ratios = np.array([vec[1], 0.5 * (vec[1] + vec[2]), vec[2]])

    return core.Harmony(
        spectral_profile=spectral,
        freq_ratios=ratios,
        rhythmic_period=max(1e-3, vec[2]),
        repetition_coeff=vec[6],
        tension=vec[4],
        symmetry=2.0 * vec[5] - 1.0,
        density=vec[3],
        contrast=vec[7],
    )


def make_state(generator, theta, seed):
    if generator == "duffing_lyapunov":
        return core.SimState(
            generator_name=generator,
            theta=theta,
            resolution=(128, 128),
            domain=(-1.0, 1.0, -1.0, 1.0),
            max_iter=400,
            escape_radius=4.0,
            trap_kind="point",
            seed=seed,
            stochastic_scale=0.0,
            extra={"n_steps": 400, "n_points": 20000},
        )

    if generator == "orbit_ifs_multi_trap":
        return core.SimState(
            generator_name=generator,
            theta=theta,
            resolution=(128, 128),
            domain=(-2.0, 2.0, -2.0, 2.0),
            max_iter=50000,
            escape_radius=4.0,
            trap_kind="point",
            seed=seed,
            stochastic_scale=0.0,
            extra={"n_steps": 400, "n_points": 20000},
        )

    return core.SimState(
        generator_name=generator,
        theta=theta,
        resolution=(128, 128),
        domain=(-2.0, 2.0, -2.0, 2.0),
        max_iter=400,
        escape_radius=4.0,
        trap_kind="point",
        seed=seed,
        stochastic_scale=0.0,
        extra={"n_steps": 400, "n_points": 20000},
    )


def run_generator(generator, state):
    if generator == "julia_orbit_trap":
        return generators.julia_orbit_trap(state)
    if generator == "orbit_ifs_multi_trap":
        return generators.orbit_ifs_multi_trap(state)
    if generator == "duffing_lyapunov":
        return generators.duffing_lyapunov_map(state)
    raise ValueError(f"Неизвестный генератор: {generator}")


def compute_relative_shift(base_result, current_result):
    base_density = np.asarray(base_result.visit_density, dtype=float)
    cur_density = np.asarray(current_result.visit_density, dtype=float)
    diff = np.abs(base_density - cur_density).mean()
    base_mean = np.mean(base_density)
    return float(diff / (base_mean + 1e-5))


def classify_preview(base_result, current_result, step, generator):
    if step == 1:
        return {
            "preview_label": "baseline",
            "approx_morphology_score": 0.0,
            "identity_confidence": 1.0,
            "threshold_profile_used": "baseline_thresholds",
        }

    relative_shift = compute_relative_shift(base_result, current_result)
    thr = THRESHOLDS.get(generator, THRESHOLDS["julia_orbit_trap"])

    if relative_shift < thr["preserved"]:
        label = "preserved-like"
        confidence = 1.0 - (relative_shift / max(thr["preserved"], 1e-8))
    elif relative_shift < thr["transformed"]:
        label = "transformed-like"
        denom = max(thr["transformed"] - thr["preserved"], 1e-8)
        confidence = 1.0 - ((relative_shift - thr["preserved"]) / denom)
    else:
        label = "broken-like"
        confidence = min(
            1.0,
            (relative_shift - thr["transformed"]) / max(thr["broken"], 1e-8),
        )

    if (
        generator == "orbit_ifs_multi_trap"
        and label == "broken-like"
        and relative_shift < thr["broken"]
    ):
        label = "weakly-transformed"

    return {
        "preview_label": label,
        "approx_morphology_score": round(relative_shift, 4),
        "identity_confidence": round(float(confidence), 4),
        "threshold_profile_used": f"{generator}_thresholds",
    }


def save_image(result, out_filepath, title):
    plt.figure(figsize=(5, 5))
    plt.imshow(result.orbit_map, cmap="magma", origin="lower")
    plt.title(title)
    plt.axis("off")
    plt.savefig(out_filepath, dpi=100, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    out_dir = ROOT / "sanity_check_outputs"
    out_dir.mkdir(exist_ok=True)

    images_dir = out_dir / "images"
    images_dir.mkdir(exist_ok=True)

    print("Запускаем Reference Run 0 (Adaptive Sanity Check)...")

    manifest_rows = []
    total_runs = 0

    summary_data = {
        "mode": "sanity_check_adaptive",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_class": INPUT_CLASS,
        "seeds": SEEDS,
        "steps_map": STEPS_MAP,
        "thresholds_used": THRESHOLDS,
        "results_by_label": {
            "baseline": 0,
            "preserved-like": 0,
            "transformed-like": 0,
            "broken-like": 0,
            "weakly-transformed": 0,
        },
        "generator_notes": {
            "julia_orbit_trap": (
                "Узкий corridor деформации; ранний переход к broken-like "
                "означает высокую хрупкость комплексной структуры."
            ),
            "orbit_ifs_multi_trap": (
                "Ожидается долгое сохранение формы с ростом плотности; "
                "weakly-transformed важен как признак насыщения без распада."
            ),
            "duffing_lyapunov": (
                "Ожидается плавный режим на малых шагах и переход к broken-like "
                "вблизи границы бифуркации."
            ),
        },
    }

    transformed_like_runs = []
    broken_like_runs = []
    generators_requiring_wider_window = []

    for generator, steps in STEPS_MAP.items():
        print(f"\nОбработка: {generator} (шаги: {steps})")

        max_steps = max(steps)

        saw_broken = False

        for seed in SEEDS:
            base_result = None

            for step in steps:
                total_runs += 1
                run_id = f"{generator}_seed{seed}_step{step:02d}"
                out_filename = f"{run_id}.png"
                out_filepath = images_dir / out_filename

                try:
                    vec = get_deformed_vec(BASE_VEC, step, generator, max_steps=max_steps)
                    harmony = vector_to_harmony(vec)
                    theta = rule_based_theta(vec, dim_out=6)
                    state = make_state(generator, theta, seed)
                    result = run_generator(generator, state)

                    if step == 1:
                        base_result = result

                    preview = classify_preview(base_result, result, step, generator)
                    label = preview["preview_label"]

                    if label == "broken-like":
                        saw_broken = True
                        broken_like_runs.append(run_id)
                    elif label == "transformed-like":
                        transformed_like_runs.append(run_id)

                    if label in summary_data["results_by_label"]:
                        summary_data["results_by_label"][label] += 1

                    save_image(result, out_filepath, f"{generator} | Step {step}")
                    status = "success"

                except Exception as exc:
                    preview = {
                        "preview_label": "error",
                        "approx_morphology_score": 0.0,
                        "identity_confidence": 0.0,
                        "threshold_profile_used": "none",
                    }
                    label = "error"
                    status = f"failed: {repr(exc)}"

                manifest_rows.append({
                    "run_id": run_id,
                    "generator": generator,
                    "input_class": INPUT_CLASS,
                    "seed": seed,
                    "deformation_step": step,
                    "output_file": f"images/{out_filename}",
                    "preview_label": preview["preview_label"],
                    "approx_morphology_score": preview["approx_morphology_score"],
                    "identity_confidence": preview["identity_confidence"],
                    "threshold_profile_used": preview["threshold_profile_used"],
                    "status": status,
                    "observer_version": OBSERVER_VERSION,
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                })

                print(
                    f"  [+] {run_id} -> {preview['preview_label']} "
                    f"(score: {preview['approx_morphology_score']})"
                )

        if not saw_broken:
            generators_requiring_wider_window.append(generator)

    summary_data["total_runs"] = total_runs
    summary_data["transformed_like_runs"] = transformed_like_runs
    summary_data["broken_like_runs"] = broken_like_runs
    summary_data["generators_requiring_wider_window"] = generators_requiring_wider_window
    summary_data["reference_run_name"] = "Reference Run 0"

    csv_path = out_dir / "sanity_check_manifest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)

    json_path = out_dir / "sanity_check_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"\nГотово! Результаты Reference Run 0 сохранены в: {out_dir}")
    print(f"Манифест: {csv_path.name}")
    print(f"Сводка: {json_path.name}")


if __name__ == "__main__":
    main()