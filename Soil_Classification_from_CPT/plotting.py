from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, LogLocator
import pandas as pd
import numpy as np
from PIL import Image
from lengkeek_chart import plot_digitised_background


def filter_points_for_plot(
    classified_df: pd.DataFrame,
    mode: str = "all",
    selected_soil_types: Optional[list[str]] = None,
    selected_layer_ids: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Filter classified CPT points for plotting.

    mode:
        "all"        -> return all points
        "soil_types" -> return points matching selected_soil_types
        "layer_ids"  -> return points matching selected_layer_ids
    """
    if mode == "all":
        return classified_df.copy()

    if mode == "soil_types":
        if not selected_soil_types:
            raise ValueError(
                "PLOT_SELECTION_MODE is 'soil_types', but SELECTED_SOIL_TYPES is empty."
            )

        return classified_df[
            classified_df["soil_type"].isin(selected_soil_types)
        ].copy()

    if mode == "layer_ids":
        if "layer_id" not in classified_df.columns:
            raise ValueError(
                "Cannot filter by layer_ids because classified_df has no 'layer_id' column."
            )

        if not selected_layer_ids:
            raise ValueError(
                "PLOT_SELECTION_MODE is 'layer_ids', but SELECTED_LAYER_IDS is empty."
            )

        return classified_df[
            classified_df["layer_id"].isin(selected_layer_ids)
        ].copy()

    raise ValueError(
        "Invalid plot selection mode. Use one of: 'all', 'soil_types', 'layer_ids'."
    )

def plot_cpt_profile(
    classified_df: pd.DataFrame,
    layers_df: Optional[pd.DataFrame] = None,
    output_path: str | Path = "output/cpt_lengkeek_profile.png",
    groundwater_level_m_nap: Optional[float] = None,
    cpt_start_level_m_nap: Optional[float] = None,
    show_soil_layer_panel: bool = True,
    soil_color_groups: Optional[dict[str, str]] = None,
    soil_group_colors: Optional[dict[str, str]] = None,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer NAP elevation if available.
    if "elevation_m_nap" in classified_df.columns:
        y = classified_df["elevation_m_nap"]
        y_label = "Elevation [m NAP]"
        invert_y = False
    else:
        y = classified_df["depth_m"]
        y_label = "Depth below CPT start [m]"
        invert_y = True

    use_layer_panel = (
        show_soil_layer_panel
        and layers_df is not None
        and not layers_df.empty
    )

    if use_layer_panel:
        fig, axes = plt.subplots(
            ncols=4,
            sharey=True,
            figsize=(13, 9),
            gridspec_kw={"width_ratios": [1.0, 1.0, 1.2, 0.8]},
        )
    else:
        fig, axes = plt.subplots(ncols=3, sharey=True, figsize=(11, 9))

    axes[0].plot(classified_df["qc_mpa"], y)
    axes[0].set_xlabel("qc [MPa]")
    axes[0].set_ylabel(y_label)
    axes[0].grid(True)

    axes[1].plot(classified_df["rf_percent"], y)
    axes[1].set_xlabel("Rf [%]")
    axes[1].grid(True)

    cats = {name: i for i, name in enumerate(classified_df["soil_type"].dropna().unique())}
    axes[2].scatter([cats[s] for s in classified_df["soil_type"]], y, s=4)
    axes[2].set_xticks(list(cats.values()))
    axes[2].set_xticklabels(list(cats.keys()), rotation=45, ha="right")
    axes[2].set_xlabel("Lengkeek classification")
    axes[2].grid(True)

    if use_layer_panel:
        layer_ax = axes[3]

        if soil_color_groups is None:
            soil_color_groups = {}

        if soil_group_colors is None:
            soil_group_colors = {}

        default_color = "#FFFFFF"

        # Decide whether to plot by NAP elevation or depth.
        using_elevation = "elevation_m_nap" in classified_df.columns

        if using_elevation:
            top_col = "top_elevation_m_nap"
            bottom_col = "bottom_elevation_m_nap"
        else:
            top_col = "top_depth_m"
            bottom_col = "bottom_depth_m"

        required_layer_cols = {top_col, bottom_col, "soil_type"}
        missing_layer_cols = required_layer_cols - set(layers_df.columns)

        if missing_layer_cols:
            raise ValueError(
                "Cannot draw soil-layer panel. Missing columns in layers_df: "
                f"{sorted(missing_layer_cols)}"
            )

        for _, layer in layers_df.iterrows():
            soil_type = str(layer["soil_type"])
            group_name = soil_color_groups.get(soil_type, soil_type)
            color = soil_group_colors.get(group_name, default_color)

            y_top = float(layer[top_col])
            y_bottom = float(layer[bottom_col])

            # In NAP coordinates, top elevation is usually larger than bottom elevation.
            y_min = min(y_top, y_bottom)
            y_max = max(y_top, y_bottom)

            layer_ax.axhspan(
                y_min,
                y_max,
                xmin=0.0,
                xmax=1.0,
                facecolor=color,
                edgecolor="black",
                linewidth=0.6,
                alpha=0.85,
            )

            label = str(layer["layer_id"]) if "layer_id" in layers_df.columns else soil_type
            y_mid = 0.5 * (y_min + y_max)

            layer_ax.text(
                0.5,
                y_mid,
                label,
                ha="center",
                va="center",
                fontsize=7,
                rotation=0,
                clip_on=True,
            )

        layer_ax.set_xlim(0, 1)
        layer_ax.set_xticks([])
        layer_ax.set_xlabel("Interpreted\nlayers")
        layer_ax.grid(False)

    # Draw CPT start and groundwater level only when using NAP elevation.
    if "elevation_m_nap" in classified_df.columns:
        for ax in axes:
            if cpt_start_level_m_nap is not None:
                ax.axhline(cpt_start_level_m_nap, linestyle=":", linewidth=1)
            if groundwater_level_m_nap is not None:
                ax.axhline(groundwater_level_m_nap, linestyle="--", linewidth=1)

    if invert_y:
        for ax in axes:
            ax.invert_yaxis()

    title = "CPT profile - Lengkeek L2024-R2010"
    if cpt_start_level_m_nap is not None:
        title += f" | CPT start: NAP {cpt_start_level_m_nap:.2f} m"
    if groundwater_level_m_nap is not None:
        title += f" | GWL: NAP {groundwater_level_m_nap:.2f} m"

    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(output_path, dpi=250)
    plt.close(fig)


def plot_cpt(classified: pd.DataFrame, output_path: str | Path) -> None:
    """Compatibility with your old function name."""
    plot_cpt_profile(classified, output_path=output_path)


def plot_lengkeek_chart(
    classified_df: pd.DataFrame,
    output_path: str | Path = "output/lengkeek_r2010_chart.png",
    groundwater_level_m_nap: Optional[float] = None,
    cpt_start_level_m_nap: Optional[float] = None,
    plot_selection_mode: str = "all",
    selected_soil_types: Optional[list[str]] = None,
    selected_layer_ids: Optional[list[str]] = None,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_df = filter_points_for_plot(
        classified_df,
        mode=plot_selection_mode,
        selected_soil_types=selected_soil_types,
        selected_layer_ids=selected_layer_ids,
    )

    if plot_df.empty:
        raise ValueError(
            "No CPT points remain after plot filtering. "
            "Check SELECTED_SOIL_TYPES or SELECTED_LAYER_IDS."
        )

    fig, ax = plt.subplots(figsize=(8, 6))

    if plot_selection_mode == "layer_ids" and "layer_id" in plot_df.columns:
        for layer_id, group in plot_df.groupby("layer_id", sort=False):
            ax.scatter(
                group["rf_percent"],
                group["qt_over_pa"],
                s=18,
                marker="o",
                alpha=0.75,
                edgecolors="black",
                linewidths=0.35,
                label=str(layer_id),
            )
    else:
        ax.scatter(
            plot_df["rf_percent"],
            plot_df["qt_over_pa"],
            s=8,
            alpha=0.55,
            edgecolors="black",
            linewidths=0.25,
            label="CPT points",
        )

    # rf_peat = pd.Series([x / 100 for x in range(511, 1201)])
    # peat_boundary = 16.7 * (rf_peat - 5.1) ** 0.25
    # ax.plot(rf_peat, peat_boundary, label="L2024-R2010 peat boundary")

    # rf_org = pd.Series([x / 100 for x in range(271, 1201)])
    # org_boundary = 10.3 * (rf_org - 2.7) ** 0.15
    # ax.plot(rf_org, org_boundary, label="L2024-R2010 organic clay boundary")

    ax.set_yscale("log")
    ax.set_xscale("log")

    ax.set_xlim(0.1, 20)
    ax.set_ylim(1, 1000)
    
    ax.xaxis.set_major_locator(LogLocator(base=10.0))
    ax.xaxis.set_minor_locator(LogLocator(base=10.0, subs="auto"))

    ax.yaxis.set_major_locator(LogLocator(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs="auto"))

    formatter = ScalarFormatter()
    formatter.set_scientific(False)

    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    ax.set_xlabel("Rf [%]")
    ax.set_ylabel("qt / pa [-]")
    ax.grid(True, which="both")

    title = "Lengkeek L2024-R2010 chart"
    if cpt_start_level_m_nap is not None:
        title += f"\nCPT start: NAP {cpt_start_level_m_nap:.2f} m"
    if groundwater_level_m_nap is not None:
        title += f" | GWL: NAP {groundwater_level_m_nap:.2f} m"

    ax.set_title(title)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=250)
    plt.close(fig)


def plot_lengkeek_chart_with_background(
    classified_df: pd.DataFrame,
    output_path: str | Path = "output/lengkeek_r2010_chart_with_background.png",
    groundwater_level_m_nap: Optional[float] = None,
    cpt_start_level_m_nap: Optional[float] = None,
    plot_selection_mode: str = "all",
    selected_soil_types: Optional[list[str]] = None,
    selected_layer_ids: Optional[list[str]] = None,
) -> None:
    """Plot CPT points on top of the final Lengkeek zone chart background."""

    required = {"rf_percent", "qt_over_pa"}
    missing = required - set(classified_df.columns)

    if missing:
        raise ValueError(
            f"Cannot plot Lengkeek chart with background. "
            f"Missing columns: {sorted(missing)}"
        )

    plot_df = filter_points_for_plot(
        classified_df,
        mode=plot_selection_mode,
        selected_soil_types=selected_soil_types,
        selected_layer_ids=selected_layer_ids,
    )

    if plot_df.empty:
        raise ValueError(
            "No CPT points remain after plot filtering. "
            "Check SELECTED_SOIL_TYPES or SELECTED_LAYER_IDS."
        )

    plot_digitised_background(
        points_df=plot_df,
        output_path=output_path,
        show=False,
    )

def plot_layer_distributions(
    classified_df: pd.DataFrame,
    output_dir: str | Path,
    plot_selection_mode: str = "all",
    selected_soil_types: Optional[list[str]] = None,
    selected_layer_ids: Optional[list[str]] = None,
    variables: Optional[list[str]] = None,
    distribution_plot_type: str = "histogram",
    use_fixed_boxplot_axes: bool = False,
    boxplot_axis_limits: Optional[dict[str, tuple[float, float]]] = None,
    boxplot_axis_scale: Optional[dict[str, str]] = None,
    add_combined_boxplot: bool = False,
    combined_boxplot_label: str = "Combined",
    plot_title_prefix: str="",
) -> None:
    """Plot distribution figures for selected CPT points/layers.

    distribution_plot_type:
        "histogram" -> one histogram per variable
        "boxplot"   -> one boxplot per variable, grouped by layer_id when possible
        "both"      -> histogram and boxplot
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if variables is None:
        variables = ["qc_mpa", "rf_percent", "qt_over_pa", "Isbt", "Bqt"]

    plot_df = filter_points_for_plot(
        classified_df,
        mode=plot_selection_mode,
        selected_soil_types=selected_soil_types,
        selected_layer_ids=selected_layer_ids,
    )

    if plot_df.empty:
        raise ValueError(
            "No CPT points remain after distribution filtering. "
            "Check SELECTED_SOIL_TYPES or SELECTED_LAYER_IDS."
        )

    valid_plot_types = {"histogram", "boxplot", "both"}
    if distribution_plot_type not in valid_plot_types:
        raise ValueError(
            f"Invalid DISTRIBUTION_PLOT_TYPE: {distribution_plot_type}. "
            f"Use one of: {sorted(valid_plot_types)}."
        )

    make_histograms = distribution_plot_type in {"histogram", "both"}
    make_boxplots = distribution_plot_type in {"boxplot", "both"}

    group_column = "layer_id" if "layer_id" in plot_df.columns else "soil_type"

    for variable in variables:
        if variable not in plot_df.columns:
            continue

        values = plot_df[variable].dropna()

        if values.empty:
            continue

        safe_variable = variable.replace("/", "_").replace(" ", "_")

        if make_histograms:
            fig, ax = plt.subplots(figsize=(7, 5))

            ax.hist(values, bins=30)
            ax.set_xlabel(variable)
            ax.set_ylabel("Frequency")

            title = f"Distribution of {variable}"

            if plot_selection_mode == "soil_types":
                title += f"\nSoil types: {', '.join(selected_soil_types or [])}"

            elif plot_selection_mode == "layer_ids":
                title += f"\nLayers: {', '.join(selected_layer_ids or [])}"

            ax.set_title(title)
            ax.grid(True)

            fig.tight_layout()

            output_path = output_dir / f"histogram_{safe_variable}.png"
            fig.savefig(output_path, dpi=250)
            plt.close(fig)

        if make_boxplots:
            boxplot_df = plot_df[[group_column, variable]].dropna()

            if boxplot_df.empty:
                continue

            grouped_values = []
            labels = []

            for label, group in boxplot_df.groupby(group_column, sort=False):
                group_values = group[variable].dropna()

                if not group_values.empty:
                    grouped_values.append(group_values)
                    labels.append(str(label))

            # Add one extra boxplot containing all selected points together.
            if add_combined_boxplot and len(grouped_values) > 1:
                combined_values = boxplot_df[variable].dropna()

                if not combined_values.empty:
                    grouped_values.append(combined_values)
                    labels.append(combined_boxplot_label)

            if not grouped_values:
                continue

            fig_width = max(7, 1.2 * len(labels))
            fig, ax = plt.subplots(figsize=(fig_width, 5))

            ax.boxplot(grouped_values, labels=labels, showmeans=True)

            ax.set_xlabel(group_column)
            ax.set_ylabel(variable)
            ax.set_title(f"{plot_title_prefix}: {variable} boxplot")

            if use_fixed_boxplot_axes:
                axis_scale = "linear"

                if boxplot_axis_scale and variable in boxplot_axis_scale:
                    axis_scale = boxplot_axis_scale[variable]

                if axis_scale not in {"linear", "log"}:
                    raise ValueError(
                        f"Invalid boxplot axis scale for {variable}: {axis_scale}. "
                        "Use 'linear' or 'log'."
                    )

                ax.set_yscale(axis_scale)

                if boxplot_axis_limits and variable in boxplot_axis_limits:
                    y_min, y_max = boxplot_axis_limits[variable]

                    if axis_scale == "log" and y_min <= 0:
                        raise ValueError(
                            f"Cannot use log scale for {variable} with y_min <= 0. "
                            f"Current limit is {y_min}."
                        )

                    ax.set_ylim(y_min, y_max)

                if axis_scale == "log":
                    if boxplot_axis_limits and variable in boxplot_axis_limits:
                        y_min, y_max = boxplot_axis_limits[variable]
                    else:
                        y_min, y_max = ax.get_ylim()

                    log_ticks = []
                    value = 1.0

                    while value <= y_max:
                        if value >= y_min:
                            log_ticks.append(value)
                        value *= 10.0

                    # Add useful intermediate ticks for qt_over_pa.
                    for value in [2, 5, 20, 50, 200, 500]:
                        if y_min <= value <= y_max:
                            log_ticks.append(value)

                    log_ticks = sorted(set(log_ticks))

                    ax.set_yticks(log_ticks)
                    ax.set_yticklabels([str(int(t)) if t >= 1 else str(t) for t in log_ticks])

            ax.grid(True, axis="y", which="both")

            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

            fig.tight_layout()

            output_path = output_dir / f"boxplot_{safe_variable}_by_{group_column}.png"
            fig.savefig(output_path, dpi=250)
            plt.close(fig)


def _infer_soil_type_from_soil_id(soil_id: str) -> str:
    """Infer original soil type from a combined soil_id string.

    Examples:
        'Sand 3' -> 'Sand'
        'Sand 3 + Sand 4' -> 'Sand'
        'Clay & silt 1' -> 'Clay & silt'
        'Dense sand / gravelly sand 1' -> 'Dense sand / gravelly sand'
    """
    soil_id = str(soil_id)

    # For combined IDs, use the first layer name.
    first_part = soil_id.split("+")[0].strip()

    # Remove the final layer number.
    parts = first_part.rsplit(" ", 1)

    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]

    return first_part



