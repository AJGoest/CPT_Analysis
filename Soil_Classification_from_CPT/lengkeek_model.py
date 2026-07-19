from __future__ import annotations

import math
from typing import Optional

import pandas as pd

PA_KPA = 100.0
GAMMA_W_KN_M3 = 10.0

# L2024-R2010 Table 7 constants (https://terraplus.app/docs/assets/papers/arny-lengkeek-cpt-organic-soils.pdf)
PEAT_AORG = 16.7
PEAT_BORG = 0.25
PEAT_RF_MIN = 5.1

ORG_CLAY_AORG = 10.3
ORG_CLAY_BORG = 0.15
ORG_CLAY_RF_MIN = 2.7


def calculate_qt_mpa(
    qc_mpa: float,
    u2_mpa: Optional[float],
    net_area_ratio: Optional[float],
) -> Optional[float]:
    """Calculate corrected cone resistance qt in MPa.

    Formula:
        qt = qc + u2 * (1 - a)

    where:
        qc = measured cone resistance [MPa]
        u2 = measured pore pressure [MPa]
        a  = net area ratio of the cone tip [-]

    If u2 or a is missing, the function falls back to qc.
    """
    if qc_mpa is None or qc_mpa <= 0:
        return None

    if u2_mpa is None or net_area_ratio is None:
        return qc_mpa

    return qc_mpa + u2_mpa * (1.0 - net_area_ratio)


def calculate_qt_over_pa(qt_mpa: Optional[float]) -> Optional[float]:
    """Calculate qt / pa.

    qt is in MPa.
    pa = 100 kPa = 0.1 MPa.

    Therefore:
        qt / pa = qt_mpa * 1000 / 100
                = qt_mpa * 10
    """
    if qt_mpa is None or qt_mpa <= 0:
        return None

    return qt_mpa * 1000.0 / PA_KPA


def calculate_isbt(
    qt_over_pa: Optional[float],
    rf_percent: float,
) -> Optional[float]:
    """Calculate Robertson 2010 non-normalized SBT index Isbt.

    Uses qt/pa, not raw qc/pa.
    """
    if qt_over_pa is None or rf_percent is None or qt_over_pa <= 0 or rf_percent <= 0:
        return None

    return math.sqrt(
        (3.47 - math.log10(qt_over_pa)) ** 2
        + (1.22 + math.log10(rf_percent)) ** 2
    )


def calculate_bqt(
    qt_mpa: Optional[float],
    u2_mpa: Optional[float],
    elevation_m_nap: Optional[float],
    groundwater_level_m_nap: Optional[float],
) -> Optional[float]:
    """Calculate Bqt = (u2 - u0) / qt.

    qt_mpa:
        Corrected cone resistance in MPa.

    u2_mpa:
        Measured pore pressure u2 in MPa.

    elevation_m_nap:
        Elevation of the CPT point in m NAP.

    groundwater_level_m_nap:
        Phreatic level in m NAP.

    Hydrostatic pore pressure:
        u0 = gamma_w * water_depth
        water_depth = groundwater_level_m_nap - elevation_m_nap
    """
    if (
        qt_mpa is None
        or qt_mpa <= 0
        or u2_mpa is None
        or elevation_m_nap is None
        or groundwater_level_m_nap is None
    ):
        return None

    water_depth_m = groundwater_level_m_nap - elevation_m_nap
    u0_kpa = max(water_depth_m * GAMMA_W_KN_M3, 0.0)

    qt_kpa = qt_mpa * 1000.0
    u2_kpa = u2_mpa * 1000.0

    return (u2_kpa - u0_kpa) / qt_kpa


def calculate_peat_boundary_qt_over_pa(rf_percent: float) -> Optional[float]:
    """Calculate L2024-R2010 peat boundary qt/pa.

    This is the boundary curve:
        qt/pa = aorg * (Rf - Rf,min)^borg

    It is not the measured CPT qt/pa.
    """
    if rf_percent is None or rf_percent <= PEAT_RF_MIN:
        return None

    return PEAT_AORG * (rf_percent - PEAT_RF_MIN) ** PEAT_BORG


def calculate_organic_clay_boundary_qt_over_pa(rf_percent: float) -> Optional[float]:
    """Calculate L2024-R2010 organic clay boundary qt/pa.

    This is the boundary curve:
        qt/pa = aorg * (Rf - Rf,min)^borg

    It is not the measured CPT qt/pa.
    """
    if rf_percent is None or rf_percent <= ORG_CLAY_RF_MIN:
        return None

    return ORG_CLAY_AORG * (rf_percent - ORG_CLAY_RF_MIN) ** ORG_CLAY_BORG


