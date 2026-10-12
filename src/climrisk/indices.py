"""Large-scale climate indices: ENSO (ONI) and the Indian Ocean Dipole (DMI).

Both are joined to the issue month with the delay a forecaster would really
face, so a backtest never sees an index value before it was published:

- ONI (NOAA CPC): 3-month running SST anomaly in the Nino-3.4 region. The
  season ending in month t (e.g. JAS for September) is published in the first
  days of month t+1, about when ERA5 finishes month t. Used at lag 0.
- DMI (NOAA PSL, HadISST): western minus eastern tropical Indian Ocean SST
  anomaly. The file is updated irregularly and runs about four months behind,
  so the value for month t-4 is used.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
DMI_URL = "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"
DMI_LAG_MONTHS = 4

# Season code -> its last month (ONI rows are labelled by 3-letter season).
SEASON_END = {
    "DJF": 2, "JFM": 3, "FMA": 4, "MAM": 5, "AMJ": 6, "MJJ": 7,
    "JJA": 8, "JAS": 9, "ASO": 10, "SON": 11, "OND": 12, "NDJ": 1,
}


def parse_oni(text: str) -> pd.Series:
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 4 or parts[0] not in SEASON_END:
            continue
        season, year, _, anom = parts
        end_month = SEASON_END[season]
        # NDJ of year Y ends in January of Y+1.
        end_year = int(year) + (1 if season == "NDJ" else 0)
        rows.append((pd.Timestamp(end_year, end_month, 1), float(anom)))
    return pd.Series(dict(rows), name="oni").sort_index()


def parse_dmi(text: str) -> pd.Series:
    rows = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 13 or not parts[0].isdigit():
            continue
        year = int(parts[0])
        for month, value in enumerate(parts[1:], start=1):
            v = float(value)
            if v > -99:
                rows[pd.Timestamp(year, month, 1)] = v
    return pd.Series(rows, name="dmi").sort_index()


def _fetch(url: str, path: Path, refresh: bool) -> str:
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resp.text, encoding="utf-8")
    return resp.text


def load_indices(refresh: bool = False, raw_dir: Path = config.RAW_DIR) -> pd.DataFrame:
    """Monthly table keyed by *issue* month with the values available at that time."""
    oni = parse_oni(_fetch(ONI_URL, raw_dir / "oni.ascii.txt", refresh))
    dmi = parse_dmi(_fetch(DMI_URL, raw_dir / "dmi.had.long.data", refresh))
    months = pd.date_range(min(oni.index.min(), dmi.index.min()), pd.Timestamp.today(), freq="MS")
    out = pd.DataFrame(index=months)
    out["oni"] = oni.reindex(months)
    out[f"dmi_lag{DMI_LAG_MONTHS}"] = dmi.reindex(months).shift(DMI_LAG_MONTHS)
    return out.rename_axis("date").reset_index()
