from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_v4"
FIG = OUT / "figures_v42_classes"
FIG.mkdir(parents=True, exist_ok=True)

RUN_TABLE_CANDIDATES = [
    OUT / "run_table.csv",
    OUT / "runs.csv",
    OUT / "features_raw.csv",
]


def find_existing(paths):
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"None of the candidate files exist: {paths}")


def ensure_column(df: pd.DataFrame, name: str, default=np.nan):
    if name not in df.columns:
        df[name] = default
    return df


def build_class_generator_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required = ["generator", "input_class"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in [
        "transition_type",
        "family_continuity_score",
        "morphology_persistence_score",
        "observer_stability_score",
        "class_stability_index",
        "identity_breakage_score",
    ]:
        ensure_column(df, col)

    df["transition_type"] = df["transition_type"].fillna("unresolved").astype(str).str.strip()

    numeric_cols = [
        "family_continuity_score",
        "morphology_persistence_score",
        "observer_stability_score",
        "class_stability_index",
        "identity_breakage_score",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    rows = []
    grouped = df.groupby(["generator", "input_class"], dropna=False)

    for (generator, input_class), sub in grouped:
        tr = sub["transition_type"]

        rows.append({
            "generator": generator,
            "input_class": input_class,
            "n_runs": len(sub),
            "preserved_rate": (tr == "preserved").mean(),
            "transformed_rate": (tr == "transformed").mean(),
            "broken_rate": (tr == "broken").mean(),
            "emergent_rate": (tr == "emergent").mean(),
            "unresolved_rate": (tr == "unresolved").mean(),
            "family_continuity_score": sub["family_continuity_score"].mean(),
            "morphology_persistence_score": sub["morphology_persistence_score"].mean(),
            "observer_stability_score": sub["observer_stability_score"].mean(),
            "class_stability_index": sub["class_stability_index"].mean(),
            "identity_breakage_score": sub["identity_breakage_score"].mean(),
        })

    out = pd.DataFrame(rows).sort_values(["generator", "input_class"]).reset_index(drop=True)
    return out


def draw_heatmap(pivot_df: pd.DataFrame, title: str, out_png: Path, cmap: str = "viridis", center=None):
    fig_w = max(9, 1.4 * len(pivot_df.columns))
    fig_h = max(6, 0.7 * len(pivot_df.index))

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)

    data = pivot_df.values.astype(float)
    im = ax.imshow(data, aspect="auto", cmap=cmap)

    ax.set_xticks(np.arange(len(pivot_df.columns)))
    ax.set_yticks(np.arange(len(pivot_df.index)))
    ax.set_xticklabels(pivot_df.columns, rotation=35, ha="right")
    ax.set_yticklabels(pivot_df.index)
    ax.set_title(title)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isnan(val):
                txt = "NaN"
                color = "black"
            else:
                txt = f"{val:.2f}"
                color = "white" if abs(val) > 0.5 else "black"
            ax.text(j, i, txt, ha="center", va="center", color=color, fontsize=8)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.set_ylabel("Value", rotation=270, labelpad=15)

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def save_top_tables(metrics: pd.DataFrame):
    best_preserved = metrics.sort_values("preserved_rate", ascending=False).copy()
    worst_broken = metrics.sort_values("broken_rate", ascending=False).copy()
    best_continuity = metrics.sort_values("family_continuity_score", ascending=False).copy()

    best_preserved.to_csv(FIG / "table_best_preserved_pairs.csv", index=False, encoding="utf-8-sig")
    worst_broken.to_csv(FIG / "table_most_broken_pairs.csv", index=False, encoding="utf-8-sig")
    best_continuity.to_csv(FIG / "table_best_family_continuity_pairs.csv", index=False, encoding="utf-8-sig")


def main():
    run_table_path = find_existing(RUN_TABLE_CANDIDATES)
    df = pd.read_csv(run_table_path)

    metrics = build_class_generator_metrics(df)
    metrics.to_csv(FIG / "class_generator_metrics.csv", index=False, encoding="utf-8-sig")

    preserved = metrics.pivot(index="generator", columns="input_class", values="preserved_rate")
    broken = metrics.pivot(index="generator", columns="input_class", values="broken_rate")
    family = metrics.pivot(index="generator", columns="input_class", values="family_continuity_score")
    persistence = metrics.pivot(index="generator", columns="input_class", values="morphology_persistence_score")
    observer = metrics.pivot(index="generator", columns="input_class", values="observer_stability_score")

    draw_heatmap(
        preserved,
        "Preserved rate by generator and input class",
        FIG / "heatmap_preserved_rate.png",
        cmap="YlGn"
    )
    draw_heatmap(
        broken,
        "Broken rate by generator and input class",
        FIG / "heatmap_broken_rate.png",
        cmap="YlOrRd"
    )
    draw_heatmap(
        family,
        "Family continuity score by generator and input class",
        FIG / "heatmap_family_continuity.png",
        cmap="viridis"
    )
    draw_heatmap(
        persistence,
        "Morphology persistence by generator and input class",
        FIG / "heatmap_morphology_persistence.png",
        cmap="cividis"
    )
    draw_heatmap(
        observer,
        "Observer stability by generator and input class",
        FIG / "heatmap_observer_stability.png",
        cmap="coolwarm"
    )

    save_top_tables(metrics)

    print(f"Done. Class figures written to: {FIG}")
    print("\nTop preserved pairs:")
    print(metrics.sort_values("preserved_rate", ascending=False).head(12).to_string(index=False))

    print("\nTop broken pairs:")
    print(metrics.sort_values("broken_rate", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()