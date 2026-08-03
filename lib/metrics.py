import numpy as np
from scipy.spatial.distance import cdist


def reproducibility_score(feature_matrix: np.ndarray, min_abs_mean: float = 0.05) -> dict:
    """
    Робастный коэффициент вариации: признаки с |mean| ниже min_abs_mean исключаются
    из усреднения CV (деление на почти-ноль даёт нефизичный взрыв CV, например для
    признаков типа symmetry_score, которые по построению центрированы около нуля).
    """
    mean = feature_matrix.mean(axis=0)
    std = feature_matrix.std(axis=0)
    cv_raw = std / (np.abs(mean) + 1e-9)
    stable_mask = np.abs(mean) >= min_abs_mean
    cv_stable = cv_raw[stable_mask] if stable_mask.any() else cv_raw
    return {
        "mean_feature": mean,
        "std_feature": std,
        "cv_raw": cv_raw,
        "n_excluded_near_zero": int((~stable_mask).sum()),
        "mean_cv": float(np.mean(np.abs(cv_stable))),
        "max_cv": float(np.max(np.abs(cv_stable))),
    }


def sensitivity_curve(feature_series: np.ndarray, param_series: np.ndarray) -> dict:
    diffs = np.linalg.norm(np.diff(feature_series, axis=0), axis=1)
    dparam = np.diff(param_series)
    dparam[dparam == 0] = 1e-9
    grad = diffs / np.abs(dparam)
    return {"gradient": grad, "max_gradient": float(np.max(grad)), "argmax": int(np.argmax(grad))}


def class_distances(feature_matrix: np.ndarray, labels: np.ndarray) -> dict:
    fm = (feature_matrix - feature_matrix.mean(axis=0)) / (feature_matrix.std(axis=0) + 1e-9)
    unique_labels = np.unique(labels)
    within = []
    for lbl in unique_labels:
        pts = fm[labels == lbl]
        if len(pts) > 1:
            d = cdist(pts, pts)
            within.append(d[np.triu_indices_from(d, k=1)].mean())
    within_mean = float(np.mean(within)) if within else 0.0

    centroids = np.array([fm[labels == lbl].mean(axis=0) for lbl in unique_labels])
    between = cdist(centroids, centroids)
    between_mean = float(between[np.triu_indices_from(between, k=1)].mean()) if len(unique_labels) > 1 else 0.0

    separability = between_mean / (within_mean + 1e-9)
    return {"within_mean": within_mean, "between_mean": between_mean, "separability": separability}


def family_cohesion(feature_matrix_variations: np.ndarray) -> dict:
    fm = (feature_matrix_variations - feature_matrix_variations.mean(axis=0)) / (feature_matrix_variations.std(axis=0) + 1e-9)
    n = len(fm)
    consecutive_d = np.linalg.norm(np.diff(fm, axis=0), axis=1).mean()
    all_d = cdist(fm, fm)
    all_mean_d = all_d[np.triu_indices_from(all_d, k=1)].mean()
    cohesion_ratio = consecutive_d / (all_mean_d + 1e-9)
    return {"consecutive_mean_dist": float(consecutive_d), "all_pairs_mean_dist": float(all_mean_d),
             "cohesion_ratio": float(cohesion_ratio)}


def detect_bifurcation_points(feature_series: np.ndarray, param_series: np.ndarray,
                                z_thresh: float = 2.0) -> dict:
    diffs = np.linalg.norm(np.diff(feature_series, axis=0), axis=1)
    dparam = np.diff(param_series)
    dparam[dparam == 0] = 1e-9
    grad = diffs / np.abs(dparam)

    mu, sigma = grad.mean(), grad.std() + 1e-12
    z_scores = (grad - mu) / sigma
    bifurcation_idx = np.where(z_scores > z_thresh)[0]
    bifurcation_params = param_series[bifurcation_idx + 1]

    return {
        "gradient": grad,
        "z_scores": z_scores,
        "n_bifurcations": int(len(bifurcation_idx)),
        "bifurcation_indices": bifurcation_idx.tolist(),
        "bifurcation_params": bifurcation_params.tolist(),
        "threshold_z": z_thresh,
    }
