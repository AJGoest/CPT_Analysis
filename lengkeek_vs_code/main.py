from __future__ import annotations

from pathlib import Path

from gef_parser import read_gef
from lengkeek_model import classify_lengkeek_r2010
from plotting import (
    plot_cpt_profile,
    plot_lengkeek_chart,
    plot_lengkeek_chart_with_background,
    plot_layer_distributions,
    plot_effective_parameter_layers,
)
from nen_table_2b_strength import (
    assign_nen_2b_strength,
    combine_equal_parameter_layers,
)
from plaxis_excel_export import create_plaxis_soil_input_excel
import os
import json


# =============================================================================
# USER INPUTS
# =============================================================================

# Put your GEF file here.
#
# Same folder as this script:
#     GEF_FILE = "sample_gef.GEF"
#
# Full path:
#     GEF_FILE = r"C:\AA_Thesis\GEF_files\my_cpt_file.GEF"
#
# IMPORTANT:
# Use r"..." for Windows paths.
# GEF_FILE = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\Pre-boren\S1022749_CPTU1-2.gef"
# GEF_FILE = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\Pre-boren\S1022749_CPTU1-4.gef"
# GEF_FILE = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\After-boren\S1022749_CPTU2-2.gef"
# GEF_FILE = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\After-boren\S1022749_CPTU2-4.gef"'
GEF_FILE = r"C:\AA_Thesis\CPT_Measurements\Wezep\2300654_S13.gef"



# Groundwater input mode.
#
# Choose one of:
#
# "manual_nap"
#     Use the value from GROUNDWATER_LEVEL_M_NAP.
#     The value is relative to NAP.
#
# "first_measurement"
#     Set groundwater level equal to the elevation of the first CPT
#     measurement point.
#
# "gef"
#     Use groundwater level from the GEF file, if available.
#
# "none"
#     Do not use groundwater level.
#
GROUNDWATER_MODE = "first_measurement"


# Manual groundwater level in m NAP.
# Only used when GROUNDWATER_MODE = "manual_nap".
GROUNDWATER_LEVEL_M_NAP = -2.00


# 1. Extract the file name with the extension (e.g., "S1022749_CPTU1-2.gef")
file_name_with_ext = os.path.basename(GEF_FILE)

# 2. Split the extension to get just the name (e.g., "S1022749_CPTU1-2")
folder_name, _ = os.path.splitext(file_name_with_ext)

# 3. Define your output directory using that name
OUTPUT_DIR = folder_name


# Minimum layer thickness for merging thin interpreted layers.
MIN_LAYER_THICKNESS_M = 0.3


# Use Lengkeek Bqt-Isbt pore-pressure filter when u2 and groundwater level
# are available.
USE_BQT = True

# =============================================================================
# PLOT SELECTION SETTINGS
# =============================================================================

# Choose one of:
#
# "all"
#     Plot all CPT points.
#
# "soil_types"
#     Plot only points whose soil_type is listed in SELECTED_SOIL_TYPES.
#
# "layer_ids"
#     Plot only points whose layer_id is listed in SELECTED_LAYER_IDS.
#
PLOT_SELECTION_MODE = "all"

# Used only when PLOT_SELECTION_MODE = "soil_types".
SELECTED_SOIL_TYPES = [
    "Peat",
    "Organic clay",
]

# Used only when PLOT_SELECTION_MODE = "layer_ids".
# Examples:
#     ["Peat 1"]
#     ["Peat 1", "Clay & silt 2"]
SELECTED_LAYER_IDS = [
    # "Sand 2", "Sand 3", "Sand 4", # for S1022749_CPTU1-2
    # "Sand 2", "Sand 3", "Sand 4", "Sand 5", "Sand 6" # for S1022749_CPTU1-4
    # "Sand 4", # for S1022749_CPTU2-2
    "Sand 4", "Sand 5", "Sand 6", # for S1022749_CPTU2-4
]

# Distribution plots for the selected points/layers.
PLOT_LAYER_DISTRIBUTION = False

# Variables to plot in the distribution figures.
DISTRIBUTION_VARIABLES = [
    "qc_mpa",
    "rf_percent",
    "qt_over_pa",
    "Isbt",
    "Bqt",
]

