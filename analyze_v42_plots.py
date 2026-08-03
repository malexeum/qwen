from pathlib import Path
import json
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_v4"
FIG = OUT / "figures_v42"
FIG.mkdir(parents=True, exist_ok=True)

RUN_TABLE_CANDIDATES = [
    OUT / "run_table.csv",
    OUT / "runs.csv",
    OUT / "features_raw.csv",
]

SUMMARY_JSON = OUT / "summary.json"


def find_existing(paths):
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"None of the candidate files exist: {paths}")


def safe_float(x):
    try:
        if x is None:
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def load_summary(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_generator_metrics(summary: dict, run_df: pd.DataFrame) -> pd.DataFrame:
    gen_counts = summary.get("summary", {}).get("n_runs_by_generator", {})
    fam = summary.get("summary", {}).get("by_generator_family_continuity", {})
    cls = summary.get("summary", {}).get("by_generator_class_stability_index", {})
    obs = summary.get("summary", {}).get("by_generator_observer_stability_score", {})

    generators = sorted(set(gen_counts) | set(fam) | set(cls) | set(obs) | set(run_df["generator"].dropna().unique()))

    rows = []
    for g in generators:
        sub = run_df[run_df["generator"] == g].copy()

        if "morphology_persistence_score" in sub.columns:
            morph_persistence = pd.to_numeric(sub["morphology_persistence_score"], errors="coerce").mean()
        else:
            morph_persistence = np.nan

        if "transition_type" in sub.columns and len(sub) > 0:
            tr = sub["transition_type"].fillna("unresolved").astype(str).str.strip()
            preserved_rate = (tr == "preserved").mean()
            transformed_rate = (tr == "transformed").mean()
            broken_rate = (tr == "broken").mean()
            emergent_rate = (tr == "emergent").mean()
            unresolved_rate = (tr == "unresolved").mean()
        else:
            preserved_rate = np.nan
            transformed_rate = np.nan
            broken_rate = np.nan
            emergent_rate = np.nan
            unresolved_rate = np.nan

        rows.append({
            "generator": g,
            "n_runs": int(gen_counts.get(g, len(sub))),
            "family_continuity_score": safe_float(fam.get(g, np.nan)),
            "class_stability_index": safe_float(cls.get(g, np.nan)),
            "observer_stability_score": safe_float(obs.get(g, np.nan)),
            "morphology_persistence_score": safe_float(morph_persistence),
            "preserved_rate": safe_float(preserved_rate),
            "transformed_rate": safe_float(transformed_rate),
            "broken_rate": safe_float(broken_rate),
            "emergent_rate": safe_float(emergent_rate),
            "unresolved_rate": safe_float(unresolved_rate),
        })

    df = pd.DataFrame(rows).sort_values("family_continuity_score", ascending=False, na_position="last")
    return df


def annotate_points(ax, df, xcol, ycol, label_col="generator"):
    for _, row in df.iterrows():
        x = row[xcol]
        y = row[ycol]
        label = str(row[label_col])
        if pd.notna(x) and pd.notna(y):
            ax.annotate(label, (x, y), xytext=(6, 4), textcoords="offset points", fontsize=9)


def plot_scatter_family_vs_stability(df: pd.DataFrame, out_png: Path):
    fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
    x = df["family_continuity_score"]
    y = df["class_stability_index"]
    sizes = 40 + 220 * df["n_runs"] / max(df["n_runs"].max(), 1)

    ax.scatter(x, y, s=sizes, alpha=0.85)
    annotate_points(ax, df, "family_continuity_score", "class_stability_index")

    ax.set_title("Generator map: family continuity vs class stability")
    ax.set_xlabel("Family continuity score")
    ax.set_ylabel("Class stability index")
    ax.grid(True, alpha=0.25)

    if x.notna().sum() >= 2 and y.notna().sum() >= 2:
        corr = np.corrcoef(x.fillna(0), y.fillna(0))[0, 1]
        ax.text(
            0.02, 0.98,
            f"Pearson r = {corr:.3f}",
            transform=ax.transAxes,
            ha="left", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def plot_scatter_persistence_vs_observer(df: pd.DataFrame, out_png: Path):
    fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
    x = df["morphology_persistence_score"]
    y = df["observer_stability_score"]
    sizes = 40 + 220 * df["n_runs"] / max(df["n_runs"].max(), 1)

    ax.scatter(x, y, s=sizes, alpha=0.85, color="#1f77b4")
    annotate_points(ax, df, "morphology_persistence_score", "observer_stability_score")

    ax.axhline(0.0, color="gray", lw=1, alpha=0.5)
    ax.set_title("Generator map: morphology persistence vs observer stability")
    ax.set_xlabel("Morphology persistence score")
    ax.set_ylabel("Observer stability score")
    ax.grid(True, alpha=0.25)

    if x.notna().sum() >= 2 and y.notna().sum() >= 2:
        corr = np.corrcoef(x.fillna(0), y.fillna(0))[0, 1]
        ax.text(
            0.02, 0.98,
            f"Pearson r = {corr:.3f}",
            transform=ax.transAxes,
            ha="left", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def plot_transition_rates(df: pd.DataFrame, out_png: Path):
    plot_df = df.copy().sort_values("preserved_rate", ascending=False)
    x = np.arange(len(plot_df))
    width = 0.2

    fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
    ax.bar(x - 1.5 * width, plot_df["preserved_rate"], width, label="preserved")
    ax.bar(x - 0.5 * width, plot_df["transformed_rate"], width, label="transformed")
    ax.bar(x + 0.5 * width, plot_df["broken_rate"], width, label="broken")
    ax.bar(x + 1.5 * width, plot_df["emergent_rate"], width, label="emergent")

    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["generator"], rotation=25, ha="right")
    ax.set_ylabel("Rate")
    ax.set_title("Transition rates by generator")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def plot_correlation_heatmap(df: pd.DataFrame, out_png: Path):
    cols = [
        "family_continuity_score",
        "class_stability_index",
        "morphology_persistence_score",
        "observer_stability_score",
        "preserved_rate",
        "transformed_rate",
        "broken_rate",
        "emergent_rate",
    ]
    corr = df[cols].corr(numeric_only=True)

    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)

    ax.set_xticks(np.arange(len(cols)))
    ax.set_yticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticklabels(cols)
    ax.set_title("Correlation heatmap of generator-level metrics")

    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            val = corr.iloc[i, j]
            text_color = "white" if abs(val) > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=text_color, fontsize=9)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def main():
    if not SUMMARY_JSON.exists():
        raise FileNotFoundError(f"summary.json not found: {SUMMARY_JSON}")

    run_table_path = find_existing(RUN_TABLE_CANDIDATES)
    summary = load_summary(SUMMARY_JSON)
    run_df = pd.read_csv(run_table_path)

    required_cols = {"generator"}
    missing = required_cols - set(run_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {run_table_path.name}: {sorted(missing)}")

    gen_df = build_generator_metrics(summary, run_df)
    gen_df.to_csv(FIG / "generator_metrics_summary.csv", index=False, encoding="utf-8-sig")

    plot_scatter_family_vs_stability(gen_df, FIG / "family_vs_stability.png")
    plot_scatter_persistence_vs_observer(gen_df, FIG / "persistence_vs_observer.png")
    plot_transition_rates(gen_df, FIG / "transition_rates_by_generator.png")
    plot_correlation_heatmap(gen_df, FIG / "generator_metric_correlation_heatmap.png")

    print(f"Done. Figures written to: {FIG}")
    print(gen_df.to_string(index=False))


if __name__ == "__main__":
    main()