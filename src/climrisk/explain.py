"""Why is a city's drought probability what it is?

A simple, model-agnostic "what if this were typical?" attribution: for each
feature, replace the live value with its training-period median and record how
much the predicted drought probability changes. Positive effect = this factor
is pushing the risk up. It ignores interactions (unlike SHAP) but is exact for
what it measures, cheap, and easy to explain to non-specialists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

LABELS = {
    "precip_anom_z": "Rainfall this month vs normal",
    "precip_anom_z_lag1": "Rainfall last month vs normal",
    "precip_anom_z_lag2": "Rainfall two months ago vs normal",
    "precip_anom_z_lag11": "Same month last year vs normal",
    "precip_anom_z_roll3": "Last 3 months' rainfall vs normal",
    "precip_anom_z_roll6": "Last 6 months' rainfall vs normal",
    "spi1": "1-month drought index",
    "spi3": "3-month drought index",
    "spi6": "6-month drought index",
    "spi12": "12-month drought index",
    "drought_prob_ens": "Drought odds from rain already observed",
    "t2m_anom": "Temperature vs normal",
    "t2m_anom_roll3": "Last 3 months' temperature vs normal",
    "rh2m_anom": "Humidity vs normal",
    "ws10m": "Wind speed",
    "target_month_sin": "Time of year",
    "target_month_cos": "Time of year",
    "clim_precip_mean_next": "Normal rainfall for the coming month",
    "lat": "Location",
    "lon": "Location",
    "oni": "El Niño / La Niña (ONI)",
    "dmi_lag4": "Indian Ocean Dipole",
}


def explain_drought(bundle: dict, feat: pd.DataFrame, top: int = 4) -> dict[str, list[dict]]:
    """Top drivers of each city's live drought probability."""
    cols = bundle["feature_columns"]
    model = bundle["clf_models"]["hgb"]
    train = feat[feat["target_date"].dt.year <= config.TRAIN_END]
    medians = train[cols].median()
    live = feat.dropna(subset=cols)
    live = live[live["date"] == live.groupby("city")["date"].transform("max")]

    out: dict[str, list[dict]] = {}
    for _, row in live.iterrows():
        x = row[cols].to_frame().T.astype(float)
        base = float(model.predict_proba(x)[:, 1][0])
        effects = []
        for c in cols:
            what_if = x.copy()
            what_if[c] = medians[c]
            effects.append((c, base - float(model.predict_proba(what_if)[:, 1][0])))
        # Merge the two "time of year" and "location" encodings.
        merged: dict[str, dict] = {}
        for c, e in effects:
            label = LABELS.get(c, c)
            m = merged.setdefault(label, {"label": label, "features": [], "effect": 0.0})
            m["features"].append(c)
            m["effect"] += e
        ranked = sorted(merged.values(), key=lambda m: -abs(m["effect"]))[:top]
        for m in ranked:
            c = m["features"][0]
            m["value"] = None if np.isnan(row[c]) else round(float(row[c]), 3)
            m["typical"] = round(float(medians[c]), 3)
            m["effect"] = round(m["effect"], 4)
        out[row["city"]] = [{"probability": round(base, 4)}] + ranked
    return out
