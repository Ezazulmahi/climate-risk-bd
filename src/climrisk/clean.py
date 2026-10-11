"""Data cleaning: physical range checks, calendar completeness, gap filling."""

from __future__ import annotations

import numpy as np
import pandas as pd

# Plausible monthly ranges for Bangladesh; anything outside is treated as missing.
VALID_RANGES = {
    "precip_mm": (0.0, 3000.0),  # monthly total
    "t2m": (0.0, 45.0),
    "t2m_max": (0.0, 50.0),
    "t2m_min": (-5.0, 40.0),
    "rh2m": (0.0, 100.0),
    "ws10m": (0.0, 100.0),  # km/h, monthly mean
}
MAX_GAP_MONTHS = 2  # interior gaps up to this length are interpolated (not precipitation)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return a cleaned copy of the monthly table and a report of what was changed.

    Steps, per city:
    1. Values outside :data:`VALID_RANGES` -> NaN.
    2. Drop duplicate (city, month) rows.
    3. Reindex to a complete monthly calendar, so ``shift(1)`` always means
       "previous month" downstream. Missing months show up as NaN rather than
       silently disappearing.
    4. Trim trailing months with no precipitation (the reanalysis lags real time).
    5. Linearly interpolate short interior gaps in the *meteorological* covariates.
       Precipitation gaps are left as NaN: inventing rainfall would contaminate
       both the SPI and the targets.
    """
    df = raw.copy()
    value_cols = [c for c in VALID_RANGES if c in df.columns]
    report: dict = {"rows_in": int(len(df))}

    df[value_cols] = df[value_cols].astype(float)
    report["missing_in"] = {c: int(df[c].isna().sum()) for c in value_cols}

    out_of_range = {}
    for col in value_cols:
        lo, hi = VALID_RANGES[col]
        bad = df[col].notna() & ~df[col].between(lo, hi)
        out_of_range[col] = int(bad.sum())
        df.loc[bad, col] = np.nan
    report["out_of_range"] = out_of_range

    dupes = df.duplicated(["city", "date"])
    report["duplicates_dropped"] = int(dupes.sum())
    df = df[~dupes]

    cities = []
    added = trimmed = interpolated = 0
    covariates = [c for c in value_cols if c != "precip_mm"]
    for _, g in df.groupby("city", sort=False):
        g = g.set_index("date").sort_index()
        full = pd.date_range(g.index.min(), g.index.max(), freq="MS")
        added += len(full) - len(g)
        g = g.reindex(full)
        for col in ("city", "lat", "lon"):
            g[col] = g[col].ffill().bfill()

        last_valid = g["precip_mm"].last_valid_index()
        trimmed += int((g.index > last_valid).sum())
        g = g.loc[:last_valid].copy()

        before = int(g[covariates].isna().sum().sum())
        g[covariates] = g[covariates].interpolate(
            method="linear", limit=MAX_GAP_MONTHS, limit_area="inside"
        )
        interpolated += before - int(g[covariates].isna().sum().sum())
        cities.append(g)

    df = pd.concat(cities).rename_axis("date").reset_index()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    report["calendar_months_added"] = added
    report["trailing_months_trimmed"] = trimmed
    report["covariate_values_interpolated"] = interpolated
    report["precip_missing_after_clean"] = int(df["precip_mm"].isna().sum())
    report["rows_out"] = int(len(df))
    report["period"] = [f"{df['date'].min():%Y-%m}", f"{df['date'].max():%Y-%m}"]

    cols = ["city", "lat", "lon", "date", "year", "month", *value_cols]
    return df[cols].sort_values(["city", "date"]).reset_index(drop=True), report
