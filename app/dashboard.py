"""Streamlit dashboard: `streamlit run app/dashboard.py`."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from climrisk import config
from climrisk.predict import Predictor

BLUE, GRAY, BAND = "#2a78d6", "#a3a29c", "#b7d3f6"
RISK_STYLE = {"low": ("Low", "#1baf7a"), "elevated": ("Elevated", "#eda100"),
              "high": ("High", "#e34948")}

st.set_page_config(page_title="Bangladesh Climate Risk", layout="wide")


@st.cache_resource
def load() -> Predictor:
    return Predictor()


try:
    pred = load()
except FileNotFoundError:
    st.error("Model not found. Run `python -m climrisk all` first.")
    st.stop()

lo, hi = pred.month_range()
st.title("Bangladesh rainfall and drought outlook")
st.caption(
    "One-month-ahead forecasts from a gradient-boosting model trained on ERA5 reanalysis "
    f"({config.START_YEAR}–{config.TRAIN_END}). A portfolio demo, not an official forecast. "
    "For decisions, use the Bangladesh Meteorological Department."
)

# ---------- Controls ----------
c1, c2 = st.columns([1, 1])
city = c1.selectbox("Division", pred.cities, index=0)
months = pd.date_range(lo, hi, freq="MS")[::-1]
month = c2.selectbox("Target month", months, format_func=lambda d: d.strftime("%B %Y"))

res = pred.predict(city, month)
rain, drought = res["rainfall"], res["drought"]

# ---------- Headline ----------
label = "Forecast" if res["is_forecast"] else "Hindcast (already observed)"
st.subheader(f"{city}, {month:%B %Y} · {label}")
st.caption(f"Issued using data through {res['issued_with_data_through']}.")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Expected rainfall", f"{rain['expected_mm']:.0f} mm",
          f"{rain['anomaly_mm']:+.0f} mm vs normal", delta_color="off")
k2.metric("80% range", f"{rain['interval_80_mm'][0]:.0f}–{rain['interval_80_mm'][1]:.0f} mm")
k3.metric("Normal for this month", f"{rain['climatology_mm']:.0f} mm")
name, colour = RISK_STYLE[drought["risk_level"]]
k4.metric("Drought probability", f"{drought['probability']:.0%}",
          f"usually {drought['usual_probability']:.0%}", delta_color="off")
st.markdown(
    f"Drought risk: <span style='color:{colour};font-weight:600'>● {name}</span> "
    f"&nbsp;·&nbsp; current SPI-3 {res['current_conditions']['spi3']:+.2f} "
    f"({res['current_conditions']['spi3_category']})",
    unsafe_allow_html=True,
)
if res["observed"]:
    o = res["observed"]
    inside = rain["interval_80_mm"][0] <= o["precip_mm"] <= rain["interval_80_mm"][1]
    st.info(
        f"Observed: **{o['precip_mm']:.0f} mm** (SPI-3 {o['spi3']:+.2f}, {o['spi3_category']}). "
        f"{'Inside' if inside else 'Outside'} the 80% range."
    )

# ---------- History ----------
st.markdown("#### Recent rainfall vs normal")
hist = pd.DataFrame(pred.history(city, start=(month - pd.DateOffset(months=36)).strftime("%Y-%m")))
hist["date"] = pd.to_datetime(hist["date"])
hist = hist.set_index("date")[["precip_mm", "clim_precip_mean"]].rename(
    columns={"precip_mm": "Observed (mm)", "clim_precip_mean": "Normal (mm)"}
)
st.line_chart(hist, color=[BLUE, GRAY], height=260)

st.markdown("#### SPI-3 (below −1 = drought)")
spi = pd.DataFrame(pred.history(city, start=(month - pd.DateOffset(months=120)).strftime("%Y-%m")))
spi["date"] = pd.to_datetime(spi["date"])
st.bar_chart(spi.set_index("date")[["spi3"]], color=BLUE, height=200)

# ---------- All divisions ----------
st.markdown("#### Latest outlook for every division")
rows = []
for r in pred.latest_forecasts():
    rows.append({
        "Division": r["city"],
        "Month": r["target_month"],
        "Expected (mm)": r["rainfall"]["expected_mm"],
        "80% range (mm)": f"{r['rainfall']['interval_80_mm'][0]:.0f}–"
                          f"{r['rainfall']['interval_80_mm'][1]:.0f}",
        "Normal (mm)": r["rainfall"]["climatology_mm"],
        "Drought prob.": f"{r['drought']['probability']:.0%}",
        "Risk": RISK_STYLE[r["drought"]["risk_level"]][0],
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------- Model quality ----------
if pred.metrics:
    with st.expander("How good is the model? (held-out test years)"):
        m = pred.metrics
        reg = pd.DataFrame(m["regression"]).T[["mae_mm", "mae_skill_vs_climatology"]]
        reg.columns = ["MAE (mm)", "Skill vs normal"]
        st.dataframe(reg.style.format({"MAE (mm)": "{:.1f}", "Skill vs normal": "{:+.1%}"}))
        clf = pd.DataFrame(m["classification"]).T[["roc_auc", "brier", "precision", "recall"]]
        st.dataframe(clf.style.format("{:.3f}"))
        st.caption(
            f"Test period {m['test_period'][0][:7]} to {m['test_period'][1][:7]}. "
            f"80% interval coverage: {m['interval']['empirical_coverage']:.0%}. "
            "See reports/evaluation.md for the full error analysis."
        )
