"""Feature engineering and the temporal train/validation/test split.

Each row is an *issue month* ``t`` for one city. Features use only data up to
and including ``t``; targets describe month ``t + 1``. So a row answers:
"standing at the end of month t, what will next month look like?"
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .spi import fit_params, spi, transform

FEATURE_COLUMNS: list[str] = [
    "precip_anom_z",
    "precip_anom_z_lag1",
    "precip_anom_z_lag2",
    "precip_anom_z_lag11",  # same calendar month as the target, one year earlier
    "precip_anom_z_roll3",
    "precip_anom_z_roll6",
    "spi1",
    "spi3",
    "spi6",
    "spi12",
    "drought_prob_ens",
    "t2m_anom",
    "t2m_anom_roll3",
    "rh2m_anom",
    "ws10m",
    "target_month_sin",
    "target_month_cos",
    "clim_precip_mean_next",
    "lat",
    "lon",
]

REG_TARGET = "target_anom_z"  # standardized anomaly; converted back to mm for evaluation
CLF_TARGET = "target_drought"


def ensemble_drought_prob(
    precip: pd.Series,
    ref_start: int,
    ref_end: int,
    threshold: float,
    scale: int = config.DROUGHT_SPI_SCALE,
) -> np.ndarray:
    """Climatological-ensemble probability that next month's SPI is <= ``threshold``.

    Next month's SPI-``scale`` total = rain already observed in the last
    ``scale - 1`` months + next month's (unknown) rain. Each reference year's
    rainfall for that calendar month is used as one equally likely scenario for
    the unknown part, and the probability is the fraction of scenarios that end
    in drought. This is the logic of Ensemble Streamflow Prediction, and it is
    the honest baseline for SPI-3: two-thirds of the window is already known.
    """
    params = fit_params(precip, scale, ref_start, ref_end)
    known = precip.rolling(scale - 1, min_periods=scale - 1).sum().to_numpy()
    idx = precip.index
    in_ref = (idx.year >= ref_start) & (idx.year <= ref_end)
    next_month = (idx + pd.offsets.MonthBegin(1)).month
    out = np.full(len(precip), np.nan)
    for month, month_params in params.items():
        scenarios = precip[in_ref & (idx.month == month)].dropna().to_numpy()
        rows = np.flatnonzero(next_month == month)
        totals = known[rows, None] + scenarios[None, :]
        prob = (transform(totals, month_params) <= threshold).mean(axis=1)
        out[rows] = np.where(np.isnan(known[rows]), np.nan, prob)
    return out


def compute_climatology(
    df: pd.DataFrame, ref_start: int = config.REF_START, ref_end: int = config.REF_END
) -> pd.DataFrame:
    """Per-city, per-calendar-month means and standard deviations over the reference years."""
    ref = df[df["year"].between(ref_start, ref_end)]
    return (
        ref.groupby(["city", "month"])
        .agg(
            clim_precip_mean=("precip_mm", "mean"),
            clim_precip_std=("precip_mm", "std"),
            clim_t2m_mean=("t2m", "mean"),
            clim_rh2m_mean=("rh2m", "mean"),
        )
        .reset_index()
    )


def build_features(
    clean_df: pd.DataFrame,
    clim: pd.DataFrame,
    ref_start: int = config.REF_START,
    ref_end: int = config.REF_END,
    drought_threshold: float = config.DROUGHT_THRESHOLD,
) -> pd.DataFrame:
    d = clean_df.merge(clim, on=["city", "month"], how="left", validate="many_to_one")
    d = d.sort_values(["city", "date"]).reset_index(drop=True)

    d["precip_anom"] = d["precip_mm"] - d["clim_precip_mean"]
    d["precip_anom_z"] = d["precip_anom"] / d["clim_precip_std"]
    d["t2m_anom"] = d["t2m"] - d["clim_t2m_mean"]
    d["rh2m_anom"] = d["rh2m"] - d["clim_rh2m_mean"]

    spi_parts = []
    for _, g in d.groupby("city", sort=False):
        series = g.set_index("date")["precip_mm"]
        cols = {
            f"spi{s}": spi(series, s, ref_start, ref_end).to_numpy() for s in config.SPI_SCALES
        }
        cols["drought_prob_ens"] = ensemble_drought_prob(
            series, ref_start, ref_end, drought_threshold
        )
        spi_parts.append(pd.DataFrame(cols, index=g.index))
    d = d.join(pd.concat(spi_parts))

    by_city = d.groupby("city", sort=False)
    for lag in (1, 2, 11):
        d[f"precip_anom_z_lag{lag}"] = by_city["precip_anom_z"].shift(lag)
    for window in (3, 6):
        d[f"precip_anom_z_roll{window}"] = by_city["precip_anom_z"].transform(
            lambda s, w=window: s.rolling(w, min_periods=w).mean()
        )
    d["t2m_anom_roll3"] = by_city["t2m_anom"].transform(lambda s: s.rolling(3).mean())

    d["target_date"] = d["date"] + pd.offsets.MonthBegin(1)
    d["target_month"] = d["target_date"].dt.month
    d["target_month_sin"] = np.sin(2 * np.pi * d["target_month"] / 12)
    d["target_month_cos"] = np.cos(2 * np.pi * d["target_month"] / 12)
    next_clim = clim.rename(
        columns={
            "month": "target_month",
            "clim_precip_mean": "clim_precip_mean_next",
            "clim_precip_std": "clim_precip_std_next",
        }
    )[["city", "target_month", "clim_precip_mean_next", "clim_precip_std_next"]]
    d = d.merge(next_clim, on=["city", "target_month"], how="left", validate="many_to_one")

    # Targets: next month's values. NaN on each city's latest row (the live forecast row).
    by_city = d.groupby("city", sort=False)
    d["target_precip_mm"] = by_city["precip_mm"].shift(-1)
    d["target_anom_mm"] = by_city["precip_anom"].shift(-1)
    d[REG_TARGET] = by_city["precip_anom_z"].shift(-1)
    d["target_spi3"] = by_city[f"spi{config.DROUGHT_SPI_SCALE}"].shift(-1)
    d[CLF_TARGET] = (d["target_spi3"] <= drought_threshold).astype(float)
    d.loc[d["target_spi3"].isna(), CLF_TARGET] = np.nan

    return d


def modelling_rows(feat: pd.DataFrame) -> pd.DataFrame:
    """Rows usable for training/evaluation: complete features and known targets."""
    needed = FEATURE_COLUMNS + [REG_TARGET, CLF_TARGET, "target_precip_mm"]
    return feat.dropna(subset=needed).reset_index(drop=True)


def temporal_split(
    feat: pd.DataFrame, train_end: int = config.TRAIN_END, val_end: int = config.VAL_END
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by the year of the *target* month. No shuffling: the future is never trained on."""
    year = feat["target_date"].dt.year
    train = feat[year <= train_end]
    val = feat[(year > train_end) & (year <= val_end)]
    test = feat[year > val_end]
    return train, val, test
