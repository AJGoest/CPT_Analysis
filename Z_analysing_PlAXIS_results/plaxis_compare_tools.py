"""
plaxis_compare_tools.py

Reusable tools for comparing PLAXIS Excel result files from different:
- constitutive models;
- borehole radii;
- calculation phases.

The module assumes the PLAXIS Excel files contain phase sheets named:
    phase_0, phase_1, ..., phase_n

and columns such as:
    x, y, z,
    sigx, sigy, sigxy,
    epsx, epsy, epsxy,
    distance_from_wall,
    radius_from_centre,
    layer_name,
    layer_index.

Main comparison modes:
    models_one_radius : compare different models at one radius and one phase
    radii_one_model   : compare different radii for one model and one phase
    phases_one_model  : compare different phases for one selected result file
    custom            : user-defined result IDs and phases
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# DEFAULT DEFINITIONS
# ============================================================

DEFAULT_COMPONENTS = {
    "radial_stress": {
        "column": "sig_rr",
        "ylabel": "Radial stress σrr [kPa]",
        "title": "Radial stress",
    },
    "hoop_stress": {
        "column": "sig_tt",
        "ylabel": "Hoop stress σθθ [kPa]",
        "title": "Hoop stress",
    },
    "radial_shear_stress": {
        "column": "tau_rt",
        "ylabel": "Radial shear stress τrθ [kPa]",
        "title": "Radial shear stress",
    },
    "radial_strain": {
        "column": "eps_rr",
        "ylabel": "Radial strain εrr [-]",
        "title": "Radial strain",
    },
    "hoop_strain": {
        "column": "eps_tt",
        "ylabel": "Hoop strain εθθ [-]",
        "title": "Hoop strain",
    },
    "radial_shear_strain": {
        "column": "eps_rt",
        "ylabel": "Radial shear strain εrθ [-]",
        "title": "Radial shear strain",
    },
    "vertical_stress": {
        "column": "sig_zz",
        "ylabel": "Vertical stress σzz [kPa]",
        "title": "Vertical stress",
    }
}

DEFAULT_X_AXES = {
    "distance_from_wall": {
        "column": "distance_from_wall",
        "xlabel": "Distance from borehole wall [m]",
    },
    "radius_from_centre": {
        "column": "radius_from_centre",
        "xlabel": "Radius from borehole centre [m]",
    },
    "r_over_R": {
        "column": "r_over_R",
        "xlabel": "Normalised radius r/R [-] from borehole centre",
    },
}


# ============================================================
# FILE DISCOVERY AND METADATA
# ============================================================

def infer_model_from_filename(filename: Union[str, Path]) -> str:
    """
    Infer constitutive model from the filename.

    Edit this function if future file names use different model identifiers.
    """
    name = Path(filename).name.lower()

    if "sanisand" in name or "sani" in name:
        return "SANISAND"

    if "_mc_" in name or "mohr" in name or "coulomb" in name:
        return "Mohr-Coulomb"

    if "linear" in name or "_le_" in name:
        return "Linear Elastic"

    return "Unknown model"


def infer_short_model_code(model_name: str) -> str:
    """Return a compact model code for result IDs."""
    mapping = {
        "Linear Elastic": "Linear",
        "Mohr-Coulomb": "MC",
        "SANISAND": "SANISAND",
    }
    return mapping.get(model_name, str(model_name).replace(" ", "_"))


def infer_radius_from_filename(filename: Union[str, Path]) -> float:
    """
    Extract radius from filename patterns such as:
    - R0.45
    - R0.25
    - R1.00

    Returns np.nan if no radius is found.
    """
    name = Path(filename).stem
    match = re.search(r"R([0-9]+(?:\.[0-9]+)?)", name, flags=re.IGNORECASE)

    if match:
        return float(match.group(1))

    return np.nan

def infer_eini_from_filename(filename: Union[str, Path]) -> float:
    """
    Extract initial void ratio eini from filename patterns such as:
        eini_0p65
        eini_0.65
        eInit_0p65
        e_init_0p65

    Returns np.nan if no eini value is found.
    """
    name = Path(filename).stem.lower()

    patterns = [
        r"eini[_\- ]*([0-9]+(?:p[0-9]+|\.[0-9]+)?)",
        r"einit[_\- ]*([0-9]+(?:p[0-9]+|\.[0-9]+)?)",
        r"e_init[_\- ]*([0-9]+(?:p[0-9]+|\.[0-9]+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)

        if match:
            value_text = match.group(1).replace("p", ".")
            return float(value_text)

    return np.nan


def format_eini_for_id(eini: float) -> str:
    """Return filesystem/result_id-safe eini text."""
    return f"eini_{eini:.3f}".replace(".", "p")


def scan_result_files(
    results_folder: Union[str, Path] = ".",
    file_pattern: str = "*PLAXIS_results_R*.xlsx",
) -> pd.DataFrame:
    """
    Scan a folder for PLAXIS Excel result files and build a run catalogue.

    Returns a dataframe with:
        result_id, path, filename, model, radius, eini, plot_label

    If eini is present in the filename, it is included in result_id and plot_label.
    If eini is absent, the old behaviour is preserved.
    """
    results_folder = Path(results_folder)
    files = sorted(results_folder.glob(file_pattern))

    records = []

    for file in files:
        model = infer_model_from_filename(file.name)
        radius = infer_radius_from_filename(file.name)
        eini = infer_eini_from_filename(file.name)
        model_code = infer_short_model_code(model)

        result_id_parts = [model_code]
        plot_label_parts = [model]

        if np.isfinite(radius):
            result_id_parts.append(f"R{radius:.2f}")
            plot_label_parts.append(f"R = {radius:.2f} m")

        if np.isfinite(eini):
            result_id_parts.append(format_eini_for_id(eini))
            plot_label_parts.append(rf"$e_{{ini}}$ = {eini:.3f}")

        result_id = "_".join(result_id_parts)
        plot_label = ", ".join(plot_label_parts)

        # Ensure unique IDs if duplicate names or unknown models occur.
        original_result_id = result_id
        duplicate_counter = 2
        existing_ids = {record["result_id"] for record in records}

        while result_id in existing_ids:
            result_id = f"{original_result_id}_{duplicate_counter}"
            duplicate_counter += 1

        records.append(
            {
                "result_id": result_id,
                "path": file,
                "filename": file.name,
                "model": model,
                "radius": radius,
                "eini": eini,
                "plot_label": plot_label,
            }
        )

    return pd.DataFrame(records)


def get_phase_names(path: Union[str, Path]) -> List[str]:
    """Return phase sheet names from a PLAXIS Excel result file."""
    xls = pd.ExcelFile(path)

    phase_names = [
        sheet for sheet in xls.sheet_names
        if sheet.startswith("phase_")
    ]

    phase_names = sorted(phase_names, key=lambda s: int(s.split("_")[1]))

    return phase_names


def add_available_phases_to_catalogue(run_catalogue: pd.DataFrame) -> pd.DataFrame:
    """Add an available_phases column to the run catalogue."""
    catalogue = run_catalogue.copy()

    if catalogue.empty:
        return catalogue

    catalogue["available_phases"] = catalogue["path"].apply(get_phase_names)
    catalogue["first_phase"] = catalogue["available_phases"].apply(lambda x: x[0] if x else None)
    catalogue["last_phase"] = catalogue["available_phases"].apply(lambda x: x[-1] if x else None)

    return catalogue


def update_plot_label(
    run_catalogue: pd.DataFrame,
    result_id: str,
    new_label: str,
) -> pd.DataFrame:
    """Return a copy of the catalogue with one plot label changed."""
    catalogue = run_catalogue.copy()
    catalogue.loc[catalogue["result_id"] == result_id, "plot_label"] = new_label
    return catalogue


# ============================================================
# COMPARISON RESOLUTION
# ============================================================

def resolve_comparison(
    run_catalogue: pd.DataFrame,
    comparison: dict,
) -> Tuple[List[str], List[str]]:
    """
    Resolve a comparison dictionary into:
        selected_result_ids, selected_phases

    Supported comparison modes:
        models_one_radius
        radii_one_model
        phases_one_model
        custom
    """
    mode = comparison.get("mode", "models_one_radius")

    if mode == "models_one_radius":
        radius = float(comparison["radius"])
        selected = run_catalogue[np.isclose(run_catalogue["radius"], radius)].copy()

        if selected.empty:
            raise ValueError(
                f"No files found for radius {radius}. "
                f"Available radii: {sorted(run_catalogue['radius'].dropna().unique())}"
            )

        preferred_order = {
            "Linear Elastic": 1,
            "Mohr-Coulomb": 2,
            "SANISAND": 3,
        }
        selected["sort_order"] = selected["model"].map(preferred_order).fillna(99)
        selected = selected.sort_values(["sort_order", "result_id"])

        result_ids = selected["result_id"].to_list()
        phases = [comparison.get("phase", "phase_11")]
        return result_ids, phases

    if mode == "radii_one_model":
        model = comparison["model"]
        selected = run_catalogue[run_catalogue["model"] == model].copy()

        if selected.empty:
            raise ValueError(
                f"No files found for model {model}. "
                f"Available models: {sorted(run_catalogue['model'].dropna().unique())}"
            )

        selected = selected.sort_values("radius")
        result_ids = selected["result_id"].to_list()
        phases = [comparison.get("phase", "phase_11")]
        return result_ids, phases

    if mode == "phases_one_model":
        result_id = comparison["result_id"]

        if result_id not in run_catalogue["result_id"].to_list():
            raise ValueError(
                f"Unknown result_id: {result_id}. "
                f"Available result IDs: {run_catalogue['result_id'].to_list()}"
            )

        phases = comparison.get("phases", None)
        if phases is None:
            path = run_catalogue.loc[run_catalogue["result_id"] == result_id, "path"].iloc[0]
            phases = get_phase_names(path)

        return [result_id], list(phases)

    if mode == "custom":
        result_ids = comparison.get("result_ids", [])
        phases = comparison.get("phases", [comparison.get("phase", "phase_11")])

        missing = [
            result_id
            for result_id in result_ids
            if result_id not in run_catalogue["result_id"].to_list()
        ]

        if missing:
            raise ValueError(
                f"Unknown result IDs: {missing}. "
                f"Available result IDs: {run_catalogue['result_id'].to_list()}"
            )

        return list(result_ids), list(phases)

    raise ValueError(
        "comparison['mode'] must be one of: "
        "'models_one_radius', 'radii_one_model', 'phases_one_model', 'custom'."
    )


# ============================================================
# LOADING AND TRANSFORMING PLAXIS DATA
# ============================================================

def infer_radius_from_dataframe(df: pd.DataFrame) -> float:
    """
    Infer borehole radius from:
        radius_from_centre - distance_from_wall
    """
    return float((df["radius_from_centre"] - df["distance_from_wall"]).median())


def check_required_columns(
    df: pd.DataFrame,
    required_columns: Sequence[str],
    context: str = "",
) -> None:
    """Raise an informative error if required columns are missing."""
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        msg = f"Missing required columns: {missing}"
        if context:
            msg += f" | Context: {context}"
        raise ValueError(msg)


def load_result_phases(
    run_catalogue: pd.DataFrame,
    result_ids: Sequence[str],
    phases: Sequence[str],
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """
    Load selected result IDs and selected phase sheets.

    Returns:
        dict[(result_id, phase)] = dataframe
    """
    loaded = {}

    for result_id in result_ids:
        row = run_catalogue[run_catalogue["result_id"] == result_id]

        if row.empty:
            raise ValueError(f"Unknown result_id: {result_id}")

        row = row.iloc[0]
        path = row["path"]
        available_phases = get_phase_names(path)

        for phase in phases:
            if phase not in available_phases:
                raise ValueError(
                    f"{phase} not found in {Path(path).name}. "
                    f"Available phases: {available_phases}"
                )

            df = pd.read_excel(path, sheet_name=phase)
            df["result_id"] = result_id
            df["phase"] = phase
            df["model"] = row["model"]
            df["radius_from_filename"] = row["radius"]
            df["plot_label"] = row["plot_label"]
            df["filename"] = row["filename"]

            loaded[(result_id, phase)] = df

    return loaded


def transform_stress_strain_to_polar(
    df: pd.DataFrame,
    *,
    stress_compression_positive: bool = True,
    strain_compression_positive: bool = True,
    shear_strain_convention: str = "tensor",
    z_round_decimals: int = 3,
) -> pd.DataFrame:
    """
    Add polar coordinates and polar stress/strain components.

    Stress:
        sigx, sigy, sigxy  -> sig_rr, sig_tt, tau_rt

    Strain:
        epsx, epsy, epsxy  -> eps_rr, eps_tt, eps_rt

    Notes:
    - sig_tt is hoop/circumferential stress.
    - eps_tt is hoop/circumferential strain.
    - PLAXIS stresses are often compression negative, so the default
      converts them to compression positive.
    """
    required = [
        "x", "y", "z",
        "sigx", "sigy", "sigxy",
        "epsx", "epsy", "epsxy",
        "distance_from_wall", "radius_from_centre",
        "layer_name",
    ]
    check_required_columns(df, required, context=f"{df.get('filename', pd.Series(['unknown'])).iloc[0]}")

    df = df.copy()

    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)

    theta = np.arctan2(y, x)
    r = np.sqrt(x**2 + y**2)

    c = np.cos(theta)
    s = np.sin(theta)

    sigx = df["sigx"].to_numpy(dtype=float)
    sigy = df["sigy"].to_numpy(dtype=float)
    sigz = df["sigz"].to_numpy(dtype=float) 
    sigxy = df["sigxy"].to_numpy(dtype=float)

    epsx = df["epsx"].to_numpy(dtype=float)
    epsy = df["epsy"].to_numpy(dtype=float)
    epsxy_raw = df["epsxy"].to_numpy(dtype=float)

    if shear_strain_convention == "tensor":
        epsxy_tensor = epsxy_raw
    elif shear_strain_convention == "engineering":
        epsxy_tensor = epsxy_raw / 2.0
    else:
        raise ValueError("shear_strain_convention must be 'tensor' or 'engineering'.")

    # Stress tensor transformation
    sig_rr = sigx * c**2 + sigy * s**2 + 2 * sigxy * s * c
    sig_tt = sigx * s**2 + sigy * c**2 - 2 * sigxy * s * c
    tau_rt = (sigy - sigx) * s * c + sigxy * (c**2 - s**2)

    # Strain tensor transformation
    eps_rr = epsx * c**2 + epsy * s**2 + 2 * epsxy_tensor * s * c
    eps_tt = epsx * s**2 + epsy * c**2 - 2 * epsxy_tensor * s * c
    eps_rt = (epsy - epsx) * s * c + epsxy_tensor * (c**2 - s**2)

    if stress_compression_positive:
        sig_rr = -sig_rr
        sig_tt = -sig_tt
        tau_rt = -tau_rt
        sig_zz = -sigz

    if strain_compression_positive:
        eps_rr = -eps_rr
        eps_tt = -eps_tt
        eps_rt = -eps_rt

    radius_inferred = infer_radius_from_dataframe(df)

    df["theta"] = theta
    df["r"] = r
    df["R_inferred"] = radius_inferred
    df["r_over_R"] = r / radius_inferred
    df["z_round"] = df["z"].round(z_round_decimals)

    df["sig_rr"] = sig_rr
    df["sig_tt"] = sig_tt
    df["tau_rt"] = tau_rt
    df["sig_zz"] = sig_zz

    df["eps_rr"] = eps_rr
    df["eps_tt"] = eps_tt
    df["eps_rt"] = eps_rt

    return df


def transform_loaded_results(
    loaded_results: Dict[Tuple[str, str], pd.DataFrame],
    *,
    stress_compression_positive: bool = True,
    strain_compression_positive: bool = True,
    shear_strain_convention: str = "tensor",
    z_round_decimals: int = 3,
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """Transform all loaded result dataframes to polar stress/strain components."""
    return {
        key: transform_stress_strain_to_polar(
            df,
            stress_compression_positive=stress_compression_positive,
            strain_compression_positive=strain_compression_positive,
            shear_strain_convention=shear_strain_convention,
            z_round_decimals=z_round_decimals,
        )
        for key, df in loaded_results.items()
    }


# ============================================================
# LAYER AND DEPTH SELECTION
# ============================================================

def create_layer_depth_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a layer/depth summary from one transformed result dataframe.

    Depth points are numbered shallow to deep within each layer.
    """
    group_cols = ["layer_name", "z_round"]

    if "layer_index" in df.columns:
        group_cols = ["layer_index"] + group_cols
    else:
        df = df.copy()
        layer_order = {name: i + 1 for i, name in enumerate(pd.unique(df["layer_name"]))}
        df["layer_index"] = df["layer_name"].map(layer_order)
        group_cols = ["layer_index", "layer_name", "z_round"]

    summary = (
        df.groupby(group_cols, as_index=False)
        .agg(
            n_points=("distance_from_wall", "count"),
            min_distance_from_wall=("distance_from_wall", "min"),
            max_distance_from_wall=("distance_from_wall", "max"),
            min_radius_from_centre=("radius_from_centre", "min"),
            max_radius_from_centre=("radius_from_centre", "max"),
        )
        .sort_values(["layer_index", "z_round"], ascending=[True, False])
    )

    summary["depth_point"] = summary.groupby("layer_index").cumcount() + 1

    # User-facing order
    summary = summary[
        [
            "layer_index",
            "layer_name",
            "depth_point",
            "z_round",
            "n_points",
            "min_distance_from_wall",
            "max_distance_from_wall",
            "min_radius_from_centre",
            "max_radius_from_centre",
        ]
    ]

    return summary


