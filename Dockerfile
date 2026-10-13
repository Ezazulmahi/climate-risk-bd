# API image: trains the model from the committed processed data at build time, then on
# start publishes observations + forecasts to DATABASE_URL and serves FastAPI.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    CLIMRISK_HOME=/app
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY data/processed ./data/processed
# Deterministic (fixed seeds, fixed training years), so every build yields the same model version.
RUN python -m climrisk train && python -m climrisk evaluate && python -m climrisk heat

EXPOSE 8000
CMD ["sh", "-c", "python -m climrisk db-sync && uvicorn climrisk.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
