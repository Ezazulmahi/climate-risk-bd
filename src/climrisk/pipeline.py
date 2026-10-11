"""End-to-end steps. Each step reads the previous step's output from disk, so any
step can be rerun on its own."""

from __future__ import annotations

import json
import logging

import joblib
import pandas as pd

from . import config
from .clean import clean
from .eda import run_eda
from .evaluate import evaluate
from .features import build_features, compute_climatology
from .ingest import ingest
from .train import train

log = logging.getLogger(__name__)

CLEAN_REPORT_PATH = config.PROCESSED_DIR / "clean_report.json"


def _read(path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run the earlier pipeline steps first.")
    columns = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(path, parse_dates=[c for c in ("date", "target_date") if c in columns])


def step_ingest(refresh: bool = False) -> None:
    raw = ingest(refresh=refresh)
    df, report = clean(raw)
    report["cities_missing"] = sorted({c.name for c in config.CITIES} - set(df["city"]))
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEAN_PATH, index=False)
    CLEAN_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Clean data: %d rows -> %s", len(df), config.CLEAN_PATH)


def step_features() -> None:
    df = _read(config.CLEAN_PATH)
    clim = compute_climatology(df)
    feat = build_features(df, clim)
    feat.to_csv(config.FEATURES_PATH, index=False)
    log.info("Features: %d rows -> %s", len(feat), config.FEATURES_PATH)


def step_eda() -> None:
    df = _read(config.CLEAN_PATH)
    feat = _read(config.FEATURES_PATH)
    report = json.loads(CLEAN_REPORT_PATH.read_text()) if CLEAN_REPORT_PATH.exists() else {}
    run_eda(df, feat, report)
    log.info("EDA written to %s", config.REPORTS_DIR / "eda.md")


def step_train() -> None:
    feat = _read(config.FEATURES_PATH)
    bundle = train(feat)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, config.BUNDLE_PATH)
    log.info("Model bundle -> %s", config.BUNDLE_PATH)


def step_evaluate() -> dict:
    feat = _read(config.FEATURES_PATH)
    bundle = joblib.load(config.BUNDLE_PATH)
    metrics = evaluate(bundle, feat)
    log.info("Evaluation written to %s", config.REPORTS_DIR / "evaluation.md")
    return metrics


def run_all(refresh: bool = False) -> None:
    step_ingest(refresh)
    step_features()
    step_eda()
    step_train()
    step_evaluate()
