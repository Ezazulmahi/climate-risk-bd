"""Database schema and engine.

PostgreSQL in deployment (``DATABASE_URL``); any SQLAlchemy URL works, and the
tests use SQLite. Tables:

- ``cities``        one row per location
- ``observations``  monthly rainfall, its normal, anomaly and SPI-3
- ``forecasts``     every forecast issued by a model version: validation and test
                    hindcasts plus the live forecast, so accuracy can be verified
- ``model_runs``    one row per model version with its test metrics
"""

from __future__ import annotations

import os
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy.engine import Engine

DEFAULT_URL = "postgresql+psycopg://climrisk@localhost:54330/climrisk"

metadata = sa.MetaData()

cities = sa.Table(
    "cities",
    metadata,
    sa.Column("name", sa.String(64), primary_key=True),
    sa.Column("lat", sa.Float, nullable=False),
    sa.Column("lon", sa.Float, nullable=False),
)

observations = sa.Table(
    "observations",
    metadata,
    sa.Column("city", sa.String(64), sa.ForeignKey("cities.name"), primary_key=True),
    sa.Column("month", sa.Date, primary_key=True),
    sa.Column("precip_mm", sa.Float),
    sa.Column("normal_mm", sa.Float),
    sa.Column("anomaly_mm", sa.Float),
    sa.Column("spi3", sa.Float),
    sa.Column("t2m", sa.Float),
    sa.Column("rh2m", sa.Float),
)

forecasts = sa.Table(
    "forecasts",
    metadata,
    sa.Column("model_version", sa.String(64), primary_key=True),
    sa.Column("city", sa.String(64), sa.ForeignKey("cities.name"), primary_key=True),
    sa.Column("target_month", sa.Date, primary_key=True),
    sa.Column("issued_through", sa.Date, nullable=False),
    sa.Column("split", sa.String(16), nullable=False),  # validation | test | live
    sa.Column("expected_mm", sa.Float, nullable=False),
    sa.Column("lower_mm", sa.Float, nullable=False),
    sa.Column("upper_mm", sa.Float, nullable=False),
    sa.Column("normal_mm", sa.Float, nullable=False),
    sa.Column("drought_prob", sa.Float, nullable=False),
    sa.Column("drought_base_rate", sa.Float, nullable=False),
    sa.Column("risk_level", sa.String(16), nullable=False),
    sa.Index("ix_forecasts_city_month", "city", "target_month"),
)

model_runs = sa.Table(
    "model_runs",
    metadata,
    sa.Column("version", sa.String(64), primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, default=False),
    sa.Column("data_through", sa.Date, nullable=False),
    sa.Column("meta", sa.JSON, nullable=False),
    sa.Column("metrics", sa.JSON),
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    # Hosted providers (Neon, Render) hand out postgres:// URLs; use the psycopg 3 driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    return sa.create_engine(url or database_url(), pool_pre_ping=True, future=True)


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine)
