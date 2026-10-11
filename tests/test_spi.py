import numpy as np
import pandas as pd
import pytest

from climrisk.spi import classify, spi


@pytest.fixture
def gamma_series():
    rng = np.random.default_rng(1)
    idx = pd.date_range("1960-01", "2019-12", freq="MS")
    return pd.Series(rng.gamma(2.0, 50.0, len(idx)), index=idx)


def test_spi_is_standard_normal_in_reference_period(gamma_series):
    s = spi(gamma_series, scale=1, ref_start=1960, ref_end=2019)
    assert abs(s.mean()) < 0.05
    assert abs(s.std() - 1) < 0.05


def test_spi_first_values_are_nan(gamma_series):
    s = spi(gamma_series, scale=3, ref_start=1960, ref_end=2019)
    assert s.iloc[:2].isna().all()
    assert s.iloc[2:].notna().all()


def test_spi_is_monotonic_within_a_calendar_month(gamma_series):
    s = spi(gamma_series, scale=1, ref_start=1960, ref_end=2019)
    jan = pd.DataFrame({"p": gamma_series, "s": s})[gamma_series.index.month == 1]
    jan = jan.sort_values("p")
    assert jan["s"].is_monotonic_increasing


def test_spi_handles_zero_rainfall():
    idx = pd.date_range("1980-01", "2019-12", freq="MS")
    rng = np.random.default_rng(2)
    p = pd.Series(rng.gamma(2.0, 20.0, len(idx)), index=idx)
    p[rng.random(len(idx)) < 0.3] = 0.0  # many completely dry months
    s = spi(p, scale=1, ref_start=1980, ref_end=2019)
    assert s.notna().all() and np.isfinite(s).all()
    # All zero months in the same calendar month share one (low) SPI value.
    zero_jan = s[(p == 0) & (p.index.month == 1)]
    assert zero_jan.nunique() == 1 and zero_jan.iloc[0] < 0


def test_spi_does_not_depend_on_data_after_reference(gamma_series):
    base = spi(gamma_series, scale=3, ref_start=1960, ref_end=2000)
    changed = gamma_series.copy()
    changed[changed.index.year > 2000] *= 5  # a very wet future
    after = spi(changed, scale=3, ref_start=1960, ref_end=2000)
    pd.testing.assert_series_equal(base[:"2000-12"], after[:"2000-12"])


@pytest.mark.parametrize(
    "value, label",
    [(-2.3, "extreme drought"), (-1.7, "severe drought"), (-1.2, "moderate drought"),
     (0.0, "near normal"), (1.5, "wet"), (float("nan"), "unknown")],
)
def test_classify(value, label):
    assert classify(value) == label
