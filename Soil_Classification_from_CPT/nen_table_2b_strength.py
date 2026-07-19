

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# =============================================================================
# USER SETTINGS if you want to run this py file separately and not via main.py
# =============================================================================

# Folder containing classified_points.csv and interpreted_layers.csv.
OUTPUT_DIR = r"C:\AA_Thesis\VSCode\lengkeek_vs_code\S1022749_CPTU1-2"

CLASSIFIED_POINTS_CSV = "classified_points.csv"
INTERPRETED_LAYERS_CSV = "interpreted_layers.csv"

OUTPUT_CSV = "layer_parameters.csv"
# -------------------------------------------------------------------------------

# =============================================================================
# NEN TABLE 2.B DATA
# =============================================================================
# IMPORTANT:
# These values should be manually checked against your NEN Table 2.b source.
#
# Where the table gives a range, this script uses the average of the range.
# Example:
#   gamma = 19 - 20  -> 19.5
#   phi'  = 35 - 40  -> 37.5
#
# qc_ref_mpa is used as the interpolation coordinate.

NEN_TABLE_2B = pd.DataFrame(
    [
        # ---------------------------------------------------------------------
        # Gravel / Grind
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Zwak siltig",
            "nen_basis": "Los",
            "qc_ref_mpa": 15.0,
            "gamma_unsat_kn_m3": 17.0,
            "gamma_sat_kn_m3": 19.0,
            "E100_mpa": 45.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 32.5,
        },
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Zwak siltig",
            "nen_basis": "Matig",
            "qc_ref_mpa": 25.0,
            "gamma_unsat_kn_m3": 18.0,
            "gamma_sat_kn_m3": 20.0,
            "E100_mpa": 75.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 35.0,
        },
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Zwak siltig",
            "nen_basis": "Vast",
            "qc_ref_mpa": 30.0,
            "gamma_unsat_kn_m3": 19.5,
            "gamma_sat_kn_m3": 21.5,
            "E100_mpa": 97.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 38.75,
        },
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Sterk siltig",
            "nen_basis": "Los",
            "qc_ref_mpa": 10.0,
            "gamma_unsat_kn_m3": 18.0,
            "gamma_sat_kn_m3": 20.0,
            "E100_mpa": 30.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 30.0,
        },
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Sterk siltig",
            "nen_basis": "Matig",
            "qc_ref_mpa": 15.0,
            "gamma_unsat_kn_m3": 19.0,
            "gamma_sat_kn_m3": 21.0,
            "E100_mpa": 45.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 32.5,
        },
        {
            "nen_soil_main": "Grind",
            "nen_soil_sub": "Sterk siltig",
            "nen_basis": "Vast",
            "qc_ref_mpa": 30.0,
            "gamma_unsat_kn_m3": 20.5,
            "gamma_sat_kn_m3": 22.25,
            "E100_mpa": 92.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 37.5,
        },

        # ---------------------------------------------------------------------
        # Sand / Zand - clean
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Zand",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Los",
            "qc_ref_mpa": 5.0,
            "gamma_unsat_kn_m3": 17.0,
            "gamma_sat_kn_m3": 19.0,
            "E100_mpa": 15.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 30.0,
        },
        {
            "nen_soil_main": "Zand",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Matig",
            "qc_ref_mpa": 15.0,
            "gamma_unsat_kn_m3": 18.0,
            "gamma_sat_kn_m3": 20.0,
            "E100_mpa": 45.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 32.5,
        },
        {
            "nen_soil_main": "Zand",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Vast",
            "qc_ref_mpa": 25.0,
            "gamma_unsat_kn_m3": 19.5,
            "gamma_sat_kn_m3": 21.5,
            "E100_mpa": 92.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 37.5,
        },

        # ---------------------------------------------------------------------
        # Sand / Zand - silty/clayey
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Zand",
            "nen_soil_sub": "Zwak siltig, kleiig",
            "nen_basis": "-",
            "qc_ref_mpa": 12.0,
            "gamma_unsat_kn_m3": 18.5,
            "gamma_sat_kn_m3": 20.5,
            "E100_mpa": 42.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 29.75,
        },
        {
            "nen_soil_main": "Zand",
            "nen_soil_sub": "Sterk siltig, kleiig",
            "nen_basis": "-",
            "qc_ref_mpa": 8.0,
            "gamma_unsat_kn_m3": 18.5,
            "gamma_sat_kn_m3": 20.5,
            "E100_mpa": 22.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 27.5,
        },

        # ---------------------------------------------------------------------
        # Loam / Leem
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Leem",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Slap",
            "qc_ref_mpa": 1.0,
            "gamma_unsat_kn_m3": 19.0,
            "gamma_sat_kn_m3": 19.0,
            "E100_mpa": 2.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 28.75,
        },
        {
            "nen_soil_main": "Leem",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Matig",
            "qc_ref_mpa": 2.0,
            "gamma_unsat_kn_m3": 20.0,
            "gamma_sat_kn_m3": 20.0,
            "E100_mpa": 3.0,
            "c_prime_kpa": 1.0,
            "phi_prime_deg": 30.0,
        },
        {
            "nen_soil_main": "Leem",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Vast",
            "qc_ref_mpa": 3.0,
            "gamma_unsat_kn_m3": 21.5,
            "gamma_sat_kn_m3": 21.5,
            "E100_mpa": 6.0,
            "c_prime_kpa": 3.15,
            "phi_prime_deg": 31.25,
        },
        {
            "nen_soil_main": "Leem",
            "nen_soil_sub": "Sterk zandig",
            "nen_basis": "-",
            "qc_ref_mpa": 2.0,
            "gamma_unsat_kn_m3": 19.5,
            "gamma_sat_kn_m3": 19.5,
            "E100_mpa": 4.0,
            "c_prime_kpa": 0.5,
            "phi_prime_deg": 31.25,
        },

        # ---------------------------------------------------------------------
        # Clay / Klei
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Slap",
            "qc_ref_mpa": 0.5,
            "gamma_unsat_kn_m3": 14.0,
            "gamma_sat_kn_m3": 14.0,
            "E100_mpa": 1.0,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 17.5,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Matig",
            "qc_ref_mpa": 1.0,
            "gamma_unsat_kn_m3": 17.0,
            "gamma_sat_kn_m3": 17.0,
            "E100_mpa": 2.0,
            "c_prime_kpa": 5.0,
            "phi_prime_deg": 17.5,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Schoon",
            "nen_basis": "Vast",
            "qc_ref_mpa": 2.0,
            "gamma_unsat_kn_m3": 19.5,
            "gamma_sat_kn_m3": 19.5,
            "E100_mpa": 7.0,
            "c_prime_kpa": 14.0,
            "phi_prime_deg": 21.25,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Slap",
            "qc_ref_mpa": 0.7,
            "gamma_unsat_kn_m3": 15.0,
            "gamma_sat_kn_m3": 15.0,
            "E100_mpa": 1.5,
            "c_prime_kpa": 0.0,
            "phi_prime_deg": 22.5,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Matig",
            "qc_ref_mpa": 1.5,
            "gamma_unsat_kn_m3": 18.0,
            "gamma_sat_kn_m3": 18.0,
            "E100_mpa": 3.0,
            "c_prime_kpa": 5.0,
            "phi_prime_deg": 22.5,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Zwak zandig",
            "nen_basis": "Vast",
            "qc_ref_mpa": 2.5,
            "gamma_unsat_kn_m3": 20.5,
            "gamma_sat_kn_m3": 20.5,
            "E100_mpa": 7.5,
            "c_prime_kpa": 14.0,
            "phi_prime_deg": 25.0,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Sterk zandig",
            "nen_basis": "-",
            "qc_ref_mpa": 1.0,
            "gamma_unsat_kn_m3": 19.0,
            "gamma_sat_kn_m3": 19.0,
            "E100_mpa": 3.5,
            "c_prime_kpa": 5.0,
            "phi_prime_deg": 30.0,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Organisch",
            "nen_basis": "Slap",
            "qc_ref_mpa": 0.2,
            "gamma_unsat_kn_m3": 13.0,
            "gamma_sat_kn_m3": 13.0,
            "E100_mpa": 0.5,
            "c_prime_kpa": 0.5,
            "phi_prime_deg": 15.0,
        },
        {
            "nen_soil_main": "Klei",
            "nen_soil_sub": "Organisch",
            "nen_basis": "Matig",
            "qc_ref_mpa": 0.5,
            "gamma_unsat_kn_m3": 15.5,
            "gamma_sat_kn_m3": 15.5,
            "E100_mpa": 1.5,
            "c_prime_kpa": 0.5,
            "phi_prime_deg": 15.0,
        },

        # ---------------------------------------------------------------------
        # Peat / Veen
        # ---------------------------------------------------------------------
        {
            "nen_soil_main": "Veen",
            "nen_soil_sub": "Niet voorbelast",
            "nen_basis": "Slap",
            "qc_ref_mpa": 0.1,
            "gamma_unsat_kn_m3": 11.0,
            "gamma_sat_kn_m3": 11.0,
            "E100_mpa": 0.35,
            "c_prime_kpa": 1.75,
            "phi_prime_deg": 15.0,
        },
        {
            "nen_soil_main": "Veen",
            "nen_soil_sub": "Matig voorbelast",
            "nen_basis": "Matig",
            "qc_ref_mpa": 0.2,
            "gamma_unsat_kn_m3": 12.5,
            "gamma_sat_kn_m3": 12.5,
            "E100_mpa": 0.75,
            "c_prime_kpa": 3.75,
            "phi_prime_deg": 15.0,
        },
    ]
)


