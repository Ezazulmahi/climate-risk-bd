"""Synthetic data so the test suite runs offline in seconds."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from climrisk.config import City

CITIES = (City("Alpha", 23.0, 90.0), City("Beta", 25.0, 89.0))
# A Bangladesh-like seasonal cycle (mm/month).
SEASONAL_MEAN = np.array([8, 20, 50, 120, 260, 380, 400, 340, 280, 150, 30, 8], dtype=float)


def make_monthly(start="1981-01", end="2024-12", seed=0) -> pd.DataFrame:
    """Clean-format monthly table with gamma-distributed rain and a weak AR(1) signal."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="MS")
    frames = []
    for city in CITIES:
        n = len(dates)
        signal = np.zeros(n)
        for i in range(1, n):
            signal[i] = 0.4 * signal[i - 1] + rng.normal(0, 0.3)
        season = np.sin(2 * np.pi * (dates.month - 4) / 12)
        mean = SEASONAL_MEAN[dates.month - 1] * np.exp(signal)
        precip = rng.gamma(shape=3.0, scale=mean / 3.0)
        frames.append(
            pd.DataFrame(
                {
                    "city": city.name,
                    "lat": city.lat,
                    "lon": city.lon,
                    "date": dates,
                    "year": dates.year,
                    "month": dates.month,
                    "precip_mm": precip,
                    "t2m": 26 + 5 * season + rng.normal(0, 0.5, n),
                    "t2m_max": 31 + rng.normal(0, 0.5, n),
                    "t2m_min": 21 + rng.normal(0, 0.5, n),
                    "rh2m": np.clip(75 + 10 * signal + rng.normal(0, 2, n), 0, 100),
                    "ws10m": 8 + rng.normal(0, 1, n),
                    "heatwave_days": rng.poisson(np.clip(8 * season, 0, None)).astype(float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(scope="session")
def monthly() -> pd.DataFrame:
    return make_monthly()

