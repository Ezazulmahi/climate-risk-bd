"""Shared matplotlib styling so every figure reads as one set."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# Categorical slots, fixed order (validated palette; never cycled).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE, ORANGE, NEUTRAL = SERIES[0], SERIES[1], "#a3a29c"
BAND = "#b7d3f6"  # light blue step for interval ribbons

# Diverging dry (red) <-> wet (blue) with a gray midpoint, for SPI.
DRY_WET = LinearSegmentedColormap.from_list(
    "dry_wet", ["#8f1d1c", "#e34948", "#f0efec", "#2a78d6", "#0d366b"]
)


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.titlecolor": TEXT,
            "axes.titleweight": "semibold",
            "axes.titlesize": 12,
            "axes.titlelocation": "left",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "text.color": TEXT,
            "lines.linewidth": 2,
            "legend.frameon": False,
            "font.size": 10,
            "figure.dpi": 110,
            "savefig.dpi": 140,
            "savefig.bbox": "tight",
        }
    )


def save(fig, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