# =============================================================================
# CPT soil type to possible NEN Table 2.b rows
# =============================================================================
# First the CPT-derived soil_type is used to choose possible NEN rows.
# Then interpolation is performed using the layer-average qc_mpa.

CPT_SOIL_TO_NEN_FILTERS = {
    "Dense sand / gravelly sand": [
        ("Grind", "Zwak siltig"),
    ],
    "Sand": [
        ("Zand", "Schoon"),
    ],
    "Sand mixtures": [
        ("Zand", "Sterk siltig, kleiig"),
    ],
    "Silty clay / clayey silt": [
        ("Leem", "Zwak zandig"),
    ],
    "Clay & silt": [
        ("Klei", "Zwak zandig"),
    ],
    "Soil, fine grain": [
        ("Klei", "Schoon"),
    ],
    "Organic clay": [
        ("Klei", "Organisch"),
    ],
    "Peat": [
        ("Veen", "Niet voorbelast"),
        ("Veen", "Matig voorbelast"),
    ],
}


PARAMETER_COLUMNS = [
    "gamma_unsat_kn_m3",
    "gamma_sat_kn_m3",
    "E100_mpa",
    "c_prime_kpa",
    "phi_prime_deg",
]


# =============================================================================
# Helper functions
# =============================================================================

def calculate_dilatancy_deg(
    nen_soil_main: Optional[str],
    phi_prime_deg: Optional[float],
) -> Optional[float]:
    """Calculate dilatancy angle for sand or gravel.

    Rule:
        psi = phi' - 30 degrees

    Applied only to:
        Zand
        Grind

    For other soils, returns None.
    """
    if nen_soil_main not in {"Zand", "Grind"}:
        return 0.0

    if phi_prime_deg is None or pd.isna(phi_prime_deg):
        return None

    return max(float(phi_prime_deg) - 30.0, 0.0)