# If you want full depth of entire soil profile use this function below and comment the one further down.


# def plot_effective_parameter_layers(
#     effective_layers_df: pd.DataFrame,
#     output_path: str | Path = "output/parameters/eff_layer_parameters_profile.png",
#     title: str = "Layer parameters",
#     soil_color_groups: Optional[dict[str, str]] = None,
#     soil_group_colors: Optional[dict[str, str]] = None,
# ) -> None:
#     """Plot combined effective parameter layers over elevation.

#     This is intended for the eff_layer_parameters.csv output.

#     Required columns:
#         soil_id
#         top_elevation_m_nap
#         bottom_elevation_m_nap
#     """
#     output_path = Path(output_path)
#     output_path.parent.mkdir(parents=True, exist_ok=True)

#     required_columns = {
#         "soil_id",
#         "top_elevation_m_nap",
#         "bottom_elevation_m_nap",
#     }

#     missing = required_columns - set(effective_layers_df.columns)

#     if missing:
#         raise ValueError(
#             "Cannot plot effective layer parameters. "
#             f"Missing columns: {sorted(missing)}"
#         )

#     if soil_color_groups is None:
#         soil_color_groups = {}

#     if soil_group_colors is None:
#         soil_group_colors = {}

#     default_color = "#FFFFFF"

