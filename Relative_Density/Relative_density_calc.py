from pathlib import Path
import re

import numpy as np
import pandas as pd


# ============================================================
# USER SETTINGS
# ============================================================

INPUT_EXCEL = Path(
    r"C:\AA_Thesis\VSCode\lengkeek_vs_code\S1022749_CPTU2-2\layer_parameters\plaxis_soil_input.xlsx"
)

INPUT_CPT_CSV = Path(
    r"C:\AA_Thesis\VSCode\lengkeek_vs_code\S1022749_CPTU2-2\classified_points.csv"
)

CPT_ID = "CPT2-2"

OUTPUT_FOLDER = Path(CPT_ID)

# -------------------------------------------------------------------------
# Layer selection options
# -------------------------------------------------------------------------
# Options:
#   "bottom_true_sand" -> selects the deepest layer named exactly Sand 1, Sand 2, etc.
#   "by_name"          -> selects the layer with name equal to SELECTED_LAYER_NAME
#
# Examples:
#   LAYER_SELECTION_MODE = "bottom_true_sand"
#   SELECTED_LAYER_NAME = None
#
#   LAYER_SELECTION_MODE = "by_name"
#   SELECTED_LAYER_NAME = "Sand 1"
# -------------------------------------------------------------------------

LAYER_SELECTION_MODE = "by_name" 
SELECTED_LAYER_NAME = "Sand 1"
MAKE_OUTPUT_FILE = False

# Output filename automatically reflects selected layer
# If bottom_true_sand is used, the selected layer name is added after selection.
OUTPUT_CSV = None

# Unit weight of water
GAMMA_W = 10.0  # kN/m3

# cone radius
rc = 22.0  # mm

# Groundwater level in m NAP.
# Use None if the whole profile is below water.
# Use a number, for example -2.0, if you want a specific groundwater level.
WATER_LEVEL_M_NAP = None

# For this Qt calculation, stresses are positive compression magnitudes.
# PLAXIS-negative stress columns are added separately at the end.
MIN_SIGMA_V0_EFF_KPA = 1e-6


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


