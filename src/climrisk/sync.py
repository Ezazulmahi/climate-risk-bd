"""Publish data and forecasts to the database.

Run after ``train``/``evaluate``. Every validation and test month gets a stored
hindcast, and each city gets one live forecast for the first unobserved month.
The step is idempotent: rerunning it replaces the rows for the same model
version.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import config
from .db import cities, create_schema, forecasts, issued_forecasts, model_runs, observations
from .predict import risk_level
from .train import predict_drought_proba, predict_regression

log = logging.getLogger(__name__)


def model_version(bundle: dict) -> str:
    """Short, deterministic id: same training setup and results -> same version."""
    payload = json.dumps(
        {"meta": bundle["meta"], "params": bundle["best_params"],
         "validation": bundle["validation"]},
        sort_keys=True, default=str,
    )
    return f"v{config.TRAIN_END}-" + hashlib.sha256(payload.encode()).hexdigest()[:8]


def _none_if_nan(records: list[dict]) -> list[dict]:
    return [
        {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
        for r in records
    ]


def build_forecast_rows(
    bundle: dict, feat: pd.DataFrame, version: str, heat: pd.DataFrame | None = None
) -> list[dict]:
    rows = feat.dropna(subset=bundle["feature_columns"])
    rows = rows[rows["target_date"].dt.year > config.TRAIN_END]
    reg = predict_regression(bundle, rows)
    prob = predict_drought_proba(bundle, rows)
    base = bundle["clf_base_rate"]
    year = rows["target_date"].dt.year
    split = np.where(
        rows["target_precip_mm"].isna(), "live",
        np.where(year <= config.VAL_END, "validation", "test"),
    )
    out = pd.DataFrame({
        "model_version": version,
        "city": rows["city"],
        "target_month": rows["target_date"].dt.date,
        "issued_through": rows["date"].dt.date,
        "split": split,
        "expected_mm": reg["precip_mm"].round(1),
        "lower_mm": reg["precip_lo_mm"].round(1),
        "upper_mm": reg["precip_hi_mm"].round(1),
        "normal_mm": rows["clim_precip_mean_next"].round(1),
        "drought_prob": np.round(prob, 4),
        "drought_base_rate": round(base, 4),
        "risk_level": [risk_level(p, base) for p in prob],
    })
    if heat is not None:
        h = heat.set_index(["city", "date"])
        key = pd.MultiIndex.from_arrays([rows["city"], rows["date"]])
        for col in ("heat_days_expected", "heat_days_normal", "heat_days_recent"):
            out[col] = h[col].reindex(key).round(2).to_numpy()
    return _none_if_nan(out.to_dict(orient="records"))


def build_observation_rows(feat: pd.DataFrame) -> list[dict]:
    obs = pd.DataFrame({
        "city": feat["city"],
        "month": feat["date"].dt.date,
        "precip_mm": feat["precip_mm"].round(1),
        "normal_mm": feat["clim_precip_mean"].round(1),
        "anomaly_mm": feat["precip_anom"].round(1),
        "spi3": feat["spi3"].round(3),
        "t2m": feat["t2m"].round(2),
        "rh2m": feat["rh2m"].round(2),
        "heatwave_days": feat["heatwave_days"] if "heatwave_days" in feat else np.nan,
    })
    return _none_if_nan(obs.to_dict(orient="records"))


def heat_table(heat_bundle: dict, feat: pd.DataFrame) -> pd.DataFrame:
    """Heat-wave outlook for every city-month, keyed by issue month."""
    from .heat import build_heat_features, predict_heat

    d = build_heat_features(feat)
    usable = d.dropna(subset=["hw_normal_next", "hw_recent_next", "heatwave_days"])
    return pd.DataFrame({
        "city": usable["city"],
        "date": usable["date"],
        "heat_days_expected": predict_heat(heat_bundle, usable),
        "heat_days_normal": usable["hw_normal_next"],
        "heat_days_recent": usable["hw_recent_next"],
    })


def sync(
    engine: Engine,
    feat: pd.DataFrame,
    bundle: dict,
    metrics: dict | None,
    heat: pd.DataFrame | None = None,
) -> dict:
    create_schema(engine)
    version = model_version(bundle)
    coords = feat.groupby("city")[["lat", "lon"]].first()
    city_rows = [
        {"name": name, "lat": float(r.lat), "lon": float(r.lon)} for name, r in coords.iterrows()
    ]
    obs_rows = build_observation_rows(feat)
    fc_rows = build_forecast_rows(bundle, feat, version, heat)
    run = {
        "version": version,
        "created_at": datetime.now(UTC),
        "is_active": True,
        "data_through": feat["date"].max().date(),
        "meta": json.loads(json.dumps(bundle["meta"], default=str)),
        "metrics": json.loads(json.dumps(metrics, default=str)) if metrics else None,
    }

    with engine.begin() as conn:
        # Children first, then parents, so foreign keys hold throughout.
        conn.execute(forecasts.delete().where(forecasts.c.model_version == version))
        conn.execute(observations.delete())
        existing = {r.name for r in conn.execute(sa.select(cities.c.name))}
        new_cities = [r for r in city_rows if r["name"] not in existing]
        if new_cities:
            conn.execute(cities.insert(), new_cities)
        if obs_rows:
            conn.execute(observations.insert(), obs_rows)
        conn.execute(model_runs.update().values(is_active=False))
        conn.execute(model_runs.delete().where(model_runs.c.version == version))
        conn.execute(model_runs.insert(), [run])
        if fc_rows:
            conn.execute(forecasts.insert(), fc_rows)

        # Freeze live forecasts the first time they are published; never overwrite.
        i = issued_forecasts.c
        frozen = {(r.city, r.target_month) for r in conn.execute(sa.select(i.city, i.target_month))}
        new_issues = [
            {k: v for k, v in r.items()
             if k not in ("split", "heat_days_normal", "heat_days_recent")}
            | {"issued_at": run["created_at"]}
            for r in fc_rows
            if r["split"] == "live" and (r["city"], r["target_month"]) not in frozen
        ]
        if new_issues:
            conn.execute(issued_forecasts.insert(), new_issues)

    counts = {"version": version, "cities": len(city_rows), "observations": len(obs_rows),
              "forecasts": len(fc_rows), "newly_issued": len(new_issues)}
    log.info("Database sync: %s", counts)
    return counts


def sync_districts(
    engine: Engine, table: pd.DataFrame, geojson: dict, extra_docs: dict | None = None
) -> dict:
    """Publish the district drought monitor (see districts.py)."""
    from .db import district_monthly, districts, documents

    create_schema(engine)
    names = [
        {"name": f["properties"]["name"], "lat": f["properties"]["lat"],
         "lon": f["properties"]["lon"]}
        for f in geojson["features"]
    ]
    rows = pd.DataFrame({
        "district": table["district"],
        "month": table["date"].dt.date,
        **{c: table[c] for c in ("precip_mm", "normal_mm", "spi1", "spi3", "spi6", "spi12",
                                 "category", "drought_prob_next")},
    })
    rows = rows.astype(object).where(rows.notna(), None).to_dict(orient="records")
    now = datetime.now(UTC)
    docs = [{"name": "districts_geojson", "updated_at": now, "content": geojson}]
    docs += [{"name": k, "updated_at": now, "content": v} for k, v in (extra_docs or {}).items()]

    with engine.begin() as conn:
        conn.execute(district_monthly.delete())
        conn.execute(districts.delete())
        conn.execute(districts.insert(), names)
        conn.execute(district_monthly.insert(), rows)
        conn.execute(documents.delete().where(documents.c.name.in_([d["name"] for d in docs])))
        conn.execute(documents.insert(), docs)
    counts = {"districts": len(names), "district_months": len(rows)}
    log.info("District sync: %s", counts)
    return counts