#     df = effective_layers_df.copy()
#     df = df.sort_values("top_elevation_m_nap", ascending=False).reset_index(drop=True)

#     fig, ax = plt.subplots(figsize=(5, 9))

#     for _, layer in df.iterrows():
#         y_top = float(layer["top_elevation_m_nap"])
#         y_bottom = float(layer["bottom_elevation_m_nap"])

#         y_min = min(y_top, y_bottom)
#         y_max = max(y_top, y_bottom)

#         inferred_soil_type = _infer_soil_type_from_soil_id(layer["soil_id"])
#         group_name = soil_color_groups.get(inferred_soil_type, inferred_soil_type)
#         color = soil_group_colors.get(group_name, default_color)

#         ax.axhspan(
#             y_min,
#             y_max,
#             xmin=0.0,
#             xmax=1.0,
#             facecolor=color,
#             edgecolor="black",
#             linewidth=0.7,
#             alpha=0.85,
#         )

#         # labels in the layers, not recommended

#         # label_lines = [str(layer["soil_id"])]

#         # if "E100_mpa" in df.columns and pd.notna(layer["E100_mpa"]):
#         #     label_lines.append(f"E100 = {layer['E100_mpa']:.2f} MPa")

#         # if "gamma_unsat_kn_m3" in df.columns and pd.notna(layer["gamma_unsat_kn_m3"]):
#         #     label_lines.append(f"γunsat = {layer['gamma_unsat_kn_m3']:.1f} kN/m³")

