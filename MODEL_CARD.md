# Model card: Bangladesh one-month rainfall and drought outlook

## What it predicts

Standing at the end of month *t*, for each of eight divisional cities:

| Output | Definition |
|---|---|
| Rainfall anomaly for month *t+1* | Total rainfall minus the 1981–2015 mean for that city and calendar month (mm), with an 80% prediction interval |
| Drought probability for month *t+1* | P(SPI-3 ≤ −1.0), meaning the 3-month total ending in *t+1* is in roughly the driest 16% of the 1981–2015 record |

## Data

- **Source:** ERA5 reanalysis (ECMWF), daily, via the Open-Meteo historical archive, pinned to `models=era5`. Aggregated to complete calendar months.
- **Locations:** one grid point (~0.25°, about 28 km) nearest each city centre: Dhaka, Chattogram, Khulna, Rajshahi, Sylhet, Barishal, Rangpur, Mymensingh.
- **Period:** January 1981 to the most recent complete month (ERA5 runs about one week behind real time).
- **Rejected source:** NASA POWER `PRECTOTCORR`. Its Bangladesh precipitation has a step change: Dhaka is about 1,000 mm/yr in the early 1990s and 2,500–4,600 mm/yr after 2016. That would make any anomaly or SPI meaningless. See `reports/data_source_check.md`.

## Training procedure

| Period (target months) | Use |
|---|---|
| 1982–2015 | Training. Also the reference period for climatology and SPI fitting |
| 2016–2019 | Validation: hyperparameter search, decision thresholds, conformal calibration |
| 2020 onward | Test, touched once |

The split is by time, not random, so the model never trains on months after the ones it is scored on. Climatology and SPI parameters are fitted on training years only, and a unit test checks that nothing after the reference period changes any feature.

Models (scikit-learn):

- Regression on the standardized anomaly: climatology (predict 0), RidgeCV, and `HistGradientBoostingRegressor` (absolute-error loss).
- 80% interval: quantile gradient boosting at 10% and 90%, widened by conformalized quantile regression (Romano et al., 2019) on the validation years.
- Drought classifier, compared against:
  - the base rate;
  - a climatological ensemble (known rain from the last two months plus each historical value of the next month);
  - logistic regression;
  - `HistGradientBoostingClassifier`.

## Evaluation

See [`reports/evaluation.md`](reports/evaluation.md) for the full tables. It covers:

- **Rainfall:** MAE/RMSE, skill against climatology, and a 95% CI from a year-block bootstrap.
- **Intervals:** coverage overall and by season.
- **Drought:** ROC-AUC, PR-AUC, Brier score, precision/recall/F1 and a reliability diagram.
- **Error analysis:** errors by season and city, the ten largest errors, and permutation importance.

## Intended use

A teaching and portfolio demonstration of a careful forecasting workflow. **It is not an operational forecast.** For decisions affecting people, crops or water, use the Bangladesh Meteorological Department (BMD) and the Flood Forecasting and Warning Centre (FFWC).

## Limitations and known failure modes

- **Reanalysis is not rain-gauge data.** ERA5's convective rainfall has biases, especially in hilly Sylhet and Chattogram. A single grid point represents a whole division.
- **One-month-ahead rainfall amounts are barely predictable** from local predictors. The regression shows near-zero skill against climatology, which is the expected result, not a bug. Real skill at this lead time comes from large-scale drivers (ENSO, the Indian Ocean Dipole, MJO) and dynamical forecast models, which are not used here.
- **The drought skill is mostly "already known rain".** SPI-3 for next month shares two of its three months with what has already been observed. That is why it is compared against the climatological ensemble, not just the base rate.
- **Extremes are under-predicted.** The worst errors are record floods such as Chattogram in August 2024 and Sylhet in June 2024. They are driven by weather systems that none of the features can see a month ahead.
- **Non-stationarity.** Climatology is fixed to 1981–2015. If the climate shifts, anomalies drift and the drought base rate changes; the test period's drought rate already differs from the training rate.
- **Small evaluation sample.** About 6–7 test years. Bootstrap CIs are wide, and differences of a few percent between models are not significant.
- **Dry-season SPI is noisy.** December to February totals are near zero, so small absolute changes move SPI a lot.

## Ethical considerations

A false "low risk" message could delay preparation, and a false alarm erodes trust. The dashboard therefore shows probabilities and ranges, never a single number, and states the base rate next to every drought probability.
