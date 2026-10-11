# climate-risk-bd: Bangladesh rainfall and drought outlook

A full-stack forecasting app. It gives one-month-ahead **rainfall** and **drought-risk** forecasts for Bangladesh divisions, built on 45 years of ERA5 reanalysis, and stores every past forecast so its accuracy can be checked against what actually fell.

- **ML pipeline (Python):** data audit, cleaning, SPI, leakage-safe features, honest baselines, uncertainty and error analysis.
- **Backend:** FastAPI on PostgreSQL, serving observations, forecasts, verification and metrics.
- **Frontend:** Next.js 16 with a risk map, division pages with forecast-vs-observed charts, and a model and accuracy page.
- **Ops:** Docker Compose, a Render + Neon + Vercel deployment and a monthly data-refresh workflow.

![Outlook page](docs/screenshot-outlook.jpg)

## What I found

1. **The obvious dataset was broken, so I checked before modelling.** NASA POWER's corrected precipitation reads 37–64% of ERA5 before 1997 and 107–231% after 2016, in every city. Dhaka goes from about 1,000 mm/yr in the 1990s to 4,600 mm in 2017. A model trained on it showed a "35% skill gain" that was really the model learning the data error. I switched to ERA5. ([check](reports/data_source_check.md))

   ![POWER vs ERA5](reports/figures/data_power_vs_era5.png)

2. **Next month's rainfall amount is not predictable from local history.** On the 2020–2026 test years, neither ridge regression nor gradient boosting beats "assume a normal month". Ridge's MAE skill is +0.6% with a 95% CI of −2.5% to +3.9%. That is the expected scientific result: skill at this lead time comes from large-scale climate drivers and dynamical models, not lagged local rainfall.

3. **Drought risk is predictable, and a simple physics-based baseline matches ML.** P(SPI-3 ≤ −1 next month) reaches ROC-AUC about 0.91 and a Brier skill of +39% over the base rate. But two of SPI-3's three months are already known, and a **climatological ensemble** captures that: known rain plus every historical value of next month. Logistic regression and gradient boosting do not improve on it (−2% to −3% Brier). Without that baseline, the ML models would look much better than they are.

4. **Intervals are close but slightly overconfident.** The 80% conformal intervals cover 76.7% of test months, and only 71% in the monsoon, because recent monsoons were more extreme than the 2016–2019 calibration years.

Full numbers: [`reports/evaluation.md`](reports/evaluation.md) · EDA: [`reports/eda.md`](reports/eda.md) · Limitations: [`MODEL_CARD.md`](MODEL_CARD.md)

## The task

Standing at the end of month *t*, predict for month *t+1* in each city:

| Target | Definition |
|---|---|
| Rainfall anomaly (regression) | Monthly total minus the 1981–2015 mean for that city and calendar month. Modelled as a standardized anomaly, scored in mm |
| Drought (classification) | SPI-3 ≤ −1.0, the WMO "moderately dry or worse" threshold, about 16% of months by construction |

