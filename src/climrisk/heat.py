"""Heat-wave outlook: how many heat-wave days (Tmax >= 36 °C, the BMD definition)
next month in each city?

Two baselines, because the climate is warming:

- ``normal``:  1981–2015 average for that city and calendar month;
- ``recent``:  average of the same calendar month over the previous 10 years
               (only years before the target, so no leakage).

The ML model is Poisson gradient boosting on what is known at the end of the
issue month: this month's heat-wave days and temperature, humidity and rainfall
anomalies, ENSO, season, and both baselines. Evaluation uses the hot season
only (months whose normal is at least ``MIN_NORMAL_DAYS``), because scoring
"0 heat-wave days in January" would flatter every model.
"""

from __future__ import annotations

import itertools
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from . import config

log = logging.getLogger(__name__)

HEAT_BUNDLE_PATH = config.MODELS_DIR / "heat_bundle.joblib"
HEAT_METRICS_PATH = config.REPORTS_DIR / "heat_metrics.json"
MIN_NORMAL_DAYS = 0.5
RECENT_YEARS = 10

HEAT_FEATURES = [
    "heatwave_days",
    "hw_anom",
    "tmax_anom",
    "t2m_anom",
    "t2m_anom_roll3",
    "rh2m_anom",
    "spi1",
    "spi3",
    "oni",
    "target_month_sin",
    "target_month_cos",
    "hw_normal_next",
    "hw_recent_next",
    "lat",
    "lon",
]

GRID = {"learning_rate": [0.03, 0.1], "max_depth": [2, 3], "max_iter": [150, 300]}


def build_heat_features(feat: pd.DataFrame) -> pd.DataFrame:
    """Add heat-specific columns to the main feature table (one row per city-month)."""
    d = feat.sort_values(["city", "date"]).copy()
    ref = d[d["year"].between(config.REF_START, config.REF_END)]
    normal = ref.groupby(["city", "month"]).agg(
        hw_normal=("heatwave_days", "mean"), tmax_normal=("t2m_max", "mean")
    ).reset_index()
    d = d.merge(normal, on=["city", "month"], how="left")
    d["hw_anom"] = d["heatwave_days"] - d["hw_normal"]
    d["tmax_anom"] = d["t2m_max"] - d["tmax_normal"]

    # Recent baseline: mean of the same calendar month in the previous RECENT_YEARS years.
    by_cm = d.groupby(["city", "month"])["heatwave_days"]
    d["hw_recent"] = by_cm.transform(
        lambda s: s.shift(1).rolling(RECENT_YEARS, min_periods=5).mean()
    )
    d = d.sort_values(["city", "date"]).reset_index(drop=True)

    # Values for the *target* month (t+1): its normal, its recent average (all known in
    # advance) and the outcome.
    nxt = d[["city", "date", "hw_normal", "hw_recent", "heatwave_days"]].copy()
    nxt["date"] = nxt["date"] - pd.offsets.MonthBegin(1)
    nxt = nxt.rename(columns={"hw_normal": "hw_normal_next", "hw_recent": "hw_recent_next",
                              "heatwave_days": "target_hw_days"})
    d = d.merge(nxt, on=["city", "date"], how="left")
    # The live row's target month has no data yet, but its baselines are known.
    last = d.groupby("city")["date"].transform("max") == d["date"]
    tm = d.loc[last, ["city", "target_month"]]
    norm = normal.set_index(["city", "month"])["hw_normal"]
    keys = list(tm.itertuples(index=False))
    d.loc[last, "hw_normal_next"] = [norm.get((c, m), np.nan) for c, m in keys]
    recent = (
        d[d["year"] >= d["year"].max() - RECENT_YEARS]
        .groupby(["city", "month"])["heatwave_days"].mean()
    )
    d.loc[last, "hw_recent_next"] = [recent.get((c, m), np.nan) for c, m in keys]
    if "oni" not in d:
        d["oni"] = np.nan
    return d


def _split(d: pd.DataFrame):
    year = d["target_date"].dt.year
    return d[year <= config.TRAIN_END], d[(year > config.TRAIN_END) & (year <= config.VAL_END)], \
        d[year > config.VAL_END]


def _model(params: dict) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson", min_samples_leaf=30, l2_regularization=1.0,
        random_state=config.RANDOM_STATE, **params,
    )


def train_heat(d: pd.DataFrame, grid: dict | None = None) -> dict:
    rows = d.dropna(subset=["target_hw_days", "hw_normal_next", "hw_recent_next", "heatwave_days"])
    tr, va, _ = _split(rows)
    # Skip features with no data at all (e.g. ENSO when the index download failed).
    feats = [c for c in HEAT_FEATURES if tr[c].notna().any()]
    best, best_mae = None, np.inf
    for combo in itertools.product(*(grid or GRID).values()):
        params = dict(zip((grid or GRID).keys(), combo, strict=True))
        m = _model(params).fit(tr[feats], tr["target_hw_days"])
        hot = va["hw_normal_next"] >= MIN_NORMAL_DAYS
        pred = m.predict(va.loc[hot, feats])
        mae = mean_absolute_error(va.loc[hot, "target_hw_days"], pred)
        if mae < best_mae:
            best, best_mae = params, mae
    trva = pd.concat([tr, va])
    model = _model(best).fit(trva[feats], trva["target_hw_days"])
    return {"model": model, "params": best, "val_mae_hot": float(best_mae), "features": feats}


