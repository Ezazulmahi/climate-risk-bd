"""Dengue: can last month's weather and cases predict next month's cases?

Data: *Monthly Division-Level Dengue Cases & Mortality ... in Bangladesh
(2020–2025)*, Hasan et al., Mendeley Data v2, doi:10.17632/cgwjshkx5k.2,
CC BY 4.0, compiled from government (DGHS) health bulletins. Annual totals
match official figures closely (2023: ~324k cases, 1,697 deaths).

Weather comes from this project's ERA5 city series (each division's capital).

Only six seasons exist, so this is a deliberately simple, honest backtest:

- persistence:      next month = this month
- seasonal ratio:   this month × the typical month-to-month growth for that
                    calendar month, learned from training years
- ridge regression: log cases, recent growth, lagged rain/temperature/humidity
                    (mosquito breeding lags rainfall by weeks), season

Train on target months 2020–2023, test on 2024–2025. A live forecast needs a
current case feed (DGHS publishes daily press releases), which is not
automated here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config

log = logging.getLogger(__name__)

DENGUE_URL = (
    "https://data.mendeley.com/public-files/datasets/cgwjshkx5k/files/"
    "603c72d9-a6b2-441d-9f3b-552ebbda30b8/file_downloaded"
)
DENGUE_RAW = config.RAW_DIR / "dengue" / "mendeley_cgwjshkx5k_v2.xlsx"
DENGUE_PROCESSED = config.PROCESSED_DIR / "dengue_monthly.csv"
DENGUE_RESULTS = config.PROCESSED_DIR / "dengue_backtest.json"
TEST_FROM = 2024

FEATURES = [
    "log_cases",
    "log_cases_lag1",
    "growth",
    "precip_lag1",
    "precip_lag2",
    "t2m",
    "rh2m",
    "month_sin",
    "month_cos",
    "seasonal_growth_next",
]


def load_cases(path: Path = DENGUE_RAW) -> pd.DataFrame:
    import requests

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(DENGUE_URL, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    raw = pd.read_excel(path)
    raw[["Division", "Year"]] = raw[["Division", "Year"]].ffill()  # merged cells in the sheet
    month = pd.to_datetime(raw["Month"].str.strip(), format="%B").dt.month
    return pd.DataFrame({
        "city": raw["Division"].str.strip(),
        "date": pd.to_datetime(dict(year=raw["Year"].astype(int), month=month, day=1)),
        "cases": raw["Infected"].astype(float),
        "deaths": raw["Death"].astype(float),
    }).sort_values(["city", "date"]).reset_index(drop=True)


def build(cases: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    d = cases.merge(weather[["city", "date", "precip_mm", "t2m", "rh2m"]],
                    on=["city", "date"], how="left")
    d = d.sort_values(["city", "date"]).reset_index(drop=True)
    g = d.groupby("city")
    d["log_cases"] = np.log1p(d["cases"])
    d["log_cases_lag1"] = g["log_cases"].shift(1)
    d["growth"] = d["log_cases"] - d["log_cases_lag1"]
    d["precip_lag1"] = g["precip_mm"].shift(1)
    d["precip_lag2"] = g["precip_mm"].shift(2)
    d["target_date"] = d["date"] + pd.offsets.MonthBegin(1)
    m = d["target_date"].dt.month
    d["month_sin"], d["month_cos"] = np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12)
    d["target_log"] = g["log_cases"].shift(-1)
    d["target_cases"] = g["cases"].shift(-1)

    # Typical log growth into each calendar month, learned from training years only.
    growth_next = g["log_cases"].shift(-1) - d["log_cases"]
    train = d["target_date"].dt.year < TEST_FROM
    seasonal = growth_next[train].groupby(m[train]).mean()
    d["seasonal_growth_next"] = m.map(seasonal).fillna(0.0)
    return d


def backtest(d: pd.DataFrame) -> dict:
    rows = d.dropna(subset=FEATURES + ["target_log"])
    train = rows[rows["target_date"].dt.year < TEST_FROM]
    test = rows[rows["target_date"].dt.year >= TEST_FROM].copy()
    model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30)))
    model.fit(train[FEATURES], train["target_log"])

    preds = {
        "persistence": test["log_cases"].to_numpy(),
        "seasonal_ratio": (test["log_cases"] + test["seasonal_growth_next"]).to_numpy(),
        "ridge": model.predict(test[FEATURES]),
    }
    y_log, y = test["target_log"].to_numpy(), test["target_cases"].to_numpy()
    scores = {}
    for name, p in preds.items():
        cases = np.expm1(np.clip(p, 0, None))
        scores[name] = {
            "mae_log": float(np.mean(np.abs(y_log - p))),
            "mae_cases": float(np.mean(np.abs(y - cases))),
            # Rising vs falling: does the forecast get the direction of change right?
            # Undefined for persistence, which never predicts a change.
            "direction_accuracy": None if name == "persistence" else float(np.mean(
                np.sign(p - test["log_cases"].to_numpy())
                == np.sign(y_log - test["log_cases"].to_numpy())
            )),
        }
        test[f"pred_{name}"] = np.round(cases, 0)
    for name in ("seasonal_ratio", "ridge"):
        scores[name]["skill_vs_persistence_log"] = (
            1 - scores[name]["mae_log"] / scores["persistence"]["mae_log"]
        )

    coefs = dict(zip(FEATURES, model[-1].coef_.round(3).tolist(), strict=True))
    series = test[["city", "target_date", "target_cases", "pred_persistence",
                   "pred_seasonal_ratio", "pred_ridge"]].assign(
        target_date=lambda x: x["target_date"].dt.strftime("%Y-%m")
    )
    return {
        "source": "Hasan et al., Mendeley Data, doi:10.17632/cgwjshkx5k.2 (CC BY 4.0)",
        "train_months": int(len(train)),
        "test_months": int(len(test)),
        "test_period": [f"{test['target_date'].min():%Y-%m}", f"{test['target_date'].max():%Y-%m}"],
        "scores": scores,
        "ridge_coefficients": coefs,
        "series": series.to_dict(orient="records"),
    }


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def write_report(res: dict, path: Path = config.REPORTS_DIR / "dengue_evaluation.md") -> None:
    s = res["scores"]
    names = {"persistence": "Persistence (same as this month)",
             "seasonal_ratio": "Seasonal growth ratio", "ridge": "Ridge regression + weather"}
    md = [
        "# Dengue one-month-ahead backtest",
        "",
        "_Generated by `python -m climrisk dengue`._",
        "",
        f"Data: {res['source']}. Train {res['train_months']} division-months (2020–2023), "
        f"test {res['test_months']} ({res['test_period'][0]} to {res['test_period'][1]}).",
        "",
        "| Forecast | MAE (log cases) | MAE (cases) | Direction right | Skill vs persistence |",
        "|---|---:|---:|---:|---:|",
        *[
            f"| {names[k]} | {v['mae_log']:.3f} | {v['mae_cases']:,.0f} | "
            f"{_pct(v['direction_accuracy'])} | "
            f"{v.get('skill_vs_persistence_log', 0):+.1%} |"
            for k, v in s.items()
        ],
        "",
        "Ridge coefficients (standardized features, log-cases target):",
        "",
        "| Feature | Coefficient |",
        "|---|---:|",
        *[f"| `{k}` | {v:+.3f} |" for k, v in res["ridge_coefficients"].items()],
        "",
        "Caveats: six seasons of data, so results are fragile. One duplicated value was noticed",
        "in the source (Dhaka, Oct 2023 equals Aug 2023). Case counts depend on testing and",
        "reporting, not just transmission. A live forecast needs a current DGHS case feed.",
        "",
    ]
    path.write_text("\n".join(md), encoding="utf-8")


def run(weather: pd.DataFrame) -> dict:
    cases = load_cases()
    d = build(cases, weather)
    res = backtest(d)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cases.to_csv(DENGUE_PROCESSED, index=False)
    DENGUE_RESULTS.write_text(json.dumps(res, indent=2), encoding="utf-8")
    write_report(res)
    log.info("Dengue backtest: %s", {k: round(v["mae_log"], 3) for k, v in res["scores"].items()})
    return res
