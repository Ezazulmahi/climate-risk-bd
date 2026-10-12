"""Experiment: does a sequence model (LSTM) beat the tabular models?

Optional: needs PyTorch (`pip install -e ".[experiments]"`). Not used in
production; it answers the question "did you try deep learning?".

The LSTM reads the last 12 months (rainfall anomaly, SPI-1, temperature and
humidity anomalies, season) for one city, adds static context (target month,
location, next month's normal, the ensemble drought probability), and has two
heads: next month's standardized rainfall anomaly (L1 loss) and drought
(binary cross-entropy). Same splits as the main models; early stopping on the
validation years; scored on the test years against the same baselines.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .features import CLF_TARGET, REG_TARGET

log = logging.getLogger(__name__)

SEQ_LEN = 12
SEQ_FEATURES = ["precip_anom_z", "spi1", "t2m_anom", "rh2m_anom"]
STATIC_FEATURES = ["target_month_sin", "target_month_cos", "lat", "lon",
                   "clim_precip_mean_next", "drought_prob_ens"]


def make_sequences(feat: pd.DataFrame) -> dict[str, np.ndarray | pd.DataFrame]:
    seqs, statics, meta = [], [], []
    for _, g in feat.sort_values(["city", "date"]).groupby("city", sort=False):
        g = g.reset_index(drop=True)
        month_angle = 2 * np.pi * g["date"].dt.month / 12
        seq_table = np.column_stack(
            [g[c].to_numpy(float) for c in SEQ_FEATURES]
            + [np.sin(month_angle), np.cos(month_angle)]
        )
        for i in range(SEQ_LEN - 1, len(g)):
            row = g.iloc[i]
            if row[[REG_TARGET, CLF_TARGET, "drought_prob_ens"]].isna().any():
                continue
            seqs.append(seq_table[i - SEQ_LEN + 1: i + 1])
            statics.append(row[STATIC_FEATURES].to_numpy(float))
            meta.append(row[["city", "target_date", REG_TARGET, CLF_TARGET, "target_anom_mm",
                             "clim_precip_std_next", "drought_prob_ens"]])
    return {"seq": np.stack(seqs), "static": np.stack(statics),
            "meta": pd.DataFrame(meta).reset_index(drop=True)}


def _run_once(feat: pd.DataFrame, epochs: int, seed: int) -> dict:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    np.random.seed(seed)
    data = make_sequences(feat)
    meta = data["meta"]
    year = pd.to_datetime(meta["target_date"]).dt.year
    split = {
        "train": (year <= config.TRAIN_END).to_numpy(),
        "val": ((year > config.TRAIN_END) & (year <= config.VAL_END)).to_numpy(),
        "test": (year > config.VAL_END).to_numpy(),
    }

    # Standardize with training statistics only; missing values become 0 (= the mean).
    seq, static = data["seq"].copy(), data["static"].copy()
    mu_s = np.nanmean(seq[split["train"]], axis=(0, 1))
    sd_s = np.nanstd(seq[split["train"]], axis=(0, 1)) + 1e-6
    mu_t = np.nanmean(static[split["train"]], axis=0)
    sd_t = np.nanstd(static[split["train"]], axis=0) + 1e-6
    seq = np.nan_to_num((seq - mu_s) / sd_s)
    static = np.nan_to_num((static - mu_t) / sd_t)
    y_reg = meta[REG_TARGET].to_numpy(float)
    y_clf = meta[CLF_TARGET].to_numpy(float)

    def tensors(mask):
        return (torch.tensor(seq[mask], dtype=torch.float32),
                torch.tensor(static[mask], dtype=torch.float32),
                torch.tensor(y_reg[mask], dtype=torch.float32),
                torch.tensor(y_clf[mask], dtype=torch.float32))

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(seq.shape[2], 32, batch_first=True)
            self.body = nn.Sequential(nn.Linear(32 + static.shape[1], 32), nn.ReLU(),
                                      nn.Dropout(0.2))
            self.reg = nn.Linear(32, 1)
            self.clf = nn.Linear(32, 1)

        def forward(self, s, t):
            _, (h, _) = self.lstm(s)
            z = self.body(torch.cat([h[-1], t], dim=1))
            return self.reg(z).squeeze(1), self.clf(z).squeeze(1)

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-4)
    tr, va, te = tensors(split["train"]), tensors(split["val"]), tensors(split["test"])

    def loss_fn(batch):
        r, c = net(batch[0], batch[1])
        return (nn.functional.l1_loss(r, batch[2])
                + nn.functional.binary_cross_entropy_with_logits(c, batch[3]))

    best, best_state, patience = np.inf, None, 0
    n = len(tr[0])
    epochs_run = 0
    for _ in range(epochs):
        epochs_run += 1
        net.train()
        for idx in torch.randperm(n).split(128):
            opt.zero_grad()
            loss = loss_fn([x[idx] for x in tr])
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            v = float(loss_fn(va))
        if v < best - 1e-4:
            best, best_state, patience = v, {k: x.clone() for k, x in net.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 12:
                break
    net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        r, c = net(te[0], te[1])
    pred_z, prob = r.numpy(), torch.sigmoid(c).numpy()

    m_test = meta[split["test"]]
    y_mm = m_test["target_anom_mm"].to_numpy(float)
    pred_mm = pred_z * m_test["clim_precip_std_next"].to_numpy(float)
    mae_lstm, mae_clim = np.mean(np.abs(y_mm - pred_mm)), np.mean(np.abs(y_mm))
    yc = m_test[CLF_TARGET].to_numpy(float)
    ens = m_test["drought_prob_ens"].to_numpy(float)
    brier_lstm, brier_ens = np.mean((prob - yc) ** 2), np.mean((ens - yc) ** 2)
    result = {
        "epochs_trained": epochs_run,
        "n_train": int(split["train"].sum()),
        "n_test": int(split["test"].sum()),
        "rainfall_mae_mm": {"lstm": float(mae_lstm), "climatology": float(mae_clim)},
        "rainfall_skill_vs_climatology": float(1 - mae_lstm / mae_clim),
        "drought_brier": {"lstm": float(brier_lstm), "ensemble": float(brier_ens)},
        "drought_skill_vs_ensemble": float(1 - brier_lstm / brier_ens),
    }

    return result


def run_experiment(
    feat: pd.DataFrame,
    epochs: int = 80,
    seeds: tuple[int, ...] = (42, 1, 2, 3, 4),
    reports_dir: Path = config.REPORTS_DIR,
) -> dict:
    """Train with several seeds: a single neural-network run is too noisy to judge."""
    runs = [_run_once(feat, epochs, seed) for seed in seeds]
    rain = np.array([r["rainfall_skill_vs_climatology"] for r in runs])
    drought = np.array([r["drought_skill_vs_ensemble"] for r in runs])
    first = runs[0]
    summary = {
        "seeds": list(seeds),
        "n_train": first["n_train"],
        "n_test": first["n_test"],
        "rainfall_skill_vs_climatology": {"mean": float(rain.mean()), "min": float(rain.min()),
                                          "max": float(rain.max())},
        "drought_skill_vs_ensemble": {"mean": float(drought.mean()), "min": float(drought.min()),
                                      "max": float(drought.max())},
        "runs": runs,
    }
    md = [
        "# Experiment: LSTM sequence model",
        "",
        "_Generated by `python -m climrisk experiment-lstm` (needs the `experiments` extra)._",
        "",
        "12-month input sequences (rainfall anomaly, SPI-1, temperature and humidity anomalies,",
        "season) plus static context, two output heads, early stopping on 2016–2019. Trained on",
        f"{first['n_train']:,} city-months and scored on {first['n_test']:,} test city-months",
        f"(2020 onward), repeated with {len(seeds)} random seeds.",
        "",
        "| Task | Baseline | LSTM skill, mean | Range across seeds |",
        "|---|---|---:|---:|",
        f"| Rainfall anomaly (MAE) | normal month | {rain.mean():+.1%} | "
        f"{rain.min():+.1%} to {rain.max():+.1%} |",
        f"| Drought next month (Brier) | climatological ensemble | {drought.mean():+.1%} | "
        f"{drought.min():+.1%} to {drought.max():+.1%} |",
        "",
        "For comparison, gradient boosting on the same test years: rainfall skill about −2%,",
        "drought about 0% vs the ensemble (see [evaluation.md](evaluation.md)).",
        "",
        "Reading: on rainfall the LSTM is "
        f"{'consistently ahead of' if rain.min() > 0 else 'not reliably ahead of'}",
        "the normal month across seeds, a small gain that the tabular models did not find. On",
        "drought it does not beat the climatological ensemble. Seeds measure training noise, not",
        "year-to-year luck: a year-block bootstrap and a longer test period would be needed",
        "before using it in production, so the deployed model stays gradient boosting.",
        "",
    ]
    (reports_dir / "experiment_lstm.md").write_text("\n".join(md), encoding="utf-8")
    log.info("LSTM experiment: rainfall %s, drought %s",
             summary["rainfall_skill_vs_climatology"], summary["drought_skill_vs_ensemble"])
    return summary