def _bootstrap_ci(test: pd.DataFrame, pred: np.ndarray, base: np.ndarray, n: int = 1000):
    rng = np.random.default_rng(config.RANDOM_STATE)
    years = test["target_date"].dt.year.to_numpy()
    y = test["target_hw_days"].to_numpy()
    e_m, e_b = np.abs(y - pred), np.abs(y - base)
    idx = {yr: np.flatnonzero(years == yr) for yr in np.unique(years)}
    uniq = np.array(list(idx))
    skills = []
    for _ in range(n):
        pick = np.concatenate([idx[yr] for yr in rng.choice(uniq, len(uniq))])
        skills.append(1 - e_m[pick].mean() / e_b[pick].mean())
    return [float(np.percentile(skills, 2.5)), float(np.percentile(skills, 97.5))]


def evaluate_heat(bundle: dict, d: pd.DataFrame) -> dict:
    rows = d.dropna(subset=["target_hw_days", "hw_normal_next", "hw_recent_next", "heatwave_days"])
    _, _, test = _split(rows)
    test = test[test["hw_normal_next"] >= MIN_NORMAL_DAYS]
    y = test["target_hw_days"].to_numpy()
    pred = bundle["model"].predict(test[bundle["features"]])
    normal, recent = test["hw_normal_next"].to_numpy(), test["hw_recent_next"].to_numpy()
    mae = {k: float(mean_absolute_error(y, v))
           for k, v in (("normal", normal), ("recent", recent), ("model", pred))}
    by_city = (
        test.assign(err_model=np.abs(y - pred), err_recent=np.abs(y - recent))
        .groupby("city")[["err_model", "err_recent"]].mean().round(2)
        .reset_index().to_dict(orient="records")
    )
    return {
        "n_test": int(len(test)),
        "hot_season_definition": f"normal >= {MIN_NORMAL_DAYS} heat-wave days",
        "mean_observed_days": float(y.mean()),
        "mean_normal_days": float(normal.mean()),
        "mae_days": mae,
        "skill_vs_normal": 1 - mae["model"] / mae["normal"],
        "skill_vs_recent": 1 - mae["model"] / mae["recent"],
        "skill_vs_recent_95ci": _bootstrap_ci(test, pred, recent),
        "recent_vs_normal": 1 - mae["recent"] / mae["normal"],
        "by_city": by_city,
        "params": bundle["params"],
    }


def predict_heat(bundle: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(bundle["model"].predict(rows[bundle["features"]]), 0, 31)


def write_report(metrics: dict, path: Path = config.REPORTS_DIR / "heat_evaluation.md") -> None:
    m = metrics["mae_days"]
    lo, hi = metrics["skill_vs_recent_95ci"]
    md = [
        "# Heat-wave outlook evaluation",
        "",
        "_Generated by `python -m climrisk heat`._",
        "",
        f"Target: number of heat-wave days (ERA5 Tmax ≥ {config.HEATWAVE_TMAX_C:.0f} °C) next "
        f"month. Test 2020 onward, hot-season months only ({metrics['hot_season_definition']}), "
        f"{metrics['n_test']} city-months.",
        "",
        f"Observed average {metrics['mean_observed_days']:.1f} days vs a 1981–2015 normal of "
        f"{metrics['mean_normal_days']:.1f}: the recent climate is hotter than the reference.",
        "",
        "| Forecast | MAE (days) |",
        "|---|---:|",
        f"| 1981–2015 normal | {m['normal']:.2f} |",
        f"| Previous 10 years' average | {m['recent']:.2f} |",
        f"| Gradient boosting (Poisson) | {m['model']:.2f} |",
        "",
        f"- Model vs normal: **{metrics['skill_vs_normal']:+.1%}**",
        f"- Model vs recent decade: **{metrics['skill_vs_recent']:+.1%}** "
        f"(95% CI {lo:+.1%} to {hi:+.1%}, year bootstrap)",
        f"- Recent decade vs normal: {metrics['recent_vs_normal']:+.1%}, i.e. the warming trend",
        "",
        "| City | Model MAE | Recent-decade MAE |",
        "|---|---:|---:|",
        *[f"| {r['city']} | {r['err_model']:.2f} | {r['err_recent']:.2f} |"
          for r in metrics["by_city"]],
        "",
        "Caveat: ERA5 is a ~28 km grid average and runs cooler than city weather stations, so",
        "absolute counts are lower than BMD reports; the outlook is about relative risk.",
        "",
    ]
    path.write_text("\n".join(md), encoding="utf-8")


def run(feat: pd.DataFrame) -> tuple[dict, dict, pd.DataFrame]:
    d = build_heat_features(feat)
    bundle = train_heat(d)
    metrics = evaluate_heat(bundle, d)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, HEAT_BUNDLE_PATH)
    HEAT_METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_report(metrics)
    log.info("Heat outlook: MAE %s, skill vs recent %+.1f%%", metrics["mae_days"],
             100 * metrics["skill_vs_recent"])
    return bundle, metrics, d
