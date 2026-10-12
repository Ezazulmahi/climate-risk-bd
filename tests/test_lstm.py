import numpy as np
import pytest

from climrisk.features import build_features, compute_climatology
from climrisk.lstm import SEQ_LEN, make_sequences

torch = pytest.importorskip("torch")


def test_sequences_end_at_the_issue_month(monthly):
    feat = build_features(monthly, compute_climatology(monthly))
    data = make_sequences(feat)
    assert data["seq"].shape[1:] == (SEQ_LEN, 6)
    assert len(data["seq"]) == len(data["static"]) == len(data["meta"])
    # The last step of the first Alpha sequence is that row's own (issue-month) anomaly.
    alpha = feat[feat["city"] == "Alpha"].sort_values("date").reset_index(drop=True)
    first = data["meta"].iloc[0]
    issue = alpha[alpha["target_date"] == first["target_date"]].iloc[0]
    assert np.isclose(data["seq"][0, -1, 0], issue["precip_anom_z"], equal_nan=True)


def test_experiment_runs(monthly, tmp_path):
    from climrisk.lstm import run_experiment

    feat = build_features(monthly, compute_climatology(monthly))
    out = run_experiment(feat, epochs=2, seeds=(0,), reports_dir=tmp_path)
    assert (tmp_path / "experiment_lstm.md").exists()
    assert np.isfinite(out["rainfall_skill_vs_climatology"]["mean"])