def passes_bqt_bounds(
    isbt: Optional[float],
    rf_percent: float,
    bqt: Optional[float],
    use_bqt: bool,
) -> bool:
    """Check Lengkeek L2024 Bqt-Isbt organic-soil bounds.

    If use_bqt is False, this filter is skipped.

    If Bqt cannot be calculated because u2 or groundwater level is missing,
    this function returns True, so the R2010 qt/pa-Rf organic bounds still work.
    """
    if not use_bqt:
        return True

    if isbt is None:
        return False

    if bqt is None:
        return True

    return (
        isbt > 2.9
        and isbt > 3.33 - 0.06 * rf_percent - 4.1 * bqt
        and isbt < 3.66 + 0.25 * rf_percent - 4.1 * bqt
    )


def fallback_robertson_2010(isbt: Optional[float]) -> str:
    """Coarse fallback classes for non-organic soil.

    The main purpose of this script is the Lengkeek organic overlay.
    The non-organic classes are grouped approximately by Isbt.
    """
    if isbt is None:
        return "Unknown material"

    if isbt > 3.60:
        return "Soil, fine grain"
    if isbt > 2.95:
        return "Clay & silt"
    if isbt > 2.60:
        return "Silty clay / clayey silt"
    if isbt > 2.05:
        return "Sand mixtures"
    if isbt > 1.31:
        return "Sand"

    return "Dense sand / gravelly sand"


def classify_point(
    qt_over_pa: Optional[float],
    rf_percent: float,
    isbt: Optional[float],
    bqt: Optional[float],
    use_bqt: bool = True,
) -> str:
    """Classify one CPT point with Lengkeek L2024-R2010 organic overlay."""
    if qt_over_pa is None or rf_percent is None or qt_over_pa <= 0 or rf_percent <= 0:
        return "Unknown material"

    # Peat first because it is the higher-Rf organic category.
    peat_boundary = calculate_peat_boundary_qt_over_pa(rf_percent)

    if peat_boundary is not None:
        if qt_over_pa <= peat_boundary and passes_bqt_bounds(
            isbt,
            rf_percent,
            bqt,
            use_bqt,
        ):
            return "Peat"

    # Organic clay second.
    organic_clay_boundary = calculate_organic_clay_boundary_qt_over_pa(rf_percent)

    if organic_clay_boundary is not None:
        if qt_over_pa <= organic_clay_boundary and passes_bqt_bounds(
            isbt,
            rf_percent,
            bqt,
            use_bqt,
        ):
            return "Organic clay"

    return fallback_robertson_2010(isbt)


def get_used_organic_boundary(
    rf_percent: float,
    soil_type: str,
) -> Optional[float]:
    """Return the boundary used for the final organic classification.

    For Peat:
        returns peat boundary.

    For Organic clay:
        returns organic clay boundary.

    For non-organic soils:
        returns None.
    """
    if soil_type == "Peat":
        return calculate_peat_boundary_qt_over_pa(rf_percent)

    if soil_type == "Organic clay":
        return calculate_organic_clay_boundary_qt_over_pa(rf_percent)

    return None