def _select_nen_candidates(soil_type: str) -> Optional[pd.DataFrame]:
    """Return possible NEN rows for a CPT-derived soil_type.

    If no mapping exists, return None.
    This is used for Unknown material or unsupported classifications.
    """
    filters = CPT_SOIL_TO_NEN_FILTERS.get(soil_type)

    if not filters:
        return None

    combined_mask = pd.Series(False, index=NEN_TABLE_2B.index)

    for main_soil, sub_soil in filters:
        mask = (
            (NEN_TABLE_2B["nen_soil_main"] == main_soil)
            & (NEN_TABLE_2B["nen_soil_sub"] == sub_soil)
        )
        combined_mask = combined_mask | mask

    candidates = NEN_TABLE_2B[combined_mask].copy()

    if candidates.empty:
        return None

    return candidates.sort_values("qc_ref_mpa").reset_index(drop=True)

def _interpolate_row(candidates: pd.DataFrame, qc_mean_mpa: float) -> dict:
    """Interpolate NEN parameters using average qc.

    If qc_mean_mpa is outside the candidate qc range, the values are clipped to
    the nearest available table row.
    """
    candidates = candidates.sort_values("qc_ref_mpa").reset_index(drop=True)
    qc_values = candidates["qc_ref_mpa"].astype(float).to_numpy()

    result = {}

    if qc_mean_mpa <= qc_values.min():
        chosen = candidates.iloc[0]

        result["nen_soil_main"] = chosen["nen_soil_main"]
        result["nen_soil_sub"] = chosen["nen_soil_sub"]
        result["nen_basis"] = chosen["nen_basis"]
        result["interpolation_status"] = "below_range_clipped"

        for col in PARAMETER_COLUMNS:
            result[col] = float(chosen[col])

        return result

    if qc_mean_mpa >= qc_values.max():
        chosen = candidates.iloc[-1]

        result["nen_soil_main"] = chosen["nen_soil_main"]
        result["nen_soil_sub"] = chosen["nen_soil_sub"]
        result["nen_basis"] = chosen["nen_basis"]
        result["interpolation_status"] = "above_range_clipped"

        for col in PARAMETER_COLUMNS:
            result[col] = float(chosen[col])

        return result

    upper_index = int(np.searchsorted(qc_values, qc_mean_mpa, side="right"))
    lower_index = upper_index - 1

    lower = candidates.iloc[lower_index]
    upper = candidates.iloc[upper_index]

    qc_lower = float(lower["qc_ref_mpa"])
    qc_upper = float(upper["qc_ref_mpa"])

    t = (qc_mean_mpa - qc_lower) / (qc_upper - qc_lower)

    result["nen_soil_main"] = lower["nen_soil_main"]
    result["nen_soil_sub"] = lower["nen_soil_sub"]
    result["nen_basis"] = f"{lower['nen_basis']} - {upper['nen_basis']}"
    result["interpolation_status"] = "interpolated"

    for col in PARAMETER_COLUMNS:
        lower_value = float(lower[col])
        upper_value = float(upper[col])
        result[col] = lower_value + t * (upper_value - lower_value)

    return result


