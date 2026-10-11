"""Standardized Precipitation Index (McKee, Doesken & Kleist, 1993).

For each calendar month, the ``scale``-month rainfall totals from a reference
period are fitted with a gamma distribution (with a point mass at zero). Each
total is mapped to its cumulative probability and then to a standard normal
quantile, so SPI = 0 is a typical value and SPI = -1 is roughly the driest
16% of comparable periods.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

MIN_REF_YEARS = 10

# calendar month -> (probability of zero, gamma shape, gamma scale)
SpiParams = dict[int, tuple[float, float, float]]


def fit_params(precip: pd.Series, scale: int, ref_start: int, ref_end: int) -> SpiParams:
    """Fit the per-calendar-month distributions of ``scale``-month totals."""
    if not isinstance(precip.index, pd.DatetimeIndex):
        raise TypeError("precip must have a DatetimeIndex")
    acc = precip.rolling(scale, min_periods=scale).sum()
    in_ref = (acc.index.year >= ref_start) & (acc.index.year <= ref_end)
    params: SpiParams = {}
    for month in range(1, 13):
        ref = acc[(acc.index.month == month) & in_ref].dropna()
        if len(ref) < MIN_REF_YEARS:
            continue
        positive = ref[ref > 0]
        if len(positive) < 3 or positive.nunique() < 2:
            continue
        shape, _, gscale = stats.gamma.fit(positive.to_numpy(), floc=0)
        params[month] = (float((ref <= 0).mean()), float(shape), float(gscale))
    return params


def transform(totals, month_params: tuple[float, float, float]) -> np.ndarray:
    """Map ``scale``-month totals to SPI values with one month's fitted parameters."""
    p_zero, shape, gscale = month_params
    totals = np.asarray(totals, dtype=float)
    cdf = p_zero + (1 - p_zero) * stats.gamma.cdf(np.clip(totals, 0, None), shape, scale=gscale)
    out = stats.norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6))
    return np.where(np.isnan(totals), np.nan, out)


def spi(precip: pd.Series, scale: int, ref_start: int, ref_end: int) -> pd.Series:
    """Compute SPI for one location.

    ``precip`` must be indexed by a complete, sorted monthly ``DatetimeIndex``.
    Only years ``ref_start..ref_end`` are used to fit the distributions, so the
    index can be extended into a test period without changing earlier values.
    """
    params = fit_params(precip, scale, ref_start, ref_end)
    acc = precip.rolling(scale, min_periods=scale).sum()
    out = pd.Series(np.nan, index=precip.index, name=f"spi{scale}")
    for month, mp in params.items():
        is_month = acc.index.month == month
        out[is_month] = transform(acc[is_month], mp)
    return out


def classify(spi_value: float) -> str:
    """WMO-style drought category for a single SPI value."""
    if spi_value is None or np.isnan(spi_value):
        return "unknown"
    if spi_value <= -2.0:
        return "extreme drought"
    if spi_value <= -1.5:
        return "severe drought"
    if spi_value <= -1.0:
        return "moderate drought"
    if spi_value < 1.0:
        return "near normal"
    return "wet"
