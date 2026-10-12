"""Model training and selection.

Two tasks, each with a naive baseline, a simple statistical model and an ML model:

Regression - next month's rainfall anomaly (trained on the standardized anomaly z,
evaluated in mm):
    climatology  -> predict anomaly 0, i.e. "next month will be average"
    ridge        -> linear regression with L2 penalty
    hgb          -> histogram gradient boosting, tuned on the validation years

Classification - will next month's SPI-3 be <= -1 (moderate drought or worse)?
    climatology  -> constant probability = training base rate
    ensemble     -> climatological ensemble: known rain + every historical next month
    logistic     -> logistic regression
    hgb          -> histogram gradient boosting classifier

Hyperparameters, decision thresholds and interval widths are chosen on the
validation years only. Point models are then refit on train+validation.
Prediction intervals use conformalized quantile regression (Romano et al., 2019):
quantile models fit on train, widened by a margin calibrated on validation.
"""

from __future__ import annotations

import itertools
import logging
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import f1_score, log_loss, mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .features import CLF_TARGET, REG_TARGET, feature_columns, modelling_rows, temporal_split

log = logging.getLogger(__name__)

DEFAULT_GRID: dict[str, list] = {
    "learning_rate": [0.03, 0.1],
    "max_depth": [2, 4],
    "max_iter": [150, 400],
}


def _grid(grid: dict[str, list]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*grid.values())]


def z_to_mm(z: np.ndarray, rows: pd.DataFrame) -> np.ndarray:
    """Convert a standardized anomaly back to a rainfall anomaly in mm."""
    return np.asarray(z) * rows["clim_precip_std_next"].to_numpy()


def make_ridge():
    return make_pipeline(
        SimpleImputer(strategy="median"), StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))
    )


def make_logistic():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.5, max_iter=2000),
    )


def _hgb_reg(params: dict, **extra) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        min_samples_leaf=30, l2_regularization=1.0, random_state=config.RANDOM_STATE,
        **params, **extra,
    )


def _hgb_clf(params: dict) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        min_samples_leaf=30, l2_regularization=1.0, random_state=config.RANDOM_STATE, **params
    )


def best_f1_threshold(y_true: np.ndarray, proba: np.ndarray) -> float:
    candidates = np.linspace(0.05, 0.9, 86)
    scores = [f1_score(y_true, proba >= t, zero_division=0) for t in candidates]
    return float(candidates[int(np.argmax(scores))])