# DATA Distributin setting:
# Choose one of:
# "histogram"
# "boxplot"
# "both"

DISTRIBUTION_PLOT_TYPE = "boxplot"

# boxplot containing all selected layers
ADD_COMBINED_BOXPLOT = True

# Label used for the combined boxplot.
COMBINED_BOXPLOT_LABEL = "Combined"

# Fixed y-axis settings for boxplots.
# These make boxplots of the same variable comparable between different plots/runs.
USE_FIXED_BOXPLOT_AXES = True

BOXPLOT_AXIS_LIMITS = {
    "qc_mpa": (0, 50),
    "rf_percent": (0, 1.5),
    "qt_over_pa": (1, 1000),
    "Isbt": (0, 5),
    "Bqt": (-1, 2),
}

# Use "linear" or "log".
BOXPLOT_AXIS_SCALE = {
    "qt_over_pa": "log",
}

# =============================================================================
# CPT PROFILE SOIL-LAYER PANEL SETTINGS
# =============================================================================

SHOW_SOIL_LAYER_PANEL = True

# Map exact classified soil types to broader plotting groups.
# This only affects colours in the profile plot.
# It does not change soil_type or layer_id in the data.
SOIL_COLOR_GROUPS = {
    "Peat": "Organic",
    "Organic clay": "Organic",
    "Soil, fine grain": "Fine-grained",
    "Clay & silt": "Fine-grained",
    "Silty clay / clayey silt": "Fine-grained",
    "Sand mixtures": "Sandy",
    "Sand": "Sandy",
    "Dense sand / gravelly sand": "Sandy",
    "Unknown material": "Unknown",
}

# Colours used for the broader plotting groups.
SOIL_GROUP_COLORS = {
    "Organic": "#8B5A2B",
    "Fine-grained": "#A9A9A9",
    "Sandy": "#E6C878",
    "Unknown": "#FFFFFF",
}

# =============================================================================
# NEN-EN TABLE 2.B PARAMETER OUTPUT SETTINGS
# =============================================================================

CREATE_LAYER_PARAMETERS = True

# Combine neighbouring layers with identical parameter values.
CREATE_EFFECTIVE_LAYER_PARAMETERS = True


# make excel file ready for PLAXIS If you want to change settings go the export file to change those
CREATE_PLAXIS_EXCEL = False

# end of user settings
# =============================================================================


def format_level(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.2f} m NAP"


