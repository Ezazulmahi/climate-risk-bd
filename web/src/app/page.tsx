import Link from "next/link";
import OutlookMap from "@/components/OutlookMap";
import { Card, ErrorPanel, RangeBar, RiskBadge } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { citySlug } from "@/lib/format";
import { cityName, getDict, mmL, monthL, num, pctL, signedMmL, signedPctL } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { lang, t } = await getDict();
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
  const riskLabel = { low: t.riskLow, elevated: t.riskElevated, high: t.riskHigh };
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
          {t.issuedWith} {health.data_through && monthL(health.data_through, lang)}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {month ? `${monthL(month, lang)}: ${t.outlookTitle}` : t.noForecast}
        </h1>
        <p className="mt-2 max-w-3xl text-ink-2">
          {t.outlookIntro} {pctL(latest[0]?.drought.usual_probability ?? 0.16, lang)}.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <h2 className="mb-3 font-semibold">{t.mapTitle}</h2>
          <OutlookMap
            points={latest.flatMap((f) => {
              const c = coords.get(f.city);
              return c
                ? [{
                    name: f.city,
                    label: cityName(f.city, lang),
                    lat: c.lat,
                    lon: c.lon,
                    risk: f.drought.risk_level,
                    probabilityText: pctL(f.drought.probability, lang),
                    probability: f.drought.probability,
                    rainText: `${t.expectedRain}: ${mmL(f.rainfall.expected_mm, lang)} (${t.normal} ${mmL(f.rainfall.normal_mm, lang)})`,
                    droughtText: t.droughtChance,
                  }]
                : [];
            })}
          />
          <p className="mt-2 text-xs text-muted">{t.mapNote}</p>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-semibold">{t.trustTitle}</h2>
          <p className="mt-1 text-sm text-ink-2">
            {t.trustIntro} ({num(v.n, lang)} {t.cityMonths}).
          </p>
          <dl className="mt-4 space-y-4 text-sm">
            <div>
              <dt className="text-muted">{t.trustRain}</dt>
              <dd className="text-lg font-semibold">
                {signedPctL(v.rainfall_skill, lang)} {t.errorReduction}
              </dd>
              <dd className="text-ink-2">{t.trustRainNote}</dd>
            </div>
            <div>
              <dt className="text-muted">{t.trustRange}</dt>
              <dd className="text-lg font-semibold">
                {pctL(v.interval_coverage, lang)} {t.ofTheTime}
              </dd>
            </div>
            <div>
              <dt className="text-muted">{t.trustDrought}</dt>
              <dd className="text-lg font-semibold">
                {v.drought_brier_skill !== null && signedPctL(v.drought_brier_skill, lang)} {t.better}
              </dd>
              <dd className="text-ink-2">{t.trustDroughtNote}</dd>
            </div>
          </dl>
          <Link href="/model" className="mt-4 inline-block text-sm text-accent underline">
            {t.fullEvaluation}
          </Link>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">{t.allDivisions}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((f) => (
            <Link key={f.city} href={`/city/${citySlug(f.city)}`} className="group">
              <Card className="h-full transition-colors group-hover:border-[var(--accent)]">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-lg font-semibold">{cityName(f.city, lang)}</h3>
                  <RiskBadge level={f.drought.risk_level} label={riskLabel[f.drought.risk_level]} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-muted">{t.expectedRain}</div>
                    <div className="text-xl font-semibold tabular">
                      {mmL(f.rainfall.expected_mm, lang)}
                    </div>
                    <div className="text-xs text-ink-2">
                      {signedMmL(f.rainfall.anomaly_mm, lang)} {t.vsNormal}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">{t.droughtChance}</div>
                    <div className="text-xl font-semibold tabular">
                      {pctL(f.drought.probability, lang)}
                    </div>
                    <div className="text-xs text-ink-2">
                      {t.usually} {pctL(f.drought.usual_probability, lang)}
                    </div>
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
                    {t.range80} {num(f.rainfall.interval_80_mm[0], lang)}–
                    {mmL(f.rainfall.interval_80_mm[1], lang)}
                  </span>
                  <span>
                    {t.normal} {mmL(f.rainfall.normal_mm, lang)}
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">{t.barsNote}</p>
      </div>
    </div>
  );
}