def train(
    feat: pd.DataFrame,
    grid: dict[str, list] | None = None,
    alpha: float = config.INTERVAL_ALPHA,
    use_indices: bool = config.USE_CLIMATE_INDICES,
) -> dict[str, Any]:
    """Fit every model and return a serializable bundle."""
    grid = grid or DEFAULT_GRID
    cols = feature_columns(feat, use_indices)
    rows = modelling_rows(feat, cols)
    tr, va, _ = temporal_split(rows)
    trva = pd.concat([tr, va])
    X_tr, X_va, X_trva = tr[cols], va[cols], trva[cols]
    log.info("Train rows: %d, validation rows: %d", len(tr), len(va))

    # ---------- Regression ----------
    y_va_mm = va["target_anom_mm"].to_numpy()
    val_reg = {"climatology": mean_absolute_error(y_va_mm, np.zeros_like(y_va_mm))}

    ridge = make_ridge().fit(X_tr, tr[REG_TARGET])
    val_reg["ridge"] = mean_absolute_error(y_va_mm, z_to_mm(ridge.predict(X_va), va))

    best_reg, best_mae = None, np.inf
    for params in _grid(grid):
        m = _hgb_reg(params, loss="absolute_error").fit(X_tr, tr[REG_TARGET])
        mae = mean_absolute_error(y_va_mm, z_to_mm(m.predict(X_va), va))
        if mae < best_mae:
            best_reg, best_mae = params, mae
    val_reg["hgb"] = best_mae
    log.info("Regression validation MAE (mm): %s; best params %s", val_reg, best_reg)

    # Conformalized quantile regression for the 80% interval.
    q_lo = _hgb_reg(best_reg, loss="quantile", quantile=alpha / 2).fit(X_tr, tr[REG_TARGET])
    q_hi = _hgb_reg(best_reg, loss="quantile", quantile=1 - alpha / 2).fit(X_tr, tr[REG_TARGET])
    y_va_z = va[REG_TARGET].to_numpy()
    scores = np.maximum(q_lo.predict(X_va) - y_va_z, y_va_z - q_hi.predict(X_va))
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    cqr_margin = float(np.quantile(scores, level, method="higher"))

    reg_models = {
        "ridge": make_ridge().fit(X_trva, trva[REG_TARGET]),
        "hgb": _hgb_reg(best_reg, loss="absolute_error").fit(X_trva, trva[REG_TARGET]),
    }

    # ---------- Classification ----------
    y_tr_c, y_va_c = tr[CLF_TARGET].astype(int), va[CLF_TARGET].astype(int)
    base_rate = float(y_tr_c.mean())
    val_clf: dict[str, dict[str, float]] = {
        "climatology": {"log_loss": log_loss(y_va_c, np.full(len(y_va_c), base_rate))}
    }
    thresholds = {"climatology": 0.5}

    p = va["drought_prob_ens"].to_numpy()
    thresholds["ensemble"] = best_f1_threshold(y_va_c, p)
    val_clf["ensemble"] = {"log_loss": log_loss(y_va_c, np.clip(p, 1e-3, 1 - 1e-3))}

    logit = make_logistic().fit(X_tr, y_tr_c)
    p = logit.predict_proba(X_va)[:, 1]
    thresholds["logistic"] = best_f1_threshold(y_va_c, p)
    val_clf["logistic"] = {"log_loss": log_loss(y_va_c, p)}

    best_clf, best_ll, best_p = None, np.inf, None
    for params in _grid(grid):
        m = _hgb_clf(params).fit(X_tr, y_tr_c)
        p = m.predict_proba(X_va)[:, 1]
        ll = log_loss(y_va_c, p)
        if ll < best_ll:
            best_clf, best_ll, best_p = params, ll, p
    thresholds["hgb"] = best_f1_threshold(y_va_c, best_p)
    val_clf["hgb"] = {"log_loss": best_ll}
    log.info("Classification validation log-loss: %s; best params %s", val_clf, best_clf)

    y_trva_c = trva[CLF_TARGET].astype(int)
    clf_models = {
        "logistic": clone(make_logistic()).fit(X_trva, y_trva_c),
        "hgb": _hgb_clf(best_clf).fit(X_trva, y_trva_c),
    }

    return {
        "feature_columns": cols,
        "reg_models": reg_models,
        "reg_interval": {"lo": q_lo, "hi": q_hi, "margin": cqr_margin, "alpha": alpha},
        "clf_models": clf_models,
        "clf_base_rate": base_rate,
        "clf_thresholds": thresholds,
        "best_params": {"regression": best_reg, "classification": best_clf},
        "validation": {"regression_mae_mm": val_reg, "classification": val_clf},
        "meta": {
            "train_years": [int(tr["target_date"].dt.year.min()), config.TRAIN_END],
            "val_years": [config.TRAIN_END + 1, config.VAL_END],
            "reference_years": [config.REF_START, config.REF_END],
            "drought_threshold": config.DROUGHT_THRESHOLD,
            "n_train": int(len(tr)),
            "n_val": int(len(va)),
            "sklearn_version": sklearn.__version__,
        },
    }


def predict_regression(bundle: dict, rows: pd.DataFrame, model: str = "hgb") -> pd.DataFrame:
    """Point forecast and conformal interval, in mm, for the given feature rows."""
    X = rows[bundle["feature_columns"]]
    if model == "climatology":
        z = np.zeros(len(rows))
    else:
        z = bundle["reg_models"][model].predict(X)
    iv = bundle["reg_interval"]
    lo_z = iv["lo"].predict(X) - iv["margin"]
    hi_z = iv["hi"].predict(X) + iv["margin"]
    clim = rows["clim_precip_mean_next"].to_numpy()
    out = pd.DataFrame(index=rows.index)
    out["anom_mm"] = z_to_mm(z, rows)
    out["anom_lo_mm"] = z_to_mm(lo_z, rows)
    out["anom_hi_mm"] = z_to_mm(hi_z, rows)
    # Rainfall can't be negative, so clip the implied totals at zero.
    out["precip_mm"] = np.clip(clim + out["anom_mm"], 0, None)
    out["precip_lo_mm"] = np.clip(clim + out["anom_lo_mm"], 0, None)
    out["precip_hi_mm"] = np.clip(clim + out["anom_hi_mm"], 0, None)
    return out


def predict_drought_proba(bundle: dict, rows: pd.DataFrame, model: str = "hgb") -> np.ndarray:
    if model == "climatology":
        return np.full(len(rows), bundle["clf_base_rate"])
    if model == "ensemble":
        return rows["drought_prob_ens"].to_numpy()
    return bundle["clf_models"][model].predict_proba(rows[bundle["feature_columns"]])[:, 1]