**Data:** ERA5 daily reanalysis via the [Open-Meteo archive](https://open-meteo.com/en/docs/historical-weather-api) (no API key), with rainfall, temperature, humidity and wind from 1981 onward. Data is aggregated to complete calendar months.

**Locations:** Dhaka, Chattogram, Khulna, Rajshahi, Sylhet, Barishal and Rangpur. Mymensingh is configured but missing from the current run because the download hit Open-Meteo's hourly rate limit; rerun `python -m climrisk all` to add it.

## Method

```
ingest ─► clean ─► features ─► EDA
                      │
                      ▼
      train (selected on 2016–2019) ─► evaluate (2020+, once) ─► API / dashboard
```

| Step | Details |
|---|---|
| Cleaning | Range checks, duplicate removal, complete monthly calendar, trimming of the unfinished current month. Short covariate gaps are interpolated; rainfall is never invented |
| Features (19) | Standardized anomalies (current, lags 1/2/11, 3- and 6-month means), SPI-1/3/6/12, temperature and humidity anomalies, wind, target-month seasonality, next month's climatology, coordinates, and the ensemble drought probability |
| Split | By time: train 1982–2015 · validation 2016–2019 · test 2020 onward. Climatology and SPI are fitted on training years only |
| Rainfall models | Climatology baseline → ridge regression → gradient boosting (`HistGradientBoostingRegressor`) |
| Drought models | Base rate → climatological ensemble → logistic regression → gradient boosting |
| Uncertainty | Conformalized quantile regression (80% intervals) and year-block bootstrap CIs on skill scores |
| Error analysis | By season and city, the ten largest misses (mostly record floods in Sylhet and Chattogram), a reliability diagram and permutation importance |

### Leakage guards (tested)

- Features at month *t* are unchanged when any data after *t* is altered, for every row after the reference period.
- Climatology ignores post-reference years.
- SPI fitted on the reference period is unaffected by later data.
- The split is ordered and disjoint, and targets never cross between cities.

## Architecture

```
 Open-Meteo (ERA5)                     GitHub Actions, monthly: update → train → evaluate → commit
        │                                                    │ push triggers redeploy
        ▼                                                    ▼
 Python pipeline ── db-sync ──► PostgreSQL ◄── FastAPI (Render) ◄── Next.js server (Vercel) ◄── browser
 (src/climrisk)                 (Neon)         reads only            fetches on the server
```

The model runs offline. `db-sync` writes the observations, a stored forecast for every validation and test month (each with its outcome), the live forecast and the evaluation metrics. The API only reads, and the web app only talks to the API from its server, so no API URL or credentials reach the browser.

| Table | Contents |
|---|---|
| `cities` | name, latitude, longitude |
| `observations` | monthly rainfall, normal, anomaly, SPI-3, temperature, humidity |
| `forecasts` | per model version, city and month: expected rainfall, 80% range, normal, drought probability, risk level, split (`validation` / `test` / `live`) |
| `model_runs` | model version, data-through date, metadata, full test metrics; one is active |

## Run it locally

**1. Python pipeline** (Python 3.11 or newer)

```bash
python -m venv .venv
```
```bash
.venv/Scripts/activate
```
On macOS/Linux use `source .venv/bin/activate` instead.
```bash
pip install -e ".[dashboard,dev]"
```
```bash
python -m climrisk all
```
That runs download → clean → features → EDA → train → evaluate, about 1 minute with cached data.
```bash
pytest
```

The processed data is committed, so `train` and `evaluate` work offline. `python -m climrisk update` fetches only recent months, which is what the monthly job uses.

**2. PostgreSQL.** Any Postgres works; set `DATABASE_URL` (see `.env.example`). Without Docker, a throwaway local server with no password, on port 54330:

```bash
initdb -D .pgdata -U climrisk -A trust
```
```bash
pg_ctl -D .pgdata -o "-p 54330" -l .pgdata/server.log start
```
```bash
createdb -h localhost -p 54330 -U climrisk climrisk
```
```bash
python -m climrisk db-sync
```

**3. API**

```bash
uvicorn climrisk.api:app --reload
```

Interactive docs are at http://127.0.0.1:8000/docs.

| Endpoint | Returns |
|---|---|
| `GET /forecasts/latest` | The live forecast for every division |
| `GET /forecast?city=Dhaka&month=2024-08` | One stored forecast, with its observed outcome if known |
| `GET /forecasts?city=Sylhet&start=2022-01` | A city's forecast history with outcomes |
| `GET /verification?city=Dhaka` | Skill, interval coverage and drought Brier score computed from stored forecasts |
| `GET /history?city=Sylhet&start=2020-01` | Monthly rainfall, normal, anomaly, SPI-3 |
| `GET /cities`, `/metrics`, `/health` | Locations, full test evaluation, status |

**4. Web app**

```bash
cd web
```
```bash
npm install
```
```bash
npm run dev
```

Then open http://localhost:3000. Set `API_URL` if the API isn't on `http://localhost:8000`.

**Or all at once with Docker:**

```bash
docker compose up --build
```

That starts Postgres, the API (trains at build time, publishes on start) and the web app on http://localhost:3000.

The Streamlit notebook-style dashboard (`streamlit run app/dashboard.py`) is still there for analysis; it reads the model files directly.

## Deploy (free tiers)

| Piece | Service | Setup |
|---|---|---|
| Database | [Neon](https://neon.tech) | Create a project and copy the connection string (`...?sslmode=require`) |
| API | [Render](https://render.com) | New → Blueprint → this repo (`render.yaml`); paste the Neon URL as `DATABASE_URL` |
| Web | [Vercel](https://vercel.com) | Import the repo, set root directory to `web`, and set `API_URL` to the Render URL |
| Refresh | GitHub Actions | `.github/workflows/refresh.yml` runs on the 10th of each month and commits new data, which redeploys the API, which republishes forecasts |

On each deploy, the Docker image retrains from the committed data. Training years are fixed and seeds are set, so the model version is identical across rebuilds. Only the live forecast and the verified months move forward.

## Project layout

```
src/climrisk/   config · ingest · clean · spi · features · train · evaluate · eda · predict
                db · sync (Postgres publishing) · api (FastAPI) · cli
web/            Next.js app: outlook map, /city/[name], /model
app/            Streamlit analysis dashboard
tests/          41 offline tests (ingest, cleaning, SPI, leakage, models, DB sync, API)
scripts/        check_power_homogeneity.py (the data-source audit)
data/processed/ cleaned monthly data and features (committed; raw downloads are cached, not committed)
reports/        generated EDA, evaluation, metrics.json and figures
Dockerfile · docker-compose.yml · render.yaml · .github/workflows/{ci,refresh}.yml
```

## Limitations

ERA5 is reanalysis, not gauge data, and a single grid point stands in for a whole division. Extremes are under-predicted. The test set covers only about 7 years. Climatology is fixed to 1981–2015. Sylhet's significant drying trend in ERA5 (−222 mm/decade) should be checked against gauges before anyone trusts it. **This is a portfolio demo, not an operational forecast.** Use [BMD](https://live6.bmd.gov.bd/) and [FFWC](http://www.ffwc.gov.bd/) for real decisions. More detail is in [`MODEL_CARD.md`](MODEL_CARD.md).

## Next steps

- Add ENSO (ONI) and Indian Ocean Dipole indices, the most plausible source of real one-month rainfall skill.
- Benchmark against ECMWF SEAS5 seasonal forecasts.
- Compare with BMD station gauges.
- Freeze each month's live forecast at issue time. Today a retrained model version re-issues its own hindcasts; storing the original issue alongside would make verification fully prospective.

## License

MIT
