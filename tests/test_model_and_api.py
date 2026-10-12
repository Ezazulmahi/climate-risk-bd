"""Train on synthetic data, publish to a SQLite database, then exercise the API."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from climrisk import api, db
from climrisk.evaluate import evaluate
from climrisk.features import build_features, compute_climatology
from climrisk.predict import Predictor
from climrisk.sync import model_version, sync
from climrisk.train import predict_regression, train

SMALL_GRID = {"learning_rate": [0.1], "max_depth": [2], "max_iter": [50]}


@pytest.fixture(scope="module")
def artefacts(monthly, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("model")
    feat = build_features(monthly, compute_climatology(monthly))
    bundle = train(feat, grid=SMALL_GRID)
    metrics = evaluate(bundle, feat, figures_dir=tmp / "fig", reports_dir=tmp, make_figures=False)
    return {"tmp": tmp, "bundle": bundle, "feat": feat, "metrics": metrics}


@pytest.fixture(scope="module")
def engine(artefacts):
    eng = db.get_engine(f"sqlite:///{artefacts['tmp'] / 'test.db'}")
    sync(eng, artefacts["feat"], artefacts["bundle"], artefacts["metrics"])
    return eng


@pytest.fixture(scope="module")
def client(engine):
    api.app.dependency_overrides[api.get_conn] = lambda: (yield from _conn(engine))
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def _conn(engine):
    with engine.connect() as conn:
        yield conn


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
    for model in ("ensemble", "logistic", "hgb"):
        assert 0.5 <= m["classification"][model]["roc_auc"] <= 1
    assert (artefacts["tmp"] / "evaluation.md").exists()


def test_intervals_contain_point_forecast(artefacts):
    feat = artefacts["feat"].dropna(subset=artefacts["bundle"]["feature_columns"])
    out = predict_regression(artefacts["bundle"], feat.tail(50))
    assert (out["precip_lo_mm"] <= out["precip_mm"] + 1e-9).all()
    assert (out["precip_mm"] <= out["precip_hi_mm"] + 1e-9).all()
    assert (out["precip_lo_mm"] >= 0).all()


def test_model_version_is_deterministic(artefacts):
    assert model_version(artefacts["bundle"]) == model_version(artefacts["bundle"])


def test_sync_is_idempotent(engine, artefacts):
    again = sync(engine, artefacts["feat"], artefacts["bundle"], artefacts["metrics"])
    assert again["forecasts"] > 0 and again["cities"] == 2


def test_stored_forecasts_match_predictor(client, artefacts, tmp_path):
    """The database must serve exactly what the model computes."""
    import joblib

    joblib.dump(artefacts["bundle"], tmp_path / "b.joblib")
    artefacts["feat"].to_csv(tmp_path / "f.csv", index=False)
    direct = Predictor(tmp_path / "b.joblib", tmp_path / "f.csv", tmp_path / "none.json")
    expected = direct.predict("Alpha", "2022-07")
    served = client.get("/forecast", params={"city": "Alpha", "month": "2022-07"}).json()
    assert served["rainfall"]["expected_mm"] == pytest.approx(
        expected["rainfall"]["expected_mm"], abs=0.06
    )
    assert served["drought"]["probability"] == pytest.approx(
        expected["drought"]["probability"], abs=1e-3
    )


def test_health_and_cities(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["model_version"].startswith("v2015-")
    assert [c["name"] for c in client.get("/cities").json()] == ["Alpha", "Beta"]


def test_forecast_past_month_includes_observation(client):
    r = client.get("/forecast", params={"city": "alpha", "month": "2022-07"})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Alpha" and body["issued_through"] == "2022-06"
    assert body["split"] == "test"
    lo, hi = body["rainfall"]["interval_80_mm"]
    assert lo <= body["rainfall"]["expected_mm"] <= hi
    assert 0 <= body["drought"]["probability"] <= 1
    assert body["observed"] is not None


def test_latest_forecasts_are_live(client):
    out = client.get("/forecasts/latest").json()
    assert [(o["city"], o["target_month"], o["split"]) for o in out] == [
        ("Alpha", "2025-01", "live"), ("Beta", "2025-01", "live")
    ]
    assert all(o["observed"] is None for o in out)


def test_forecast_series(client):
    rows = client.get("/forecasts", params={"city": "Beta", "start": "2020-01",
                                            "end": "2020-12"}).json()
    assert len(rows) == 12 and {r["split"] for r in rows} == {"test"}
    assert [r["target_month"] for r in rows] == sorted(r["target_month"] for r in rows)


@pytest.mark.parametrize(
    "path, params, status",
    [
        ("/forecast", {"city": "Atlantis", "month": "2022-07"}, 404),
        ("/forecast", {"city": "Alpha", "month": "2022-13"}, 422),
        ("/forecast", {"city": "Alpha", "month": "July"}, 422),
        ("/forecast", {"city": "Alpha", "month": "1990-01"}, 404),  # training years: none stored
        ("/history", {"city": "Alpha", "start": "bad"}, 422),
        ("/verification", {"split": "train"}, 422),
    ],
)
def test_errors(client, path, params, status):
    assert client.get(path, params=params).status_code == status


def test_history(client):
    rows = client.get("/history", params={"city": "Alpha", "start": "2020-01",
                                          "end": "2020-12"}).json()
    assert len(rows) == 12
    assert {"month", "precip_mm", "normal_mm", "spi3"} <= set(rows[0])


def test_verification_matches_offline_evaluation(client, artefacts):
    v = client.get("/verification").json()
    m = artefacts["metrics"]
    assert v["n"] == m["n_test"]
    assert v["interval_coverage"] == pytest.approx(m["interval"]["empirical_coverage"], abs=0.01)
    assert v["rainfall_mae_mm"] == pytest.approx(m["regression"]["hgb"]["mae_mm"], rel=0.02)


def test_metrics_endpoint(client):
    body = client.get("/metrics").json()
    assert "regression" in body and body["model_version"].startswith("v2015-")


def test_issued_forecasts_are_frozen(engine, artefacts, client):
    """A retrained model must not rewrite a forecast that was already published."""
    first = client.get("/issued", params={"city": "Alpha"}).json()
    assert [r["target_month"] for r in first] == ["2025-01"]

    retrained = dict(artefacts["bundle"])
    retrained["clf_base_rate"] = 0.42  # different model -> different version and numbers
    retrained["validation"] = {**retrained["validation"], "note": "retrained"}
    sync(engine, artefacts["feat"], retrained, artefacts["metrics"])

    after = client.get("/issued", params={"city": "Alpha"}).json()
    assert after == first
    live = client.get("/forecast", params={"city": "Alpha", "month": "2025-01"}).json()
    assert live["drought"]["usual_probability"] == 0.42  # the live view did move on


def test_explanations_and_document_publishing(engine, artefacts, client):
    from climrisk.explain import explain_drought
    from climrisk.sync import publish_documents

    expl = explain_drought(artefacts["bundle"], artefacts["feat"])
    assert set(expl) == {"Alpha", "Beta"}
    head, *drivers = expl["Alpha"]
    assert 0 <= head["probability"] <= 1 and 1 <= len(drivers) <= 4
    effects = [abs(d["effect"]) for d in drivers]
    assert effects == sorted(effects, reverse=True)

    assert publish_documents(engine, {"drought_explanations": expl}) == 1
    body = client.get("/explain", params={"city": "alpha"}).json()
    assert body["city"] == "Alpha" and body["drivers"][0]["label"]
    assert client.get("/explain", params={"city": "Atlantis"}).status_code == 404


def test_alerts_feed_is_valid_rss(client):
    import xml.dom.minidom

    r = client.get("/alerts.rss")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/rss+xml")
    doc = xml.dom.minidom.parseString(r.text)
    assert doc.getElementsByTagName("channel")


def test_csv_exports(client):
    r = client.get("/export/forecasts.csv", params={"city": "Beta"})
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("model_version,city,target_month")
    assert all(",Beta," in line for line in lines[1:])
    assert "attachment" in r.headers["content-disposition"]
