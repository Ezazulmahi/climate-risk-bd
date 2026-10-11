import type { Metadata } from "next";
import { Card, ErrorPanel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { pct, signedPct } from "@/lib/format";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Model & accuracy" };

const REG_NAMES = { climatology: "Assume a normal month", ridge: "Ridge regression", hgb: "Gradient boosting" };
const CLF_NAMES = {
  climatology: "Usual rate (base rate)",
  ensemble: "Climatological ensemble",
  logistic: "Logistic regression",
  hgb: "Gradient boosting",
};

export default async function ModelPage() {
  let m;
  try {
    m = await api.metrics();
  } catch (e) {
    return <ErrorPanel message={e instanceof ApiError ? e.message : String(e)} />;
  }
  const th = "py-2 pr-4 font-medium text-muted";
  const td = "py-2 pr-4 tabular";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Model &amp; accuracy</h1>
        <p className="mt-2 max-w-3xl text-ink-2">
          Trained on 1982–2015, tuned on 2016–2019, and scored once on{" "}
          {m.test_period[0].slice(0, 7)} to {m.test_period[1].slice(0, 7)} ({m.n_test.toLocaleString()}{" "}
          city-months). Model version <code className="text-sm">{m.model_version}</code>.
        </p>
      </div>

      <Card>
        <h2 className="font-semibold">What the results say</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2">
          <li>
            <b className="text-ink">Rainfall amounts a month ahead are not predictable from local history.</b>{" "}
            No model beats “assume a normal month” beyond the noise. Real skill at this lead time needs
            large-scale drivers (ENSO, Indian Ocean Dipole) or dynamical forecast models.
          </li>
          <li>
            <b className="text-ink">Drought risk is predictable, and a simple baseline is as good as ML.</b>{" "}
            Two of SPI-3&apos;s three months are already known. A climatological ensemble (known rain plus
            every historical value of the coming month) matches gradient boosting.
          </li>
          <li>
            <b className="text-ink">The obvious dataset was wrong.</b> NASA POWER rainfall over Bangladesh
            changes behaviour after 2016 (1.1–2.3× ERA5, up from 0.4–0.6× before 1997). Training on it
            produced a fake 35% skill, so the project uses ERA5.
          </li>
        </ul>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Next month&apos;s rainfall</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className={th}>Model</th>
                  <th className={th}>MAE</th>
                  <th className={th}>Skill</th>
                  <th className={th}>95% CI</th>
                </tr>
              </thead>
              <tbody>
                {(Object.keys(REG_NAMES) as (keyof typeof REG_NAMES)[]).map((k) => {
                  const r = m.regression[k];
                  return (
                    <tr key={k} className="border-t border-line">
                      <td className="py-2 pr-4">{REG_NAMES[k]}</td>
                      <td className={td}>{r.mae_mm.toFixed(1)} mm</td>
                      <td className={td}>{signedPct(r.mae_skill_vs_climatology)}</td>
                      <td className={td}>
                        {r.mae_skill_95ci
                          ? `${signedPct(r.mae_skill_95ci[0])} to ${signedPct(r.mae_skill_95ci[1])}`
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-ink-2">
            80% intervals contained the observation {pct(m.interval.empirical_coverage, 1)} of the time
            (average width {Math.round(m.interval.mean_width_mm)} mm).
          </p>
          <ul className="mt-2 grid grid-cols-2 gap-x-4 text-sm tabular text-ink-2">
            {Object.entries(m.interval.coverage_by_season).map(([s, c]) => (
              <li key={s} className="flex justify-between border-t border-line py-1">
                <span>{s}</span>
                <span>{pct(c)}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <h2 className="font-semibold">Drought next month (SPI-3 ≤ −1)</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className={th}>Model</th>
                  <th className={th}>ROC-AUC</th>
                  <th className={th}>Brier</th>
                  <th className={th}>vs ensemble</th>
                  <th className={th}>F1</th>
                </tr>
              </thead>
              <tbody>
                {(Object.keys(CLF_NAMES) as (keyof typeof CLF_NAMES)[]).map((k) => {
                  const c = m.classification[k];
                  return (
                    <tr key={k} className="border-t border-line">
                      <td className="py-2 pr-4">{CLF_NAMES[k]}</td>
                      <td className={td}>{c.roc_auc.toFixed(3)}</td>
                      <td className={td}>{c.brier.toFixed(3)}</td>
                      <td className={td}>{signedPct(c.brier_skill_vs_ensemble)}</td>
                      <td className={td}>{c.f1.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-ink-2">
            Drought occurred in {pct(m.drought_rate_test, 1)} of test months.
          </p>
        </Card>
      </div>

      <Card>
        <h2 className="font-semibold">Largest misses</h2>
        <p className="mt-1 text-sm text-ink-2">
          All monsoon-season months in Sylhet and Chattogram, the wettest divisions. They include floods
          the model under-forecast (August 2024) and months that turned out far drier than forecast. Both
          are driven by weather systems no monthly feature can see coming.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <th className={th}>City</th>
                <th className={th}>Month</th>
                <th className={th}>Observed</th>
                <th className={th}>Normal</th>
                <th className={th}>Forecast</th>
                <th className={th}>Error</th>
              </tr>
            </thead>
            <tbody>
              {m.largest_errors.map((e) => (
                <tr key={`${e.city}-${e.target_date}`} className="border-t border-line">
                  <td className="py-2 pr-4">{e.city}</td>
                  <td className={td}>{e.target_date}</td>
                  <td className={td}>{Math.round(e.target_precip_mm)} mm</td>
                  <td className={td}>{Math.round(e.clim_precip_mean_next)} mm</td>
                  <td className={td}>{Math.round(e.predicted_mm)} mm</td>
                  <td className={td}>{e.err_hgb > 0 ? "+" : "−"}{Math.abs(Math.round(e.err_hgb))} mm</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Limitations</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-ink-2">
          <li>ERA5 is reanalysis, not rain-gauge data; one ~28 km grid point stands in for each division.</li>
          <li>About 7 test years: differences of a few percent between models are not significant.</li>
          <li>The normal is fixed to 1981–2015; a changing climate shifts anomalies and drought rates.</li>
          <li>Dry-season SPI is noisy because December–February totals are near zero.</li>
        </ul>
      </Card>
    </div>
  );
}
