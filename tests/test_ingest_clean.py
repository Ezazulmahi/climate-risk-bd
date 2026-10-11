import numpy as np
import pandas as pd

from climrisk.clean import clean
from climrisk.config import City
from climrisk.ingest import parse_daily, to_monthly

CITY = City("Alpha", 23.0, 90.0)


def _payload(days: pd.DatetimeIndex, precip: list) -> dict:
    n = len(days)
    return {
        "daily": {
            "time": [d.strftime("%Y-%m-%d") for d in days],
            "precipitation_sum": precip,
            "temperature_2m_mean": [25.0] * n,
            "temperature_2m_max": [30.0] * n,
            "temperature_2m_min": [20.0] * n,
            "relative_humidity_2m_mean": [80.0] * n,
            "wind_speed_10m_mean": [7.0] * n,
        }
    }


def test_to_monthly_sums_rain_and_drops_partial_month():
    days = pd.date_range("2024-01-01", "2024-03-10")
    precip = [1.0] * len(days)
    precip[-3:] = [None] * 3  # reanalysis not yet available for the last days
    monthly = to_monthly(parse_daily(_payload(days, precip)), CITY)

    assert list(monthly["date"].dt.strftime("%Y-%m")) == ["2024-01", "2024-02"]
    assert monthly["precip_mm"].tolist() == [31.0, 29.0]  # 2024 is a leap year
    assert monthly["t2m"].tolist() == [25.0, 25.0]
    assert (monthly["city"] == "Alpha").all()


def test_clean_flags_out_of_range_and_fills_calendar(monthly):
    raw = monthly[monthly["city"] == "Alpha"].copy()
    raw.loc[raw.index[5], "precip_mm"] = -4.0  # impossible
    raw.loc[raw.index[6], "rh2m"] = 140.0  # impossible
    raw = raw.drop(raw.index[10])  # a missing month
    raw = pd.concat([raw, raw.iloc[[0]]])  # a duplicate row

    df, report = clean(raw)

    assert report["out_of_range"]["precip_mm"] == 1
    assert report["out_of_range"]["rh2m"] == 1
    assert report["duplicates_dropped"] == 1
    assert report["calendar_months_added"] == 1
    # Calendar is complete again, so shift(1) means "previous month".
    assert (df["date"].diff().dropna().dt.days.between(28, 31)).all()
    # Precipitation is never invented...
    assert np.isnan(df.loc[5, "precip_mm"]) and np.isnan(df.loc[10, "precip_mm"])
    # ...but short covariate gaps are interpolated.
    assert not np.isnan(df.loc[6, "rh2m"])


def test_clean_trims_trailing_months_without_rain(monthly):
    raw = monthly[monthly["city"] == "Alpha"].copy()
    raw.loc[raw.index[-2:], "precip_mm"] = np.nan
    df, report = clean(raw)
    assert report["trailing_months_trimmed"] == 2
    assert df["date"].max() == raw["date"].iloc[-3]


def test_update_refetches_only_recent_months(monkeypatch, monthly):
    from climrisk import config, ingest

    existing = monthly[monthly["city"] == "Alpha"].copy()
    calls = []

    def fake_fetch(city, start, end, refresh):
        calls.append((city.name, start))
        days = pd.date_range(start, "2025-02-28")
        return _payload(days, [2.0] * len(days))

    monkeypatch.setattr(config, "CITIES", (CITY, City("Gamma", 24.0, 91.0)))
    monkeypatch.setattr(ingest, "fetch_city", fake_fetch)
    out = ingest.update(existing, months_back=3)

    # Alpha: from three months before its last month; Gamma (no data yet): full history.
    assert calls == [("Alpha", "2024-09-01"), ("Gamma", f"{config.START_YEAR}-01-01")]
    alpha = out[out["city"] == "Alpha"].set_index("date")
    assert alpha.index.is_unique and alpha.index.max() == pd.Timestamp("2025-02-01")
    # Old months untouched, refreshed months replaced.
    assert alpha.loc["2010-05-01", "precip_mm"] == existing.set_index("date").loc[
        "2010-05-01", "precip_mm"]
    assert alpha.loc["2024-10-01", "precip_mm"] == 62.0
