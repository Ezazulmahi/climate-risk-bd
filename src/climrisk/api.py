"""FastAPI service backed by the forecasts database.

Every response is read from PostgreSQL; the model runs offline in the pipeline
(``python -m climrisk all && python -m climrisk db-sync``), so the API stays
small and fast. Run locally with::

    uvicorn climrisk.api:app --reload

and open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
import re
from datetime import date

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Connection

from . import __version__
from .db import (
    cities,
    district_monthly,
    districts,
    documents,
    forecasts,
    get_engine,
    issued_forecasts,
    model_runs,
    observations,
)
from .districts import CATEGORIES
from .spi import classify

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

app = FastAPI(
    title="Bangladesh Climate Risk API",
    version=__version__,
    description=(
        "One-month-ahead rainfall and drought-risk (SPI-3 <= -1) forecasts for Bangladesh "
        "divisional cities, trained on ERA5 reanalysis, with every past forecast stored "
        "for verification. Research demo, not an official forecast."
    ),
)
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"])


def get_conn():
    with get_engine().connect() as conn:
        yield conn


def _month(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    if not MONTH_RE.match(value):
        raise HTTPException(422, f"{name} must look like YYYY-MM")
    return date(int(value[:4]), int(value[5:]), 1)


def _active_version(conn: Connection) -> str:
    version = conn.execute(
        sa.select(model_runs.c.version).where(model_runs.c.is_active)
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(503, "no model published yet; run `python -m climrisk db-sync`")
    return version


def _city(conn: Connection, name: str) -> str:
    found = conn.execute(
        sa.select(cities.c.name).where(sa.func.lower(cities.c.name) == name.strip().lower())
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(404, f"unknown city '{name}'; see /cities")
    return found


def _forecast_query(version: str):
    o = observations
    return (
        sa.select(
            forecasts,
            o.c.precip_mm.label("observed_mm"),
            o.c.spi3.label("observed_spi3"),
            o.c.heatwave_days.label("observed_heat_days"),
        )
        .select_from(
            forecasts.outerjoin(
                o, (o.c.city == forecasts.c.city) & (o.c.month == forecasts.c.target_month)
            )
        )
        .where(forecasts.c.model_version == version)
    )


def _forecast_dict(row) -> dict:
    r = row._mapping
    observed = None
    if r["observed_mm"] is not None:
        spi3 = r["observed_spi3"]
        observed = {
            "precip_mm": r["observed_mm"],
            "spi3": spi3,
            "spi3_category": classify(spi3) if spi3 is not None else "unknown",
            "drought": spi3 is not None and spi3 <= -1.0,
            "inside_interval": r["lower_mm"] <= r["observed_mm"] <= r["upper_mm"],
            "heatwave_days": r["observed_heat_days"],
        }
    heat = None
    if r["heat_days_expected"] is not None:
        heat = {
            "expected_days": r["heat_days_expected"],
            "normal_days": r["heat_days_normal"],
            "recent_decade_days": r["heat_days_recent"],
            "threshold_c": 36,
        }
    return {
        "city": r["city"],
        "target_month": r["target_month"].strftime("%Y-%m"),
        "issued_through": r["issued_through"].strftime("%Y-%m"),
        "split": r["split"],
        "rainfall": {
            "expected_mm": r["expected_mm"],
            "interval_80_mm": [r["lower_mm"], r["upper_mm"]],
            "normal_mm": r["normal_mm"],
            "anomaly_mm": round(r["expected_mm"] - r["normal_mm"], 1),
        },
        "drought": {
            "probability": r["drought_prob"],
            "usual_probability": r["drought_base_rate"],
            "risk_level": r["risk_level"],
        },
        "heat": heat,
        "observed": observed,
        "model_version": r["model_version"],
    }


@app.get("/health")
def health(conn: Connection = Depends(get_conn)) -> dict:
    run = conn.execute(
        sa.select(model_runs.c.version, model_runs.c.data_through).where(model_runs.c.is_active)
    ).first()
    return {
        "status": "ok",
        "version": __version__,
        "model_version": run.version if run else None,
        "data_through": run.data_through.strftime("%Y-%m") if run else None,
    }


@app.get("/cities")
def list_cities(conn: Connection = Depends(get_conn)) -> list[dict]:
    rows = conn.execute(sa.select(cities).order_by(cities.c.name))
    return [dict(r._mapping) for r in rows]


@app.get("/forecasts/latest")
def latest(conn: Connection = Depends(get_conn)) -> list[dict]:
    """The live forecast (first month not yet observed) for every city."""
    version = _active_version(conn)
    rows = conn.execute(
        _forecast_query(version).where(forecasts.c.split == "live").order_by(forecasts.c.city)
    )
    return [_forecast_dict(r) for r in rows]


@app.get("/forecasts")
def list_forecasts(
    city: str,
    start: str | None = Query(None, description="YYYY-MM"),
    end: str | None = Query(None, description="YYYY-MM"),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    """Stored forecasts for a city, each with its observed outcome when known."""
    name = _city(conn, city)
    q = _forecast_query(_active_version(conn)).where(forecasts.c.city == name)
    if (s := _month(start, "start")) is not None:
        q = q.where(forecasts.c.target_month >= s)
    if (e := _month(end, "end")) is not None:
        q = q.where(forecasts.c.target_month <= e)
    return [_forecast_dict(r) for r in conn.execute(q.order_by(forecasts.c.target_month))]


@app.get("/forecast")
def one_forecast(
    city: str = Query(..., examples=["Dhaka"]),
    month: str = Query(..., description="Target month, YYYY-MM", examples=["2026-10"]),
    conn: Connection = Depends(get_conn),
) -> dict:
    name = _city(conn, city)
    target = _month(month, "month")
    row = conn.execute(
        _forecast_query(_active_version(conn)).where(
            (forecasts.c.city == name) & (forecasts.c.target_month == target)
        )
    ).first()
    if row is None:
        raise HTTPException(404, f"no forecast for {name} in {month}")
    return _forecast_dict(row)


@app.get("/history")
def history(
    city: str,
    start: str | None = Query(None, description="YYYY-MM"),
    end: str | None = Query(None, description="YYYY-MM"),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    name = _city(conn, city)
    q = sa.select(observations).where(observations.c.city == name)
    if (s := _month(start, "start")) is not None:
        q = q.where(observations.c.month >= s)
    if (e := _month(end, "end")) is not None:
        q = q.where(observations.c.month <= e)
    out = []
    for r in conn.execute(q.order_by(observations.c.month)):
        d = dict(r._mapping)
        d["month"] = d["month"].strftime("%Y-%m")
        d.pop("city")
        out.append(d)
    return out


@app.get("/verification")
def verification(
    city: str | None = None,
    split: str = Query("test", pattern="^(validation|test)$"),
    conn: Connection = Depends(get_conn),
) -> dict:
    """How the stored forecasts did once the rain was observed."""
    q = _forecast_query(_active_version(conn)).where(forecasts.c.split == split)
    if city:
        q = q.where(forecasts.c.city == _city(conn, city))
    rows = [r._mapping for r in conn.execute(q) if r._mapping["observed_mm"] is not None]
    if not rows:
        raise HTTPException(404, "no verified forecasts")
    n = len(rows)
    mae = sum(abs(r["observed_mm"] - r["expected_mm"]) for r in rows) / n
    mae_normal = sum(abs(r["observed_mm"] - r["normal_mm"]) for r in rows) / n
    coverage = sum(r["lower_mm"] <= r["observed_mm"] <= r["upper_mm"] for r in rows) / n
    outcomes = [
        (r["drought_prob"], float(r["observed_spi3"] is not None and r["observed_spi3"] <= -1.0),
         r["drought_base_rate"])
        for r in rows
    ]
    brier = sum((p - y) ** 2 for p, y, _ in outcomes) / n
    brier_base = sum((b - y) ** 2 for _, y, b in outcomes) / n
    return {
        "split": split,
        "city": city,
        "n": n,
        "rainfall_mae_mm": round(mae, 1),
        "normal_mae_mm": round(mae_normal, 1),
        "rainfall_skill": round(1 - mae / mae_normal, 4),
        "interval_coverage": round(coverage, 4),
        "drought_rate": round(sum(y for _, y, _ in outcomes) / n, 4),
        "drought_brier": round(brier, 4),
        "drought_brier_skill": round(1 - brier / brier_base, 4) if brier_base else None,
    }


@app.get("/issued")
def issued(city: str | None = None, conn: Connection = Depends(get_conn)) -> list[dict]:
    """The append-only forecast log: each live forecast exactly as first published,
    with the observed outcome once it is known. Retraining never changes these rows."""
    i, o = issued_forecasts, observations
    q = sa.select(
        i, o.c.precip_mm.label("observed_mm"), o.c.spi3.label("observed_spi3")
    ).select_from(
        i.outerjoin(o, (o.c.city == i.c.city) & (o.c.month == i.c.target_month))
    )
    if city:
        q = q.where(i.c.city == _city(conn, city))
    out = []
    for r in conn.execute(q.order_by(i.c.target_month.desc(), i.c.city)):
        m = r._mapping
        observed = None
        if m["observed_mm"] is not None:
            observed = {
                "precip_mm": m["observed_mm"],
                "spi3": m["observed_spi3"],
                "inside_interval": m["lower_mm"] <= m["observed_mm"] <= m["upper_mm"],
                "drought": m["observed_spi3"] is not None and m["observed_spi3"] <= -1.0,
            }
        out.append({
            "city": m["city"],
            "target_month": m["target_month"].strftime("%Y-%m"),
            "issued_at": m["issued_at"].isoformat(),
            "issued_through": m["issued_through"].strftime("%Y-%m"),
            "model_version": m["model_version"],
            "rainfall": {"expected_mm": m["expected_mm"],
                         "interval_80_mm": [m["lower_mm"], m["upper_mm"]],
                         "normal_mm": m["normal_mm"]},
            "drought": {"probability": m["drought_prob"],
                        "usual_probability": m["drought_base_rate"],
                        "risk_level": m["risk_level"]},
            "observed": observed,
        })
    return out


def _document(conn: Connection, name: str):
    content = conn.execute(
        sa.select(documents.c.content).where(documents.c.name == name)
    ).scalar_one_or_none()
    if content is None:
        raise HTTPException(404, f"{name} not published; run `climrisk districts` then db-sync")
    return content


def _district(conn: Connection, name: str) -> str:
    found = conn.execute(
        sa.select(districts.c.name).where(sa.func.lower(districts.c.name) == name.strip().lower())
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(404, f"unknown district '{name}'; see /districts")
    return found


@app.get("/districts")
def district_status(
    month: str | None = Query(None, description="YYYY-MM; default: latest available"),
    conn: Connection = Depends(get_conn),
) -> dict:
    """Drought monitor for all 64 districts in one month, with next month's outlook."""
    dm = district_monthly
    target = _month(month, "month") or conn.execute(sa.select(sa.func.max(dm.c.month))).scalar()
    if target is None:
        raise HTTPException(404, "district monitor not published")
    rows = conn.execute(
        sa.select(dm, districts.c.lat, districts.c.lon)
        .join(districts, districts.c.name == dm.c.district)
        .where(dm.c.month == target)
        .order_by(dm.c.spi3)
    )
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["month"] = d["month"].strftime("%Y-%m")
        out.append(d)
    if not out:
        raise HTTPException(404, f"no district data for {month}")
    return {
        "month": target.strftime("%Y-%m"),
        "categories": [{"code": c, "label": label, "spi_at_or_below": ub}
                       for ub, c, label in CATEGORIES],
        "districts": out,
    }


