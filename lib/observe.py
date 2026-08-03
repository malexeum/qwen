import numpy as np


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_image(result, mode="orbit_map"):
    if mode == "orbit_map":
        f = result.orbit_map
    elif mode == "visit_density":
        f = result.visit_density
    elif mode == "log_visit":
        f = np.log1p(result.visit_density)
    else:
        raise ValueError(mode)

    f = _sanitize_array(f)
    fmin, fmax = np.percentile(f, 1), np.percentile(f, 99)
    if fmax - fmin < 1e-12:
        fmax = fmin + 1e-12
    norm = np.clip((f - fmin) / (fmax - fmin), 0.0, 1.0)
    return norm


def extract_features(result) -> dict:
    om = _sanitize_array(result.orbit_map)
    vd = _sanitize_array(result.visit_density)
    lv = np.log1p(vd)

    om_n = _normalize_robust(om)
    vd_n = _normalize_robust(vd)
    lv_n = _normalize_robust(lv)

    feats = {}

    # -----------------------------------------------------------------------
    # Backward-compatible v4.1 features
    # -----------------------------------------------------------------------
    feats["mean_orbit"] = float(np.mean(om))
    feats["std_orbit"] = float(np.std(om))
    feats["skew_orbit"] = float(_skew(om))
    feats["kurt_orbit"] = float(_kurtosis(om))
    feats["mean_visit"] = float(np.mean(vd))
    feats["std_visit"] = float(np.std(vd))
    feats["entropy_orbit"] = float(_hist_entropy(om))
    feats["entropy_visit"] = float(_hist_entropy(vd))
    feats["symmetry_score"] = float(_symmetry_score(om_n))
    feats["edge_density"] = float(_edge_density(om_n))
    feats["basin_entropy"] = float(_basin_entropy_proxy(om_n))
    feats["fractal_dim_proxy"] = float(_box_counting_dim(om_n))

    # -----------------------------------------------------------------------
    # Stable field statistics
    # -----------------------------------------------------------------------
    feats["median_orbit"] = float(np.median(om))
    feats["median_visit"] = float(np.median(vd))
    feats["mad_orbit"] = float(_mad(om))
    feats["mad_visit"] = float(_mad(vd))
    feats["iqr_orbit"] = float(_iqr(om))
    feats["iqr_visit"] = float(_iqr(vd))
    feats["p90_p10_orbit"] = float(np.percentile(om, 90) - np.percentile(om, 10))
    feats["p90_p10_visit"] = float(np.percentile(vd, 90) - np.percentile(vd, 10))

    # -----------------------------------------------------------------------
    # Multi-scale morphology
    # -----------------------------------------------------------------------
    ms_levels = [1, 2, 4]
    for ds in ms_levels:
        om_ds = _downsample_mean(om_n, ds)
        vd_ds = _downsample_mean(vd_n, ds)
        lv_ds = _downsample_mean(lv_n, ds)

        suffix = f"s{ds}"
        feats[f"multi_scale_entropy_orbit_{suffix}"] = float(_hist_entropy(om_ds))
        feats[f"multi_scale_entropy_visit_{suffix}"] = float(_hist_entropy(vd_ds))
        feats[f"multi_scale_fractal_dim_{suffix}"] = float(_box_counting_dim(om_ds))
        feats[f"multi_scale_edge_density_{suffix}"] = float(_edge_density(om_ds))
        feats[f"multi_scale_lacunarity_{suffix}"] = float(_lacunarity(om_ds))
        feats[f"multi_scale_symmetry_{suffix}"] = float(_symmetry_score(om_ds))
        feats[f"multi_scale_visit_mass_{suffix}"] = float(np.mean(lv_ds))
        feats[f"multi_scale_basin_entropy_{suffix}"] = float(_basin_entropy_proxy(vd_ds))

    # -----------------------------------------------------------------------
    # Topological connectivity (binary masks at robust thresholds)
    # -----------------------------------------------------------------------
    topo_orbit = _binary_topology_features(om_n, threshold=np.percentile(om_n, 75), prefix="topology_orbit")
    topo_visit = _binary_topology_features(vd_n, threshold=np.percentile(vd_n, 75), prefix="topology_visit")
    feats.update(topo_orbit)
    feats.update(topo_visit)

    # -----------------------------------------------------------------------
    # Boundary complexity
    # -----------------------------------------------------------------------
    boundary_orbit = _boundary_features(om_n, threshold=np.percentile(om_n, 75), prefix="boundary_orbit")
    boundary_visit = _boundary_features(vd_n, threshold=np.percentile(vd_n, 75), prefix="boundary_visit")
    feats.update(boundary_orbit)
    feats.update(boundary_visit)

    # -----------------------------------------------------------------------
    # Basin geometry
    # -----------------------------------------------------------------------
    basin_orbit = _region_geometry_features(om_n, threshold=np.percentile(om_n, 75), prefix="basin_geom_orbit")
    basin_visit = _region_geometry_features(vd_n, threshold=np.percentile(vd_n, 75), prefix="basin_geom_visit")
    feats.update(basin_orbit)
    feats.update(basin_visit)

    # -----------------------------------------------------------------------
    # Local curvature / angular complexity
    # -----------------------------------------------------------------------
    feats.update(_curvature_features(om_n, prefix="curvature_orbit"))
    feats.update(_curvature_features(vd_n, prefix="curvature_visit"))

    # -----------------------------------------------------------------------
    # Persistence / stability proxies
    # -----------------------------------------------------------------------
    feats["persistence_scale_consistency"] = float(_scale_consistency_score(feats))
    feats["persistence_topology_stability"] = float(_topology_stability_score(feats))
    feats["persistence_boundary_stability"] = float(_boundary_stability_score(feats))
    feats["morphology_persistence_score"] = float(
        np.mean([
            feats["persistence_scale_consistency"],
            feats["persistence_topology_stability"],
            feats["persistence_boundary_stability"],
        ])
    )

    # -----------------------------------------------------------------------
    # Observer stabilization metrics
    # -----------------------------------------------------------------------
    feats["observer_stability_proxy"] = float(_observer_stability_proxy(om_n, vd_n))
    feats["density_variation"] = float(_density_variation_multiscale(vd_n))

    return {k: float(np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)) for k, v in feats.items()}


