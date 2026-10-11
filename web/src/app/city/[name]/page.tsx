import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ForecastChart, SpiChart } from "@/components/charts";
import { Card, ErrorPanel, RangeBar, RiskBadge, Stat } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { mm, monthLabel, monthsBefore, pct, signedMm, signedPct } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/city/[name]">): Promise<Metadata> {
  const { name } = await params;
  const city = decodeURIComponent(name);
  return { title: city.charAt(0).toUpperCase() + city.slice(1) };
}

export default async function CityPage({ params }: PageProps<"/city/[name]">) {
  const city = decodeURIComponent((await params).name);
  let data;
  try {
    const latest = await api.latest();
    const live = latest.find((f) => f.city.toLowerCase() === city.toLowerCase());
    if (!live) notFound();
    const since = monthsBefore(live.target_month, 48);
    const [forecasts, history, verification] = await Promise.all([
      api.forecasts(live.city, since),
      api.history(live.city, monthsBefore(live.target_month, 120)),
      api.verification(live.city),
    ]);
    data = { live, forecasts, history, verification };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiError) return <ErrorPanel message={e.message} />;
    throw e;
  }
  const { live: f, forecasts, history, verification: v } = data;
  const r = f.rainfall;

  const chart = forecasts.map((x) => ({
    month: x.target_month,
    expected: x.rainfall.expected_mm,
    band: x.rainfall.interval_80_mm,
    normal: x.rainfall.normal_mm,
    observed: x.observed?.precip_mm ?? null,
    live: x.split === "live",
  }));
  const verified = forecasts.filter((x) => x.observed);
  const hits = verified.filter((x) => x.observed!.inside_interval).length;
  const spi = history
    .filter((h) => h.spi3 !== null)
    .map((h) => ({ month: h.month, spi3: h.spi3 as number }));
  const current = spi.at(-1);

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-ink-2 hover:text-ink">
        ← All divisions
      </Link>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted">
              Forecast for {monthLabel(f.target_month)} · data through {monthLabel(f.issued_through)}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">{f.city}</h1>
          </div>
          <RiskBadge level={f.drought.risk_level} />
        </div>
        <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Stat label="Expected rainfall" value={mm(r.expected_mm)} sub={`${signedMm(r.anomaly_mm)} vs normal`} />
          <Stat
            label="80% range"
            value={<span className="tabular">{Math.round(r.interval_80_mm[0])}–{Math.round(r.interval_80_mm[1])} mm</span>}
            sub="8 in 10 outcomes should land here"
          />
          <Stat label="Normal for the month" value={mm(r.normal_mm)} sub="1981–2015 average" />
          <Stat
            label="Drought probability"
            value={pct(f.drought.probability)}
            sub={`usually ${pct(f.drought.usual_probability)}`}
          />
        </div>
        <RangeBar
          lower={r.interval_80_mm[0]}
          upper={r.interval_80_mm[1]}
          expected={r.expected_mm}
          normal={r.normal_mm}
          max={Math.max(r.interval_80_mm[1], r.normal_mm) * 1.15}
        />
        {current && (
          <p className="mt-4 text-sm text-ink-2">
            Current conditions: SPI-3 is <b className="tabular">{current.spi3.toFixed(2)}</b> for the
            three months to {monthLabel(current.month)}.
          </p>
        )}
      </Card>

      <Card>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">Past forecasts vs what fell</h2>
          <span className="text-sm text-ink-2">
            {hits} of {verified.length} observed months inside the 80% range ({pct(hits / Math.max(verified.length, 1))})
          </span>
        </div>
        <p className="mt-1 text-sm text-ink-2">
          Each point was forecast a month ahead using only data available at the time. The last point is
          the live forecast.
        </p>
        <div className="mt-4">
          <ForecastChart data={chart} />
        </div>
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-ink-2">Show as table</summary>
          <div className="mt-2 max-h-72 overflow-auto">
            <table className="w-full text-left tabular">
              <thead className="sticky top-0 bg-surface text-muted">
                <tr>
                  <th className="py-1 pr-4 font-medium">Month</th>
                  <th className="py-1 pr-4 font-medium">Forecast</th>
                  <th className="py-1 pr-4 font-medium">80% range</th>
                  <th className="py-1 pr-4 font-medium">Normal</th>
                  <th className="py-1 font-medium">Observed</th>
                </tr>
              </thead>
              <tbody>
                {[...forecasts].reverse().map((x) => (
                  <tr key={x.target_month} className="border-t border-line">
                    <td className="py-1 pr-4">{monthLabel(x.target_month, "short")}</td>
                    <td className="py-1 pr-4">{Math.round(x.rainfall.expected_mm)}</td>
                    <td className="py-1 pr-4">
                      {Math.round(x.rainfall.interval_80_mm[0])}–{Math.round(x.rainfall.interval_80_mm[1])}
                    </td>
                    <td className="py-1 pr-4">{Math.round(x.rainfall.normal_mm)}</td>
                    <td className="py-1">{x.observed ? Math.round(x.observed.precip_mm) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold">Drought index (SPI-3), last 10 years</h2>
          <p className="mt-1 text-sm text-ink-2">
            Below −1 (red) means the 3-month rainfall was in roughly the driest 16% for that time of year.
          </p>
          <div className="mt-4">
            <SpiChart data={spi} />
          </div>
        </Card>
        <Card>
          <h2 className="font-semibold">Track record for {f.city}</h2>
          <p className="mt-1 text-sm text-ink-2">Test period 2020 onward, {v.n} months.</p>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">Rainfall error (MAE)</dt>
              <dd className="font-semibold tabular">{mm(v.rainfall_mae_mm)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">If we always said “normal”</dt>
              <dd className="font-semibold tabular">{mm(v.normal_mae_mm)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">Rainfall skill</dt>
              <dd className="font-semibold tabular">{signedPct(v.rainfall_skill)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">80% range coverage</dt>
              <dd className="font-semibold tabular">{pct(v.interval_coverage)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">Drought months</dt>
              <dd className="font-semibold tabular">{pct(v.drought_rate)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-2">Drought Brier skill</dt>
              <dd className="font-semibold tabular">
                {v.drought_brier_skill === null ? "—" : signedPct(v.drought_brier_skill)}
              </dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
