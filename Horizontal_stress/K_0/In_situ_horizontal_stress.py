from pathlib import Path
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# USER SETTINGS
# ============================================================
# Values extracted from PLAXIS are effective stresses

INPUT_EXCEL = Path(r"C:\AA_Thesis\VSCode\lengkeek_vs_code\S1022749_CPTU2-4\layer_parameters\plaxis_soil_input.xlsx")

# CPT/output name
CPT_ID = "CPT2-4"

# Output
SAVE_FIGURE = True
FIGURE_FOLDER = Path(CPT_ID)
FIGURE_NAME = f"{CPT_ID}_deepest_sand_K0.png"

EXPORT_EXCEL = True
EXPORT_FILE = FIGURE_FOLDER / FIGURE_NAME.replace(".png", ".xlsx")

SHOW_PLOT = True
PLOT_EFFECTIVE_STRESS = True

# Unit weight of water
GAMMA_W = 10.0  # kN/m3

# If True, use gamma_eff = gamma - gamma_w below groundwater.
# If False, use gamma_eff = gamma everywhere.
USE_EFFECTIVE_UNIT_WEIGHT = True

# Groundwater level in m NAP.
# Use a number, for example -2.0.
# Use None if you want to assume the full profile is below water.
WATER_LEVEL_M_NAP = None

# If True, overwrite all Excel K0 values with K0_DEFAULT.
# If False, use K0x/K0y from Excel, with K0_DEFAULT only as fallback for missing values.
OVERWRITE_EXCEL_K0 = True

# K0 value used when OVERWRITE_EXCEL_K0 = True.
# Also used as fallback if OVERWRITE_EXCEL_K0 = False and K0x/K0y is missing.
K0_DEFAULT = 0.5

# Which horizontal stress to plot:
# "K0x" or "K0y"
K0_DIRECTION = "K0x"

# Vertical resolution for plotting
DZ = 0.02  # m


# ============================================================
# HELPERS
# ============================================================

def normalise_layer_name(name):
    return (
        str(name)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("&", "and")
        .replace("  ", " ")
    )


def safe_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return default


def first_existing_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def is_true_sand_layer(layer_name: str) -> bool:
    """
    Return True only for layers named exactly:
        Sand 1
        Sand 2
        Sand 3
        etc.

    This intentionally excludes:
        Silty sand 1
        Dense sand 1
        Sand mixtures 1
        Zand 1
    """
    name = str(layer_name).strip()
    return re.fullmatch(r"Sand\s+\d+", name, flags=re.IGNORECASE) is not None


# ============================================================
# READ SOIL PROFILE
# ============================================================

def read_soil_layers(input_excel: Path) -> pd.DataFrame:
    """
    Read layer top/bottom elevations and soil properties from plaxis_soil_input.xlsx.
    """
    profile = pd.read_excel(input_excel, sheet_name="OHE Ground Profile")
    props = pd.read_excel(input_excel, sheet_name="Soil Properties")

    name_col = first_existing_column(profile, ["Name", "layer_name", "Layer"])
    z_col = first_existing_column(profile, ["BH1", "z_level", "z", "Level"])

    if name_col is None or z_col is None:
        raise ValueError(
            "Could not identify layer name and elevation columns in OHE Ground Profile."
        )

    profile = profile[[name_col, z_col]].copy()
    profile.columns = ["name", "z"]
    profile = profile.dropna()

    top_row = profile[
        profile["name"].astype(str).str.strip().str.lower() == "top"
    ]

    if top_row.empty:
        raise ValueError("Could not find row named 'Top' in OHE Ground Profile.")

    ground_surface_z = float(top_row["z"].iloc[0])
    top_index = top_row.index[0]

    profile_layers = profile.loc[top_index + 1:].copy()
    profile_layers["z"] = profile_layers["z"].astype(float)

    layers = []
    current_top = ground_surface_z

    for _, row in profile_layers.iterrows():
        layer_name = row["name"]
        bottom_z = float(row["z"])

        layers.append({
            "layer_name": layer_name,
            "name_norm": normalise_layer_name(layer_name),
            "top_z": current_top,
            "bottom_z": bottom_z,
            "mid_z": 0.5 * (current_top + bottom_z),
            "thickness": current_top - bottom_z,
            "is_true_sand": is_true_sand_layer(layer_name),
        })

        current_top = bottom_z

    layers = pd.DataFrame(layers)

    props = props.copy()
    props["name_norm"] = props["Name"].apply(normalise_layer_name)

    property_cols = ["name_norm"]

    for col in [
        "Unit weight (kN/m3)",
        "K0x",
        "K0y",
        "K0",
        "K0x =K0y",
    ]:
        if col in props.columns:
            property_cols.append(col)

    layers = layers.merge(
        props[property_cols],
        on="name_norm",
        how="left",
    )

    if "Unit weight (kN/m3)" not in layers.columns:
        raise ValueError("Could not find 'Unit weight (kN/m3)' in Soil Properties.")

    layers = layers.rename(columns={
        "Unit weight (kN/m3)": "gamma",
    })

    # ------------------------------------------------------------
    # K0 handling
    # ------------------------------------------------------------
    if OVERWRITE_EXCEL_K0:
        layers["K0x_used"] = K0_DEFAULT
        layers["K0y_used"] = K0_DEFAULT
        layers["K0_source"] = f"manual overwrite: K0_DEFAULT = {K0_DEFAULT}"

    else:
        if "K0x" in layers.columns:
            layers["K0x_used"] = layers["K0x"].apply(lambda x: safe_float(x, np.nan))
        else:
            layers["K0x_used"] = np.nan

        if "K0y" in layers.columns:
            layers["K0y_used"] = layers["K0y"].apply(lambda x: safe_float(x, np.nan))
        else:
            layers["K0y_used"] = np.nan

        layers["K0x_used"] = layers["K0x_used"].fillna(K0_DEFAULT)
        layers["K0y_used"] = layers["K0y_used"].fillna(K0_DEFAULT)

        layers["K0_source"] = "Excel K0 values; K0_DEFAULT only used as fallback"

    return layers


