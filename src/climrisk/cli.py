"""Command line entry point: ``python -m climrisk <step>``."""

from __future__ import annotations

import argparse
import logging

from . import pipeline

STEPS = {
    "ingest": "download (or load cached) ERA5 data and clean it",
    "update": "fetch only recent months and merge into the processed data",
    "features": "compute climatology, SPI and model features",
    "eda": "exploratory figures and reports/eda.md",
    "train": "fit baselines and models, save models/model_bundle.joblib",
    "evaluate": "score on the held-out test years, write reports/evaluation.md",
    "all": "run every step in order (ingest .. evaluate)",
    "db-sync": "publish observations, forecasts and metrics to DATABASE_URL",
    "experiment": "compare the model with and without ENSO/IOD indices",
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="climrisk", description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    for name, help_text in STEPS.items():
        p = sub.add_parser(name, help=help_text)
        if name in ("ingest", "all"):
            p.add_argument("--refresh", action="store_true", help="ignore the download cache")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    refresh = getattr(args, "refresh", False)
    {
        "ingest": lambda: pipeline.step_ingest(refresh),
        "update": pipeline.step_update,
        "db-sync": pipeline.step_db_sync,
        "experiment": pipeline.step_experiment,
        "features": pipeline.step_features,
        "eda": pipeline.step_eda,
        "train": pipeline.step_train,
        "evaluate": pipeline.step_evaluate,
        "all": lambda: pipeline.run_all(refresh),
    }[args.step]()


if __name__ == "__main__":
    main()
