# plotting horizontal movement away from borehole center as positive, towards center as negative

from pathlib import Path
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from gef_parser_trajectory import read_gef

# This gef_parser is slightly different from the one in lengkeek as it does account for the angle in the first few measurements

# ============================================================
# USER SETTINGS
# ============================================================

GEF_FILE = Path(
    r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\After-boren\S1022749_CPTU2-4.gef"
)

# Use corrected_depth if available, otherwise depth_m.
USE_CORRECTED_DEPTH = True

# Use elevation on vertical axis if available.
# If False, depth is plotted downward.
USE_ELEVATION_M_NAP = True

# Save figures
SHOW_FIGURES = False
SAVE_FIGURES = True

# Export calculated trajectory to Excel
EXPORT_EXCEL = False

# Borehole location relative to CPT start point
SHOW_BOREHOLE = True
BOREHOLE_RADIUS = 0.45

# Choose how the borehole coordinates are defined:
#
# "absolute"
#     Use real-world coordinates of the borehole.
#     The script subtracts the CPT start coordinates from the GEF header.
#
# "relative"
#     Use borehole coordinates directly relative to the CPT start point.
#
BOREHOLE_COORDINATE_MODE = "absolute"

BOREHOLE_X_ABSOLUTE = 85991.08
BOREHOLE_Y_ABSOLUTE = 445047.5

# Fallback manual coordinates if GEF header does not contain x/y
BOREHOLE_X_RELATIVE = -2.0
BOREHOLE_Y_RELATIVE = 0.0

# ============================================================
# FILE NAME HELPERS
# ============================================================

def get_cpt_id_from_gef_filename(gef_file: Path) -> str:
    """
    Extract CPT number from a GEF filename.

    Example:
        S1022749_CPTU2-2.gef -> CPT2-2
    """
    stem = gef_file.stem

    match = re.search(r"CPTU?(\d+-\d+)", stem, flags=re.IGNORECASE)

    if not match:
        raise ValueError(f"Could not find CPT number in filename: {gef_file.name}")

    return f"CPT{match.group(1)}"


CPT_ID = get_cpt_id_from_gef_filename(GEF_FILE)
FIGURE_BASENAME = f"{CPT_ID}_cone_trajectory"

FIGURE_FOLDER = Path(f"{CPT_ID}_figures")
FIGURE_FOLDER.mkdir(parents=True, exist_ok=True)

EXPORT_FILE = FIGURE_FOLDER / f"{FIGURE_BASENAME}.xlsx"

# column remover helpers

def remove_unnecessary_export_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove raw CPT columns that are not needed in the exported trajectory Excel.
    """
    columns_to_remove = [
        "qc_mpa",
        "fs_mpa",
        "rf_percent",
        "u2_mpa",
        "col_9",
    ]

    return df.drop(columns=columns_to_remove, errors="ignore")

# ============================================================
# COLUMN HELPERS
# ============================================================

def get_first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """
    Return the first column from candidates that exists in df.
    """
    for col in candidates:
        if col in df.columns:
            return col

    raise ValueError(
        f"None of these columns were found: {candidates}\n"
        f"Available columns are: {df.columns.tolist()}"
    )


def get_depth_column(df: pd.DataFrame) -> str:
    """
    Choose which depth column to use for the trajectory calculation.
    """
    if USE_CORRECTED_DEPTH:
        for col in ["corrected_depth_m"]:
            if col in df.columns:
                return col

    if "depth_m" in df.columns:
        return "depth_m"

    raise ValueError(
        "No usable depth column found. Expected one of: "
        "'corrected_depth_m'."
    )


def get_inclination_columns(df: pd.DataFrame) -> tuple[str, str]:
    """
    Return x/y inclination columns.

    Supports both naming styles:
        inclination_x, inclination_y
    and:
        inclination_x_deg, inclination_y_deg
    """
    x_col = get_first_existing_column(
        df,
        ["inclination_x_deg", "inclination_x"],
    )

    y_col = get_first_existing_column(
        df,
        ["inclination_y_deg", "inclination_y"],
    )

    return x_col, y_col

# ============================================================
# BOREHOLE POSITION HELPER
# ============================================================

def get_borehole_position_relative_to_cpt(gef) -> tuple[float, float]:
    """
    Return borehole x/y position relative to the CPT start point.

    CPT start point is treated as:
        x = 0
        y = 0

    If BOREHOLE_COORDINATE_MODE = "absolute":
        borehole_relative = borehole_absolute - CPT_absolute_from_GEF

    If BOREHOLE_COORDINATE_MODE = "relative":
        use manually specified relative coordinates.
    """
    if not SHOW_BOREHOLE:
        return np.nan, np.nan

    if BOREHOLE_COORDINATE_MODE == "relative":
        return BOREHOLE_X_RELATIVE, BOREHOLE_Y_RELATIVE

    if BOREHOLE_COORDINATE_MODE == "absolute":
        if gef.x is None or gef.y is None:
            raise ValueError(
                "BOREHOLE_COORDINATE_MODE is 'absolute', but the GEF file does not contain x/y coordinates."
            )

        borehole_x_relative = BOREHOLE_X_ABSOLUTE - gef.x
        borehole_y_relative = BOREHOLE_Y_ABSOLUTE - gef.y

        return borehole_x_relative, borehole_y_relative

    raise ValueError(
        "Invalid BOREHOLE_COORDINATE_MODE. Use 'absolute' or 'relative'."
    )

# ============================================================
# TRAJECTORY CALCULATION
# ============================================================

def calculate_cpt_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cumulative CPT x/y movement from x/y inclination.

    Assumption:
        dx = tan(inclination_x) * dz
        dy = tan(inclination_y) * dz

    where dz is the incremental depth step.
    """
    df = df.copy()

    depth_col = get_depth_column(df)
    inclination_x_col, inclination_y_col = get_inclination_columns(df)

    df = df.sort_values(depth_col).reset_index(drop=True)

    df["trajectory_depth_m"] = df[depth_col]
    df["delta_depth_m"] = df["trajectory_depth_m"].diff().fillna(0.0)

    inclination_x_rad = np.deg2rad(df[inclination_x_col].fillna(0.0))
    inclination_y_rad = np.deg2rad(df[inclination_y_col].fillna(0.0))

    df["delta_x_m"] = np.tan(inclination_x_rad) * df["delta_depth_m"]
    df["delta_y_m"] = np.tan(inclination_y_rad) * df["delta_depth_m"]

    df["x_movement_m"] = -df["delta_x_m"].cumsum() # It is negative because that means it is moving to the right on the x-y axis
    df["y_movement_m"] = df["delta_y_m"].cumsum()

    return df