# ============================================================
# DEEPEST TRUE SAND LAYER SELECTION
# ============================================================

def get_deepest_true_sand_layer(layers: pd.DataFrame) -> pd.Series:
    """
    Select the deepest true Sand x layer.

    Deepest means the Sand x layer with the lowest bottom_z.
    """
    sand_layers = layers[layers["is_true_sand"]].copy()

    if sand_layers.empty:
        raise ValueError(
            "No layer named 'Sand x' was found. Expected names like 'Sand 1', 'Sand 2', etc."
        )

    deepest_idx = sand_layers["bottom_z"].idxmin()
    return layers.loc[deepest_idx]


# ============================================================
# STRESS CALCULATION
# ============================================================

def gamma_effective_at_z(layer, z):
    """
    Return effective unit weight at elevation z.
    """
    gamma = float(layer["gamma"])

    if not USE_EFFECTIVE_UNIT_WEIGHT:
        return gamma

    if WATER_LEVEL_M_NAP is None:
        return gamma - GAMMA_W

    if z <= WATER_LEVEL_M_NAP:
        return gamma - GAMMA_W

    return gamma


def get_layer_at_z(layers, z):
    matches = layers[
        (z <= layers["top_z"]) &
        (z >= layers["bottom_z"])
    ]

    if not matches.empty:
        return matches.iloc[0]

    nearest_idx = (layers["mid_z"] - z).abs().idxmin()
    return layers.loc[nearest_idx]


def sigma_v_eff_at_z(layers, z):
    """
    Calculate vertical effective stress at elevation z.

    Important:
    This integrates the full soil column above z.
    So the stress inside the deepest sand layer still includes the overburden
    from all layers above it.
    """
    ground_surface_z = float(layers["top_z"].iloc[0])

    if z >= ground_surface_z:
        return 0.0

    sigma_v = 0.0

    for _, layer in layers.iterrows():
        top_z = float(layer["top_z"])
        bottom_z = float(layer["bottom_z"])

        if z >= top_z:
            continue

        used_bottom = max(z, bottom_z)
        thickness = top_z - used_bottom

        if thickness > 0:
            z_mid = 0.5 * (top_z + used_bottom)
            gamma_eff = gamma_effective_at_z(layer, z_mid)
            sigma_v += gamma_eff * thickness

        if z >= bottom_z:
            break

    return sigma_v


