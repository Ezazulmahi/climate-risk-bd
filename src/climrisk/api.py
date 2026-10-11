"""FastAPI service.

Run with ``uvicorn climrisk.api:app --reload`` and open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query

from . import __version__, config
from .predict import OutOfRangeError, Predictor, UnknownCityError

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

app = FastAPI(
    title="Bangladesh Climate Risk API",
    version=__version__,
    description=(
        "One-month-ahead rainfall anomaly and drought-risk (SPI-3 <= -1) forecasts for eight "
        "Bangladesh divisional cities, trained on ERA5 reanalysis. Research demo, not an "
        "official forecast."
    ),
)


@lru_cache(maxsize=1)
def get_predictor() -> Predictor:
    return Predictor(
        bundle_path=Path(os.environ.get("CLIMRISK_BUNDLE", config.BUNDLE_PATH)),
        features_path=Path(os.environ.get("CLIMRISK_FEATURES", config.FEATURES_PATH)),
        metrics_path=Path(os.environ.get("CLIMRISK_METRICS", config.METRICS_PATH)),
    )


@app.get("/health")
def health(pred: Predictor = Depends(get_predictor)) -> dict:
    lo, hi = pred.month_range()
    return {"status": "ok", "version": __version__, "months": [f"{lo:%Y-%m}", f"{hi:%Y-%m}"]}


@app.get("/cities")
def cities(pred: Predictor = Depends(get_predictor)) -> list[str]:
    return pred.cities


@app.get("/predict")
def predict(
    city: str = Query(..., examples=["Dhaka"]),
    month: str = Query(..., description="Target month, YYYY-MM", examples=["2026-09"]),
    pred: Predictor = Depends(get_predictor),
) -> dict:
    if not MONTH_RE.match(month):
        raise HTTPException(422, "month must look like YYYY-MM")
    try:
        return pred.predict(city, month)
    except UnknownCityError:
        raise HTTPException(404, f"unknown city '{city}'; see /cities") from None
    except OutOfRangeError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/forecast/latest")
def latest(pred: Predictor = Depends(get_predictor)) -> list[dict]:
    """The newest month that has not been observed yet, for every city."""
    return pred.latest_forecasts()


@app.get("/history")
def history(
    city: str,
    start: str | None = Query(None, description="YYYY-MM"),
    end: str | None = Query(None, description="YYYY-MM"),
    pred: Predictor = Depends(get_predictor),
) -> list[dict]:
    for v in (start, end):
        if v is not None and not MONTH_RE.match(v):
            raise HTTPException(422, "start/end must look like YYYY-MM")
    try:
        return pred.history(city, start, end)
    except UnknownCityError:
        raise HTTPException(404, f"unknown city '{city}'; see /cities") from None


@app.get("/metrics")
def metrics(pred: Predictor = Depends(get_predictor)) -> dict:
    if pred.metrics is None:
        raise HTTPException(404, "metrics not found; run `python -m climrisk evaluate`")
    return pred.metrics
