from __future__ import annotations

from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

# =============================================================================
# USER SETTINGS
# =============================================================================

# Root folder containing location folders, e.g. Zwolle, Wezep.
PROJECT_ROOT = Path(r"C:\AA_Thesis\VSCode\ZZ_Zwolle_Wezep\Zwolle")

# Folder where lengkeek_chart.py and lengkeek_chart_clean.jpg are located.
CODE_ROOT = Path(r"C:\AA_Thesis\VSCode\ZZ_Zwolle_Wezep")
BACKGROUND_PATH = CODE_ROOT / "lengkeek_chart_clean.jpg"

# Confidence ellipse levels to export.
# 1.52 = approximately 68.3% for 2 variables.
# 2.14 = approximately 90% for 2 variables.
CONFIDENCE_LEVELS = [1.52, 2.14]

# Only layers with IDs exactly like Sand 1, Sand 2, Sand 3, ... are used.
SAND_LAYER_REGEX = re.compile(r"^Sand\s+\d+$", flags=re.IGNORECASE)

# Output folder name created inside each borehole folder.
OUTPUT_FOLDER_NAME = "robertson_charts"

# Recursively scan all location folders under PROJECT_ROOT.
# A borehole folder is any folder whose name contains "vs" and contains at least
# one classified_points.csv somewhere below it.
BOREHOLE_NAME_CONTAINS = "vs"

# =============================================================================
# Plot appearance
# =============================================================================
POINT_SIZE = 8
POINT_ALPHA = 0.15
ELLIPSE_LINEWIDTH = 2.0
CENTRE_SIZE = 120

# Fixed colour list so each CPT gets its own colour.
# Points, centre marker, and ellipse will all use the same CPT colour.
CPT_COLOURS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # grey
    "#bcbd22",  # olive
    "#17becf",  # cyan
    "#003f5c",  # dark blue
    "#ffa600",  # amber
]


# =============================================================================
# IMPORT BACKGROUND PLOTTER
# =============================================================================

sys.path.insert(0, str(CODE_ROOT))
from lengkeek_chart import create_lengkeek_background_axis  # noqa: E402


# =============================================================================
# HELPERS
# =============================================================================

def make_safe_filename(text: object) -> str:
    text = str(text).replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_\.\-]+", "", text)


def is_sand_layer_id(value: object) -> bool:
    return SAND_LAYER_REGEX.fullmatch(str(value).strip()) is not None


def find_borehole_folders(project_root: Path) -> list[Path]:
    """Find borehole folders below PROJECT_ROOT."""
    boreholes = []

    for folder in project_root.rglob("*"):
        if not folder.is_dir():
            continue

        if BOREHOLE_NAME_CONTAINS.lower() not in folder.name.lower():
            continue

        if any(folder.rglob("classified_points.csv")):
            boreholes.append(folder)

    return sorted(set(boreholes))


def find_cpt_output_folders(borehole_folder: Path) -> list[Path]:
    """Return folders containing classified_points.csv below one borehole folder."""
    cpt_folders = []

    for csv_path in borehole_folder.rglob("classified_points.csv"):
        if OUTPUT_FOLDER_NAME in csv_path.parts:
            continue
        cpt_folders.append(csv_path.parent)

    return sorted(set(cpt_folders))


def load_sand_points(cpt_folder: Path) -> pd.DataFrame:
    """Load all exact Sand X points from one analysed CPT folder."""
    csv_path = cpt_folder / "classified_points.csv"
    df = pd.read_csv(csv_path)

    required = {"rf_percent", "qt_over_pa", "layer_id"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{csv_path} is missing required columns: {sorted(missing)}"
        )

    sand_df = df[df["layer_id"].apply(is_sand_layer_id)].copy()

    sand_df = sand_df[["rf_percent", "qt_over_pa", "layer_id"]].dropna()
    sand_df = sand_df[
        (sand_df["rf_percent"] > 0.0)
        & (sand_df["qt_over_pa"] > 0.0)
    ].copy()

    if sand_df.empty:
        return sand_df

    sand_df["cpt_name"] = cpt_folder.name
    sand_df["cpt_folder"] = str(cpt_folder)
    sand_df["log_rf_percent"] = np.log10(sand_df["rf_percent"].astype(float))
    sand_df["log_qt_over_pa"] = np.log10(sand_df["qt_over_pa"].astype(float))

    return sand_df


def add_covariance_ellipse(ax, x, y, n_std: float, **kwargs) -> None:
    """Add covariance ellipse in log10(Rf)-log10(qt/pa) space."""
    if len(x) < 3:
        return

    cov = np.cov(x, y)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = eigenvalues.argsort()[::-1]

    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    # Numerical safety for nearly identical points.
    eigenvalues = np.maximum(eigenvalues, 0.0)

    angle = np.degrees(
        np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0])
    )

    width, height = 2.0 * n_std * np.sqrt(eigenvalues)

    ellipse = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width,
        height=height,
        angle=angle,
        fill=False,
        linewidth=ELLIPSE_LINEWIDTH,
        **kwargs,
    )

    ax.add_patch(ellipse)