def calculate_horizontal_stress_in_layer(layers, target_layer):
    """
    Calculate vertical and horizontal stress inside the selected target layer.

    If PLOT_EFFECTIVE_STRESS = True:
        uses effective vertical stress sigma'_v
        and calculates sigma'_h = K0 * sigma'_v

    If PLOT_TOTAL_STRESS = True:
        uses total vertical stress sigma_v
        and calculates sigma_h = K0 * sigma_v
    """
    z_top = float(target_layer["top_z"])
    z_bottom = float(target_layer["bottom_z"])

    z_values = np.arange(z_top, z_bottom - DZ, -DZ)

    rows = []

    for z in z_values:
        layer = get_layer_at_z(layers, z)

        if K0_DIRECTION == "K0x":
            K0 = float(layer["K0x_used"])
        elif K0_DIRECTION == "K0y":
            K0 = float(layer["K0y_used"])
        else:
            raise ValueError("K0_DIRECTION must be 'K0x' or 'K0y'.")

        base_row = {
            "z_m_nap": z,
            "depth_below_surface_m": float(layers["top_z"].iloc[0]) - z,
            "layer_name": layer["layer_name"],
            "target_layer_name": target_layer["layer_name"],
            "target_layer_top_z": z_top,
            "target_layer_bottom_z": z_bottom,
            "gamma_kN_m3": layer["gamma"],
            "K0_used": K0,
            "K0_source": layer["K0_source"],
        }

        if PLOT_EFFECTIVE_STRESS:
            sigma_v_eff = sigma_v_eff_at_z(layers, z)
            sigma_h_eff = K0 * sigma_v_eff

            row = base_row.copy()
            row.update({
                "stress_type": "effective",
                "sigma_v_kPa": sigma_v_eff,
                "sigma_h_kPa": sigma_h_eff,
            })
            rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# PLOTTING
# ============================================================

def plot_horizontal_stress_deepest_sand(df_stress, target_layer):
    plt.figure(figsize=(6, 9))

    for stress_type, df_part in df_stress.groupby("stress_type"):
        if stress_type == "effective":
            label = r"$\sigma'_h = K_0 \cdot \sigma'_v$"
        elif stress_type == "total":
            label = r"$\sigma_h = K_0 \cdot \sigma_v$"
        else:
            label = stress_type

        plt.plot(
            df_part["sigma_h_kPa"],
            df_part["z_m_nap"],
            linewidth=2,
            label=label,
        )

    plt.axhline(
        target_layer["top_z"],
        linestyle="--",
        linewidth=1.2,
        label=f"Top {target_layer['layer_name']}",
    )

    plt.axhline(
        target_layer["bottom_z"],
        linestyle="--",
        linewidth=1.2,
        label=f"Bottom {target_layer['layer_name']}",
    )

    if PLOT_EFFECTIVE_STRESS:
        xlabel = "Horizontal effective stress $\\sigma'_h$ [kPa]"
        title_type = "Horizontal effective stress"
    else:
        raise ValueError(
            "At least one of PLOT_EFFECTIVE_STRESS or PLOT_TOTAL_STRESS must be True."
        )

    plt.xlabel(xlabel)
    plt.ylabel("Elevation [m NAP]")
    plt.title(
        f"{title_type} in deepest Sand layer\n"
        f"{target_layer['layer_name']} | "
        f"NAP {target_layer['top_z']:.2f} to {target_layer['bottom_z']:.2f} m"
    )

    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    if SAVE_FIGURE:
        FIGURE_FOLDER.mkdir(parents=True, exist_ok=True)
        fig_path = FIGURE_FOLDER / FIGURE_NAME
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        print(f"Saved figure: {fig_path}")

    if SHOW_PLOT:
        plt.show()

    plt.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    FIGURE_FOLDER.mkdir(parents=True, exist_ok=True)

    layers = read_soil_layers(INPUT_EXCEL)

    print("Soil layers:")
    print(layers[[
        "layer_name",
        "top_z",
        "bottom_z",
        "gamma",
        "K0x_used",
        "K0y_used",
        "K0_source",
        "is_true_sand",
    ]])

    deepest_sand_layer = get_deepest_true_sand_layer(layers)

    print("\nSelected deepest true Sand layer:")
    print(deepest_sand_layer[[
        "layer_name",
        "top_z",
        "bottom_z",
        "gamma",
        "K0x_used",
        "K0y_used",
        "K0_source",
    ]])

    df_stress = calculate_horizontal_stress_in_layer(
        layers,
        deepest_sand_layer,
    )

    print("\nHorizontal stress in deepest true Sand layer preview:")
    print(df_stress.head())

    plot_horizontal_stress_deepest_sand(
        df_stress,
        deepest_sand_layer,
    )

    if EXPORT_EXCEL:
        EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df_stress.to_excel(EXPORT_FILE, index=False)
        print(f"Exported stress profile: {EXPORT_FILE}")