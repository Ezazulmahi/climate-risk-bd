"""Download ERA5 daily reanalysis from the Open-Meteo archive and aggregate to months.

Why ERA5 and not NASA POWER: POWER's corrected precipitation (PRECTOTCORR) is not
homogeneous over Bangladesh - Dhaka's annual total roughly doubles between the
1990s and the late 2010s, a step change that does not appear in ERA5 or in the
gauge record. Anomaly and drought indices assume a stable baseline, so the
project uses ERA5. ``scripts/check_power_homogeneity.py`` reproduces the
comparison.

Raw API responses are cached as JSON under ``data/raw`` so reruns are offline
and reproducible; pass ``refresh=True`` to re-download.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from . import config
from .config import City

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo daily variable -> our column name, and how to aggregate it to a month.
DAILY_VARS: dict[str, tuple[str, str]] = {
    "precipitation_sum": ("precip_mm", "sum"),
    "temperature_2m_mean": ("t2m", "mean"),
    "temperature_2m_max": ("t2m_max", "mean"),
    "temperature_2m_min": ("t2m_min", "mean"),
    "relative_humidity_2m_mean": ("rh2m", "mean"),
    "wind_speed_10m_mean": ("ws10m", "mean"),
}


def _cache_path(city: City, start: str, end: str, raw_dir: Path) -> Path:
    return raw_dir / f"{city.name.lower()}_{start}_{end}.json"


def fetch_city(
    city: City,
    start: str = f"{config.START_YEAR}-01-01",
    end: str | None = None,
    raw_dir: Path = config.RAW_DIR,
    refresh: bool = False,
    retries: int = 4,
) -> dict:
    """Return the Open-Meteo JSON payload for one city, using the on-disk cache if present.

    ``end`` defaults to today; the archive simply returns nulls for days ERA5 has
    not reached yet (about a week of latency).
    """
    if not refresh:
        # Reuse the newest cached download unless a specific end date was requested.
        pattern = _cache_path(city, start, end or "*", raw_dir).name
        cached = sorted(raw_dir.glob(pattern))
        if cached:
            return json.loads(cached[-1].read_text(encoding="utf-8"))

    end = end or date.today().isoformat()
    path = _cache_path(city, start, end, raw_dir)

    query = {
        "latitude": city.lat,
        "longitude": city.lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "models": config.REANALYSIS_MODEL,
        "timezone": "Asia/Dhaka",
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(ARCHIVE_URL, params=query, timeout=180)
            resp.raise_for_status()
            payload = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise
            # A 46-year request counts as many "calls" against Open-Meteo's per-minute
            # quota, so a 429 needs a full minute to clear.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            wait = 65 if status == 429 else 10 * attempt
            log.warning("Request for %s failed (%s); retrying in %ss", city.name, exc, wait)
            time.sleep(wait)

    raw_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def parse_daily(payload: dict) -> pd.DataFrame:
    daily = payload["daily"]
    df = pd.DataFrame({k: daily[k] for k in DAILY_VARS if k in daily})
    df.index = pd.to_datetime(daily["time"])
    return df.astype(float)


def to_monthly(daily: pd.DataFrame, city: City, min_coverage: float = 1.0) -> pd.DataFrame:
    """Aggregate daily values to calendar months.

    A month is kept only if at least ``min_coverage`` of its days have precipitation;
    by default that means complete months only, which drops the current partial
    month. A partial monthly *sum* would look like a drought.
    """
    month = daily.index.to_period("M")
    agg = {}
    for var, (name, how) in DAILY_VARS.items():
        if var in daily:
            agg[name] = daily[var].groupby(month).agg(how)
    out = pd.DataFrame(agg)
    days_present = daily["precipitation_sum"].notna().groupby(month).sum()
    days_in_month = out.index.days_in_month
    out["days_with_data"] = days_present
    out = out[days_present >= min_coverage * days_in_month]

    out = out.reset_index(names="period")
    out["date"] = out["period"].dt.to_timestamp()
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    out.insert(0, "city", city.name)
    out["lat"] = city.lat
    out["lon"] = city.lon
    return out.drop(columns="period")


def ingest(
    cities: Iterable[City] = config.CITIES,
    raw_dir: Path = config.RAW_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load every city. A city that cannot be downloaded is skipped with an error
    log (and listed by the clean report) rather than aborting the whole run."""
    frames = []
    for city in cities:
        log.info("Loading %s", city.name)
        try:
            payload = fetch_city(city, raw_dir=raw_dir, refresh=refresh)
        except requests.RequestException as exc:
            log.error("Skipping %s: download failed (%s)", city.name, exc)
            continue
        frames.append(to_monthly(parse_daily(payload), city))
    if not frames:
        raise RuntimeError("No city could be loaded")
    return pd.concat(frames, ignore_index=True)