def classify_dataframe(
    df: pd.DataFrame,
    groundwater_level_m_nap: Optional[float] = None,
    net_area_ratio: Optional[float] = None,
    use_bqt: bool = True,
) -> pd.DataFrame:
    """Classify all CPT points.

    Required dataframe columns:
        depth_m
        qc_mpa
        rf_percent

    Optional dataframe columns:
        u2_mpa
        elevation_m_nap

    Constant metadata input:
        net_area_ratio

    Output columns added:
        qt_mpa
        qt_over_pa
        Isbt
        Bqt
        peat_boundary_qt_over_pa
        organic_clay_boundary_qt_over_pa
        soil_type
        used_organic_boundary_qt_over_pa
        distance_to_used_organic_boundary
    """
    out = df.copy()

    if "u2_mpa" in out.columns:
        u2_series = out["u2_mpa"]
    else:
        u2_series = pd.Series([None] * len(out))

    # Corrected cone resistance qt.
    out["qt_mpa"] = [
        calculate_qt_mpa(qc, u2, net_area_ratio)
        for qc, u2 in zip(out["qc_mpa"], u2_series)
    ]

    # Normalized corrected cone resistance qt/pa.
    out["qt_over_pa"] = [
        calculate_qt_over_pa(qt)
        for qt in out["qt_mpa"]
    ]

    # Robertson 2010 non-normalized SBT index.
    out["Isbt"] = [
        calculate_isbt(qtpa, rf)
        for qtpa, rf in zip(out["qt_over_pa"], out["rf_percent"])
    ]

    # Pore-pressure ratio Bqt.
    if "u2_mpa" in out.columns and "elevation_m_nap" in out.columns:
        out["Bqt"] = [
            calculate_bqt(qt, u2, elev, groundwater_level_m_nap)
            for qt, u2, elev in zip(
                out["qt_mpa"],
                out["u2_mpa"],
                out["elevation_m_nap"],
            )
        ]
    else:
        out["Bqt"] = None

    # Boundary values for checking/debugging.
    out["peat_boundary_qt_over_pa"] = [
        calculate_peat_boundary_qt_over_pa(rf)
        for rf in out["rf_percent"]
    ]

    out["organic_clay_boundary_qt_over_pa"] = [
        calculate_organic_clay_boundary_qt_over_pa(rf)
        for rf in out["rf_percent"]
    ]

    # Final classification.
    out["soil_type"] = [
        classify_point(qtpa, rf, isbt, bqt, use_bqt=use_bqt)
        for qtpa, rf, isbt, bqt in zip(
            out["qt_over_pa"],
            out["rf_percent"],
            out["Isbt"],
            out["Bqt"],
        )
    ]

    # Boundary actually used by the final classification.
    out["used_organic_boundary_qt_over_pa"] = [
        get_used_organic_boundary(rf, soil)
        for rf, soil in zip(out["rf_percent"], out["soil_type"])
    ]

    out["distance_to_used_organic_boundary"] = (
        out["qt_over_pa"] - out["used_organic_boundary_qt_over_pa"]
    )

    return out


def make_layers(
    classified: pd.DataFrame,
    min_thickness_m: float = 0.20,
) -> pd.DataFrame:
    """Merge consecutive classified points into interpreted layers.

    Layers are primarily reported by depth below CPT start level.

    If elevation_m_nap is present, top and bottom elevations in m NAP
    are also added.
    """
    if classified.empty:
        return pd.DataFrame(
            columns=[
                "top_depth_m",
                "bottom_depth_m",
                "top_elevation_m_nap",
                "bottom_elevation_m_nap",
                "soil_type",
                "thickness_m",
                "soil_layer_number",
                "layer_id",
            ]
        )

    df = classified.sort_values("depth_m").reset_index(drop=True)

    layers = []

    current_soil = df.loc[0, "soil_type"]
    top_depth = float(df.loc[0, "depth_m"])
    prev_depth = top_depth

    for _, row in df.iloc[1:].iterrows():
        depth = float(row["depth_m"])
        soil = row["soil_type"]

        if soil != current_soil:
            layers.append(
                {
                    "top_depth_m": top_depth,
                    "bottom_depth_m": prev_depth,
                    "soil_type": current_soil,
                }
            )

            current_soil = soil
            top_depth = prev_depth

        prev_depth = depth

    layers.append(
        {
            "top_depth_m": top_depth,
            "bottom_depth_m": prev_depth,
            "soil_type": current_soil,
        }
    )

    layers_df = pd.DataFrame(layers)
    layers_df["thickness_m"] = layers_df["bottom_depth_m"] - layers_df["top_depth_m"]

    # Simple thin-layer filter:
    # merge layers thinner than threshold into the previous layer when possible.
    filtered = []

    for row in layers_df.to_dict("records"):
        if filtered and row["thickness_m"] < min_thickness_m:
            filtered[-1]["bottom_depth_m"] = row["bottom_depth_m"]
            filtered[-1]["thickness_m"] = (
                filtered[-1]["bottom_depth_m"] - filtered[-1]["top_depth_m"]
            )
        else:
            filtered.append(row)

    layers_df = pd.DataFrame(filtered)

    # Add NAP elevations if available.
    if "elevation_m_nap" in df.columns:
        depth_to_elevation = (
            df[["depth_m", "elevation_m_nap"]]
            .dropna()
            .sort_values("depth_m")
        )

        if not depth_to_elevation.empty:
            # Since:
            #   elevation = CPT_start_level - depth
            #
            # then:
            #   CPT_start_level = elevation + depth
            first = depth_to_elevation.iloc[0]
            cpt_start_level_m_nap = float(first["elevation_m_nap"] + first["depth_m"])

            layers_df["top_elevation_m_nap"] = (
                cpt_start_level_m_nap - layers_df["top_depth_m"]
            )

            layers_df["bottom_elevation_m_nap"] = (
                cpt_start_level_m_nap - layers_df["bottom_depth_m"]
            )
    
    # add layer numbering per soil type
    layers_df["soil_layer_number"] = (
        layers_df.groupby("soil_type").cumcount() + 1
    )

    layers_df["layer_id"] = (
        layers_df["soil_type"] + " " + layers_df["soil_layer_number"].astype(str)
    )

    return layers_df