def plot_borehole_robertson_chart(
    borehole_folder: Path,
    confidence: float,
) -> Path | None:
    """Create one Robertson/Lengkeek chart for one borehole folder."""
    cpt_folders = find_cpt_output_folders(borehole_folder)

    if not cpt_folders:
        print(f"Skipping {borehole_folder}: no analysed CPT folders found.")
        return None

    output_folder = borehole_folder / OUTPUT_FOLDER_NAME
    output_folder.mkdir(parents=True, exist_ok=True)

    fig, ax = create_lengkeek_background_axis(
        background_path=BACKGROUND_PATH,
        figsize=(8, 6),
        alpha=1.0,
    )

    stats_rows = []
    plotted_anything = False

    for cpt_index, cpt_folder in enumerate(cpt_folders):
        colour = CPT_COLOURS[cpt_index % len(CPT_COLOURS)]

        try:
            sand_data = load_sand_points(cpt_folder)
        except Exception as exc:
            print(f"Warning: could not load {cpt_folder}: {exc}")
            continue

        if sand_data.empty:
            print(f"Warning: no Sand X data found in {cpt_folder}")
            continue

        x = sand_data["log_rf_percent"].values
        y = sand_data["log_qt_over_pa"].values

        # Plot individual points
        ax.scatter(
            x,
            y,
            s=POINT_SIZE,
            alpha=POINT_ALPHA,
            color=colour,
            label=f"{cpt_folder.name} points",
            zorder=2,
        )

        # Plot centre
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        ax.scatter(
            x_mean,
            y_mean,
            s=CENTRE_SIZE,
            marker="x",
            linewidths=3,
            color=colour,
            label=f"{cpt_folder.name} centre",
            zorder=4,
        )

        # Plot covariance / confidence ellipse
        add_covariance_ellipse(
            ax,
            x,
            y,
            n_std=confidence,
            edgecolor=colour,
            zorder=3,
        )

        plotted_anything = True

        stats_rows.append({
            "cpt_name": cpt_folder.name,
            "n_points": len(sand_data),
            "centre_rf_percent": 10 ** x_mean,
            "centre_qt_over_pa": 10 ** y_mean,
            "std_log10_rf_percent": np.std(x, ddof=1) if len(x) > 1 else np.nan,
            "std_log10_qt_over_pa": np.std(y, ddof=1) if len(y) > 1 else np.nan,
        })

        print(
            f"{cpt_folder.name}: "
            f"n = {len(sand_data)}, "
            f"centre Rf = {10**x_mean:.3f} %, "
            f"centre qt/pa = {10**y_mean:.3f}"
        )

    if not plotted_anything:
        plt.close(fig)
        print(f"Skipping {borehole_folder}: no Sand X data found in any CPT.")
        return None

    conf_label = str(confidence).replace(".", "p")

    title = (
        f"Robertson chart — all Sand X layers\n"
        f"{borehole_folder.name} | confidence = {confidence}"
    )

    ax.set_title(title)
    ax.legend(fontsize=7, loc="best")

    fig.tight_layout()

    png_path = (
        output_folder
        / f"{make_safe_filename(borehole_folder.name)}_sand_robertson_conf_{conf_label}.png"
    )

    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    stats_path = (
        output_folder
        / f"{make_safe_filename(borehole_folder.name)}_sand_robertson_conf_{conf_label}_stats.csv"
    )

    pd.DataFrame(stats_rows).to_csv(stats_path, index=False)

    print(f"Saved: {png_path}")
    print(f"Saved: {stats_path}")

    return png_path


def main() -> None:
    if not PROJECT_ROOT.exists():
        raise FileNotFoundError(f"PROJECT_ROOT does not exist: {PROJECT_ROOT}")

    if not BACKGROUND_PATH.exists():
        raise FileNotFoundError(f"BACKGROUND_PATH does not exist: {BACKGROUND_PATH}")

    borehole_folders = find_borehole_folders(PROJECT_ROOT)

    if not borehole_folders:
        raise ValueError(
            f"No borehole folders found below {PROJECT_ROOT}. "
            f"Expected folder names containing '{BOREHOLE_NAME_CONTAINS}' "
            "and containing analysed CPT folders with classified_points.csv."
        )

    print("Found borehole folders:")
    for folder in borehole_folders:
        print(f"  {folder}")

    for borehole_folder in borehole_folders:
        for confidence in CONFIDENCE_LEVELS:
            plot_borehole_robertson_chart(
                borehole_folder=borehole_folder,
                confidence=confidence,
            )

    print("Done.")


if __name__ == "__main__":
    main()
