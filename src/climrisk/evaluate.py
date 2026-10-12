"""Held-out test evaluation, error analysis and uncertainty.

The test years are used exactly once, here, after every modelling choice has
been made on the validation years.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

from . import config, plots
from .features import CLF_TARGET, REG_TARGET, modelling_rows, temporal_split
from .train import predict_drought_proba, predict_regression

REG_MODELS = ("climatology", "ridge", "hgb")
CLF_MODELS = ("climatology", "ensemble", "logistic", "hgb")
SEASON_ORDER = ["Winter (DJF)", "Pre-monsoon (MAM)", "Monsoon (JJAS)", "Post-monsoon (ON)"]


def _reg_metrics(y: np.ndarray, pred: np.ndarray, y_clim_err: np.ndarray) -> dict:
    mae = mean_absolute_error(y, pred)
    mse = mean_squared_error(y, pred)
    return {
        "mae_mm": float(mae),
        "rmse_mm": float(np.sqrt(mse)),
        "mae_skill_vs_climatology": float(1 - mae / np.mean(np.abs(y_clim_err))),
        "mse_skill_vs_climatology": float(1 - mse / np.mean(y_clim_err**2)),
    }


def bootstrap_skill(
    test: pd.DataFrame, pred: np.ndarray, n_boot: int = 1000, seed: int = config.RANDOM_STATE
) -> list[float]:
    """95% CI of MAE skill vs climatology, resampling whole target *years*.

    Resampling years (not individual months) respects the fact that months in
    the same year and across cities are correlated.
    """
    rng = np.random.default_rng(seed)
    years = test["target_date"].dt.year.to_numpy()
    uniq = np.unique(years)
    err_model = np.abs(test["target_anom_mm"].to_numpy() - pred)
    err_clim = np.abs(test["target_anom_mm"].to_numpy())
    idx_by_year = {y: np.flatnonzero(years == y) for y in uniq}
    skills = []
    for _ in range(n_boot):
        idx = np.concatenate([idx_by_year[y] for y in rng.choice(uniq, size=len(uniq))])
        skills.append(1 - err_model[idx].mean() / err_clim[idx].mean())
    return [float(np.percentile(skills, 2.5)), float(np.percentile(skills, 97.5))]


def evaluate(
    bundle: dict,
    feat: pd.DataFrame,
    figures_dir: Path = config.FIGURES_DIR,
    reports_dir: Path = config.REPORTS_DIR,
    make_figures: bool = True,
) -> dict:
    rows = modelling_rows(feat, bundle["feature_columns"])
    _, _, test = temporal_split(rows)
    test = test.copy()
    if test.empty:
        raise ValueError("No test rows: is there data after the validation period?")
    y = test["target_anom_mm"].to_numpy()
    test["season"] = test["target_month"].map(config.SEASONS)

    # ---------- Regression ----------
    reg = {}
    preds = {}
    for name in REG_MODELS:
        out = predict_regression(bundle, test, model=name)
        preds[name] = out
        reg[name] = _reg_metrics(y, out["anom_mm"].to_numpy(), y)
    for name in ("ridge", "hgb"):
        reg[name]["mae_skill_95ci"] = bootstrap_skill(test, preds[name]["anom_mm"].to_numpy())

    best = preds["hgb"]
    inside = (y >= best["anom_lo_mm"]) & (y <= best["anom_hi_mm"])
    interval = {
        "nominal_coverage": 1 - bundle["reg_interval"]["alpha"],
        "empirical_coverage": float(inside.mean()),
        "mean_width_mm": float((best["anom_hi_mm"] - best["anom_lo_mm"]).mean()),
        "coverage_by_season": {
            s: float(inside[test["season"] == s].mean()) for s in SEASON_ORDER
        },
    }

    test["err_hgb"] = y - best["anom_mm"].to_numpy()
    test["abs_err_hgb"] = test["err_hgb"].abs()
    test["abs_err_clim"] = np.abs(y)
    by_season = (
        test.groupby("season")[["abs_err_hgb", "abs_err_clim"]].mean().reindex(SEASON_ORDER)
    )
    by_season["skill"] = 1 - by_season["abs_err_hgb"] / by_season["abs_err_clim"]
    by_city = test.groupby("city")[["abs_err_hgb", "abs_err_clim"]].mean()
    by_city["skill"] = 1 - by_city["abs_err_hgb"] / by_city["abs_err_clim"]
    worst = test.nlargest(10, "abs_err_hgb")[
        ["city", "target_date", "target_precip_mm", "clim_precip_mean_next", "err_hgb"]
    ].assign(
        predicted_mm=lambda d: best.loc[d.index, "precip_mm"].round(0),
        target_date=lambda d: d["target_date"].dt.strftime("%Y-%m"),
    )

    # ---------- Classification ----------
    yc = test[CLF_TARGET].astype(int).to_numpy()
    clf = {}
    probas = {}
    for name in CLF_MODELS:
        p = predict_drought_proba(bundle, test, model=name)
        probas[name] = p
        thr = bundle["clf_thresholds"][name]
        yhat = (p >= thr).astype(int)
        clf[name] = {
            "threshold": thr,
            "roc_auc": float(roc_auc_score(yc, p)) if np.ptp(p) > 0 else 0.5,
            "pr_auc": float(average_precision_score(yc, p)),
            "brier": float(brier_score_loss(yc, p)),
            "f1": float(f1_score(yc, yhat, zero_division=0)),
            "precision": float(precision_score(yc, yhat, zero_division=0)),
            "recall": float(recall_score(yc, yhat, zero_division=0)),
            "confusion_matrix": confusion_matrix(yc, yhat, labels=[0, 1]).tolist(),
        }
    for name in CLF_MODELS:
        clf[name]["brier_skill_vs_climatology"] = float(
            1 - clf[name]["brier"] / clf["climatology"]["brier"]
        )
        clf[name]["brier_skill_vs_ensemble"] = float(
            1 - clf[name]["brier"] / clf["ensemble"]["brier"]
        )

    # Permutation importance on the test set (for interpretation only).
    feats = bundle["feature_columns"]
    imp_reg = permutation_importance(
        bundle["reg_models"]["hgb"], test[feats], test[REG_TARGET],
        scoring="neg_mean_absolute_error", n_repeats=5, random_state=config.RANDOM_STATE,
    )
    imp_clf = permutation_importance(
        bundle["clf_models"]["hgb"], test[feats], yc,
        scoring="neg_brier_score", n_repeats=5, random_state=config.RANDOM_STATE,
    )
    importance = pd.DataFrame(
        {"regression": imp_reg.importances_mean, "drought": imp_clf.importances_mean},
        index=feats,
    ).sort_values("drought", ascending=False)

    metrics = {
        "test_period": [
            str(test["target_date"].min().date()), str(test["target_date"].max().date())
        ],
        "n_test": int(len(test)),
        "drought_rate_test": float(yc.mean()),
        "regression": reg,
        "interval": interval,
        "classification": clf,
        "error_by_season": by_season.round(3).reset_index().to_dict(orient="records"),
        "error_by_city": by_city.round(3).reset_index().to_dict(orient="records"),
        "largest_errors": worst.round(1).to_dict(orient="records"),
        "permutation_importance": importance.round(4).reset_index(names="feature")
        .to_dict(orient="records"),
        "validation": bundle["validation"],
        "best_params": bundle["best_params"],
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    if make_figures:
        _figures(test, preds, probas, yc, by_season, by_city, importance, bundle, figures_dir)
    _write_markdown(metrics, by_season, by_city, worst, importance, reports_dir)
    return metrics


def _figures(test, preds, probas, yc, by_season, by_city, importance, bundle, figures_dir):
    plots.apply_style()
    best = preds["hgb"]

    # Dhaka test-period forecast with 80% interval
    city = "Dhaka" if "Dhaka" in set(test["city"]) else test["city"].iloc[0]
    m = (test["city"] == city).to_numpy()
    t = test.loc[m, "target_date"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(t, best.loc[m, "precip_lo_mm"], best.loc[m, "precip_hi_mm"],
                    color=plots.BAND, linewidth=0, label="80% interval")
    ax.plot(t, test.loc[m, "clim_precip_mean_next"], color=plots.NEUTRAL, linewidth=1.5,
            linestyle="--", label="Climatology")
    ax.plot(t, best.loc[m, "precip_mm"], color=plots.BLUE, label="Gradient boosting")
    ax.plot(t, test.loc[m, "target_precip_mm"], color=plots.TEXT, linewidth=0,
            marker="o", markersize=4, label="Observed")
    ax.set_ylabel("Monthly rainfall (mm)")
    ax.set_title(f"{city}: one-month-ahead forecasts on the test years")
    ax.legend(ncol=4, loc="upper left", fontsize=8)
    plots.save(fig, figures_dir / "eval_forecast_dhaka.png")

    # MAE by season, model vs climatology
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(by_season))
    ax.bar(x - 0.18, by_season["abs_err_clim"], width=0.34, color=plots.NEUTRAL,
           label="Climatology")
    ax.bar(x + 0.18, by_season["abs_err_hgb"], width=0.34, color=plots.BLUE,
           label="Gradient boosting")
    ax.set_xticks(x, by_season.index)
    ax.set_ylabel("MAE (mm)")
    ax.set_title("Test error by season: monsoon errors dominate in absolute terms")
    ax.legend(loc="upper left")
    plots.save(fig, figures_dir / "eval_mae_by_season.png")

    # Skill by city
    s = by_city["skill"].sort_values()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(s.index, s.values * 100, color=[plots.ORANGE if v < 0 else plots.BLUE for v in s],
            height=0.6)
    ax.axvline(0, color=plots.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xlabel("MAE skill vs climatology (%)")
    ax.set_title("Where the model beats 'assume an average month'")
    plots.save(fig, figures_dir / "eval_skill_by_city.png")

    # Reliability diagram
    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.plot([0, 1], [0, 1], color=plots.NEUTRAL, linestyle="--", linewidth=1,
            label="Perfect calibration")
    labels = {"ensemble": "Climatological ensemble", "logistic": "Logistic regression",
              "hgb": "Gradient boosting"}
    for i, name in enumerate(labels):
        frac, mean_p = calibration_curve(yc, probas[name], n_bins=8, strategy="quantile")
        ax.plot(mean_p, frac, marker="o", markersize=5, color=plots.SERIES[i], label=labels[name])
    ax.set_xlabel("Predicted drought probability")
    ax.set_ylabel("Observed drought frequency")
    ax.set_title("Drought probability calibration (test)")
    ax.legend(loc="upper left")
    plots.save(fig, figures_dir / "eval_reliability.png")

    # Confusion matrix
    cm = np.array(confusion_matrix(yc, probas["hgb"] >= bundle["clf_thresholds"]["hgb"]))
    fig, ax = plt.subplots(figsize=(4.4, 4))
    ax.imshow(cm, cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "b", ["#f0efec", plots.BLUE]))
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(v), ha="center", va="center",
                color="white" if v > cm.max() / 2 else plots.TEXT, fontsize=12)
    ax.set_xticks([0, 1], ["No drought", "Drought"])
    ax.set_yticks([0, 1], ["No drought", "Drought"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Observed")
    ax.grid(False)
    ax.set_title("Drought classifier (test)")
    plots.save(fig, figures_dir / "eval_confusion.png")

    # Permutation importance
    top = importance.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.barh(top.index, top["drought"], color=plots.BLUE, height=0.6)
    ax.set_xlabel("Increase in Brier score when shuffled")
    ax.set_title("What drives the drought forecast")
    plots.save(fig, figures_dir / "eval_importance.png")


def _write_markdown(metrics, by_season, by_city, worst, importance, reports_dir):
    r, c, iv = metrics["regression"], metrics["classification"], metrics["interval"]
    names = {"climatology": "Climatology baseline", "ridge": "Ridge regression",
             "ensemble": "Climatological ensemble",
             "logistic": "Logistic regression", "hgb": "Gradient boosting"}

    def ci(m):
        lo, hi = r[m].get("mae_skill_95ci", [np.nan, np.nan])
        return "-" if np.isnan(lo) else f"[{lo:+.1%}, {hi:+.1%}]"

    md = [
        "# Test-set evaluation",
        "",
        "_Generated by `python -m climrisk evaluate`. Do not edit by hand._",
        "",
        f"Test period (target months): {metrics['test_period'][0]} to "
        f"{metrics['test_period'][1]}, {metrics['n_test']:,} city-months.",
        "",
        "## Next-month rainfall anomaly",
        "",
        "| Model | MAE (mm) | RMSE (mm) | MAE skill | 95% CI (year bootstrap) | MSE skill |",
        "|---|---:|---:|---:|---:|---:|",
        *[
            f"| {names[k]} | {v['mae_mm']:.1f} | {v['rmse_mm']:.1f} | "
            f"{v['mae_skill_vs_climatology']:+.1%} | {ci(k)} | "
            f"{v['mse_skill_vs_climatology']:+.1%} |"
            for k, v in r.items()
        ],
        "",
        f"80% conformal interval: empirical coverage **{iv['empirical_coverage']:.1%}**, "
        f"mean width {iv['mean_width_mm']:.0f} mm.",
        "",
        "| Season | Coverage |",
        "|---|---:|",
        *[f"| {s} | {v:.1%} |" for s, v in iv["coverage_by_season"].items()],
        "",
        "## Drought next month (SPI-3 <= -1)",
        "",
        f"Base rate in test: {metrics['drought_rate_test']:.1%}.",
        "",
        "| Model | ROC-AUC | PR-AUC | Brier | Brier skill vs base rate | vs ensemble "
        "| Threshold | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {names[k]} | {v['roc_auc']:.3f} | {v['pr_auc']:.3f} | {v['brier']:.3f} | "
            f"{v['brier_skill_vs_climatology']:+.1%} | {v['brier_skill_vs_ensemble']:+.1%} | "
            f"{v['threshold']:.2f} | "
            f"{v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} |"
            for k, v in c.items()
        ],
        "",
        "## Error analysis",
        "",
        "### By season (gradient boosting vs climatology, MAE in mm)",
        "",
        "| Season | Model | Climatology | Skill |",
        "|---|---:|---:|---:|",
        *[
            f"| {s} | {row.abs_err_hgb:.1f} | {row.abs_err_clim:.1f} | {row.skill:+.1%} |"
            for s, row in by_season.iterrows()
        ],
        "",
        "### By city",
        "",
        "| City | Model | Climatology | Skill |",
        "|---|---:|---:|---:|",
        *[
            f"| {s} | {row.abs_err_hgb:.1f} | {row.abs_err_clim:.1f} | {row.skill:+.1%} |"
            for s, row in by_city.sort_values("skill", ascending=False).iterrows()
        ],
        "",
        "### Ten largest errors",
        "",
        "| City | Month | Observed (mm) | Climatology (mm) | Predicted (mm) | Error (mm) |",
        "|---|---|---:|---:|---:|---:|",
        *[
            f"| {w.city} | {w.target_date} | {w.target_precip_mm:.0f} | "
            f"{w.clim_precip_mean_next:.0f} | {w.predicted_mm:.0f} | {w.err_hgb:+.0f} |"
            for w in worst.itertuples()
        ],
        "",
        "### Permutation importance (top 8)",
        "",
        "| Feature | Drought (Brier) | Anomaly (MAE, z units) |",
        "|---|---:|---:|",
        *[
            f"| `{f}` | {row.drought:.4f} | {row.regression:.4f} |"
            for f, row in importance.head(8).iterrows()
        ],
        "",
        "## Figures",
        "",
        "![Forecast](figures/eval_forecast_dhaka.png)",
        "![MAE by season](figures/eval_mae_by_season.png)",
        "![Skill by city](figures/eval_skill_by_city.png)",
        "![Reliability](figures/eval_reliability.png)",
        "![Confusion matrix](figures/eval_confusion.png)",
        "![Importance](figures/eval_importance.png)",
        "",
    ]
    (reports_dir / "evaluation.md").write_text("\n".join(md), encoding="utf-8")