def _calculate_layer_mean_qc(classified_points: pd.DataFrame) -> pd.DataFrame:
    """Calculate average qc_mpa per layer_id."""
    required = {"layer_id", "qc_mpa"}
    missing = required - set(classified_points.columns)

    if missing:
        raise ValueError(
            f"classified_points.csv is missing required columns: {sorted(missing)}"
        )

    return (
        classified_points
        .dropna(subset=["layer_id", "qc_mpa"])
        .groupby("layer_id", as_index=False)
        .agg(qc_mpa_mean=("qc_mpa", "mean"))
    )


def assign_nen_2b_strength(
    interpreted_layers: pd.DataFrame,
    classified_points: pd.DataFrame,
) -> pd.DataFrame:
    """Assign NEN Table 2.b parameters to interpreted CPT layers."""
    required_layers = {
        "layer_id",
        "soil_type",
        "top_elevation_m_nap",
        "bottom_elevation_m_nap",
    }

    missing = required_layers - set(interpreted_layers.columns)

    if missing:
        raise ValueError(
            f"interpreted_layers.csv is missing required columns: {sorted(missing)}"
        )

    qc_by_layer = _calculate_layer_mean_qc(classified_points)

    layers = interpreted_layers.merge(
        qc_by_layer,
        on="layer_id",
        how="left",
    )

    output_rows = []

    for _, layer in layers.iterrows():
        layer_id = layer["layer_id"]
        soil_type = layer["soil_type"]
        qc_mean = layer["qc_mpa_mean"]

        row = {
            "soil_id": layer_id,
            "top_elevation_m_nap": layer["top_elevation_m_nap"],
            "bottom_elevation_m_nap": layer["bottom_elevation_m_nap"],
            "soil depth_m": layer["top_elevation_m_nap"] - layer["bottom_elevation_m_nap"],
            "qc_mpa_mean": qc_mean,
        }

        if pd.isna(qc_mean):
            row.update(
                {
                    "nen_soil_main": None,
                    "nen_soil_sub": None,
                    "nen_basis": None,
                    "gamma_unsat_kn_m3": None,
                    "gamma_sat_kn_m3": None,
                    "E100_mpa": None,
                    "c_prime_kpa": None,
                    "phi_prime_deg": None,
                    "dilatancy_deg": None,
                    "interpolation_status": "no_qc_available",
                }
            )
            output_rows.append(row)
            continue

        candidates = _select_nen_candidates(str(soil_type))

        if candidates is None:
            row.update(
                {
                    "nen_soil_main": "Unknown material",
                    "nen_soil_sub": None,
                    "nen_basis": None,
                    "gamma_unsat_kn_m3": None,
                    "gamma_sat_kn_m3": None,
                    "E100_mpa": None,
                    "c_prime_kpa": None,
                    "phi_prime_deg": None,
                    "dilatancy_deg": None,
                    "interpolation_status": "no_nen_mapping_available",
                }
            )
            output_rows.append(row)
            continue
        
        
        row["nen_soil_main"] = candidates.iloc[0]["nen_soil_main"]
        row["nen_soil_sub"] = candidates.iloc[0]["nen_soil_sub"]

        nen_values = _interpolate_row(candidates, float(qc_mean))

        row.update(nen_values)

        row["dilatancy_deg"] = calculate_dilatancy_deg(
            nen_soil_main=row["nen_soil_main"],
            phi_prime_deg=row["phi_prime_deg"],
        )

        output_rows.append(row)

    result = pd.DataFrame(output_rows)

    # Clean deliverable column order.
    output_columns = [
        "soil_id",
        "top_elevation_m_nap",
        "bottom_elevation_m_nap",
        "soil depth_m",
        "qc_mpa_mean",
        # "nen_soil_main",
        # "nen_soil_sub",
        # "nen_basis",
        "gamma_unsat_kn_m3",
        "gamma_sat_kn_m3",
        "E100_mpa",
        "c_prime_kpa",
        "phi_prime_deg",
        "dilatancy_deg",
        "interpolation_status",
    ]

    output_columns = [col for col in output_columns if col in result.columns]
    result = result[output_columns]

    # Round output for clean CSV deliverable.
    rounding = {
        "top_elevation_m_nap": 3,
        "bottom_elevation_m_nap": 3,
        "qc_mpa_mean": 2,
        "gamma_unsat_kn_m3": 1,
        "gamma_sat_kn_m3": 1,
        "E100_mpa": 2,
        "c_prime_kpa": 2,
        "phi_prime_deg": 1,
        "dilatancy_deg": 1,
    }

    for col, decimals in rounding.items():
        if col in result.columns:
            result[col] = result[col].round(decimals)

    return result

