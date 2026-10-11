"""Serving-side wrapper used by both the API and the dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from . import config
from .spi import classify
from .train import predict_drought_proba, predict_regression


class UnknownCityError(KeyError):
    pass


class OutOfRangeError(ValueError):
    pass


def risk_level(p: float, base_rate: float) -> str:
    """Translate a probability into a plain-language level relative to the usual rate."""
    if p >= max(0.5, 2.5 * base_rate):
        return "high"
    if p >= 1.5 * base_rate:
        return "elevated"
    return "low"


class Predictor:
    def __init__(
        self,
        bundle_path: Path = config.BUNDLE_PATH,
        features_path: Path = config.FEATURES_PATH,
        metrics_path: Path = config.METRICS_PATH,
    ):
        self.bundle = joblib.load(bundle_path)
        self.feat = pd.read_csv(features_path, parse_dates=["date", "target_date"])
        self.metrics = (
            json.loads(Path(metrics_path).read_text()) if Path(metrics_path).exists() else None
        )
        keys = zip(self.feat["city"].str.lower(), self.feat["target_date"], strict=True)
        self._index = {key: i for i, key in enumerate(keys)}

    @property
    def cities(self) -> list[str]:
        order = [c.name for c in config.CITIES]
        present = set(self.feat["city"])
        return [c for c in order if c in present] + sorted(present - set(order))

    def _canonical_city(self, city: str) -> str:
        for c in self.cities:
            if c.lower() == city.strip().lower():
                return c
        raise UnknownCityError(city)

    def month_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        usable = self.feat.dropna(subset=self.bundle["feature_columns"])
        return usable["target_date"].min(), usable["target_date"].max()

    def predict(self, city: str, month: str | pd.Timestamp) -> dict:
        """Forecast for ``month`` (YYYY-MM) issued at the end of the previous month."""
        name = self._canonical_city(city)
        target = pd.Timestamp(month).to_period("M").to_timestamp()
        i = self._index.get((name.lower(), target))
        lo, hi = self.month_range()
        if i is None or target < lo or target > hi:
            raise OutOfRangeError(
                f"month must be between {lo:%Y-%m} and {hi:%Y-%m} for {name}"
            )
        row = self.feat.iloc[[i]]
        reg = predict_regression(self.bundle, row).iloc[0]
        p = float(predict_drought_proba(self.bundle, row)[0])
        base = self.bundle["clf_base_rate"]

        observed = None
        if not np.isnan(row["target_precip_mm"].iloc[0]):
            spi3 = float(row["target_spi3"].iloc[0])
            observed = {
                "precip_mm": round(float(row["target_precip_mm"].iloc[0]), 1),
                "anomaly_mm": round(float(row["target_anom_mm"].iloc[0]), 1),
                "spi3": round(spi3, 2),
                "spi3_category": classify(spi3),
                "drought": bool(spi3 <= self.bundle["meta"]["drought_threshold"]),
            }
        return {
            "city": name,
            "target_month": f"{target:%Y-%m}",
            "issued_with_data_through": f"{row['date'].iloc[0]:%Y-%m}",
            "is_forecast": observed is None,
            "rainfall": {
                "expected_mm": round(float(reg["precip_mm"]), 1),
                "interval_80_mm": [
                    round(float(reg["precip_lo_mm"]), 1), round(float(reg["precip_hi_mm"]), 1)
                ],
                "climatology_mm": round(float(row["clim_precip_mean_next"].iloc[0]), 1),
                "anomaly_mm": round(float(reg["anom_mm"]), 1),
            },
            "drought": {
                "probability": round(p, 3),
                "usual_probability": round(base, 3),
                "risk_level": risk_level(p, base),
                "definition": "SPI-3 <= -1.0 in the target month",
            },
            "current_conditions": {
                "spi3": round(float(row["spi3"].iloc[0]), 2),
                "spi3_category": classify(float(row["spi3"].iloc[0])),
            },
            "observed": observed,
        }

    def history(self, city: str, start: str | None = None, end: str | None = None) -> list[dict]:
        name = self._canonical_city(city)
        h = self.feat[self.feat["city"] == name]
        if start:
            h = h[h["date"] >= pd.Timestamp(start)]
        if end:
            h = h[h["date"] <= pd.Timestamp(end)]
        out = h[["date", "precip_mm", "clim_precip_mean", "precip_anom", "spi3"]].copy()
        out["date"] = out["date"].dt.strftime("%Y-%m")
        out = out.round(2)
        return out.astype(object).where(out.notna(), None).to_dict(orient="records")

    def latest_forecasts(self) -> list[dict]:
        """The newest forecast month for every city (the one with no observation yet)."""
        out = []
        for city in self.cities:
            rows = self.feat[self.feat["city"] == city].dropna(
                subset=self.bundle["feature_columns"]
            )
            out.append(self.predict(city, rows["target_date"].max()))
        return out
