"""District drought monitor: aggregation, categories, outlook scoring, API."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from climrisk import api, db
from climrisk.districts import (
    build_district_table,
    category,
    district_rainfall,
    evaluate_outlook,
    simplified_geojson,
)
from climrisk.sync import sync_districts


def _square(x0, y0, size):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]
    ]]}


@pytest.fixture(scope="module")
def tiny():
    """A 10x10 grid of 0.1° cells with two square districts and 45 years of rain."""
    rng = np.random.default_rng(5)
    months = pd.date_range("1981-01", "2025-12", freq="MS")
    lats = np.arange(23.05, 24.05, 0.1)
    lons = np.arange(90.05, 91.05, 0.1)
    data = rng.gamma(2.0, 50.0, (len(months), len(lats), len(lons)))
    data[:, :, 5:] *= 2  # the east is twice as wet
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"shapeName": name}, "geometry": _square(x, 23.0, 0.5)}
        for name, x in (("West", 90.0), ("East", 90.5))
    ]}
    rain, meta = district_rainfall(geo, (months, lats, lons, data))
    return {"geo": geo, "rain": rain, "meta": meta, "data": data}


@pytest.mark.parametrize("value, code", [
    (-2.5, "D4"), (-1.8, "D3"), (-1.4, "D2"), (-1.0, "D1"), (-0.6, "D0"), (0.3, None),
    (float("nan"), None),
])
def test_category_uses_us_drought_monitor_breakpoints(value, code):
    assert category(value) == code


def test_district_rainfall_is_the_mean_of_cells_inside(tiny):
    rain, meta = tiny["rain"], tiny["meta"]
    assert {m["name"]: m["cells"] for m in meta} == {"West": 25, "East": 25}
    west = rain[rain["district"] == "West"].set_index("date")["precip_mm"]
    np.testing.assert_allclose(west.iloc[0], tiny["data"][0, :5, :5].mean())
    east = rain[rain["district"] == "East"]["precip_mm"].mean()
    assert east == pytest.approx(2 * rain[rain["district"] == "West"]["precip_mm"].mean(), rel=0.1)


def test_table_and_outlook_evaluation(tiny):
    table = build_district_table(tiny["rain"])
    assert {"spi3", "category", "drought_prob_next", "normal_mm"} <= set(table.columns)
    assert table["drought_prob_next"].dropna().between(0, 1).all()
    ev = evaluate_outlook(table)
    assert ev["n_test"] == 2 * 72  # 2020-01..2025-12 target months
    assert ev["brier_skill"] > 0  # two known months beat the base rate


def test_simplified_geojson_keeps_every_district(tiny):
    out = simplified_geojson(tiny["geo"], tiny["meta"])
    assert [f["properties"]["name"] for f in out["features"]] == ["West", "East"]


def test_district_api(tiny, tmp_path):
    engine = db.get_engine(f"sqlite:///{tmp_path / 'd.db'}")
    table = build_district_table(tiny["rain"])
    geo = simplified_geojson(tiny["geo"], tiny["meta"])
    counts = sync_districts(engine, table, geo, {"district_outlook_eval": evaluate_outlook(table)})
    assert counts == {"districts": 2, "district_months": len(table)}

    def conn():
        with engine.connect() as c:
            yield c

    api.app.dependency_overrides[api.get_conn] = conn
    try:
        client = TestClient(api.app)
        body = client.get("/districts").json()
        assert body["month"] == "2025-12" and len(body["districts"]) == 2
        spis = [d["spi3"] for d in body["districts"]]
        assert spis == sorted(spis)  # driest first
        assert len(client.get("/districts/geojson").json()["features"]) == 2
        assert client.get("/districts/evaluation").json()["n_test"] == 144
        hist = client.get("/districts/west", params={"start": "2025-01"}).json()
        assert len(hist) == 12 and hist[0]["district"] == "West"
        assert client.get("/districts/atlantis").status_code == 404
        assert client.get("/districts", params={"month": "1900-01"}).status_code == 404
    finally:
        api.app.dependency_overrides.clear()