def main() -> None:
    gef_file = Path(GEF_FILE)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Read GEF file
    # -------------------------------------------------------------------------
    gef = read_gef(gef_file)

    # -------------------------------------------------------------------------
    # Decide groundwater level
    # -------------------------------------------------------------------------
    if GROUNDWATER_MODE == "manual_nap":
        groundwater_level_m_nap = GROUNDWATER_LEVEL_M_NAP
        groundwater_source = "manual user input in main.py"

    elif GROUNDWATER_MODE == "first_measurement":
        if "elevation_m_nap" not in gef.dataframe.columns or gef.dataframe.empty:
            raise ValueError(
                "Cannot set groundwater level to first measurement point because "
                "elevation_m_nap is not available."
            )

        groundwater_level_m_nap = float(gef.dataframe.loc[0, "elevation_m_nap"])
        groundwater_source = "first CPT measurement point"

    elif GROUNDWATER_MODE == "gef":
        if gef.water_level_m_nap is not None:
            groundwater_level_m_nap = gef.water_level_m_nap
            groundwater_source = "GEF file"
        else:
            groundwater_level_m_nap = None
            groundwater_source = "GEF file, but no groundwater level found"

    elif GROUNDWATER_MODE == "none":
        groundwater_level_m_nap = None
        groundwater_source = "not used"

    else:
        raise ValueError(
            "Invalid GROUNDWATER_MODE. Use one of: "
            "'manual_nap', 'first_measurement', 'gef', or 'none'."
        )

    # -------------------------------------------------------------------------
    # Print input metadata
    # -------------------------------------------------------------------------
    print("")
    print("Input")
    print("-----")
    print(f"GEF file: {gef_file}")
    print(f"CPT start level / ground level: {format_level(gef.ground_level_m_nap)}")
    print(f"Groundwater level: {format_level(groundwater_level_m_nap)}")
    print(f"Groundwater source: {groundwater_source}")

    if GROUNDWATER_MODE == "first_measurement":
        first_depth = float(gef.dataframe.loc[0, "depth_m"])
        first_elevation = float(gef.dataframe.loc[0, "elevation_m_nap"])
        print(f"First measurement depth: {first_depth:.3f} m below CPT start")
        print(f"First measurement elevation: {first_elevation:.3f} m NAP")

    print("")
    print("Vertical reference")
    print("------------------")
    print("The second value in #ZID is used as CPT start level in m NAP.")
    print("Example: #ZID= 31000, -1.48, 0.03 means CPT starts at NAP -1.48 m.")
    print("Elevation is calculated as:")
    print("    elevation_m_nap = CPT_start_level_m_nap - depth_m")

    if groundwater_level_m_nap is None:
        print("")
        print("Warning")
        print("-------")
        print("No groundwater level is available.")
        print("The Lengkeek Bqt pore-pressure filter cannot be calculated.")
        print("The classification will still use the qt/pa - Rf organic soil boundaries.")

    # -------------------------------------------------------------------------
    # Run Lengkeek L2024-R2010 classification
    # -------------------------------------------------------------------------
    classified_df, layers_df = classify_lengkeek_r2010(
        gef.dataframe,
        groundwater_level_m_nap=groundwater_level_m_nap,
        net_area_ratio=gef.net_area_ratio,
        use_bqt=USE_BQT,
        min_layer_thickness_m=MIN_LAYER_THICKNESS_M,
    )

    # -------------------------------------------------------------------------
    # Add metadata to json
    # -------------------------------------------------------------------------
    metadata = {
        "gef_file": str(gef_file),
        "output_dir": str(output_dir),
        "cpt_start_level_m_nap": gef.ground_level_m_nap,
        "groundwater_level_m_nap": groundwater_level_m_nap,
        "groundwater_source": groundwater_source,
        "net_area_ratio": gef.net_area_ratio,
        "classification_settings": {
            "use_bqt": USE_BQT,
            "min_layer_thickness_m": MIN_LAYER_THICKNESS_M,
        },
        "x": gef.x,
        "y": gef.y
    }

    # -------------------------------------------------------------------------
    # Save outputs
    # -------------------------------------------------------------------------
    classified_points_path = output_dir / "classified_points.csv"
    interpreted_layers_path = output_dir / "interpreted_layers.csv"
    profile_plot_path = output_dir / "cpt_lengkeek_profile.png"
    chart_plot_path = output_dir / "lengkeek_r2010_chart.png"
    checking_layers = output_dir / "checking_layers.csv"
    chart_background_path = output_dir / "lengkeek_chart_background.png"
    metadata_path = output_dir / "run_metadata.json"
    parameters_dir = output_dir / "layer_parameters"
    layer_parameters_path = parameters_dir / "layer_parameters.csv"
    effective_layer_parameters_path = parameters_dir / "eff_layer_parameters.csv"
    effective_layer_parameters_plot_path = parameters_dir / "eff_layer_parameters_profile.png"
    plaxis_soil_input_path = parameters_dir / "plaxis_soil_input.xlsx"
    
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    # Put NAP elevation as the first column in the point CSV.
    if "elevation_m_nap" in classified_df.columns:
        first_cols = ["elevation_m_nap"]
        other_cols = [col for col in classified_df.columns if col not in first_cols]
        classified_df = classified_df[first_cols + other_cols]

    # Put NAP layer elevations as the first columns in the layer CSV.
    layer_first_cols = [
        col for col in ["top_elevation_m_nap", "bottom_elevation_m_nap"] 
        if col in layers_df.columns
    ]
    if layer_first_cols:
        other_cols = [col for col in layers_df.columns if col not in layer_first_cols]
        layers_df = layers_df[layer_first_cols + other_cols]

    classified_df.to_csv(classified_points_path, index=False)
    layers_df.to_csv(interpreted_layers_path, index=False)
    layers_df[["layer_id","top_elevation_m_nap", "bottom_elevation_m_nap", "soil_type"]].to_csv(checking_layers, index=False)

    # -------------------------------------------------------------------------
    # Create NEN Table 2.b layer parameter outputs
    # -------------------------------------------------------------------------
    if CREATE_LAYER_PARAMETERS:
        parameters_dir.mkdir(parents=True, exist_ok=True)

        layer_parameters_df = assign_nen_2b_strength(
            interpreted_layers=layers_df,
            classified_points=classified_df,
        )

        layer_parameters_df.to_csv(layer_parameters_path, index=False)

        if CREATE_EFFECTIVE_LAYER_PARAMETERS:
            effective_layer_parameters_df = combine_equal_parameter_layers(
                layer_parameters=layer_parameters_df,
            )

            effective_layer_parameters_df.to_csv(
                effective_layer_parameters_path,
                index=False,
            )

            plot_effective_parameter_layers(
                effective_layer_parameters_df,
                output_path=effective_layer_parameters_plot_path,
                title="Combined layers " + gef_file.stem,
                soil_color_groups=SOIL_COLOR_GROUPS,
                soil_group_colors=SOIL_GROUP_COLORS,
            )

            if CREATE_PLAXIS_EXCEL:
                create_plaxis_soil_input_excel(
                    effective_layer_parameters_df,
                    output_path=plaxis_soil_input_path,
                )


    plot_cpt_profile(
        classified_df,
        layers_df,
        output_path=profile_plot_path,
        groundwater_level_m_nap=groundwater_level_m_nap,
        cpt_start_level_m_nap=gef.ground_level_m_nap,
        show_soil_layer_panel=SHOW_SOIL_LAYER_PANEL,
        soil_color_groups=SOIL_COLOR_GROUPS,
        soil_group_colors=SOIL_GROUP_COLORS,
    )

    plot_lengkeek_chart(
    classified_df,
    output_path=chart_plot_path,
    groundwater_level_m_nap=groundwater_level_m_nap,
    cpt_start_level_m_nap=gef.ground_level_m_nap,
    plot_selection_mode=PLOT_SELECTION_MODE,
    selected_soil_types=SELECTED_SOIL_TYPES,
    selected_layer_ids=SELECTED_LAYER_IDS,
    )

    plot_lengkeek_chart_with_background(
    classified_df=classified_df,
    output_path=chart_background_path,
    groundwater_level_m_nap=groundwater_level_m_nap,
    cpt_start_level_m_nap=gef.ground_level_m_nap,
    plot_selection_mode=PLOT_SELECTION_MODE,
    selected_soil_types=SELECTED_SOIL_TYPES,
    selected_layer_ids=SELECTED_LAYER_IDS,
    )

    if PLOT_LAYER_DISTRIBUTION:
        plot_layer_distributions(
            classified_df,
            output_dir=output_dir / "distributions",
            plot_selection_mode=PLOT_SELECTION_MODE,
            selected_soil_types=SELECTED_SOIL_TYPES,
            selected_layer_ids=SELECTED_LAYER_IDS,
            variables=DISTRIBUTION_VARIABLES,
            distribution_plot_type=DISTRIBUTION_PLOT_TYPE,
            use_fixed_boxplot_axes=USE_FIXED_BOXPLOT_AXES,
            boxplot_axis_limits=BOXPLOT_AXIS_LIMITS,
            boxplot_axis_scale=BOXPLOT_AXIS_SCALE,
            add_combined_boxplot=ADD_COMBINED_BOXPLOT,
            combined_boxplot_label=COMBINED_BOXPLOT_LABEL,
            plot_title_prefix=folder_name,
        )
    # -------------------------------------------------------------------------
    # Print output locations
    # -------------------------------------------------------------------------
    print("")
    print("Output")
    print("------")
    print(f"Classified points: {classified_points_path}")
    print(f"Interpreted layers: {interpreted_layers_path}")
    print(f"CPT profile plot: {profile_plot_path}")
    print(f"Lengkeek chart plot: {chart_plot_path}")
    print(f"Net area ratio a: {gef.net_area_ratio}")
    if CREATE_LAYER_PARAMETERS:
        print(f"Layer parameters: {layer_parameters_path}")

        if CREATE_EFFECTIVE_LAYER_PARAMETERS:
            print(f"Effective layer parameters: {effective_layer_parameters_path}")

    print("")
    print("Done.")


if __name__ == "__main__":
    main()