def feature_vector(result) -> np.ndarray:
    f = extract_features(result)
    keys = sorted(f.keys())
    return np.array([f[k] for k in keys], dtype=float), keys


# ---------------------------------------------------------------------------
# Core utilities
# ---------------------------------------------------------------------------

def _sanitize_array(a):
    a = np.asarray(a, dtype=float)
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)


def _normalize_robust(a):
    a = _sanitize_array(a)
    p1, p99 = np.percentile(a, 1), np.percentile(a, 99)
    if p99 - p1 < 1e-12:
        return np.zeros_like(a, dtype=float)
    x = np.clip((a - p1) / (p99 - p1), 0.0, 1.0)
    return x


def _mad(a):
    a = np.ravel(_sanitize_array(a))
    med = np.median(a)
    return float(np.median(np.abs(a - med)))


def _iqr(a):
    a = np.ravel(_sanitize_array(a))
    return float(np.percentile(a, 75) - np.percentile(a, 25))


def _downsample_mean(a, factor):
    a = _sanitize_array(a)
    if factor <= 1:
        return a.copy()
    h, w = a.shape
    hh = (h // factor) * factor
    ww = (w // factor) * factor
    if hh < factor or ww < factor:
        return a.copy()
    cropped = a[:hh, :ww]
    return cropped.reshape(hh // factor, factor, ww // factor, factor).mean(axis=(1, 3))


# ---------------------------------------------------------------------------
# Classical descriptors
# ---------------------------------------------------------------------------

def _skew(a):
    a = _sanitize_array(a).ravel()
    m = a.mean()
    s = a.std() + 1e-12
    return float(np.mean(((a - m) / s) ** 3))


def _kurtosis(a):
    a = _sanitize_array(a).ravel()
    m = a.mean()
    s = a.std() + 1e-12
    return float(np.mean(((a - m) / s) ** 4) - 3.0)


def _hist_entropy(a, bins=64):
    a = _sanitize_array(a).ravel()
    hist, _ = np.histogram(a, bins=bins, density=False)
    p = hist / (hist.sum() + 1e-12)
    p = p[p > 0]
    return float(-np.sum(p * np.log(p + 1e-12)))


def _symmetry_score(a):
    a = _sanitize_array(a)
    flip_h = np.fliplr(a)
    flip_v = np.flipud(a)

    def corr(x, y):
        x = x.ravel() - x.mean()
        y = y.ravel() - y.mean()
        denom = np.linalg.norm(x) * np.linalg.norm(y) + 1e-12
        return float(np.dot(x, y) / denom)

    return float(0.5 * (corr(a, flip_h) + corr(a, flip_v)))


def _edge_density(a):
    a = _sanitize_array(a)
    gy, gx = np.gradient(a)
    grad_mag = np.sqrt(gx ** 2 + gy ** 2)
    thresh = np.percentile(grad_mag, 90)
    return float(np.mean(grad_mag > thresh))


def _basin_entropy_proxy(a, box=8):
    a = _sanitize_array(a)
    H, W = a.shape
    k_bins = 5
    amin, amax = float(a.min()), float(a.max())
    if amax - amin < 1e-12:
        return 0.0

    discretized = np.digitize(a, np.linspace(amin, amax + 1e-9, k_bins))
    entropies = []

    for i in range(0, max(H - box + 1, 1), box):
        for j in range(0, max(W - box + 1, 1), box):
            patch = discretized[i:i + box, j:j + box].ravel()
            if patch.size == 0:
                continue
            _, counts = np.unique(patch, return_counts=True)
            p = counts / counts.sum()
            ent = -np.sum(p * np.log(p + 1e-12))
            entropies.append(ent)

    return float(np.mean(entropies)) if entropies else 0.0


def _box_counting_dim(a, thresh_pct=70):
    a = _sanitize_array(a)
    thresh = np.percentile(a, thresh_pct)
    binary = a > thresh

    H, W = binary.shape
    min_dim = min(H, W)
    if min_dim < 4:
        return 0.0

    sizes = []
    counts = []
    max_pow = int(np.floor(np.log2(min_dim)))

    for k in range(1, max_pow):
        box = 2 ** k
        if box >= min_dim:
            continue
        count = 0
        for i in range(0, H, box):
            for j in range(0, W, box):
                if binary[i:i + box, j:j + box].any():
                    count += 1
        if count > 0:
            sizes.append(float(box))
            counts.append(float(count))

    if len(sizes) < 2:
        return 0.0

    logs_inv_size = np.log(1.0 / np.array(sizes, dtype=float))
    logs_count = np.log(np.array(counts, dtype=float))
    coeff = np.polyfit(logs_inv_size, logs_count, 1)
    return float(coeff[0])


def _lacunarity(a, box=8):
    a = _sanitize_array(a)
    H, W = a.shape
    masses = []
    for i in range(0, max(H - box + 1, 1), box):
        for j in range(0, max(W - box + 1, 1), box):
            patch = a[i:i + box, j:j + box]
            if patch.size > 0:
                masses.append(float(np.sum(patch)))
    if len(masses) < 2:
        return 0.0
    masses = np.asarray(masses, dtype=float)
    m1 = np.mean(masses)
    m2 = np.mean(masses ** 2)
    if m1 ** 2 < 1e-12:
        return 0.0
    return float(m2 / (m1 ** 2) - 1.0)


# ---------------------------------------------------------------------------
# Binary morphology / topology
# ---------------------------------------------------------------------------

def _binary_mask(a, threshold):
    a = _sanitize_array(a)
    return np.asarray(a > threshold, dtype=bool)


def _neighbors8(y, x, h, w):
    for yy in range(max(0, y - 1), min(h, y + 2)):
        for xx in range(max(0, x - 1), min(w, x + 2)):
            if yy == y and xx == x:
                continue
            yield yy, xx


def _connected_components(mask):
    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    labels = np.full((h, w), -1, dtype=int)
    components = []
    label = 0

    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] >= 0:
                continue

            stack = [(y, x)]
            labels[y, x] = label
            pixels = []

            while stack:
                cy, cx = stack.pop()
                pixels.append((cy, cx))
                for ny, nx in _neighbors8(cy, cx, h, w):
                    if mask[ny, nx] and labels[ny, nx] < 0:
                        labels[ny, nx] = label
                        stack.append((ny, nx))

            components.append(pixels)
            label += 1

    return labels, components


def _component_holes(mask):
    mask = np.asarray(mask, dtype=bool)
    inv = ~mask
    h, w = inv.shape
    visited = np.zeros_like(inv, dtype=bool)
    holes = 0

    for y in range(h):
        for x in range(w):
            if not inv[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            touches_border = False

            while stack:
                cy, cx = stack.pop()
                if cy == 0 or cx == 0 or cy == h - 1 or cx == w - 1:
                    touches_border = True

                for ny, nx in _neighbors8(cy, cx, h, w):
                    if inv[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))

            if not touches_border:
                holes += 1

    return int(holes)


def _binary_topology_features(a, threshold, prefix):
    mask = _binary_mask(a, threshold)
    labels, components = _connected_components(mask)
    sizes = np.array([len(c) for c in components], dtype=float) if components else np.array([], dtype=float)

    n_components = int(len(components))
    foreground_fraction = float(np.mean(mask))
    largest_component = float(np.max(sizes)) if sizes.size else 0.0
    mean_component = float(np.mean(sizes)) if sizes.size else 0.0
    std_component = float(np.std(sizes)) if sizes.size else 0.0
    holes = _component_holes(mask)
    euler_number = float(n_components - holes)

    survival_threshold = max(4, int(0.0025 * mask.size))
    surviving = float(np.sum(sizes >= survival_threshold)) if sizes.size else 0.0
    persistence = float(surviving / max(n_components, 1))

    return {
        f"{prefix}_foreground_fraction": foreground_fraction,
        f"{prefix}_n_components": float(n_components),
        f"{prefix}_largest_component_fraction": float(largest_component / max(mask.size, 1)),
        f"{prefix}_mean_component_size": mean_component,
        f"{prefix}_std_component_size": std_component,
        f"{prefix}_holes": float(holes),
        f"{prefix}_euler_number": euler_number,
        f"{prefix}_component_persistence": persistence,
    }


# ---------------------------------------------------------------------------
# Boundary complexity
# ---------------------------------------------------------------------------

def _boundary_mask(mask):
    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    boundary = np.zeros_like(mask, dtype=bool)

    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            for ny, nx in _neighbors8(y, x, h, w):
                if not mask[ny, nx]:
                    boundary[y, x] = True
                    break

    return boundary


def _boundary_features(a, threshold, prefix):
    mask = _binary_mask(a, threshold)
    boundary = _boundary_mask(mask)

    area = float(np.sum(mask))
    perimeter = float(np.sum(boundary))
    if area < 1.0:
        area = 1.0

    compactness = float((4.0 * np.pi * area) / max(perimeter ** 2, 1e-12))
    shape_index = float(perimeter / max(2.0 * np.sqrt(np.pi * area), 1e-12))
    boundary_density = float(perimeter / max(mask.size, 1))
    boundary_dim = float(_box_counting_dim(boundary.astype(float), thresh_pct=50))
    curvature_map = _gradient_orientation_curvature(a)
    boundary_curvature = curvature_map[boundary] if np.any(boundary) else np.array([0.0])

    return {
        f"{prefix}_perimeter_fraction": float(perimeter / max(mask.size, 1)),
        f"{prefix}_compactness": compactness,
        f"{prefix}_shape_index": shape_index,
        f"{prefix}_boundary_density": boundary_density,
        f"{prefix}_boundary_fractal_dim": boundary_dim,
        f"{prefix}_boundary_curvature_mean": float(np.mean(np.abs(boundary_curvature))),
        f"{prefix}_boundary_curvature_std": float(np.std(boundary_curvature)),
    }


# ---------------------------------------------------------------------------
# Region geometry
# ---------------------------------------------------------------------------

def _component_bbox(pixels):
    ys = np.array([p[0] for p in pixels], dtype=float)
    xs = np.array([p[1] for p in pixels], dtype=float)
    return ys.min(), ys.max(), xs.min(), xs.max()


def _component_moments(pixels):
    ys = np.array([p[0] for p in pixels], dtype=float)
    xs = np.array([p[1] for p in pixels], dtype=float)
    yc = np.mean(ys)
    xc = np.mean(xs)

    y0 = ys - yc
    x0 = xs - xc
    cov = np.array([
        [np.mean(x0 * x0), np.mean(x0 * y0)],
        [np.mean(y0 * x0), np.mean(y0 * y0)],
    ], dtype=float)
    vals = np.linalg.eigvalsh(cov)
    vals = np.sort(np.maximum(vals, 1e-12))
    minor, major = float(vals[0]), float(vals[1])
    return major, minor


def _region_geometry_features(a, threshold, prefix):
    mask = _binary_mask(a, threshold)
    _, components = _connected_components(mask)

    if not components:
        return {
            f"{prefix}_area_mean": 0.0,
            f"{prefix}_area_std": 0.0,
            f"{prefix}_elongation_mean": 0.0,
            f"{prefix}_elongation_std": 0.0,
            f"{prefix}_bbox_fill_mean": 0.0,
            f"{prefix}_bbox_fill_std": 0.0,
        }

    areas = []
    elongations = []
    fills = []

    for comp in components:
        area = float(len(comp))
        y0, y1, x0, x1 = _component_bbox(comp)
        bbox_area = float((y1 - y0 + 1.0) * (x1 - x0 + 1.0))
        fill = float(area / max(bbox_area, 1e-12))

        major, minor = _component_moments(comp)
        elongation = float(np.sqrt(major / max(minor, 1e-12)))

        areas.append(area)
        elongations.append(elongation)
        fills.append(fill)

    return {
        f"{prefix}_area_mean": float(np.mean(areas)),
        f"{prefix}_area_std": float(np.std(areas)),
        f"{prefix}_elongation_mean": float(np.mean(elongations)),
        f"{prefix}_elongation_std": float(np.std(elongations)),
        f"{prefix}_bbox_fill_mean": float(np.mean(fills)),
        f"{prefix}_bbox_fill_std": float(np.std(fills)),
    }


# ---------------------------------------------------------------------------
# Curvature / angular complexity
# ---------------------------------------------------------------------------

def _gradient_orientation_curvature(a):
    a = _sanitize_array(a)
    gy, gx = np.gradient(a)
    theta = np.arctan2(gy, gx + 1e-12)
    dty, dtx = np.gradient(theta)
    return np.sqrt(dtx ** 2 + dty ** 2)


def _curvature_features(a, prefix):
    a = _sanitize_array(a)
    curv = _gradient_orientation_curvature(a)

    high = np.percentile(curv, 90)
    med = np.percentile(curv, 50)

    return {
        f"{prefix}_mean": float(np.mean(curv)),
        f"{prefix}_std": float(np.std(curv)),
        f"{prefix}_p90": float(high),
        f"{prefix}_p50": float(med),
        f"{prefix}_corner_density": float(np.mean(curv > high)),
    }


# ---------------------------------------------------------------------------
# Persistence / consistency proxies
# ---------------------------------------------------------------------------

def _scale_consistency_score(feats):
    vals = np.array([
        feats.get("multi_scale_fractal_dim_s1", 0.0),
        feats.get("multi_scale_fractal_dim_s2", 0.0),
        feats.get("multi_scale_fractal_dim_s4", 0.0),
        feats.get("multi_scale_edge_density_s1", 0.0),
        feats.get("multi_scale_edge_density_s2", 0.0),
        feats.get("multi_scale_edge_density_s4", 0.0),
    ], dtype=float)
    if vals.size == 0:
        return 0.0
    return float(1.0 / (1.0 + np.std(vals)))


def _topology_stability_score(feats):
    vals = np.array([
        feats.get("topology_orbit_n_components", 0.0),
        feats.get("topology_visit_n_components", 0.0),
        feats.get("topology_orbit_component_persistence", 0.0),
        feats.get("topology_visit_component_persistence", 0.0),
    ], dtype=float)
    if vals.size == 0:
        return 0.0
    return float(1.0 / (1.0 + np.std(vals)))


def _boundary_stability_score(feats):
    vals = np.array([
        feats.get("boundary_orbit_shape_index", 0.0),
        feats.get("boundary_visit_shape_index", 0.0),
        feats.get("boundary_orbit_boundary_fractal_dim", 0.0),
        feats.get("boundary_visit_boundary_fractal_dim", 0.0),
    ], dtype=float)
    if vals.size == 0:
        return 0.0
    return float(1.0 / (1.0 + np.std(vals)))


def _observer_stability_proxy(om_n, vd_n):
    g1 = np.sqrt(np.sum(np.gradient(om_n)[0] ** 2 + np.gradient(om_n)[1] ** 2))
    g2 = np.sqrt(np.sum(np.gradient(vd_n)[0] ** 2 + np.gradient(vd_n)[1] ** 2))
    hf = 0.5 * (g1 + g2) / max(om_n.size, 1)
    return float(1.0 / (1.0 + hf))


def _density_variation_multiscale(vd_n):
    scales = [1, 2, 4]
    vals = []
    for ds in scales:
        x = _downsample_mean(vd_n, ds)
        vals.append(float(np.std(x)))
    return float(np.mean(vals))