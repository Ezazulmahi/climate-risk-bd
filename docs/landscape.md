# Landscape: related work, the US–Bangladesh gap and the roadmap

This page puts the project in context:

1. Who has worked on rainfall and drought prediction for Bangladesh already.
2. Which climate-risk tools are standard in the United States but missing or early-stage in Bangladesh.
3. Which follow-up projects can reuse this pipeline.

> Scope note: the literature summary comes from abstracts and search summaries, not full re-analysis of each paper. The "missing in Bangladesh" column reflects public, continuously updated tools; pilots or internal government systems may exist.

---

## 1. Related work

### Research on Bangladesh

| Study | What it did | How this project relates |
|---|---|---|
| *Forecasting SPI using data intelligence models: regional investigation of Bangladesh*, Scientific Reports, 2021 ([link](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7873304/)) | RF, ELM, MPMR, M5 Tree and OSELM forecasting SPI-1/3/6/12 at Barisal, Bogra, Faridpur and Mymensingh from 1949–2013 gauge data | The closest academic match to the drought task. This project adds a climatological-ensemble baseline, a strict time-based split and a deployed service |
| Hossain et al., *An ensemble learning approach for drought analysis and forecasting* ([link](https://pure.kfupm.edu.sa/en/publications/an-ensemble-learning-approach-for-drought-analysis-and-forecastin/)) | Seven central stations, 1990–2022, RF at ~94% accuracy on SPI/SPEI, ARIMA projections to 2030 | High accuracy figures on SPI are expected because SPI windows overlap; this project measures skill *relative to* a baseline that already knows the overlapping months |
| Akter et al., Rangpur drought trends and prediction, 2023 ([link](https://doaj.org/article/d9c7c90c3d2548e98703e4887cf740c8)) | ANN, SVM and RF for SPI/SPEI, 1979–2020; long-term drought predicted poorly | Consistent with this project's finding that skill beyond what is already observed is limited |
| Monthly rainfall ML for northwest, southwest and Rajshahi, International Journal of Statistical Sciences, 2025 ([link](https://www.banglajol.info/index.php/ijss/article/view/85776)) | RF, MLR, KNN, MLP and hybrid distribution-fitting models on BMD station data | This project finds no skill over climatology for rainfall *amounts* one month ahead, using a held-out future period |
| LSTM monthly rainfall at nine stations, arXiv 2024 ([link](https://arxiv.org/html/2401.08070v2)) | Bayesian-optimized LSTM lags | Possible future model to compare, against the same climatology baseline |
| Debnath & Pranta, *Precision Rainfall Modeling…*, Mendeley Data ([link](https://data.mendeley.com/datasets/y8yn7ttm4n/3)) | Open code and CSV for monthly rainfall ML | A public dataset for cross-checking |

### Apps and dashboards elsewhere

| Tool | What it is |
|---|---|
| [drought-predictor](https://github.com/rishav-raj-sinha/drought-predictor) | SPI-12 forecast with Prophet, Streamlit and Folium map (not Bangladesh-specific) |
| [DroughtObserve (UN-IHE)](https://waterpip.un-ihe.org/droughtobserve) | Operational drought dashboard with 6-month forecasts |
| [IWMI South Asia Drought Outlook](https://www.iwmi.cgiar.org/tools/drought-bulletin/2021/7-south_asia_drought_outlook-2021-sep-issue-7.pdf) | Regional bulletin that includes Bangladesh |
| Web-based SPI prediction, South Sumatra ([link](https://ejournal.ust.ac.id/index.php/JTIUST/article/view/5333)) | RNN/LSTM SPI forecasts in a web app |

### What this project does differently

| | Typical study | This project |
|---|---|---|
| Data quality | Use the dataset as given | Audits the source first. NASA POWER rainfall was found to be inhomogeneous over Bangladesh and was rejected ([check](../reports/data_source_check.md)) |
| Evaluation | Random or in-sample splits, accuracy or R² | Strict time split (train ≤2015, tune 2016–19, test 2020+), leakage tests, bootstrap confidence intervals |
| Baselines | Often none, or a persistence model | Climatology plus a climatological ensemble for SPI-3, which ML did **not** beat. Reported plainly |
| Uncertainty | Point forecasts | Conformal 80% intervals with measured coverage |
| Delivery | Paper or notebook | Database, API, website and monthly refresh, with a public record of every forecast against its outcome |

---

## 2. What the US has that Bangladesh lacks (climate risk)

| In the US | What it does | Bangladesh today | Fit with this project |
|---|---|---|---|
| [US Drought Monitor](https://droughtmonitor.unl.edu) | Weekly county-level drought severity map | No continuous public drought-monitoring map; a gap noted in a [Bangladesh drought-monitoring presentation](https://www.gwp.org/globalassets/global/gwp-sas_files/news-and-activities/sadms/session-2/md.-shadekul-alam-bangladesh-.pdf) | **Direct.** SPI is already computed; extend to 64 districts |
| [drought.gov](https://www.drought.gov) (NIDIS) | One portal for drought maps, outlooks and impacts | Information spread across BMD, BAMIS and papers | The website is a small version of this |
| NOAA CPC monthly/seasonal outlooks | Probabilistic above/near/below-normal outlooks | BMD outlooks are mostly text/PDF bulletins | Same format as this project's forecasts |
| NOAA outlook verification | Public scoring of past outlooks | Rarely published | **Already built**: `/verification` and the track-record panels |
| [NWS HeatRisk](https://www.wpc.ncep.noaa.gov/heatrisk/) | Heat warnings tied to health impact | Mostly temperature-only warnings | Temperature and humidity are already ingested |
| Weather-index crop insurance | Automatic payouts when an index crosses a threshold | Small pilots | Drought probability or SPI could serve as the trigger |
| USDA satellite crop-yield forecasts | Yield per county before harvest | Not public per district | Same pipeline with satellite greenness (NDVI) as extra features |
| CDC FluSight | Weekly outbreak forecasts with scored accuracy | No public dengue forecast | Weather-driven, so it reuses this pipeline end to end |
| AirNow | AQI forecasts and health advice | Monitoring exists; public forecasts are limited | Weather features plus pollution data |
| USGS landslide hazard maps | Rainfall-triggered susceptibility | Research maps for Chattogram Hill Tracts | Rainfall thresholds from this data |
| FEMA National Risk Index | Hazard × exposure × vulnerability per county | Mostly in reports | Hazard layer from this project + census vulnerability |

Flood forecasting is where Bangladesh is relatively strong (FFWC, Google Flood Hub), so this project doesn't try to compete there.

---

## 3. Roadmap

Ordered by how directly each one reuses the existing pipeline (ingest → clean → features → baseline vs. ML → stored forecasts → API → web).

| # | Project | New data needed | Baseline to beat | Effort |
|---|---|---|---|---|
| 1 | **Bangladesh Drought Monitor**: all 64 districts, monthly map with US Drought Monitor-style categories plus a one-month outlook | None (ERA5 covers the country) | Climatological ensemble | Small |
| 2 | **Large-scale climate drivers**: add ENSO (ONI) and Indian Ocean Dipole indices as features | NOAA PSL index files (public) | Current model | Small |
| 3 | **Dhaka heat-stress forecast**: days above a heat-index threshold next week or month | ERA5 hourly temperature/humidity | Climatology of hot days | Small |
| 4 | **Dengue outbreak forecast for Dhaka**: weekly cases 2–8 weeks ahead from rain, temperature and past cases | DGHS daily dengue reports | Seasonal average and last-season persistence | Medium |
| 5 | **Rice yield outlook per district**: Aman/Boro yield from weather, SPI and satellite NDVI | MODIS/Sentinel NDVI, BBS yield statistics | Trend line per district | Medium |
| 6 | **Drought-index insurance simulator**: payout rules triggered by SPI, back-tested on 1981 onward | None | Rule-based triggers | Small |
| 7 | **Dhaka waterlogging nowcast**: which areas flood after X mm of rain | Crowd-sourced or news-reported flood locations | Rainfall threshold rule | Medium |
| 8 | **Landslide early warning (Chattogram Hill Tracts)**: rainfall thresholds | Landslide event inventory, elevation data | Antecedent-rainfall threshold | Medium |
| 9 | **Gauge validation**: compare ERA5 with BMD station records | BMD station data (request or purchase) | — | Medium |
| 10 | **Prospective verification**: freeze each live forecast at issue time | None | — | Small |

Other high-impact Bangladesh ML ideas that are outside this project's scope include riverbank erosion prediction, satellite poverty mapping, Bangla legal and government-service assistants, and mobile-money credit scoring.