def print_layer_depth_summary(summary: pd.DataFrame) -> None:
    """Print a readable layer/depth selection table."""
    print("Available soil layers and PLAXIS measurement depth points")
    print("Depth point numbering is shallow to deep within each layer.\n")

    for layer_index, df_layer in summary.groupby("layer_index", sort=True):
        layer_name = df_layer["layer_name"].iloc[0]
        print(f"[{int(layer_index)}] {layer_name}")

        for _, row in df_layer.iterrows():
            print(
                f"    point {int(row['depth_point'])}: "
                f"z = {row['z_round']:.3f} m | "
                f"{int(row['n_points'])} radial points | "
                f"distance from wall = {row['min_distance_from_wall']:.3f} to "
                f"{row['max_distance_from_wall']:.3f} m"
            )

        print()


def normalise_name(value: object) -> str:
    """Normalize a layer name for comparison."""
    return str(value).strip().lower().replace("_", " ")


def resolve_layer(summary: pd.DataFrame, selected_layer: Union[str, int]) -> Tuple[int, str]:
    """
    Resolve selected layer by:
    - integer layer index;
    - exact layer name;
    - 'auto_bottom_sand';
    - 'auto_deepest'.
    """
    unique_layers = (
        summary[["layer_index", "layer_name"]]
        .drop_duplicates()
        .sort_values("layer_index")
    )

    if isinstance(selected_layer, (int, np.integer)):
        matches = unique_layers[unique_layers["layer_index"] == int(selected_layer)]

    elif selected_layer == "auto_bottom_sand":
        sand_layers = unique_layers[
            unique_layers["layer_name"].str.lower().str.contains("sand", na=False)
        ]

        if sand_layers.empty:
            raise ValueError("No layer containing the word 'sand' was found.")

        matches = sand_layers.sort_values("layer_index").tail(1)

    elif selected_layer == "auto_deepest":
        matches = unique_layers.sort_values("layer_index").tail(1)

    else:
        selected_norm = normalise_name(selected_layer)
        matches = unique_layers[
            unique_layers["layer_name"].apply(normalise_name) == selected_norm
        ]

    if matches.empty:
        raise ValueError(
            f"Could not resolve selected_layer = {selected_layer}.\n"
            f"Available layers:\n{unique_layers.to_string(index=False)}"
        )

    return int(matches["layer_index"].iloc[0]), matches["layer_name"].iloc[0]