#         # if "gamma_sat_kn_m3" in df.columns and pd.notna(layer["gamma_sat_kn_m3"]):
#         #     label_lines.append(f"γsat = {layer['gamma_sat_kn_m3']:.1f} kN/m³")

#         # if "c_prime_kpa" in df.columns and pd.notna(layer["c_prime_kpa"]):
#         #     label_lines.append(f"c' = {layer['c_prime_kpa']:.1f} kPa")

#         # if "phi_prime_deg" in df.columns and pd.notna(layer["phi_prime_deg"]):
#         #     label_lines.append(f"φ' = {layer['phi_prime_deg']:.1f}°")

#         # if "dilatancy_deg" in df.columns and pd.notna(layer["dilatancy_deg"]):
#         #     label_lines.append(f"ψ = {layer['dilatancy_deg']:.1f}°")

#         # label = "\n".join(label_lines)
#         y_mid = 0.5 * (y_min + y_max)

#         ax.text(
#             0.5,
#             y_mid,
#             str(layer["soil_id"]),
#             ha="center",
#             va="center",
#             fontsize=7,
#             rotation=0,
#             clip_on=True,
#         )

#     ax.set_xlim(0, 1)
#     ax.set_xticks([])
#     ax.set_ylabel("Elevation [m NAP]")
#     ax.set_xlabel("Effective\nlayers")
#     ax.set_title(title)

