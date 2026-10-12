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
from .ingest import ingest, update
from .train import train

log = logging.getLogger(__name__)

CLEAN_REPORT_PATH = config.PROCESSED_DIR / "clean_report.json"


def _read(path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run the earlier pipeline steps first.")
    columns = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(path, parse_dates=[c for c in ("date", "target_date") if c in columns])


def _write_clean(raw: pd.DataFrame) -> None:
    df, report = clean(raw)
    report["cities_missing"] = sorted({c.name for c in config.CITIES} - set(df["city"]))
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEAN_PATH, index=False)
    CLEAN_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Clean data: %d rows -> %s", len(df), config.CLEAN_PATH)


def step_ingest(refresh: bool = False) -> None:
    _write_clean(ingest(refresh=refresh))


def step_update() -> None:
    """Incremental refresh of recent months (used by the monthly job)."""
    _write_clean(update(_read(config.CLEAN_PATH)))


def step_features() -> None:
    from .indices import load_indices

    df = _read(config.CLEAN_PATH)
    clim = compute_climatology(df)
    try:
        indices = load_indices()
    except Exception as exc:  # the model still works without them
        log.warning("Climate indices unavailable (%s); continuing without", exc)
        indices = None
    feat = build_features(df, clim, indices=indices)
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


def step_db_sync() -> dict:
    """Publish everything the API serves. Optional parts are skipped if not built."""
    # Imported lazily so the offline pipeline needs no database driver.
    from .db import get_engine
    from .dengue import DENGUE_RESULTS
    from .districts import DISTRICT_EVAL_PATH, DISTRICT_GEOJSON_PATH, DISTRICT_MONTHLY_PATH
    from .explain import explain_drought
    from .heat import HEAT_BUNDLE_PATH, HEAT_METRICS_PATH
    from .sync import heat_table, publish_documents, sync, sync_districts
    from .validation import VALIDATION_PATH

    engine = get_engine()
    feat = _read(config.FEATURES_PATH)
    bundle = joblib.load(config.BUNDLE_PATH)
    metrics = json.loads(config.METRICS_PATH.read_text()) if config.METRICS_PATH.exists() else None
    heat = heat_table(joblib.load(HEAT_BUNDLE_PATH), feat) if HEAT_BUNDLE_PATH.exists() else None
    counts = sync(engine, feat, bundle, metrics, heat)

    if DISTRICT_MONTHLY_PATH.exists():
        counts.update(sync_districts(
            engine,
            _read(DISTRICT_MONTHLY_PATH),
            json.loads(DISTRICT_GEOJSON_PATH.read_text(encoding="utf-8")),
        ))
    else:
        log.info("No district data; run `python -m climrisk districts` to build it")

    docs = {"drought_explanations": explain_drought(bundle, feat)}
    for name, path in (("district_outlook_eval", DISTRICT_EVAL_PATH),
                       ("era5_chirps_validation", VALIDATION_PATH),
                       ("heat_metrics", HEAT_METRICS_PATH),
                       ("dengue_backtest", DENGUE_RESULTS)):
        if path.exists():
            docs[name] = json.loads(path.read_text(encoding="utf-8"))
    counts["documents"] = publish_documents(engine, docs)
    return counts


def step_heat() -> dict:
    from .heat import run

    return run(_read(config.FEATURES_PATH))[1]


def step_dengue() -> dict:
    from .dengue import run

    return run(_read(config.CLEAN_PATH))


def step_districts(refresh: bool = False) -> None:
    """64-district drought monitor from CHIRPS, plus the ERA5-vs-CHIRPS check."""
    from . import districts, validation

    result = districts.build(refresh=refresh)
    validation.write_report(_read(config.CLEAN_PATH), result["chirps"])


def step_experiment() -> dict:
    from .experiments import compare_indices

    return compare_indices(_read(config.FEATURES_PATH))


def run_all(refresh: bool = False) -> None:
    step_ingest(refresh)
    step_features()
    step_eda()
    step_train()
    step_evaluate()
    step_heat()