def get_vertical_axis(df: pd.DataFrame):
    """
    Return vertical column, label, and whether to invert the axis.
    """
    if USE_ELEVATION_M_NAP and "elevation_m_nap" in df.columns:
        return "elevation_m_nap", "Elevation [m NAP]", False

    return "trajectory_depth_m", "Depth below CPT start [m]", True


# ============================================================
# PLOTTING HELPERS
# ============================================================

def save_or_close(filename: str):
    """
    Save and close current figure.
    """
    if SAVE_FIGURES:
        FIGURE_FOLDER.mkdir(parents=True, exist_ok=True)
        path = FIGURE_FOLDER / filename
        plt.savefig(path, dpi=300, bbox_inches="tight")
        print(f"Saved: {path}")

    if SHOW_FIGURES:
        plt.show()
    
    plt.close()


def add_borehole_interval_to_2d_x_plot(borehole_x, borehole_y):
    """
    Add borehole x-position to x-movement plot.

    The annotation also states the y-offset, because the borehole is not
    necessarily located on y = 0.
    """
    if not SHOW_BOREHOLE:
        return

    plt.axvline(
        x=borehole_x,
        linestyle="--",
        linewidth=2,
        label=(
            f"Borehole centre x = {borehole_x:.2f} m "
            f"(y offset = {borehole_y:.2f} m)"
        ),
    )

    plt.axvspan(
        borehole_x - BOREHOLE_RADIUS,
        borehole_x + BOREHOLE_RADIUS,
        alpha=0.15,
        label=f"Borehole x-range, radius = {BOREHOLE_RADIUS:.2f} m",
    )


def add_borehole_interval_to_2d_y_plot(borehole_x, borehole_y):
    """
    Add borehole y-position to y-movement plot.

    The annotation also states the x-offset.
    """
    if not SHOW_BOREHOLE:
        return

    plt.axvline(
        x=borehole_y,
        linestyle="--",
        linewidth=2,
        label=(
            f"Borehole centre y = {borehole_y:.2f} m "
            f"(x offset = {borehole_x:.2f} m)"
        ),
    )

    plt.axvspan(
        borehole_y - BOREHOLE_RADIUS,
        borehole_y + BOREHOLE_RADIUS,
        alpha=0.15,
        label=f"Borehole y-range, radius = {BOREHOLE_RADIUS:.2f} m",
    )


# ============================================================
# 2D PLOTS
# ============================================================

