import Link from "next/link";
import OutlookMap from "@/components/OutlookMap";
import { Card, ErrorPanel, RangeBar, RiskBadge } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { citySlug, mm, monthLabel, pct, signedMm, signedPct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function Home() {
  let data;
  try {
    const [latest, cities, verification, health] = await Promise.all([
      api.latest(),
      api.cities(),
      api.verification(),
      api.health(),
    ]);
    data = { latest, cities, verification, health };
  } catch (e) {
    return <ErrorPanel message={e instanceof ApiError ? e.message : String(e)} />;
  }
  const { latest, cities, verification: v, health } = data;
  const month = latest[0]?.target_month;
  const coords = new Map(cities.map((c) => [c.name, c]));
  const order = { high: 0, elevated: 1, low: 2 } as const;
  const sorted = [...latest].sort(
    (a, b) =>
      order[a.drought.risk_level] - order[b.drought.risk_level] ||
      b.drought.probability - a.drought.probability,
  );
  const scaleMax = Math.max(...latest.map((f) => f.rainfall.interval_80_mm[1]), 1) * 1.05;

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-muted">
          Outlook issued with data through {health.data_through && monthLabel(health.data_through)}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {month ? monthLabel(month) : "No forecast yet"}: rainfall and drought outlook
        </h1>
        <p className="mt-2 max-w-3xl text-ink-2">
          For each division: next month&apos;s expected rainfall with an 80% range, and the chance
          that the 3-month rainfall ending that month is in drought territory (SPI-3 ≤ −1). The usual
          chance is about {pct(latest[0]?.drought.usual_probability ?? 0.16)}.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <h2 className="mb-3 font-semibold">Drought risk by division</h2>
          <OutlookMap
            points={latest.flatMap((f) => {
              const c = coords.get(f.city);
              return c
                ? [{
                    name: f.city,
                    lat: c.lat,
                    lon: c.lon,
                    risk: f.drought.risk_level,
                    probability: f.drought.probability,
                    expected: f.rainfall.expected_mm,
                    normal: f.rainfall.normal_mm,
                  }]
                : [];
            })}
          />
          <p className="mt-2 text-xs text-muted">
            Circle size = drought probability. Click a circle for details.
          </p>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-semibold">How much to trust this</h2>
          <p className="mt-1 text-sm text-ink-2">
            Every forecast since 2020 was stored and checked against what fell ({v.n} city-months).
          </p>
          <dl className="mt-4 space-y-4 text-sm">
            <div>
              <dt className="text-muted">Rainfall amount, vs. assuming a normal month</dt>
              <dd className="text-lg font-semibold">{signedPct(v.rainfall_skill)} error reduction</dd>
              <dd className="text-ink-2">
                Effectively no skill. One-month-ahead rainfall is hard to predict, so treat the
                expected amount as “about normal” and read the range.
              </dd>
            </div>
            <div>
              <dt className="text-muted">80% range contained the actual rainfall</dt>
              <dd className="text-lg font-semibold">{pct(v.interval_coverage)} of the time</dd>
            </div>
            <div>
              <dt className="text-muted">Drought probability, vs. the usual rate</dt>
              <dd className="text-lg font-semibold">
                {v.drought_brier_skill !== null && signedPct(v.drought_brier_skill)} better (Brier)
              </dd>
              <dd className="text-ink-2">
                Real skill. Two of the three months are already observed when the forecast is made.
              </dd>
            </div>
          </dl>
          <Link href="/model" className="mt-4 inline-block text-sm text-accent underline">
            Full evaluation →
          </Link>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">All divisions</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((f) => (
            <Link key={f.city} href={`/city/${citySlug(f.city)}`} className="group">
              <Card className="h-full transition-colors group-hover:border-[var(--accent)]">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-lg font-semibold">{f.city}</h3>
                  <RiskBadge level={f.drought.risk_level} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-muted">Expected rain</div>
                    <div className="text-xl font-semibold tabular">{mm(f.rainfall.expected_mm)}</div>
                    <div className="text-xs text-ink-2">
                      {signedMm(f.rainfall.anomaly_mm)} vs normal
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">Drought chance</div>
                    <div className="text-xl font-semibold tabular">{pct(f.drought.probability)}</div>
                    <div className="text-xs text-ink-2">usually {pct(f.drought.usual_probability)}</div>
                  </div>
                </div>
                <RangeBar
                  lower={f.rainfall.interval_80_mm[0]}
                  upper={f.rainfall.interval_80_mm[1]}
                  expected={f.rainfall.expected_mm}
                  normal={f.rainfall.normal_mm}
                  max={scaleMax}
                />
                <div className="mt-1 flex justify-between text-xs text-muted tabular">
                  <span>
                    80% range {Math.round(f.rainfall.interval_80_mm[0])}–
                    {Math.round(f.rainfall.interval_80_mm[1])} mm
                  </span>
                  <span>normal {Math.round(f.rainfall.normal_mm)} mm</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">
          Bars share one scale: light band = 80% range, dot = expected, grey tick = normal.
        </p>
      </div>
    </div>
  );
}
