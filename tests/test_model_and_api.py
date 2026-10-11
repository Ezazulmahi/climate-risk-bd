"""Train on synthetic data, then exercise evaluation, the predictor and the API."""

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from climrisk import api
from climrisk.evaluate import evaluate
from climrisk.features import build_features, compute_climatology
from climrisk.train import predict_regression, train

SMALL_GRID = {"learning_rate": [0.1], "max_depth": [2], "max_iter": [50]}


@pytest.fixture(scope="module")
def artefacts(monthly, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("model")
    feat = build_features(monthly, compute_climatology(monthly))
    bundle = train(feat, grid=SMALL_GRID)
    metrics = evaluate(bundle, feat, figures_dir=tmp / "fig", reports_dir=tmp, make_figures=False)
    joblib.dump(bundle, tmp / "bundle.joblib")
    feat.to_csv(tmp / "features.csv", index=False)
    return {"tmp": tmp, "bundle": bundle, "feat": feat, "metrics": metrics}


def test_bundle_contents(artefacts):
    b = artefacts["bundle"]
    assert set(b["reg_models"]) == {"ridge", "hgb"}
    assert set(b["clf_models"]) == {"logistic", "hgb"}
    assert 0 < b["clf_base_rate"] < 0.5
    assert np.isfinite(b["reg_interval"]["margin"])


def test_metrics_are_sane(artefacts):
    m = artefacts["metrics"]
    assert m["regression"]["climatology"]["mae_skill_vs_climatology"] == pytest.approx(0)
    assert 0.6 <= m["interval"]["empirical_coverage"] <= 0.98
    for model in ("logistic", "hgb"):
        assert 0.5 <= m["classification"][model]["roc_auc"] <= 1
    assert (artefacts["tmp"] / "evaluation.md").exists()


def test_intervals_contain_point_forecast(artefacts):
    feat = artefacts["feat"].dropna(subset=artefacts["bundle"]["feature_columns"])
    out = predict_regression(artefacts["bundle"], feat.tail(50))
    assert (out["precip_lo_mm"] <= out["precip_mm"] + 1e-9).all()
    assert (out["precip_mm"] <= out["precip_hi_mm"] + 1e-9).all()
    assert (out["precip_lo_mm"] >= 0).all()


@pytest.fixture(scope="module")
def client(artefacts, monkeypatch_module):
    tmp = artefacts["tmp"]
    monkeypatch_module.setenv("CLIMRISK_BUNDLE", str(tmp / "bundle.joblib"))
    monkeypatch_module.setenv("CLIMRISK_FEATURES", str(tmp / "features.csv"))
    monkeypatch_module.setenv("CLIMRISK_METRICS", str(tmp / "metrics.json"))
    api.get_predictor.cache_clear()
    yield TestClient(api.app)
    api.get_predictor.cache_clear()


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_health_and_cities(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/cities").json() == ["Alpha", "Beta"]


def test_predict_past_month_includes_observation(client):
    r = client.get("/predict", params={"city": "alpha", "month": "2022-07"})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Alpha" and body["issued_with_data_through"] == "2022-06"
    lo, hi = body["rainfall"]["interval_80_mm"]
    assert lo <= body["rainfall"]["expected_mm"] <= hi
    assert 0 <= body["drought"]["probability"] <= 1
    assert body["observed"] is not None and not body["is_forecast"]


def test_predict_live_month_is_a_forecast(client):
    body = client.get("/predict", params={"city": "Beta", "month": "2025-01"}).json()
    assert body["is_forecast"] and body["observed"] is None


def test_latest_forecasts(client):
    out = client.get("/forecast/latest").json()
    assert [o["target_month"] for o in out] == ["2025-01", "2025-01"]


@pytest.mark.parametrize(
    "params, status",
    [
        ({"city": "Atlantis", "month": "2022-07"}, 404),
        ({"city": "Alpha", "month": "2022-13"}, 422),
        ({"city": "Alpha", "month": "July"}, 422),
        ({"city": "Alpha", "month": "1950-01"}, 400),
        ({"city": "Alpha", "month": "2030-01"}, 400),
    ],
)
def test_predict_errors(client, params, status):
    assert client.get("/predict", params=params).status_code == status


def test_history(client):
    rows = client.get("/history", params={"city": "Alpha", "start": "2020-01",
                                          "end": "2020-12"}).json()
    assert len(rows) == 12
    assert {"date", "precip_mm", "spi3"} <= set(rows[0])
    assert all(np.isfinite(r["precip_mm"]) for r in rows)


def test_metrics_endpoint(client):
    assert "regression" in client.get("/metrics").json()