def resolve_depths(
    summary: pd.DataFrame,
    selected_layer_index: int,
    selected_depth_point: Union[str, int],
) -> List[float]:
    """
    Resolve selected depth point(s) to z-values.

    selected_depth_point can be:
        integer
        'all'
        'shallowest'
        'deepest'
        'middle'
    """
    df_layer = summary[summary["layer_index"] == selected_layer_index].copy()

    if df_layer.empty:
        raise ValueError(f"No depths found for layer index {selected_layer_index}.")

    df_layer = df_layer.sort_values("z_round", ascending=False)

    if selected_depth_point == "all":
        return df_layer["z_round"].astype(float).to_list()

    if selected_depth_point == "shallowest":
        return [float(df_layer["z_round"].iloc[0])]

    if selected_depth_point == "deepest":
        return [float(df_layer["z_round"].iloc[-1])]

    if selected_depth_point == "middle":
        values = df_layer["z_round"].astype(float).to_list()
        return [values[len(values) // 2]]

    matches = df_layer[df_layer["depth_point"] == int(selected_depth_point)]

    if matches.empty:
        raise ValueError(
            f"Depth point {selected_depth_point} not found for layer index {selected_layer_index}.\n"
            f"Available depth points:\n"
            f"{df_layer[['depth_point', 'z_round']].to_string(index=False)}"
        )

    return [float(matches["z_round"].iloc[0])]


# ============================================================
# PLOTTING
# ============================================================

def force_stress_axis_to_zero(component: str) -> bool:
    """Return True for stress plots where the y-axis should include/go to zero."""
    return component in [
        "radial_stress",
        "hoop_stress",
        "radial_shear_stress",
    ]

def make_safe_filename(text: object) -> str:
    """Convert plot text into a safe filename fragment."""
    text = str(text).replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_\.\-]+", "", text)


def filter_result_for_layer_depth(
    df: pd.DataFrame,
    selected_layer_name: str,
    selected_z: float,
    *,
    z_round_decimals: int = 3,
) -> pd.DataFrame:
    """Filter a dataframe by layer and rounded z-level."""
    return df[
        (df["layer_name"] == selected_layer_name)
        & (np.isclose(df["z_round"], selected_z, atol=10 ** (-z_round_decimals)))
    ].copy()


def build_line_label(
    df_plot: pd.DataFrame,
    comparison_mode: str,
    result_id: str,
    phase: str,
) -> str:
    """Build a readable legend label depending on comparison mode."""
    base_label = df_plot["plot_label"].iloc[0] if "plot_label" in df_plot.columns else result_id

    if comparison_mode == "phases_one_model":
        load_factor = None
        if "load_factor" in df_plot.columns and df_plot["load_factor"].notna().any():
            load_factor = float(df_plot["load_factor"].dropna().iloc[0])

        if load_factor is not None:
            return f"{phase}, LF={load_factor:.2f}"

        return phase

    return base_label


def build_radius_part(comparison: dict) -> str:
    """
    Build a compact radius description for plot subtitles.

    This avoids repeating the x-axis name in the title when the x-axis label
    already states, for example, 'Distance from borehole wall [m]'.
    """
    mode = comparison.get("mode", "")

    if mode == "models_one_radius":
        radius = comparison.get("radius", None)
        if radius is not None:
            return f"R = {float(radius):.2f} m"
        return "one radius"

    if mode == "radii_one_model":
        model = comparison.get("model", "selected model")
        return f"{model}, multiple radii"

    if mode == "phases_one_model":
        result_id = comparison.get("result_id", "selected result")
        # result_id usually contains the radius, e.g. MC_R0.45.
        return str(result_id)

    if mode == "custom":
        result_ids = comparison.get("result_ids", [])
        if len(result_ids) == 1:
            return str(result_ids[0])

        if len(result_ids) > 1:
            # Extract radius fragments such as R0.45 where possible.
            radii = []
            for result_id in result_ids:
                match = re.search(r"R([0-9]+(?:\.[0-9]+)?)", str(result_id))
                if match:
                    radii.append(float(match.group(1)))

            if radii:
                unique_radii = sorted(set(radii))
                if len(unique_radii) == 1:
                    return f"R = {unique_radii[0]:.2f} m"
                return "multiple radii"

            return "multiple selected results"

    return ""


def build_auto_subtitle(
    comparison: dict,
    selected_layer_name: str,
    selected_z: Union[float, str],
    x_axis: str,
) -> str:
    """Build an automatic subtitle unless the user provided one."""
    if comparison.get("subtitle"):
        return comparison["subtitle"]

    phase_part = ""
    mode = comparison.get("mode", "")

    if mode == "phases_one_model":
        phase_part = "multiple phases"
    else:
        phase_part = f"phase: {comparison.get('phase', 'phase_11')}"

    if isinstance(selected_z, str):
        z_part = selected_z
    else:
        z_part = f"z = {selected_z:.3f} m"

    radius_part = build_radius_part(comparison)

    if radius_part:
        return (
            f"Layer: {selected_layer_name}, {z_part}, "
            f"{radius_part}, {phase_part}"
        )

    return (
        f"Layer: {selected_layer_name}, {z_part}, "
        f"{phase_part}"
    )

def plot_component_overlay(
    transformed_results: Dict[Tuple[str, str], pd.DataFrame],
    comparison: dict,
    result_ids: Sequence[str],
    phases: Sequence[str],
    selected_layer_name: str,
    selected_z_values: Sequence[float],
    components_group: Sequence[str],
    *,
    x_axis: str = "distance_from_wall",
    components: dict = DEFAULT_COMPONENTS,
    x_axes: dict = DEFAULT_X_AXES,
    z_round_decimals: int = 3,
    save_figures: bool = False,
    figure_folder: Union[str, Path] = "figures",
    figure_dpi: int = 300,
) -> Optional[Path]:
    """
    Plot multiple components on the same axes.

    Typical groups:
        ["hoop_stress", "radial_stress"]
        ["hoop_strain", "radial_strain"]
    """
    for component in components_group:
        if component not in components:
            raise ValueError(
                f"Unknown component '{component}'. "
                f"Available: {list(components)}"
            )

    if x_axis not in x_axes:
        raise ValueError(
            f"Unknown x_axis '{x_axis}'. "
            f"Available: {list(x_axes)}"
        )

    x_info = x_axes[x_axis]
    x_col = x_info["column"]

    title_prefix = comparison.get("title", comparison.get("name", "PLAXIS comparison"))
    comparison_mode = comparison.get("mode", "")

    plt.figure(figsize=comparison.get("figsize", (10, 6)))

    plotted_anything = False

    for component in components_group:
        component_info = components[component]
        y_col = component_info["column"]

        for selected_z in selected_z_values:
            for result_id in result_ids:
                for phase in phases:
                    key = (result_id, phase)

                    if key not in transformed_results:
                        continue

                    df = transformed_results[key]

                    df_plot = filter_result_for_layer_depth(
                        df,
                        selected_layer_name,
                        selected_z,
                        z_round_decimals=z_round_decimals,
                    )

                    if df_plot.empty:
                        continue

                    df_plot = df_plot.sort_values(x_col)

                    base_label = build_line_label(
                        df_plot,
                        comparison_mode,
                        result_id,
                        phase,
                    )

                    if len(selected_z_values) > 1:
                        label = f"{base_label}, {component_info['title']}, z={selected_z:.2f} m"
                    else:
                        label = f"{base_label}, {component_info['title']}"

                    plt.plot(
                        df_plot[x_col],
                        df_plot[y_col],
                        marker=comparison.get("marker", "o"),
                        markersize=comparison.get("markersize", 3),
                        linewidth=comparison.get("linewidth", 1.6),
                        label=label,
                    )

                    plotted_anything = True

    if not plotted_anything:
        plt.close()
        print(f"No data plotted for component group: {components_group}")
        return None

    if len(selected_z_values) == 1:
        z_for_subtitle = selected_z_values[0]
    else:
        z_for_subtitle = "multiple depths"

    subtitle = build_auto_subtitle(
        comparison,
        selected_layer_name,
        z_for_subtitle,
        x_axis,
    )

    group_title = " + ".join(
        components[component]["title"]
        for component in components_group
    )

    plt.xlabel(x_info["xlabel"])

    # Use a shared y-label depending on the plotted group
    if all("stress" in component for component in components_group):
        plt.ylabel("Stress [kPa]")
    elif all("strain" in component for component in components_group):
        plt.ylabel("Strain [-]")
    else:
        plt.ylabel("Value")

    plt.title(f"{title_prefix} — {group_title}\n{subtitle}")
    plt.grid(True)
    plt.legend(loc="lower right", fontsize=8)

    # Optional y-limits:
    # "ylim": (0, 160)
    # or component-group-specific:
    # "ylims": {"stress": (0, 160), "strain": (-0.02, 0.02)}
    if "ylims" in comparison and comparison["ylims"] is not None:
        if all("stress" in component for component in components_group):
            if "stress" in comparison["ylims"]:
                plt.ylim(comparison["ylims"]["stress"])
        elif all("strain" in component for component in components_group):
            if "strain" in comparison["ylims"]:
                plt.ylim(comparison["ylims"]["strain"])
    elif "ylim" in comparison and comparison["ylim"] is not None:
        plt.ylim(comparison["ylim"])

    plt.tight_layout()

    saved_path = None

    if save_figures:
        figure_folder = Path(figure_folder)
        figure_folder.mkdir(parents=True, exist_ok=True)

        group_name = "_".join(components_group)

        if len(selected_z_values) == 1:
            depth_name = f"z_{selected_z_values[0]:.3f}"
        else:
            depth_name = "multiple_depths"

        phase_part = comparison.get("phase", None)

        if phase_part is None:
            if len(phases) == 1:
                phase_part = phases[0]
            else:
                phase_part = "multiple_phases"

        phase_part = str(phase_part).replace("phase_", "phase")

        filename = (
            f"{make_safe_filename(title_prefix)}_"
            f"{group_name}_"
            f"{depth_name}_"
            f"{phase_part}_"
            f"{x_axis}.png"
        )

        saved_path = figure_folder / filename
        plt.savefig(saved_path, dpi=figure_dpi, bbox_inches="tight")
        print(f"Saved: {saved_path}")

    plt.show()

    return saved_path


def plot_component_for_depth(
    transformed_results: Dict[Tuple[str, str], pd.DataFrame],
    comparison: dict,
    result_ids: Sequence[str],
    phases: Sequence[str],
    selected_layer_name: str,
    selected_z: float,
    component: str,
    *,
    x_axis: str = "distance_from_wall",
    components: dict = DEFAULT_COMPONENTS,
    x_axes: dict = DEFAULT_X_AXES,
    z_round_decimals: int = 3,
    save_figures: bool = False,
    figure_folder: Union[str, Path] = "figures",
    figure_dpi: int = 300,
) -> Optional[Path]:
    """
    Plot one component at one depth for selected result IDs and phases.

    Returns the saved path if save_figures=True, otherwise None.
    """
    if component not in components:
        raise ValueError(f"Unknown component '{component}'. Available: {list(components)}")

    if x_axis not in x_axes:
        raise ValueError(f"Unknown x_axis '{x_axis}'. Available: {list(x_axes)}")

    component_info = components[component]
    x_info = x_axes[x_axis]

    y_col = component_info["column"]
    x_col = x_info["column"]

    title_prefix = comparison.get("title", comparison.get("name", "PLAXIS comparison"))
    comparison_mode = comparison.get("mode", "")

    plt.figure(figsize=comparison.get("figsize", (10, 6)))

    plotted_anything = False

    for result_id in result_ids:
        for phase in phases:
            key = (result_id, phase)

            if key not in transformed_results:
                continue

            df = transformed_results[key]
            df_plot = filter_result_for_layer_depth(
                df,
                selected_layer_name,
                selected_z,
                z_round_decimals=z_round_decimals,
            )

            if df_plot.empty:
                print(f"Warning: no data for {result_id}, {phase}, {selected_layer_name}, z={selected_z:.3f}")
                continue

            df_plot = df_plot.sort_values(x_col)
            label = build_line_label(df_plot, comparison_mode, result_id, phase)

            plt.plot(
                df_plot[x_col],
                df_plot[y_col],
                marker=comparison.get("marker", "o"),
                markersize=comparison.get("markersize", 3),
                linewidth=comparison.get("linewidth", 1.6),
                label=label,
            )

            plotted_anything = True

    if not plotted_anything:
        plt.close()
        print(f"No data plotted for {component}, z={selected_z:.3f}.")
        return None

    subtitle = build_auto_subtitle(comparison, selected_layer_name, selected_z, x_axis)

    # plt.axvline(x=4.44, color="indigo", linestyle="--", linewidth=0.8, label="CPT cone location") # first CPT point (4.44), 6.66 for cpt point at depth 24
    plt.xlabel(x_info["xlabel"])
    plt.ylabel(component_info["ylabel"])
    plt.title(f"{title_prefix} — {component_info['title']}\n{subtitle}")
    plt.grid(True)
    plt.legend(loc="lower right")
    

    if force_stress_axis_to_zero(component):
        ymin, ymax = plt.ylim()

        # Compression-positive stresses are usually positive.
        # Extend the lower y-axis limit to 0 without cutting off data.
        if ymin > -2:
            plt.ylim(bottom=-3)

        # If the stress data are negative, extend the upper y-axis limit to 0.
        elif ymax < 0:
            plt.ylim(top=3)

        # If the data already cross zero, leave the axis unchanged.
    
    if "ylim" in comparison and comparison["ylim"] is not None:
        plt.ylim(comparison["ylim"])
    plt.tight_layout()

    saved_path = None

    if save_figures:
        figure_folder = Path(figure_folder)
        figure_folder.mkdir(parents=True, exist_ok=True)

        filename = (
            f"{make_safe_filename(title_prefix)}_"
            f"{component}_"
            f"{make_safe_filename(selected_layer_name)}_"
            f"z_{selected_z:.3f}_"
            f"{x_axis}.png"
        )

        saved_path = figure_folder / filename
        plt.savefig(saved_path, dpi=figure_dpi, bbox_inches="tight")
        print(f"Saved: {saved_path}")

    plt.show()

    return saved_path


def plot_component_combined_depths(
    transformed_results: Dict[Tuple[str, str], pd.DataFrame],
    comparison: dict,
    result_ids: Sequence[str],
    phases: Sequence[str],
    selected_layer_name: str,
    selected_z_values: Sequence[float],
    component: str,
    *,
    x_axis: str = "distance_from_wall",
    components: dict = DEFAULT_COMPONENTS,
    x_axes: dict = DEFAULT_X_AXES,
    z_round_decimals: int = 3,
    save_figures: bool = False,
    figure_folder: Union[str, Path] = "figures",
    figure_dpi: int = 300,
) -> Optional[Path]:
    """
    Plot one component with multiple depths overlaid.
    """
    if component not in components:
        raise ValueError(f"Unknown component '{component}'. Available: {list(components)}")

    if x_axis not in x_axes:
        raise ValueError(f"Unknown x_axis '{x_axis}'. Available: {list(x_axes)}")

    component_info = components[component]
    x_info = x_axes[x_axis]

    y_col = component_info["column"]
    x_col = x_info["column"]

    title_prefix = comparison.get("title", comparison.get("name", "PLAXIS comparison"))
    comparison_mode = comparison.get("mode", "")

    plt.figure(figsize=comparison.get("figsize", (11, 7)))

    plotted_anything = False

    for selected_z in selected_z_values:
        for result_id in result_ids:
            for phase in phases:
                key = (result_id, phase)

                if key not in transformed_results:
                    continue

                df = transformed_results[key]
                df_plot = filter_result_for_layer_depth(
                    df,
                    selected_layer_name,
                    selected_z,
                    z_round_decimals=z_round_decimals,
                )

                if df_plot.empty:
                    continue

                df_plot = df_plot.sort_values(x_col)
                base_label = build_line_label(df_plot, comparison_mode, result_id, phase)
                label = f"{base_label}, z={selected_z:.2f} m"

                plt.plot(
                    df_plot[x_col],
                    df_plot[y_col],
                    marker=comparison.get("marker", "o"),
                    markersize=comparison.get("markersize", 2.5),
                    linewidth=comparison.get("linewidth", 1.3),
                    label=label,
                )

                plotted_anything = True

    if not plotted_anything:
        plt.close()
        print(f"No data plotted for {component}.")
        return None

    subtitle = build_auto_subtitle(comparison, selected_layer_name, "multiple depths", x_axis)

    plt.xlabel(x_info["xlabel"])
    plt.ylabel(component_info["ylabel"])
    plt.title(f"{title_prefix} — {component_info['title']}\n{subtitle}")
    plt.grid(True)
    plt.legend(loc="lower right",fontsize=8)
    
    if force_stress_axis_to_zero(component):
        ymin, ymax = plt.ylim()

        # Compression-positive stresses are usually positive.
        # Extend the lower y-axis limit to 0 without cutting off data.
        if ymin > -2:
            plt.ylim(bottom=-3)

        # If the stress data are negative, extend the upper y-axis limit to 0.
        elif ymax < 0:
            plt.ylim(top=3)

        # If the data already cross zero, leave the axis unchanged.
    
    if "ylim" in comparison and comparison["ylim"] is not None:
        plt.ylim(comparison["ylim"])

    plt.tight_layout()

    saved_path = None

    if save_figures:
        figure_folder = Path(figure_folder)
        figure_folder.mkdir(parents=True, exist_ok=True)

        phase_name = comparison.get("phase", "phase_unknown")
        phase_name = phase_name.replace("phase_", "phase")

        component_filename_names = {
            "radial_stress": "Radial_stress",
            "radial_strain": "Radial_strain",
            "hoop_stress": "Hoop_stress",
            "hoop_strain": "Hoop_strain",
            "radial_shear_stress": "Radial_shear_stress",
            "radial_shear_strain": "Radial_shear_strain",
        }

        component_file_name = component_filename_names.get(component, component)

        phase_name = comparison.get("phase", "phase_unknown")
        phase_name = phase_name.replace("phase_", "phase")

        filename = (
            f"{component_file_name}_"
            f"{selected_z:.2f}m_"
            f"{phase_name}_"
            f"all_models.png"
        )

        saved_path = figure_folder / filename
        plt.savefig(saved_path, dpi=figure_dpi, bbox_inches="tight")
        print(f"Saved: {saved_path}")

    plt.show()

    return saved_path


# ============================================================
# HIGH-LEVEL WORKFLOW
# ============================================================

def run_comparison(
    run_catalogue: pd.DataFrame,
    comparison: dict,
    *,
    stress_compression_positive: bool = True,
    strain_compression_positive: bool = True,
    shear_strain_convention: str = "tensor",
    z_round_decimals: int = 3,
    save_figures_default: bool = False,
    figure_folder_default: Union[str, Path] = "figures",
    figure_dpi: int = 300,
    print_selection_table: bool = True,
) -> dict:
    """
    Run one comparison dictionary end-to-end:
    - resolve selected result IDs and phases;
    - load phase sheets;
    - transform stress/strain;
    - print layer/depth table;
    - resolve selected layer/depth;
    - create requested plots.

    Supports:
        component_layout = "separate"
        component_layout = "overlay"
    """
    result_ids, phases = resolve_comparison(run_catalogue, comparison)

    loaded = load_result_phases(run_catalogue, result_ids, phases)

    transformed = transform_loaded_results(
        loaded,
        stress_compression_positive=stress_compression_positive,
        strain_compression_positive=strain_compression_positive,
        shear_strain_convention=shear_strain_convention,
        z_round_decimals=z_round_decimals,
    )

    first_key = next(iter(transformed))
    reference_df = transformed[first_key]
    summary = create_layer_depth_summary(reference_df)

    if print_selection_table:
        print("\n" + "=" * 80)
        print(
            f"Comparison: "
            f"{comparison.get('name', comparison.get('title', 'Unnamed comparison'))}"
        )
        print("=" * 80)
        print_layer_depth_summary(summary)

    selected_layer_index, selected_layer_name = resolve_layer(
        summary,
        comparison.get("layer", "auto_bottom_sand"),
    )

    selected_z_values = resolve_depths(
        summary,
        selected_layer_index,
        comparison.get("depth_point", 1),
    )

    components = comparison.get(
        "components",
        ["radial_stress", "radial_strain"],
    )

    x_axis = comparison.get("x_axis", "distance_from_wall")
    depth_layout = comparison.get("depth_layout", "separate")
    component_layout = comparison.get("component_layout", "separate")

    save_figures = comparison.get("save_figures", save_figures_default)
    figure_folder = comparison.get("figure_folder", figure_folder_default)

    print("Resolved plotting selection:")
    print(f"  result IDs        : {result_ids}")
    print(f"  phases            : {phases}")
    print(f"  layer             : [{selected_layer_index}] {selected_layer_name}")
    print(f"  z-values          : {selected_z_values}")
    print(f"  components        : {components}")
    print(f"  component layout  : {component_layout}")
    print(f"  x-axis            : {x_axis}")
    print(f"  depth layout      : {depth_layout}")

    saved_paths = []

    # ---------------------------------------------------------------------
    # Component layout: overlay
    # ---------------------------------------------------------------------
    if component_layout == "overlay":

        component_groups = comparison.get(
            "component_groups",
            [
                ["hoop_stress", "radial_stress"],
                ["hoop_strain", "radial_strain"],
            ],
        )

        if depth_layout == "combined_depths":
            z_groups = [selected_z_values]

        elif depth_layout == "separate":
            z_groups = [[selected_z] for selected_z in selected_z_values]

        else:
            raise ValueError(
                "When component_layout='overlay', depth_layout must be "
                "'separate' or 'combined_depths'."
            )

        for z_group in z_groups:
            for group in component_groups:

                # Only plot group if all components in the group were requested.
                if not all(component in components for component in group):
                    continue

                saved = plot_component_overlay(
                    transformed,
                    comparison,
                    result_ids,
                    phases,
                    selected_layer_name,
                    z_group,
                    group,
                    x_axis=x_axis,
                    z_round_decimals=z_round_decimals,
                    save_figures=save_figures,
                    figure_folder=figure_folder,
                    figure_dpi=figure_dpi,
                )

                if saved is not None:
                    saved_paths.append(saved)

    # ---------------------------------------------------------------------
    # Component layout: separate
    # ---------------------------------------------------------------------
    elif component_layout == "separate":

        if depth_layout == "separate":
            for component in components:
                for selected_z in selected_z_values:
                    saved = plot_component_for_depth(
                        transformed,
                        comparison,
                        result_ids,
                        phases,
                        selected_layer_name,
                        selected_z,
                        component,
                        x_axis=x_axis,
                        z_round_decimals=z_round_decimals,
                        save_figures=save_figures,
                        figure_folder=figure_folder,
                        figure_dpi=figure_dpi,
                    )

                    if saved is not None:
                        saved_paths.append(saved)

        elif depth_layout == "combined_depths":
            for component in components:
                saved = plot_component_combined_depths(
                    transformed,
                    comparison,
                    result_ids,
                    phases,
                    selected_layer_name,
                    selected_z_values,
                    component,
                    x_axis=x_axis,
                    z_round_decimals=z_round_decimals,
                    save_figures=save_figures,
                    figure_folder=figure_folder,
                    figure_dpi=figure_dpi,
                )

                if saved is not None:
                    saved_paths.append(saved)

        else:
            raise ValueError(
                "depth_layout must be 'separate' or 'combined_depths'."
            )

    else:
        raise ValueError(
            "component_layout must be 'separate' or 'overlay'."
        )

    return {
        "comparison": comparison,
        "result_ids": result_ids,
        "phases": phases,
        "loaded": loaded,
        "transformed": transformed,
        "layer_depth_summary": summary,
        "selected_layer_index": selected_layer_index,
        "selected_layer_name": selected_layer_name,
        "selected_z_values": selected_z_values,
        "saved_paths": saved_paths,
    }


def run_many_comparisons(
    run_catalogue: pd.DataFrame,
    comparisons: Sequence[dict],
    **kwargs,
) -> List[dict]:
    """Run multiple comparison dictionaries."""
    outputs = []

    for comparison in comparisons:
        output = run_comparison(run_catalogue, comparison, **kwargs)
        outputs.append(output)

    return outputs


def export_selected_plot_data(
    output: dict,
    export_file: Union[str, Path],
    *,
    z_round_decimals: int = 3,
) -> Path:
    """
    Export the selected filtered data used in one comparison output.
    """
    export_rows = []
    comparison = output["comparison"]
    components = comparison.get("components", ["radial_stress", "radial_strain"])

    selected_layer_name = output["selected_layer_name"]
    selected_z_values = output["selected_z_values"]

    transformed = output["transformed"]

    for (result_id, phase), df in transformed.items():
        for selected_z in selected_z_values:
            df_plot = filter_result_for_layer_depth(
                df,
                selected_layer_name,
                selected_z,
                z_round_decimals=z_round_decimals,
            )

            if not df_plot.empty:
                df_plot = df_plot.copy()
                df_plot["selected_component_list"] = ", ".join(components)
                export_rows.append(df_plot)

    if not export_rows:
        raise ValueError("No selected data available to export.")

    export_df = pd.concat(export_rows, ignore_index=True)
    export_file = Path(export_file)
    export_df.to_excel(export_file, index=False)

    return export_file
