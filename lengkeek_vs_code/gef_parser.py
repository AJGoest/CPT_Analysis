from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class GEFData:
    dataframe: pd.DataFrame

    # Elevation of the CPT starting point / ground level in m NAP.
    # This is read from the second value in #ZID.
    # Example:
    #   #ZID= 31000, -1.48, 0.03
    # means:
    #   CPT start level = NAP -1.48 m
    ground_level_m_nap: Optional[float]

    # Groundwater level in m NAP, if available in the GEF.
    # User input in main.py can override this value.
    water_level_m_nap: Optional[float]

    # Net area ratio of the cone tip, if available in the GEF.
    # Read from:
    #   #MEASUREMENTVAR= 3, 0.58, -, netto oppervlaktequotient van de conuspunt
    net_area_ratio: Optional[float]

    x: Optional[float]
    y: Optional[float]
    headers: Dict[str, str]


COLUMN_TYPE_MAP = {
    1: "depth_m",              # penetration length / depth below CPT start level
    2: "qc_mpa",               # cone resistance
    3: "fs_mpa",               # local sleeve friction
    4: "rf_percent",           # friction ratio
    6: "u2_mpa",               # pore pressure u2
    11: "corrected_depth",      # corrected depth
    21: "inclination_x_deg",        # inclination x in degrees
    22: "inclination_y_deg",        # inclination y in degrees
}


def _parse_float(value: str) -> Optional[float]:
    """Parse a float safely."""
    try:
        return float(value.strip())
    except Exception:
        return None


def _clean_voids(df: pd.DataFrame) -> pd.DataFrame:
    """Replace GEF void values with NA.

    This avoids DataFrame.applymap(), because some PLAXIS/Seequent
    Python distributions have a pandas version where applymap is unavailable.
    """
    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    return numeric_df.mask(numeric_df <= -9990)


def read_gef(path: str | Path) -> GEFData:
    """Read a Dutch GEF CPT file into a dataframe.

    Important vertical reference
    ----------------------------
    The second value in #ZID is interpreted as the CPT start elevation
    relative to NAP.

    Example:
        #ZID= 31000, -1.48, 0.03

    This means:
        CPT start level = NAP -1.48 m

    Therefore:
        elevation_m_nap = ground_level_m_nap - depth_m

    Example:
        ground_level_m_nap = -1.48
        depth_m = 2.00
        elevation_m_nap = -1.48 - 2.00 = -3.48 m NAP
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"GEF file not found: {path}")

    text = path.read_text(encoding="ISO-8859-1", errors="replace")

    if "#EOH=" not in text:
        raise ValueError("Invalid GEF file: missing #EOH= header terminator.")

    header_text, data_text = text.split("#EOH=", 1)

    headers: Dict[str, str] = {}
    col_names: Dict[int, str] = {}

    ground_level_m_nap = None
    water_level_m_nap = None
    net_area_ratio = None
    x = None
    y = None

    for line in header_text.splitlines():
        line = line.strip()

        if not line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line[1:].split("=", 1)
        key = key.strip().upper()
        raw_value = raw_value.strip()

        headers.setdefault(key, raw_value)

        if key == "COLUMNINFO":
            parts = [p.strip() for p in raw_value.split(",")]

            if len(parts) >= 4:
                try:
                    col_index = int(parts[0])
                    gef_type = int(float(parts[3]))
                    col_names[col_index] = COLUMN_TYPE_MAP.get(
                        gef_type,
                        f"col_{col_index}",
                    )
                except ValueError:
                    continue

        elif key == "ZID":
            # Example:
            #   #ZID= 31000, -1.48, 0.03
            #
            # The second value is the CPT start elevation / ground level
            # relative to NAP, in metres.
            parts = [p.strip() for p in raw_value.split(",")]

            if len(parts) >= 2:
                ground_level_m_nap = _parse_float(parts[1])

        elif key == "XYID":
            # Usually:
            #   #XYID= coordinate-system, x, y
            parts = [p.strip() for p in raw_value.split(",")]

            if len(parts) >= 3:
                x = _parse_float(parts[1])
                y = _parse_float(parts[2])

        elif key == "MEASUREMENTVAR":
            parts = [p.strip() for p in raw_value.split(",")]

            if len(parts) >= 2:
                measurement_var_id = parts[0].strip()
                measurement_value = _parse_float(parts[1])

                # MEASUREMENTVAR 3 = net area ratio of cone tip, a.
                #
                # Example:
                #   #MEASUREMENTVAR= 3, 0.58, -, netto oppervlaktequotient van de conuspunt
                #
                # This is a constant cone property, not a depth-varying CPT value.
                if measurement_var_id == "3":
                    net_area_ratio = measurement_value

                # MEASUREMENTVAR 14 is often groundwater / phreatic level.
                # This parser assumes that, if present, the value is in m NAP.
                if measurement_var_id == "14":
                    water_level_m_nap = measurement_value

    if not col_names:
        raise ValueError("No #COLUMNINFO records found. Cannot map GEF columns.")

    rows: List[List[float]] = []

    for line in data_text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        try:
            values = [float(v) for v in re.split(r"\s+", line) if v]
        except ValueError:
            continue

        if values:
            rows.append(values)

    if not rows:
        raise ValueError("No numeric measurement rows found after #EOH=.")

    max_cols = max(len(row) for row in rows)
    names = [col_names.get(i, f"col_{i}") for i in range(1, max_cols + 1)]

    normalized_rows = []

    for row in rows:
        if len(row) < max_cols:
            row = row + [None] * (max_cols - len(row))
        elif len(row) > max_cols:
            row = row[:max_cols]

        normalized_rows.append(row)

    df = pd.DataFrame(normalized_rows, columns=names)
    df = _clean_voids(df)

    # Calculate friction ratio if it is not directly available.
    # GEF usually stores qc and fs in MPa:
    #
    #   Rf [%] = fs / qc * 100
    #
    if "rf_percent" not in df.columns and {"qc_mpa", "fs_mpa"}.issubset(df.columns):
        df["rf_percent"] = (df["fs_mpa"] / df["qc_mpa"]) * 100.0

    # Calculate elevation relative to NAP.
    # This should be used for vertical plotting and layer output.
    if "depth_m" in df.columns:
        if ground_level_m_nap is not None:
            df["elevation_m_nap"] = ground_level_m_nap - df["depth_m"]
        else:
            # Fallback only if #ZID is missing.
            # This is not truly NAP-referenced.
            df["elevation_m_nap"] = -df["depth_m"]

    # Remove unusable rows.
    required_columns = [c for c in ["depth_m", "qc_mpa", "rf_percent"] if c in df.columns]

    if required_columns:
        df = df.dropna(subset=required_columns).reset_index(drop=True)

    if "qc_mpa" in df.columns:
        df = df[df["qc_mpa"] > 0].reset_index(drop=True)

    return GEFData(
        dataframe=df,
        ground_level_m_nap=ground_level_m_nap,
        water_level_m_nap=water_level_m_nap,
        net_area_ratio=net_area_ratio,
        x=x,
        y=y,
        headers=headers,
    )
