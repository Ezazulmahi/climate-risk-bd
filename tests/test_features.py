import numpy as np
import pandas as pd

from climrisk.features import (
    FEATURE_COLUMNS,
    build_features,
    compute_climatology,
    ensemble_drought_prob,
    modelling_rows,
    temporal_split,
)


def _features(df):
    return build_features(df, compute_climatology(df))


def test_targets_are_next_month(monthly):
    feat = _features(monthly)
    alpha = feat[feat["city"] == "Alpha"].reset_index(drop=True)
    np.testing.assert_allclose(alpha["target_precip_mm"].iloc[:-1], alpha["precip_mm"].iloc[1:])
    assert (alpha["target_date"] == alpha["date"] + pd.offsets.MonthBegin(1)).all()
    # The newest row has features but no target: that is the live forecast row.
    assert np.isnan(alpha["target_precip_mm"].iloc[-1])


def test_targets_do_not_cross_cities(monthly):
    feat = _features(monthly)
    last_alpha = feat[feat["city"] == "Alpha"].iloc[-1]
    assert np.isnan(last_alpha["target_precip_mm"])


def test_features_do_not_use_the_future(monthly):
    """Changing data after month t must not change any feature at month t.

    Climatology and SPI distributions are fitted on the reference years (the
    training period), so the guarantee holds for any t after the reference
    period - i.e. for every validation and test row. Within the training years,
    features legitimately depend on the training-period normals, as with any
    standardization fitted on the training set.
    """
    ref_start, ref_end = 1981, 2015
    cutoff = pd.Timestamp("2018-06-01")
    clim = compute_climatology(monthly, ref_start, ref_end)
    base = build_features(monthly, clim, ref_start, ref_end)

    future = monthly.copy()
    future.loc[future["date"] > cutoff, ["precip_mm", "t2m", "rh2m", "ws10m"]] *= 3
    changed = build_features(future, compute_climatology(future, ref_start, ref_end),
                             ref_start, ref_end)

    cols = ["city", "date", *FEATURE_COLUMNS]
    a = base.loc[base["date"] <= cutoff, cols].reset_index(drop=True)
    b = changed.loc[changed["date"] <= cutoff, cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_climatology_uses_reference_years_only(monthly):
    clim = compute_climatology(monthly, 1981, 2015)
    later = monthly.copy()
    later.loc[later["year"] > 2015, "precip_mm"] += 1000
    pd.testing.assert_frame_equal(clim, compute_climatology(later, 1981, 2015))


def test_temporal_split_is_ordered_and_disjoint(monthly):
    rows = modelling_rows(_features(monthly))
    train, val, test = temporal_split(rows, train_end=2015, val_end=2019)
    assert train["target_date"].max() < val["target_date"].min()
    assert val["target_date"].max() < test["target_date"].min()
    assert len(train) + len(val) + len(test) == len(rows)
    assert not rows[FEATURE_COLUMNS].isna().any().any()


def test_drought_label_matches_spi(monthly):
    feat = modelling_rows(_features(monthly))
    assert ((feat["target_spi3"] <= -1.0) == (feat["target_drought"] == 1)).all()


def test_ensemble_drought_prob_falls_as_known_rain_rises():
    rng = np.random.default_rng(3)
    idx = pd.date_range("1981-01", "2020-12", freq="MS")
    precip = pd.Series(rng.gamma(2.0, 50.0, len(idx)), index=idx)
    base = ensemble_drought_prob(precip, 1981, 2015, threshold=-1.0)
    assert np.nanmin(base) >= 0 and np.nanmax(base) <= 1

    wetter = precip.copy()
    wetter.iloc[-2:] *= 4  # two very wet known months
    dryer = precip.copy()
    dryer.iloc[-2:] = 0.0  # two completely dry known months
    p_wet = ensemble_drought_prob(wetter, 1981, 2015, -1.0)[-1]
    p_dry = ensemble_drought_prob(dryer, 1981, 2015, -1.0)[-1]
    assert p_dry > base[-1] > p_wet


def test_climate_indices_are_aligned_to_publication():
    from climrisk.indices import parse_dmi, parse_oni

    oni = parse_oni(
        " SEAS  YR   TOTAL   ANOM\n  JAS 2026  29.12   2.16\n  NDJ 2025  26.0  -0.50\n"
    )
    # A season is keyed by its last month; NDJ 2025 ends in January 2026.
    assert oni[pd.Timestamp("2026-09-01")] == 2.16
    assert oni[pd.Timestamp("2026-01-01")] == -0.5

    dmi = parse_dmi(
        " 2025 2026\n2026 0.1 0.2 0.3 0.4 0.5 -9999 -9999 -9999 -9999 -9999 -9999 -9999\n"
    )
    assert len(dmi) == 5 and dmi[pd.Timestamp("2026-05-01")] == 0.5


def test_index_features_are_optional(monthly):
    from climrisk.features import INDEX_FEATURES, feature_columns

    feat = _features(monthly)
    assert feature_columns(feat, use_indices=True) == FEATURE_COLUMNS  # none present
    idx = pd.DataFrame({"date": monthly["date"].unique()})
    idx["oni"], idx["dmi_lag4"] = 0.5, -0.1
    with_idx = build_features(monthly, compute_climatology(monthly), indices=idx)
    assert feature_columns(with_idx, use_indices=True) == FEATURE_COLUMNS + INDEX_FEATURES
    assert feature_columns(with_idx, use_indices=False) == FEATURE_COLUMNS