def assign_layers_to_points(
    classified_df: pd.DataFrame,
    layers_df: pd.DataFrame,
) -> pd.DataFrame:
    """Assign interpreted layer information back to every classified CPT point.

    Adds these columns to classified_df:
        layer_id
        soil_layer_number
        layer_top_depth_m
        layer_bottom_depth_m
        layer_top_elevation_m_nap
        layer_bottom_elevation_m_nap

    The original point-by-point soil_type remains unchanged.
    """
    out = classified_df.copy()

    out["layer_id"] = None
    out["soil_layer_number"] = None
    out["layer_top_depth_m"] = None
    out["layer_bottom_depth_m"] = None

    if "top_elevation_m_nap" in layers_df.columns:
        out["layer_top_elevation_m_nap"] = None

    if "bottom_elevation_m_nap" in layers_df.columns:
        out["layer_bottom_elevation_m_nap"] = None

    if out.empty or layers_df.empty:
        return out

    for _, layer in layers_df.iterrows():
        top_depth = float(layer["top_depth_m"])
        bottom_depth = float(layer["bottom_depth_m"])

        # Include top, exclude bottom.
        # The final layer gets handled below so the deepest point is not lost.
        mask = (
            (out["depth_m"] >= top_depth)
            & (out["depth_m"] < bottom_depth)
        )

        out.loc[mask, "layer_id"] = layer["layer_id"]
        out.loc[mask, "soil_layer_number"] = layer["soil_layer_number"]
        out.loc[mask, "layer_top_depth_m"] = top_depth
        out.loc[mask, "layer_bottom_depth_m"] = bottom_depth

        if "top_elevation_m_nap" in layers_df.columns:
            out.loc[mask, "layer_top_elevation_m_nap"] = layer["top_elevation_m_nap"]

        if "bottom_elevation_m_nap" in layers_df.columns:
            out.loc[mask, "layer_bottom_elevation_m_nap"] = layer["bottom_elevation_m_nap"]

    # Make sure the deepest point, which may be exactly equal to the final
    # bottom_depth_m, is assigned to the last layer.
    last_layer = layers_df.iloc[-1]
    last_bottom_depth = float(last_layer["bottom_depth_m"])

    last_mask = out["depth_m"] == last_bottom_depth

    out.loc[last_mask, "layer_id"] = last_layer["layer_id"]
    out.loc[last_mask, "soil_layer_number"] = last_layer["soil_layer_number"]
    out.loc[last_mask, "layer_top_depth_m"] = last_layer["top_depth_m"]
    out.loc[last_mask, "layer_bottom_depth_m"] = last_layer["bottom_depth_m"]

    if "top_elevation_m_nap" in layers_df.columns:
        out.loc[last_mask, "layer_top_elevation_m_nap"] = last_layer["top_elevation_m_nap"]

    if "bottom_elevation_m_nap" in layers_df.columns:
        out.loc[last_mask, "layer_bottom_elevation_m_nap"] = last_layer["bottom_elevation_m_nap"]

    return out


def classify_lengkeek_r2010(
    df: pd.DataFrame,
    groundwater_level_m_nap: Optional[float] = None,
    net_area_ratio: Optional[float] = None,
    use_bqt: bool = True,
    min_layer_thickness_m: float = 0.20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Main function called by main.py.

    Parameters
    ----------
    df:
        CPT dataframe from gef_parser.py.

    groundwater_level_m_nap:
        User-defined or GEF-derived groundwater level in m NAP.

    net_area_ratio:
        Net area ratio of the cone tip, read from GEF MEASUREMENTVAR 3.

    use_bqt:
        If True, apply the Lengkeek Bqt-Isbt pore-pressure filter where
        u2 and groundwater data are available.

    min_layer_thickness_m:
        Minimum interpreted layer thickness.

    Returns
    -------
    classified_df:
        Point-by-point CPT dataframe with qt_mpa, qt_over_pa, Isbt, Bqt,
        and soil_type.

    layers_df:
        Interpreted soil layers.
    """
    classified_df = classify_dataframe(
        df,
        groundwater_level_m_nap=groundwater_level_m_nap,
        net_area_ratio=net_area_ratio,
        use_bqt=use_bqt,
    )

    layers_df = make_layers(
        classified_df,
        min_thickness_m=min_layer_thickness_m,
    )

    classified_df = assign_layers_to_points(
        classified_df,
        layers_df,
    )
    return classified_df, layers_df