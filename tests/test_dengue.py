import numpy as np
import pandas as pd

from climrisk.dengue import FEATURES, backtest, build


def _cases():
    rows = []
    for city, scale in (("Alpha", 1.0), ("Beta", 0.3)):
        for date in pd.date_range("2020-01", "2024-12", freq="MS"):
            peak = np.exp(-((date.month - 9) ** 2) / 4)  # September peak
            rows.append({"city": city, "date": date, "cases": 10 + 5000 * scale * peak,
                         "deaths": 0.0})
    return pd.DataFrame(rows)


def test_seasonal_baseline_uses_training_years_only(monthly):
    cases = _cases()
    weather = monthly[monthly["date"] >= "2019-01-01"]
    base = build(cases, weather)
    changed = cases.copy()
    changed.loc[changed["date"].dt.year >= 2024, "cases"] *= 50  # a wild test year
    after = build(changed, weather)
    pd.testing.assert_series_equal(base["seasonal_growth_next"], after["seasonal_growth_next"])


def test_backtest_beats_persistence_on_seasonal_data(monthly):
    d = build(_cases(), monthly[monthly["date"] >= "2019-01-01"])
    assert not d.dropna(subset=FEATURES).empty
    res = backtest(d)
    s = res["scores"]
    # The last target month is lost to the one-month-ahead shift.
    assert res["test_period"] == ["2024-01", "2024-12"]
    assert s["seasonal_ratio"]["mae_log"] < s["persistence"]["mae_log"]
    assert s["persistence"]["direction_accuracy"] is None
    assert len(res["series"]) == res["test_months"]