def plot_x_movement(df: pd.DataFrame, borehole_x: float, borehole_y: float):
    vertical_col, vertical_label, invert_y = get_vertical_axis(df)

    plt.figure(figsize=(6, 8))
    plt.plot(
        df["x_from_borehole_m"],
        df[vertical_col],
        label="CPT trajectory",
    )

    if SHOW_BOREHOLE:
        plt.axvline(
            x=0.0,
            linestyle="--",
            linewidth=2,
            label="Borehole centre x = 0.00 m",
        )

        plt.axvspan(
            -BOREHOLE_RADIUS,
            BOREHOLE_RADIUS,
            alpha=0.15,
            label=f"Borehole radius = {BOREHOLE_RADIUS:.2f} m",
        )

    plt.xlabel("CPT x-position relative to borehole centre [m]")
    plt.xlim(-2, 6.25)
    plt.ylabel(vertical_label)
    plt.title(
        f"{CPT_ID} x-position with depth\n"
        f"Borehole-centred coordinates | CPT start x = {-borehole_x:.2f} m"
    )
    plt.grid(True)
    plt.legend()

    if invert_y:
        plt.gca().invert_yaxis()

    plt.tight_layout()
    save_or_close(f"{FIGURE_BASENAME}_x_movement.png")

def plot_y_movement(df: pd.DataFrame, borehole_x: float, borehole_y: float):
    vertical_col, vertical_label, invert_y = get_vertical_axis(df)

    plt.figure(figsize=(6, 8))
    plt.plot(
        df["y_from_borehole_m"],
        df[vertical_col],
        label="CPT trajectory",
    )

    if SHOW_BOREHOLE:
        plt.axvline(
            x=0.0,
            linestyle="--",
            linewidth=2,
            label="Borehole centre y = 0.00 m",
        )

        plt.axvspan(
            -BOREHOLE_RADIUS,
            BOREHOLE_RADIUS,
            alpha=0.15,
            label=f"Borehole radius = {BOREHOLE_RADIUS:.2f} m",
        )

    plt.xlabel("CPT y-position relative to borehole centre [m]")
    plt.xlim(-2, 6.25)
    plt.ylabel(vertical_label)
    plt.title(
        f"{CPT_ID} y-position with depth\n"
        f"Borehole-centred coordinates | CPT start y = {-borehole_y:.2f} m"
    )
    plt.grid(True)
    plt.legend()

    if invert_y:
        plt.gca().invert_yaxis()

    plt.tight_layout()
    save_or_close(f"{FIGURE_BASENAME}_y_movement.png")


# ============================================================
# 3D PLOT WITH BOREHOLE CYLINDER
# ============================================================

def plot_3d_trajectory(df: pd.DataFrame, borehole_x: float, borehole_y: float):
    vertical_col, vertical_label, invert_z = get_vertical_axis(df)

    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot(
        df["x_from_borehole_m"],
        df["y_from_borehole_m"],
        df[vertical_col],
        linewidth=2,
        label="CPT trajectory",
    )

    if SHOW_BOREHOLE:
        z_min = df[vertical_col].min()
        z_max = df[vertical_col].max()

        theta = np.linspace(0, 2 * np.pi, 80)
        z_cyl = np.linspace(z_min, z_max, 60)

        theta_grid, z_grid = np.meshgrid(theta, z_cyl)

        x_cyl = BOREHOLE_RADIUS * np.cos(theta_grid)
        y_cyl = BOREHOLE_RADIUS * np.sin(theta_grid)

        ax.plot_surface(
            x_cyl,
            y_cyl,
            z_grid,
            alpha=0.30,
            linewidth=0,
        )

        ax.plot(
            [0.0, 0.0],
            [0.0, 0.0],
            [z_min, z_max],
            linestyle="--",
            linewidth=2,
            label="Borehole centreline",
        )

    ax.set_xlabel("x relative to borehole centre [m]")
    ax.set_xlim(-1, 6.25)
    ax.set_ylabel("y relative to borehole centre [m]")
    ax.set_ylim(-1.25, 1.25)
    ax.set_zlabel(vertical_label)
    ax.set_title(
        f"{CPT_ID} cone trajectory with borehole\n"
        f"Borehole-centred coordinates"
    )
    ax.view_init(elev=20, azim=-100)

    if invert_z:
        ax.invert_zaxis()

    ax.legend()
    plt.tight_layout()

    if SAVE_FIGURES:
        FIGURE_FOLDER.mkdir(parents=True, exist_ok=True)
        path = FIGURE_FOLDER / f"{FIGURE_BASENAME}_3d.png"
        plt.savefig(path, dpi=300, bbox_inches="tight")
        print(f"Saved: {path}")

    if SHOW_FIGURES:
        plt.show()

    plt.close()


