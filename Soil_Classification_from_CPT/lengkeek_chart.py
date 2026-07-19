from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


# this is the code to have the Lengkeek chart as a background image for the CPT point plot


# =============================================================================
# USER SETTINGS
# =============================================================================

IMAGE_PATH = r"C:\AA_Thesis\VSCode\lengkeek_vs_code\lengkeek_chart_clean.jpg"
OUTPUT_PATH = r"output\lengkeek_digitised_background_check.png"

# Axis limits of the actual Lengkeek chart.
RF_MIN = 0.1
RF_MAX = 20.0

QTPA_MIN = 1.0
QTPA_MAX = 1000.0

# Manual crop settings.
CROP_LEFT = None
CROP_RIGHT = None
CROP_TOP = None
CROP_BOTTOM = None

SHOW_FIGURE = True


# =============================================================================
# Manual raster alignment tuning
# =============================================================================
# These are in log10-axis units.
# Increase X_RIGHT_SHIFT to stretch the image further to the right.
# Decrease X_LEFT_SHIFT to stretch the image further to the left.
# Increase Y_TOP_SHIFT to stretch the image upward.
# Decrease Y_BOTTOM_SHIFT to stretch the image downward.

X_LEFT_SHIFT = 0.0
X_RIGHT_SHIFT = 0.135
Y_BOTTOM_SHIFT = 0.0
Y_TOP_SHIFT = 0.02


# =============================================================================
# Helpers
# =============================================================================

def _crop_image(image_rgb: np.ndarray) -> np.ndarray:
    """Crop image using manual crop settings."""
    height, width, _ = image_rgb.shape

    left = 0 if CROP_LEFT is None else CROP_LEFT
    right = width if CROP_RIGHT is None else CROP_RIGHT
    top = 0 if CROP_TOP is None else CROP_TOP
    bottom = height if CROP_BOTTOM is None else CROP_BOTTOM

    return image_rgb[top:bottom, left:right, :]


def _log_tick_positions(values: list[float]) -> list[float]:
    return [np.log10(v) for v in values]


def _log_minor_tick_positions(vmin: float, vmax: float) -> list[float]:
    """Create minor gridline positions in log10-space.

    This mimics the visual spacing of a true matplotlib log axis.
    """
    ticks = []

    min_decade = int(np.floor(np.log10(vmin)))
    max_decade = int(np.ceil(np.log10(vmax)))

    for decade in range(min_decade, max_decade + 1):
        base = 10.0 ** decade

        for multiplier in range(2, 10):
            value = multiplier * base

            if vmin <= value <= vmax:
                ticks.append(np.log10(value))

    return ticks


def _set_log_like_axes(ax) -> None:
    """Use linear axes in log10-space, but format them like the CPT point plot.

    This keeps the raster image correctly aligned while making the grid and
    tick labels look like the normal log-log datapoint plot.
    """

    # Major labels: same style as plot_lengkeek_chart.
    # Important: do not include 20 as a labelled major tick.
    x_major_values = [0.1, 1, 10]
    y_major_values = [1, 10, 100, 1000]

    ax.set_xticks(_log_tick_positions(x_major_values))
    ax.set_xticklabels([str(v) for v in x_major_values])

    ax.set_yticks(_log_tick_positions(y_major_values))
    ax.set_yticklabels([str(v) for v in y_major_values])

    # Minor ticks/gridlines.
    x_minor_ticks = _log_minor_tick_positions(RF_MIN, RF_MAX)
    y_minor_ticks = _log_minor_tick_positions(QTPA_MIN, QTPA_MAX)

    ax.set_xticks(x_minor_ticks, minor=True)
    ax.set_yticks(y_minor_ticks, minor=True)

    # Same actual axis range as your point plot.
    ax.set_xlim(np.log10(RF_MIN), np.log10(RF_MAX))
    ax.set_ylim(np.log10(QTPA_MIN), np.log10(QTPA_MAX))

    ax.set_xlabel("Rf [%]")
    ax.set_ylabel("qt / pa [-]")

    # Similar to ax.grid(True, which="both") in your point plot.
    ax.grid(True, which="major", color="black", alpha=0.35, linewidth=0.55)
    ax.grid(True, which="minor", color="black", alpha=0.20, linewidth=0.35)

def create_lengkeek_background_axis(background_path, figsize=(8, 6), alpha=1.0):
    """
    Create a figure with the Lengkeek/Robertson chart as background.

    The axis uses the same log10-space and alignment settings as the
    normal Lengkeek chart plotting functions.
    """
    fig, ax = plt.subplots(figsize=figsize)

    image_rgb = Image.open(background_path).convert("RGB")
    image_rgb = np.array(image_rgb)
    image_rgb = _crop_image(image_rgb)

    ax.imshow(
        image_rgb,
        extent=[
            np.log10(RF_MIN) + X_LEFT_SHIFT,
            np.log10(RF_MAX) + X_RIGHT_SHIFT,
            np.log10(QTPA_MIN) + Y_BOTTOM_SHIFT,
            np.log10(QTPA_MAX) + Y_TOP_SHIFT,
        ],
        origin="upper",
        aspect="auto",
        alpha=alpha,
        zorder=0,
    )

    _set_log_like_axes(ax)

    return fig, ax


def plot_digitised_background(
    points_df: Optional[pd.DataFrame] = None,
    image_path: str | Path = IMAGE_PATH,
    output_path: str | Path = OUTPUT_PATH,
    show: bool = SHOW_FIGURE,
) -> None:
    """Show the Lengkeek image background using the same chart layout as the CPT plot.

    If points_df is provided, it must contain:
        rf_percent
        qt_over_pa
    """

    image_path = Path(image_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}\n"
            f"Put the cropped chart image in this folder and name it "
            f"'lengkeek_chart_clean.jpg', or change IMAGE_PATH."
        )

    image = Image.open(image_path).convert("RGB")
    image_rgb = np.array(image)
    image_rgb = _crop_image(image_rgb)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.imshow(
        image_rgb,
        extent=[
            np.log10(RF_MIN) + X_LEFT_SHIFT,
            np.log10(RF_MAX) + X_RIGHT_SHIFT,
            np.log10(QTPA_MIN) + Y_BOTTOM_SHIFT,
            np.log10(QTPA_MAX) + Y_TOP_SHIFT,
        ],
        origin="upper",
        aspect="auto",
    )

    _set_log_like_axes(ax)

    if points_df is not None:
        required = {"rf_percent", "qt_over_pa"}
        missing = required - set(points_df.columns)

        if missing:
            raise ValueError(f"Missing columns for plotting points: {sorted(missing)}")

        rf = points_df["rf_percent"].astype(float)
        qtpa = points_df["qt_over_pa"].astype(float)

        valid = (rf > 0) & (qtpa > 0)

        ax.scatter(
            np.log10(rf[valid]),
            np.log10(qtpa[valid]),
            s=8,
            alpha=0.55,
            label="CPT points",
        )

        ax.legend()

    ax.set_title("Lengkeek L2024-R2010 chart")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)

    plt.close(fig)
    # if show:
    #     plt.show()
    # else:
    #     plt.close(fig)


if __name__ == "__main__":
    plot_digitised_background()