@app.get("/districts/geojson")
def district_geojson(conn: Connection = Depends(get_conn)) -> dict:
    """Simplified district polygons (geoBoundaries ADM2, BBS/OCHA, CC BY 3.0 IGO)."""
    return _document(conn, "districts_geojson")


@app.get("/districts/evaluation")
def district_evaluation(conn: Connection = Depends(get_conn)) -> dict:
    """How the district drought outlook scored on the test years."""
    return _document(conn, "district_outlook_eval")


@app.get("/districts/{name}")
def district_history(
    name: str,
    start: str | None = Query(None, description="YYYY-MM"),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    district = _district(conn, name)
    dm = district_monthly
    q = sa.select(dm).where(dm.c.district == district)
    if (s := _month(start, "start")) is not None:
        q = q.where(dm.c.month >= s)
    out = []
    for r in conn.execute(q.order_by(dm.c.month)):
        d = dict(r._mapping)
        d["month"] = d["month"].strftime("%Y-%m")
        out.append(d)
    return out


@app.get("/validation")
def data_validation(conn: Connection = Depends(get_conn)) -> list[dict]:
    """Agreement between ERA5 (city model) and CHIRPS (satellite + gauges) at each city."""
    return _document(conn, "era5_chirps_validation")


@app.get("/heat/evaluation")
def heat_evaluation(conn: Connection = Depends(get_conn)) -> dict:
    """Test-period skill of the heat-wave-days outlook against two baselines."""
    return _document(conn, "heat_metrics")


@app.get("/dengue")
def dengue_backtest(conn: Connection = Depends(get_conn)) -> dict:
    """Dengue one-month-ahead backtest by division (2024-2025 test), with the series."""
    return _document(conn, "dengue_backtest")


@app.get("/metrics")
def metrics(conn: Connection = Depends(get_conn)) -> dict:
    """Full held-out evaluation of the active model (see reports/evaluation.md)."""
    run = conn.execute(sa.select(model_runs).where(model_runs.c.is_active)).first()
    if run is None or run.metrics is None:
        raise HTTPException(404, "metrics not published; run evaluate then db-sync")
    return {"model_version": run.version, "meta": run.meta, **run.metrics}
