import numpy as np
import pandas as pd

from climrisk.features import build_features, compute_climatology
from climrisk.heat import build_heat_features, evaluate_heat, predict_heat, train_heat

GRID = {"learning_rate": [0.1], "max_depth": [2], "max_iter": [50]}


def _heat(monthly):
    return build_heat_features(build_features(monthly, compute_climatology(monthly)))


def test_recent_baseline_uses_only_earlier_years(monthly):
    base = _heat(monthly)
    changed = monthly.copy()
    changed.loc[changed["year"] == 2022, "heatwave_days"] += 20
    after = _heat(changed)
    key = (base["city"] == "Alpha") & (base["year"] == 2022)
    # The 2022 rows' own recent-decade baseline must ignore 2022 itself...
    np.testing.assert_allclose(base.loc[key, "hw_recent"], after.loc[key, "hw_recent"])
    # ...while 2023 does see it.
    key23 = (base["city"] == "Alpha") & (base["year"] == 2023) & (base["month"] == 5)
    before_23 = base.loc[key23, "hw_recent"].to_numpy()
    assert (after.loc[key23, "hw_recent"].to_numpy() > before_23).all()


def test_target_is_next_month(monthly):
    d = _heat(monthly)
    a = d[d["city"] == "Alpha"].reset_index(drop=True)
    np.testing.assert_allclose(a["target_hw_days"].iloc[:-1], a["heatwave_days"].iloc[1:])
    # The live row still has its baselines.
    assert not np.isnan(a["hw_normal_next"].iloc[-1]) and np.isnan(a["target_hw_days"].iloc[-1])


def test_train_and_evaluate(monthly):
    d = _heat(monthly)
    bundle = train_heat(d, grid=GRID)
    m = evaluate_heat(bundle, d)
    assert m["n_test"] > 0 and set(m["mae_days"]) == {"normal", "recent", "model"}
    live = d[d["date"] == d["date"].max()]
    pred = predict_heat(bundle, live)
    assert ((pred >= 0) & (pred <= 31)).all()
    assert isinstance(m["skill_vs_recent_95ci"], list) and len(pd.Series(pred)) == 2