# ============================================================
# OPTIONAL TOP VIEW
# ============================================================

def plot_top_view(df: pd.DataFrame, borehole_x: float, borehole_y: float):
    """
    Plot x-y top view with the borehole centre as origin.

    Coordinate system:
        Borehole centre = (0, 0)
        CPT start       = (-borehole_x, -borehole_y)
        CPT trajectory  = x_from_borehole_m, y_from_borehole_m
    """
    plt.figure(figsize=(7, 7))

    plt.plot(
        df["x_from_borehole_m"],
        df["y_from_borehole_m"],
        linewidth=2,
        label="CPT trajectory",
    )

    # CPT start location in borehole-centred coordinates
    plt.scatter(
        [-borehole_x],
        [-borehole_y],
        marker="o",
        s=60,
        label="CPT start",
    )

    if SHOW_BOREHOLE:
        theta = np.linspace(0, 2 * np.pi, 200)
        x_circle = BOREHOLE_RADIUS * np.cos(theta)
        y_circle = BOREHOLE_RADIUS * np.sin(theta)

        plt.plot(
            x_circle,
            y_circle,
            linewidth=2,
            label="Borehole wall",
        )

        plt.scatter(
            [0.0],
            [0.0],
            marker="x",
            s=80,
            label="Borehole centre",
        )

    plt.xlabel("x relative to borehole centre [m]")
    plt.ylabel("y relative to borehole centre [m]")
    plt.title(
        f"{CPT_ID} top view trajectory\n"
        f"Borehole-centred coordinates | "
        f"CPT start: x = {-borehole_x:.2f} m, y = {-borehole_y:.2f} m"
    )
    plt.axis("equal")
    plt.ylim(-2, 2)
    plt.xlim(-1, 6.25)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    save_or_close(f"{FIGURE_BASENAME}_top_view.png")


# ============================================================
# MAIN
# ============================================================

def main():
    gef = read_gef(GEF_FILE)
    df = gef.dataframe.copy()

    print("GEF metadata")
    print(f"  GEF file: {GEF_FILE}")
    print(f"  CPT ID: {CPT_ID}")
    print(f"  x header coordinate: {gef.x}")
    print(f"  y header coordinate: {gef.y}")
    print(f"  ground level [m NAP]: {gef.ground_level_m_nap}")
    print(f"  dataframe columns: {df.columns.tolist()}")

    df_traj = calculate_cpt_trajectory(df)

    borehole_x, borehole_y = get_borehole_position_relative_to_cpt(gef)

    df_traj["x_from_borehole_m"] = df_traj["x_movement_m"] - borehole_x
    df_traj["y_from_borehole_m"] = df_traj["y_movement_m"] - borehole_y

    df_traj["cpt_start_x_from_borehole_m"] = -borehole_x
    df_traj["cpt_start_y_from_borehole_m"] = -borehole_y
    df_traj["borehole_x_from_borehole_m"] = 0.0
    df_traj["borehole_y_from_borehole_m"] = 0.0
    df_traj["borehole_radius_m"] = BOREHOLE_RADIUS

    print("\nBorehole position relative to CPT start:")
    print(f"  borehole_x_relative = {borehole_x:.3f} m")
    print(f"  borehole_y_relative = {borehole_y:.3f} m")
    print(f"  borehole_radius      = {BOREHOLE_RADIUS:.3f} m")

    # Add absolute coordinates if GEF header x/y are available
    if gef.x is not None:
        df_traj["x_absolute_m"] = gef.x + df_traj["x_movement_m"]

    if gef.y is not None:
        df_traj["y_absolute_m"] = gef.y + df_traj["y_movement_m"]

    print("\nCalculated trajectory preview:")
    preview_cols = [
        "trajectory_depth_m",
        "x_movement_m",
        "y_movement_m",
    ]
    print(df_traj[preview_cols].head())

    plot_x_movement(df_traj, borehole_x, borehole_y)
    plot_y_movement(df_traj, borehole_x, borehole_y)
    plot_3d_trajectory(df_traj, borehole_x, borehole_y)
    plot_top_view(df_traj, borehole_x, borehole_y)

    df_traj["borehole_x_relative_m"] = borehole_x
    df_traj["borehole_y_relative_m"] = borehole_y
    df_traj["borehole_radius_m"] = BOREHOLE_RADIUS

    if EXPORT_EXCEL:
        df = remove_unnecessary_export_columns(df_traj)
        df.to_excel(EXPORT_FILE, index=False)
        print(f"Exported trajectory data: {EXPORT_FILE}")


if __name__ == "__main__":
    main()