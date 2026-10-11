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
from .db import cities, forecasts, get_engine, model_runs, observations
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
        sa.select(forecasts, o.c.precip_mm.label("observed_mm"), o.c.spi3.label("observed_spi3"))
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


@app.get("/metrics")
def metrics(conn: Connection = Depends(get_conn)) -> dict:
    """Full held-out evaluation of the active model (see reports/evaluation.md)."""
    run = conn.execute(sa.select(model_runs).where(model_runs.c.is_active)).first()
    if run is None or run.metrics is None:
        raise HTTPException(404, "metrics not published; run evaluate then db-sync")
    return {"model_version": run.version, "meta": run.meta, **run.metrics}