def safe_name_for_file(name):
    return (
        str(name)
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("&", "and")
    )


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

    This excludes:
        Silty sand 1
        Dense sand 1
        Sand mixtures 1
    """
    name = str(layer_name).strip()
    return re.fullmatch(r"Sand\s+\d+", name, flags=re.IGNORECASE) is not None


# ============================================================
# READ PLAXIS EXCEL
# ============================================================

def read_soil_layers(input_excel: Path) -> pd.DataFrame:
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
            "thickness_m": current_top - bottom_z,
            "is_true_sand": is_true_sand_layer(layer_name),
        })

        current_top = bottom_z

    layers = pd.DataFrame(layers)

    props = props.copy()
    props["name_norm"] = props["Name"].apply(normalise_layer_name)

    if "Unit weight (kN/m3)" not in props.columns:
        raise ValueError("Could not find 'Unit weight (kN/m3)' in Soil Properties.")

    props_small = props[["name_norm", "Unit weight (kN/m3)"]].copy()
    props_small = props_small.rename(columns={"Unit weight (kN/m3)": "gamma_kN_m3"})

    layers = layers.merge(
        props_small,
        on="name_norm",
        how="left",
    )

    layers["gamma_kN_m3"] = pd.to_numeric(layers["gamma_kN_m3"], errors="coerce")

    if layers["gamma_kN_m3"].isna().any():
        bad = layers[layers["gamma_kN_m3"].isna()][["layer_name", "gamma_kN_m3"]]
        raise ValueError(
            "Some layers have missing gamma values:\n"
            f"{bad}"
        )

    return layers


# ============================================================
# LAYER SELECTION
# ============================================================

def get_bottom_true_sand_layer(layers: pd.DataFrame) -> pd.Series:
    sand_layers = layers[layers["is_true_sand"]].copy()

    if sand_layers.empty:
        raise ValueError(
            "No layer named 'Sand x' was found. Expected names like 'Sand 1', 'Sand 2', etc."
        )

    deepest_idx = sand_layers["bottom_z"].idxmin()
    return layers.loc[deepest_idx]


def get_layer_by_name(layers: pd.DataFrame, selected_layer_name: str) -> pd.Series:
    selected_norm = normalise_layer_name(selected_layer_name)

    matches = layers[
        layers["layer_name"].apply(normalise_layer_name) == selected_norm
    ].copy()

    if matches.empty:
        available = layers[["layer_name", "top_z", "bottom_z"]].to_string(index=False)

        raise ValueError(
            f"Could not find selected layer '{selected_layer_name}'.\n\n"
            f"Available layers are:\n{available}"
        )

    if len(matches) > 1:
        raise ValueError(
            f"Multiple layers found with name '{selected_layer_name}'. "
            "Layer names should be unique in the PLAXIS input."
        )

    return matches.iloc[0]


def select_target_layer(
    layers: pd.DataFrame,
    selection_mode: str,
    selected_layer_name: str | None = None,
) -> pd.Series:
    if selection_mode == "bottom_true_sand":
        return get_bottom_true_sand_layer(layers)

    if selection_mode == "by_name":
        if selected_layer_name is None:
            raise ValueError(
                "SELECTED_LAYER_NAME must be given when LAYER_SELECTION_MODE = 'by_name'."
            )

        return get_layer_by_name(layers, selected_layer_name)

    raise ValueError(
        "LAYER_SELECTION_MODE must be either 'bottom_true_sand' or 'by_name'."
    )


def make_output_csv_path(
    output_folder: Path,
    cpt_id: str,
    selection_mode: str,
    selected_layer: pd.Series,
) -> Path:
    layer_file_name = safe_name_for_file(selected_layer["layer_name"])

    if selection_mode == "bottom_true_sand":
        return output_folder / f"{cpt_id}_bottom_sand_{layer_file_name}_Qt_Dr.csv"

    return output_folder / f"{cpt_id}_{layer_file_name}_Qt_Dr.csv"


# ============================================================
# STRESS CALCULATION
# ============================================================

def gamma_eff_at_z(layer: pd.Series, z: float) -> float:
    gamma = float(layer["gamma_kN_m3"])

    if WATER_LEVEL_M_NAP is None:
        return gamma - GAMMA_W

    if z <= WATER_LEVEL_M_NAP:
        return gamma - GAMMA_W

    return gamma


def sigma_v0_total_at_z(layers: pd.DataFrame, z: float) -> float:
    """
    Total vertical stress sigma_v0 at elevation z.

    Unit: kPa.
    Sign convention: positive compression magnitude.
    """
    ground_surface_z = float(layers["top_z"].iloc[0])

    if z >= ground_surface_z:
        return 0.0

    sigma_v0 = 0.0

    for _, layer in layers.iterrows():
        top_z = float(layer["top_z"])
        bottom_z = float(layer["bottom_z"])

        if z >= top_z:
            continue

        used_bottom = max(z, bottom_z)
        thickness = top_z - used_bottom

        if thickness > 0:
            sigma_v0 += float(layer["gamma_kN_m3"]) * thickness

        if z >= bottom_z:
            break

    return sigma_v0


def sigma_v0_eff_at_z(layers: pd.DataFrame, z: float) -> float:
    """
    Effective vertical stress sigma_v0_eff at elevation z.

    Unit: kPa.
    Sign convention: positive compression magnitude.
    """
    ground_surface_z = float(layers["top_z"].iloc[0])

    if z >= ground_surface_z:
        return 0.0

    sigma_v0_eff = 0.0

    for _, layer in layers.iterrows():
        top_z = float(layer["top_z"])
        bottom_z = float(layer["bottom_z"])

        if z >= top_z:
            continue

        used_bottom = max(z, bottom_z)
        thickness = top_z - used_bottom

        if thickness > 0:
            z_mid = 0.5 * (top_z + used_bottom)
            sigma_v0_eff += gamma_eff_at_z(layer, z_mid) * thickness

        if z >= bottom_z:
            break

    return sigma_v0_eff


# ============================================================
# CPT CSV READING
# ============================================================

def read_classified_points(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)

    required_cols = ["elevation_m_nap", "depth_m", "qt_mpa"]

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"classified_points.csv is missing required columns: {missing}\n"
            f"Available columns are: {df.columns.tolist()}"
        )

    df = df.copy()

    df["z_m_nap"] = pd.to_numeric(df["elevation_m_nap"], errors="coerce")
    df["depth_m"] = pd.to_numeric(df["depth_m"], errors="coerce")
    df["qt_mpa"] = pd.to_numeric(df["qt_mpa"], errors="coerce")
    df["qt_kPa"] = df["qt_mpa"] * 1000.0

    df = df.dropna(subset=["z_m_nap", "depth_m", "qt_kPa", "qc_mpa"])

    return df


# ============================================================
# MAIN CALCULATION
# ============================================================

def calculate_layer_qt_dr(
    classified_points: pd.DataFrame,
    layers: pd.DataFrame,
    selected_layer: pd.Series,
) -> pd.DataFrame:
    z_top = float(selected_layer["top_z"])
    z_bottom = float(selected_layer["bottom_z"])

    df = classified_points.copy()

    df = df[
        (df["z_m_nap"] <= z_top) &
        (df["z_m_nap"] >= z_bottom)
    ].copy()

    df = df.sort_values("z_m_nap", ascending=False).reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "No CPT points found inside the selected layer.\n"
            f"Selected layer: {selected_layer['layer_name']} "
            f"from NAP {z_top:.2f} m to {z_bottom:.2f} m."
        )

    df["selected_layer_name"] = selected_layer["layer_name"]
    df["selected_layer_top_z_m_nap"] = z_top
    df["selected_layer_bottom_z_m_nap"] = z_bottom
    df["selected_layer_gamma_kN_m3"] = float(selected_layer["gamma_kN_m3"])

    df["sigma_v0_kPa"] = df["z_m_nap"].apply(
        lambda z: sigma_v0_total_at_z(layers, float(z))
    )

    df["sigma_v0_eff_kPa"] = df["z_m_nap"].apply(
        lambda z: sigma_v0_eff_at_z(layers, float(z))
    )

    df["Qt"] = np.where(
        df["sigma_v0_eff_kPa"] > MIN_SIGMA_V0_EFF_KPA,
        (df["qt_kPa"] - df["sigma_v0_kPa"]) / df["sigma_v0_eff_kPa"],
        np.nan,
    )

    df["Dr"] = np.where(
        df["Qt"] >= 0.0,
        np.sqrt(df["Qt"] / 350.0),
        np.nan,
    )

    df["fs_kPa"] = df["fs_mpa"] * 1000.0
    df["qc_kPa"] = df["qc_mpa"] * 1000.0

    # Extra PLAXIS-sign columns for later use.
    # These are not used in the Qt formula.
    df["sigma_v0_plaxis_kPa"] = -df["sigma_v0_kPa"]
    df["sigma_v0_eff_plaxis_kPa"] = -df["sigma_v0_eff_kPa"]

    output_columns = [
        "selected_layer_name",
        "selected_layer_top_z_m_nap",
        "selected_layer_bottom_z_m_nap",
        "selected_layer_gamma_kN_m3",
        "z_m_nap",
        "depth_m",
        "qc_mpa",
        "qc_kPa",
        "qt_kPa",
        "sigma_v0_kPa",
        "sigma_v0_eff_kPa",
        "fs_kPa",
        "Qt",
        "Dr",
    ]

    return df[output_columns]


# ============================================================
# RUN
# ============================================================

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    layers = read_soil_layers(INPUT_EXCEL)

    selected_layer = select_target_layer(
        layers=layers,
        selection_mode=LAYER_SELECTION_MODE,
        selected_layer_name=SELECTED_LAYER_NAME,
    )

    print("\nSelected layer:")
    print(selected_layer[[
        "layer_name",
        "top_z",
        "bottom_z",
        "gamma_kN_m3",
        "is_true_sand",
    ]])

    classified_points = read_classified_points(INPUT_CPT_CSV)

    result = calculate_layer_qt_dr(
        classified_points=classified_points,
        layers=layers,
        selected_layer=selected_layer,
    )

    if MAKE_OUTPUT_FILE:
        OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

        if OUTPUT_CSV is None:
            output_csv = make_output_csv_path(
                output_folder=OUTPUT_FOLDER,
                cpt_id=CPT_ID,
                selection_mode=LAYER_SELECTION_MODE,
                selected_layer=selected_layer,
            )
        else:
            output_csv = Path(OUTPUT_CSV)

        result.to_csv(output_csv, index=False)

        print("\nSaved:")
        print(output_csv)
    else:
        print("\nMAKE_OUTPUT_FILE = False, so no output CSV file was created.")

    print("\nPreview:")
    print(result.head(15))

    print("\nSummary:")
    print(result[[
        "z_m_nap",
        "depth_m",
        "qc_kPa",
        "qt_kPa",
        "sigma_v0_kPa",
        "sigma_v0_eff_kPa",
        "fs_kPa",
        "Qt",
        "Dr",
    ]].describe())