#     fig.tight_layout()
#     fig.savefig(output_path, dpi=250)
#     plt.close(fig)

def plot_effective_parameter_layers(
    effective_layers_df: pd.DataFrame,
    output_path: str | Path = "output/parameters/eff_layer_parameters_profile.png",
    title: str = "Layer parameters",
    soil_color_groups: Optional[dict[str, str]] = None,
    soil_group_colors: Optional[dict[str, str]] = None,
    bottom_elevation_m_nap: float = -30.0,
) -> None:
    """Plot combined effective parameter layers over elevation.

    This is intended for the eff_layer_parameters.csv output.

    Required columns:
        soil_id
        top_elevation_m_nap
        bottom_elevation_m_nap
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    required_columns = {
        "soil_id",
        "top_elevation_m_nap",
        "bottom_elevation_m_nap",
    }

    missing = required_columns - set(effective_layers_df.columns)

    if missing:
        raise ValueError(
            "Cannot plot effective layer parameters. "
            f"Missing columns: {sorted(missing)}"
        )

    if soil_color_groups is None:
        soil_color_groups = {}

    if soil_group_colors is None:
        soil_group_colors = {}

    default_color = "#FFFFFF"

    df = effective_layers_df.copy()
    df = df.sort_values("top_elevation_m_nap", ascending=False).reset_index(drop=True)

    # Keep only layers that intersect the plotted interval.
    # Layers entirely below -30 m NAP are removed.
    df = df[df["top_elevation_m_nap"].astype(float) > bottom_elevation_m_nap].copy()

    if df.empty:
        raise ValueError(
            f"No layers remain above bottom elevation {bottom_elevation_m_nap} m NAP."
        )

    # Determine top of plotted profile.
    profile_top = float(df["top_elevation_m_nap"].max())

    fig, ax = plt.subplots(figsize=(5, 9))

    for _, layer in df.iterrows():
        y_top = float(layer["top_elevation_m_nap"])
        y_bottom = float(layer["bottom_elevation_m_nap"])

        # Skip layers completely below the requested bottom elevation.
        if y_top <= bottom_elevation_m_nap:
            continue

        # Clip layer if it extends below -30 m NAP.
        y_bottom = max(y_bottom, bottom_elevation_m_nap)

        y_min = min(y_top, y_bottom)
        y_max = max(y_top, y_bottom)

        if y_max <= bottom_elevation_m_nap:
            continue

        inferred_soil_type = _infer_soil_type_from_soil_id(layer["soil_id"])
        group_name = soil_color_groups.get(inferred_soil_type, inferred_soil_type)
        color = soil_group_colors.get(group_name, default_color)

        ax.axhspan(
            y_min,
            y_max,
            xmin=0.0,
            xmax=1.0,
            facecolor=color,
            edgecolor="black",
            linewidth=0.7,
            alpha=0.85,
        )

        y_mid = 0.5 * (y_min + y_max)

        ax.text(
            0.5,
            y_mid,
            str(layer["soil_id"]),
            ha="center",
            va="center",
            fontsize=7,
            rotation=0,
            clip_on=True,
        )

    ax.set_xlim(0, 1)
    ax.set_ylim(bottom_elevation_m_nap, profile_top)

    ax.set_xticks([])
    ax.set_ylabel("Elevation [m NAP]")
    ax.set_xlabel("Effective\nlayers")
    ax.set_title(title)

    fig.tight_layout()
    fig.savefig(output_path, dpi=250)
    plt.close(fig)