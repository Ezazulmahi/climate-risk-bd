"""Project-wide constants: locations, periods, paths.

Everything that defines *what experiment we ran* lives here so it is easy to audit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("CLIMRISK_HOME", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

CLEAN_PATH = PROCESSED_DIR / "monthly_clean.csv"
FEATURES_PATH = PROCESSED_DIR / "features.csv"
BUNDLE_PATH = MODELS_DIR / "model_bundle.joblib"
METRICS_PATH = REPORTS_DIR / "metrics.json"


@dataclass(frozen=True)
class City:
    name: str
    lat: float
    lon: float


# One point per administrative division (approximate city-centre coordinates).
CITIES: tuple[City, ...] = (
    City("Dhaka", 23.81, 90.41),
    City("Chattogram", 22.36, 91.78),
    City("Khulna", 22.85, 89.54),
    City("Rajshahi", 24.37, 88.60),
    City("Sylhet", 24.89, 91.87),
    City("Barishal", 22.70, 90.37),
    City("Rangpur", 25.74, 89.28),
    City("Mymensingh", 24.75, 90.41),
)
CITY_BY_NAME = {c.name.lower(): c for c in CITIES}

# ERA5 via the Open-Meteo archive (https://open-meteo.com/en/docs/historical-weather-api).
# Pinning the model to "era5" avoids the archive's default blend, which mixes in
# other products for recent dates and would break homogeneity.
REANALYSIS_MODEL = "era5"

START_YEAR = 1981

# Temporal split, by the year of the month being *predicted*.
TRAIN_END = 2015  # train: 1982 .. 2015
VAL_END = 2019  # validation: 2016 .. 2019 (model selection, thresholds, interval calibration)
#                 test: 2020 .. latest (touched once, in evaluate)

# Climatology and SPI are calibrated on the training years only, so the test
# period never leaks into the anomaly definitions.
REF_START = START_YEAR
REF_END = TRAIN_END

SPI_SCALES: tuple[int, ...] = (1, 3, 6, 12)
DROUGHT_SPI_SCALE = 3
DROUGHT_THRESHOLD = -1.0  # SPI-3 <= -1.0 is "moderately dry" or worse (McKee et al., 1993)
INTERVAL_ALPHA = 0.2  # 80% prediction intervals

RANDOM_STATE = 42

# Bangladesh Meteorological Department: a heat-wave day has Tmax >= 36 °C
# (mild 36-38, moderate 38-40, severe 40-42, very severe >= 42).
HEATWAVE_TMAX_C = 36.0

# Add ENSO/IOD indices as features. Decided on the validation years by
# `python -m climrisk experiment` (see reports/experiments.md).
USE_CLIMATE_INDICES = False

SEASONS = {
    12: "Winter (DJF)", 1: "Winter (DJF)", 2: "Winter (DJF)",
    3: "Pre-monsoon (MAM)", 4: "Pre-monsoon (MAM)", 5: "Pre-monsoon (MAM)",
    6: "Monsoon (JJAS)", 7: "Monsoon (JJAS)", 8: "Monsoon (JJAS)", 9: "Monsoon (JJAS)",
    10: "Post-monsoon (ON)", 11: "Post-monsoon (ON)",
}
