"""Bangladesh Drought Monitor: all 64 districts from CHIRPS rainfall.

CHIRPS v2.0 (Climate Hazards Center, UCSB) blends satellite rainfall estimates
with rain-gauge records at 0.05° (~5.5 km). It is the dataset FEWS NET uses
for drought monitoring, and because it includes gauges it doubles as an
independent check on the ERA5 data used by the city model.

For each district (geoBoundaries ADM2, sourced from BBS/OCHA):

- monthly rainfall = mean of the CHIRPS cells whose centres fall inside it;
- SPI-1/3/6/12, fitted on 1981–2015 like the city model;
- a drought category per month using the US Drought Monitor's SPI breakpoints
  (D0 abnormally dry to D4 exceptional drought);
- a one-month outlook: the climatological-ensemble probability that next
  month's SPI-3 is <= -1. That method matched or beat every ML model in
  the city evaluation, so it is used directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import shapely
from scipy.io import netcdf_file
from shapely.geometry import mapping, shape

from . import config
from .features import ensemble_drought_prob
from .spi import spi

log = logging.getLogger(__name__)

CHIRPS_URL = (
    "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/"
    ".precipitation/X/88.0/92.75/RANGEEDGES/Y/20.5/26.75/RANGEEDGES/data.nc"
)
BOUNDARY_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/BGD/ADM2/"
    "geoBoundaries-BGD-ADM2_simplified.geojson"
)
CHIRPS_PATH = config.RAW_DIR / "chirps" / "chirps_bgd_monthly.nc"
BOUNDARY_PATH = config.RAW_DIR / "boundaries" / "bgd_adm2_simplified.geojson"
DISTRICT_MONTHLY_PATH = config.PROCESSED_DIR / "district_monthly.csv"
DISTRICT_GEOJSON_PATH = config.PROCESSED_DIR / "districts.geojson"
DISTRICT_EVAL_PATH = config.PROCESSED_DIR / "district_outlook_eval.json"

# US Drought Monitor SPI breakpoints (upper bound, code, label), most severe first.
CATEGORIES: list[tuple[float, str, str]] = [
    (-2.0, "D4", "Exceptional drought"),
    (-1.6, "D3", "Extreme drought"),
    (-1.3, "D2", "Severe drought"),
    (-0.8, "D1", "Moderate drought"),
    (-0.5, "D0", "Abnormally dry"),
]


def category(spi_value: float) -> str | None:
    if spi_value is None or np.isnan(spi_value):
        return None
    for upper, code, _ in CATEGORIES:
        if spi_value <= upper:
            return code
    return None


def _download(url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and not refresh:
        return path
    log.info("Downloading %s", url)
    resp = requests.get(url, timeout=900)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path


def load_chirps(path: Path) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray]:
    """Return (months, lats, lons, precip[t, y, x]) with missing values as NaN."""
    with netcdf_file(path, "r", mmap=False) as f:
        t = f.variables["T"][:].copy()  # months since 1960-01, at mid-month
        lats = f.variables["Y"][:].copy()
        lons = f.variables["X"][:].copy()
        var = f.variables["precipitation"]
        data = var[:].astype(float)
        missing = getattr(var, "missing_value", None)
    if missing is not None:
        data[data == float(missing)] = np.nan
    data[data < 0] = np.nan
    months = pd.DatetimeIndex(
        [pd.Timestamp(1960 + int(m) // 12, int(m) % 12 + 1, 1) for m in np.floor(t)]
    )
    return months, lats, lons, data


def district_rainfall(geojson: dict, chirps) -> tuple[pd.DataFrame, list[dict]]:
    """Area-mean monthly rainfall per district plus per-district metadata."""
    months, lats, lons, data = chirps
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    frames, meta = [], []
    for feat in geojson["features"]:
        name = feat["properties"]["shapeName"]
        geom = shape(feat["geometry"])
        inside = shapely.contains_xy(geom, grid_lon, grid_lat)
        if inside.sum() == 0:  # tiny district: fall back to the nearest cell
            c = geom.centroid
            inside = np.zeros_like(grid_lat, dtype=bool)
            inside[np.abs(lats - c.y).argmin(), np.abs(lons - c.x).argmin()] = True
        series = np.nanmean(data[:, inside], axis=1)
        frames.append(pd.DataFrame({"district": name, "date": months, "precip_mm": series}))
        c = geom.representative_point()
        meta.append({"name": name, "lat": round(c.y, 4), "lon": round(c.x, 4),
                     "cells": int(inside.sum())})
    return pd.concat(frames, ignore_index=True), meta


def build_district_table(rain: pd.DataFrame) -> pd.DataFrame:
    """SPI, categories and the next-month ensemble outlook for every district-month."""
    parts = []
    for name, g in rain.groupby("district", sort=False):
        s = g.set_index("date")["precip_mm"].sort_index()
        out = pd.DataFrame({"district": name, "date": s.index, "precip_mm": s.to_numpy()})
        ref = s[(s.index.year >= config.REF_START) & (s.index.year <= config.REF_END)]
        normal = ref.groupby(ref.index.month).mean()
        out["normal_mm"] = out["date"].dt.month.map(normal).to_numpy()
        for k in config.SPI_SCALES:
            out[f"spi{k}"] = spi(s, k, config.REF_START, config.REF_END).to_numpy()
        out["drought_prob_next"] = ensemble_drought_prob(
            s, config.REF_START, config.REF_END, config.DROUGHT_THRESHOLD
        )
        parts.append(out)
    table = pd.concat(parts, ignore_index=True)
    table["category"] = table["spi3"].map(category)
    return table


def evaluate_outlook(table: pd.DataFrame) -> dict:
    """Score the ensemble outlook on the test years against the base rate."""
    t = table.sort_values(["district", "date"]).copy()
    t["target"] = t.groupby("district")["spi3"].shift(-1) <= config.DROUGHT_THRESHOLD
    t["target_known"] = t.groupby("district")["spi3"].shift(-1).notna()
    t["target_year"] = (t["date"] + pd.offsets.MonthBegin(1)).dt.year
    usable = t[t["target_known"] & t["drought_prob_next"].notna()]
    train = usable[usable["target_year"] <= config.TRAIN_END]
    test = usable[usable["target_year"] > config.VAL_END]
    base = float(train["target"].mean())
    y = test["target"].astype(float).to_numpy()
    p = test["drought_prob_next"].to_numpy()
    brier = float(np.mean((p - y) ** 2))
    brier_base = float(np.mean((base - y) ** 2))
    bins = np.linspace(0, 1, 6)
    which = np.clip(np.digitize(p, bins) - 1, 0, 4)
    reliability = [
        {"bin": f"{bins[i]:.1f}–{bins[i + 1]:.1f}", "n": int((which == i).sum()),
         "mean_forecast": float(p[which == i].mean()) if (which == i).any() else None,
         "observed_rate": float(y[which == i].mean()) if (which == i).any() else None}
        for i in range(5)
    ]
    return {
        "n_test": int(len(test)),
        "base_rate_train": base,
        "drought_rate_test": float(y.mean()),
        "brier": brier,
        "brier_base_rate": brier_base,
        "brier_skill": 1 - brier / brier_base,
        "reliability": reliability,
    }


def simplified_geojson(geojson: dict, meta: list[dict], tolerance: float = 0.005) -> dict:
    """Lighter polygons for the web map (~0.5 km tolerance)."""
    by_name = {m["name"]: m for m in meta}
    features = []
    for feat in geojson["features"]:
        name = feat["properties"]["shapeName"]
        geom = shape(feat["geometry"]).simplify(tolerance, preserve_topology=True)
        geom = shapely.set_precision(geom, 1e-4)
        features.append({
            "type": "Feature",
            "properties": {"name": name, **{k: by_name[name][k] for k in ("lat", "lon")}},
            "geometry": mapping(geom),
        })
    return {"type": "FeatureCollection", "features": features}


def build(refresh: bool = False) -> dict:
    chirps = load_chirps(_download(CHIRPS_URL, CHIRPS_PATH, refresh))
    geojson = json.loads(_download(BOUNDARY_URL, BOUNDARY_PATH, refresh).read_text())
    rain, meta = district_rainfall(geojson, chirps)
    table = build_district_table(rain)
    evaluation = evaluate_outlook(table)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    numeric = table.select_dtypes("number").columns
    table.assign(**{c: table[c].round(3) for c in numeric}).to_csv(
        DISTRICT_MONTHLY_PATH, index=False
    )
    DISTRICT_GEOJSON_PATH.write_text(
        json.dumps(simplified_geojson(geojson, meta), separators=(",", ":")), encoding="utf-8"
    )
    DISTRICT_EVAL_PATH.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    log.info("Districts: %d, months %s..%s, outlook Brier skill %+.1f%%", len(meta),
             f"{table['date'].min():%Y-%m}", f"{table['date'].max():%Y-%m}",
             100 * evaluation["brier_skill"])
    return {"chirps": chirps, "table": table, "evaluation": evaluation, "meta": meta}
