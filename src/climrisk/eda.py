"""Exploratory analysis: figures plus a short generated markdown summary."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

from . import config, plots
from .features import FEATURE_COLUMNS

MONTH_LABELS = list("JFMAMJJASOND")


def _trend_table(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Linear trend in annual rainfall per city (complete years only)."""
    counts = clean_df.groupby(["city", "year"])["precip_mm"].count()
    full_years = counts[counts == 12].index
    annual = clean_df.groupby(["city", "year"])["precip_mm"].sum().loc[full_years].reset_index()
    rows = []
    for city, g in annual.groupby("city"):
        fit = stats.linregress(g["year"], g["precip_mm"])
        rows.append(
            {
                "city": city,
                "mean_annual_mm": g["precip_mm"].mean(),
                "trend_mm_per_decade": fit.slope * 10,
                "p_value": fit.pvalue,
            }
        )
    return pd.DataFrame(rows).sort_values("mean_annual_mm", ascending=False)


def run_eda(
    clean_df: pd.DataFrame,
    feat: pd.DataFrame,
    clean_report: dict,
    figures_dir: Path = config.FIGURES_DIR,
    reports_dir: Path = config.REPORTS_DIR,
) -> dict:
    plots.apply_style()
    cities = [c.name for c in config.CITIES if c.name in set(clean_df["city"])]

    # 1. Seasonal cycle per city
    clim = clean_df.groupby(["city", "month"])["precip_mm"].mean().unstack()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, city in enumerate(cities):
        ax.plot(range(1, 13), clim.loc[city], color=plots.SERIES[i], label=city)
    ax.set_xticks(range(1, 13), MONTH_LABELS)
    ax.set_ylabel("Mean monthly rainfall (mm)")
    share = clim[[6, 7, 8, 9]].sum(axis=1).sum() / clim.sum(axis=1).sum()
    ax.set_title(f"Monsoon dominates: {share:.0%} of annual rain falls June-September")
    ax.legend(ncol=4, fontsize=8, loc="upper left")
    plots.save(fig, figures_dir / "eda_seasonal_cycle.png")

    # 2. Annual totals over time
    counts = clean_df.groupby(["city", "year"])["precip_mm"].count()
    annual = clean_df.groupby(["city", "year"])["precip_mm"].sum()[counts == 12].unstack(0)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, city in enumerate(cities):
        ax.plot(annual.index, annual[city], color=plots.SERIES[i], label=city, linewidth=1.5)
    ax.set_ylabel("Annual rainfall (mm)")
    ax.set_title("Annual rainfall by division, 1981 onward")
    ax.legend(ncol=4, fontsize=8, loc="upper left")
    plots.save(fig, figures_dir / "eda_annual_totals.png")

    # 3. SPI-3 heat strip for every city
    spi = feat.pivot(index="city", columns="date", values="spi3").loc[cities]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    im = ax.imshow(spi.to_numpy(), aspect="auto", cmap=plots.DRY_WET, vmin=-2.5, vmax=2.5,
                   interpolation="nearest")
    ax.set_yticks(range(len(cities)), cities)
    years, months = spi.columns.year, spi.columns.month
    ticks = [i for i in range(len(years)) if months[i] == 1 and years[i] % 5 == 0]
    ax.set_xticks(ticks, [str(years[i]) for i in ticks])
    ax.grid(False)
    ax.set_title("SPI-3 through time (red = dry, blue = wet)")
    fig.colorbar(im, ax=ax, label="SPI-3", fraction=0.025, pad=0.01)
    plots.save(fig, figures_dir / "eda_spi3_heatmap.png")

    # 4. Feature correlation with next month's anomaly
    usable = feat.dropna(subset=FEATURE_COLUMNS + ["target_anom_z", "target_spi3"])
    corr = (
        usable[FEATURE_COLUMNS]
        .corrwith(usable["target_anom_z"], method="spearman")
        .sort_values()
    )
    fig, ax = plt.subplots(figsize=(7, 5.2))
    colors = [plots.ORANGE if v < 0 else plots.BLUE for v in corr]
    ax.barh(corr.index, corr.values, color=colors, height=0.6)
    ax.axvline(0, color=plots.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xlabel("Spearman correlation with next month's standardized anomaly")
    ax.set_title("Which issue-month signals track next month's rainfall?")
    plots.save(fig, figures_dir / "eda_feature_correlation.png")

    # 5. Distribution of monthly rainfall by season (skewness)
    seasons = clean_df["month"].map(config.SEASONS)
    order = ["Winter (DJF)", "Pre-monsoon (MAM)", "Monsoon (JJAS)", "Post-monsoon (ON)"]
    fig, ax = plt.subplots(figsize=(8, 4))
    data = [clean_df.loc[seasons == s, "precip_mm"] for s in order]
    bp = ax.boxplot(data, tick_labels=order, patch_artist=True, widths=0.5,
                    medianprops={"color": plots.TEXT}, flierprops={"markersize": 3,
                    "markerfacecolor": plots.NEUTRAL, "markeredgecolor": plots.NEUTRAL})
    for patch in bp["boxes"]:
        patch.set_facecolor(plots.BAND)
        patch.set_edgecolor(plots.BLUE)
    ax.set_ylabel("Monthly rainfall (mm)")
    ax.set_title("Rainfall is skewed and its spread scales with the season")
    plots.save(fig, figures_dir / "eda_seasonal_distribution.png")

    trend = _trend_table(clean_df)
    corr_abs = corr.abs().sort_values(ascending=False)
    summary = {
        "n_rows": int(len(clean_df)),
        "cities": cities,
        "period": [str(clean_df["date"].min().date()), str(clean_df["date"].max().date())],
        "monsoon_share": float(share),
        "top_correlations": {k: float(corr[k]) for k in corr_abs.index[:5]},
        "drought_rate_ref": float(
            (feat.loc[feat["year"].between(config.REF_START, config.REF_END), "spi3"]
             <= config.DROUGHT_THRESHOLD).mean()
        ),
    }

    md = [
        "# Exploratory data analysis",
        "",
        "_Generated by `python -m climrisk eda`. Do not edit by hand._",
        "",
        f"- Rows: {summary['n_rows']:,} city-months, {summary['period'][0]} to "
        f"{summary['period'][1]}, {len(cities)} locations.",
        f"- Share of annual rainfall falling June-September: {summary['monsoon_share']:.0%}.",
        f"- Fraction of reference-period months with SPI-3 <= {config.DROUGHT_THRESHOLD}: "
        f"{summary['drought_rate_ref']:.1%} (theory: ~15.9%).",
        "",
        "## Cleaning report",
        "",
        "```",
        *[f"{k}: {v}" for k, v in clean_report.items()],
        "```",
        "",
        "## Annual rainfall trend (linear, complete years)",
        "",
        "| City | Mean annual (mm) | Trend (mm/decade) | p-value |",
        "|---|---:|---:|---:|",
        *[
            f"| {r.city} | {r.mean_annual_mm:,.0f} | {r.trend_mm_per_decade:+.0f} | "
            f"{r.p_value:.2f} |"
            for r in trend.itertuples()
        ],
        "",
        "## Figures",
        "",
        "![Seasonal cycle](figures/eda_seasonal_cycle.png)",
        "![Annual totals](figures/eda_annual_totals.png)",
        "![Seasonal distribution](figures/eda_seasonal_distribution.png)",
        "![SPI-3 heatmap](figures/eda_spi3_heatmap.png)",
        "![Feature correlation](figures/eda_feature_correlation.png)",
        "",
    ]
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "eda.md").write_text("\n".join(md), encoding="utf-8")
    summary["trend"] = trend.round(3).to_dict(orient="records")
    return summary