def combine_equal_parameter_layers(
    layer_parameters: pd.DataFrame,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Combine neighbouring layers with identical strength parameters.

    This creates an effective layer parameter table.

    Parameters
    ----------
    layer_parameters:
        Output from assign_nen_2b_strength().

    max_rows:
        Optional. If given, only the first max_rows are used.
        This is useful if you want to exclude deeper layers from the effective
        parameter table.

    Returns
    -------
    combined:
        DataFrame with neighbouring rows merged when their selected parameter
        values are equal.
    """
    df = layer_parameters.copy()

    if df.empty:
        return df.copy()

    same_value_cols = [
        "gamma_unsat_kn_m3",
        "gamma_sat_kn_m3",
        "E100_mpa",
        "c_prime_kpa",
        "phi_prime_deg",
        "dilatancy_deg",
    ]

    same_value_cols = [col for col in same_value_cols if col in df.columns]

    if not same_value_cols:
        raise ValueError(
            "Cannot combine layers because none of the parameter columns are present."
        )

    # Avoid tiny floating-point differences preventing merging.
    df_compare = df[same_value_cols].round(6)

    group_id = (
        (df_compare != df_compare.shift())
        .any(axis=1)
        .cumsum()
    )

    agg_dict = {
        "soil_id": ("soil_id", lambda x: " + ".join(x.astype(str))),
        "top_elevation_m_nap": ("top_elevation_m_nap", "first"),
        "bottom_elevation_m_nap": ("bottom_elevation_m_nap", "last"),
        "qc_mpa_mean": ("qc_mpa_mean", "mean"),
    }

    optional_first_cols = [
        "nen_soil_main",
        "nen_soil_sub",
        "nen_basis",
        "gamma_unsat_kn_m3",
        "gamma_sat_kn_m3",
        "E100_mpa",
        "c_prime_kpa",
        "phi_prime_deg",
        "dilatancy_deg",
        "interpolation_status",
    ]

    for col in optional_first_cols:
        if col in df.columns:
            agg_dict[col] = (col, "first")

    combined = (
        df.groupby(group_id, as_index=False)
        .agg(**agg_dict)
    )

    rounding = {
        "top_elevation_m_nap": 3,
        "bottom_elevation_m_nap": 3,
        "qc_mpa_mean": 2,
        "gamma_unsat_kn_m3": 1,
        "gamma_sat_kn_m3": 1,
        "E100_mpa": 2,
        "c_prime_kpa": 2,
        "phi_prime_deg": 1,
        "dilatancy_deg": 1,
    }

    for col, decimals in rounding.items():
        if col in combined.columns:
            combined[col] = combined[col].round(decimals)

    return combined



def main() -> None:
    output_dir = Path(OUTPUT_DIR)

    interpreted_layers_path = output_dir / INTERPRETED_LAYERS_CSV
    classified_points_path = output_dir / CLASSIFIED_POINTS_CSV
    output_path = output_dir / OUTPUT_CSV

    interpreted_layers = pd.read_csv(interpreted_layers_path)
    classified_points = pd.read_csv(classified_points_path)

    result = assign_nen_2b_strength(
        interpreted_layers=interpreted_layers,
        classified_points=classified_points,
    )

    result.to_csv(output_path, index=False)

    print("")
    print("NEN Table 2.b strength assignment complete.")
    print(f"Input layers: {interpreted_layers_path}")
    print(f"Input classified points: {classified_points_path}")
    print(f"Output: {output_path}")
    print("")


if __name__ == "__main__":
    main()