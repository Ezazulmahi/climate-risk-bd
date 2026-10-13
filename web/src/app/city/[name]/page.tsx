import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ForecastChart, SpiChart } from "@/components/charts";
import { Card, ErrorPanel, RangeBar, RiskBadge, Stat } from "@/components/ui";
import { api, ApiError, type Explanation, type Issued } from "@/lib/api";
import { monthsBefore } from "@/lib/format";
import {
  cityName,
  driverLabel,
  getDict,
  mmL,
  monthL,
  num,
  pctL,
  signedMmL,
  signedPctL,
} from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/city/[name]">): Promise<Metadata> {
  const { name } = await params;
  const city = decodeURIComponent(name);
  return { title: city.charAt(0).toUpperCase() + city.slice(1) };
}

export default async function CityPage({ params }: PageProps<"/city/[name]">) {
  const { lang, t } = await getDict();
  const city = decodeURIComponent((await params).name);
  let data;
  try {
    const latest = await api.latest();
    const live = latest.find((f) => f.city.toLowerCase() === city.toLowerCase());
    if (!live) notFound();
    const [forecasts, history, verification, issued, explanation] = await Promise.all([
      api.forecasts(live.city, monthsBefore(live.target_month, 48)),
      api.history(live.city, monthsBefore(live.target_month, 120)),
      api.verification(live.city),
      api.issued(live.city).catch(() => [] as Issued[]),
      api.explain(live.city).catch(() => null as Explanation | null),
    ]);
    data = { live, forecasts, history, verification, issued, explanation };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiError) return <ErrorPanel message={e.message} />;
    throw e;
  }
  const { live: f, forecasts, history, verification: v, issued, explanation } = data;
  const r = f.rainfall;
  const name = cityName(f.city, lang);
  const riskLabel = { low: t.riskLow, elevated: t.riskElevated, high: t.riskHigh };

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
  const heat = f.heat;
  const heatSeason = heat && (heat.normal_days >= 0.5 || heat.expected_days >= 0.5);
  const maxEffect = Math.max(...(explanation?.drivers.map((d) => Math.abs(d.effect)) ?? [0]), 0.01);

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-ink-2 hover:text-ink">
        {t.backAll}
      </Link>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted">
              {t.forecastFor} {monthL(f.target_month, lang)} · {t.dataThrough}{" "}
              {monthL(f.issued_through, lang)}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">{name}</h1>
          </div>
          <RiskBadge level={f.drought.risk_level} label={riskLabel[f.drought.risk_level]} />
        </div>
        <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Stat
            label={t.expectedRainfall}
            value={mmL(r.expected_mm, lang)}
            sub={`${signedMmL(r.anomaly_mm, lang)} ${t.vsNormal}`}
          />
          <Stat
            label={t.range80}
            value={
              <span className="tabular">
                {num(r.interval_80_mm[0], lang)}–{mmL(r.interval_80_mm[1], lang)}
              </span>
            }
            sub={t.outcomesLand}
          />
          <Stat label={t.normalForMonth} value={mmL(r.normal_mm, lang)} sub={t.avg8115} />
          <Stat
            label={t.droughtProbability}
            value={pctL(f.drought.probability, lang)}
            sub={`${t.usually} ${pctL(f.drought.usual_probability, lang)}`}
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
            {lang === "bn" ? (
              <>
                বর্তমান অবস্থা: {monthL(current.month, lang)} পর্যন্ত তিন মাসের SPI-3 হলো{" "}
                <b className="tabular">{num(current.spi3, lang, 2)}</b>।
              </>
            ) : (
              <>
                {t.currentConditions} <b className="tabular">{num(current.spi3, lang, 2)}</b>{" "}
                {t.forThreeMonths} {monthL(current.month, lang)}.
              </>
            )}
          </p>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {explanation && (
          <Card className="lg:col-span-2">
            <h2 className="font-semibold">{t.whyTitle}</h2>
            <p className="mt-1 text-sm text-ink-2">{t.whyIntro}</p>
            <ul className="mt-4 space-y-3">
              {explanation.drivers.map((d) => (
                <li key={d.label} className="text-sm">
                  <div className="flex justify-between gap-3">
                    <span>{driverLabel(d.label, d.features, lang)}</span>
                    <span className="tabular font-semibold">
                      {d.effect >= 0 ? "+" : "−"}
                      {num(Math.abs(d.effect) * 100, lang, 1)}
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-surface-2">
                    <div
                      className="h-2 rounded-full"
                      style={{
                        width: `${(Math.abs(d.effect) / maxEffect) * 100}%`,
                        background: d.effect >= 0 ? "var(--dry)" : "var(--series-1)",
                      }}
                    />
                  </div>
                  {d.value !== null && (
                    <div className="mt-0.5 text-xs text-muted tabular">
                      {t.now} {num(d.value, lang, 2)} · {t.typical} {num(d.typical, lang, 2)}
                    </div>
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">
              {lang === "bn" ? "শতাংশ পয়েন্ট" : "Percentage points of drought probability."}
            </p>
          </Card>
        )}
        <Card>
          <h2 className="font-semibold">{t.heatTitle}</h2>
          {heat && heatSeason ? (
            <>
              <div className="mt-3 text-3xl font-semibold tabular">
                {num(heat.expected_days, lang, heat.expected_days < 10 ? 1 : 0)}
              </div>
              <div className="text-sm text-ink-2">{t.heatDays}</div>
              <dl className="mt-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-ink-2">{t.heatNormal}</dt>
                  <dd className="tabular">{num(heat.normal_days, lang, 1)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-ink-2">{t.heatRecent}</dt>
                  <dd className="tabular">{num(heat.recent_decade_days, lang, 1)}</dd>
                </div>
              </dl>
            </>
          ) : (
            <p className="mt-3 text-sm text-ink-2">{t.heatOff}</p>
          )}
          <p className="mt-3 text-xs text-muted">{t.heatNote}</p>
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">{t.pastTitle}</h2>
          <span className="text-sm text-ink-2">
            {num(hits, lang)} / {num(verified.length, lang)} {t.insideRange} (
            {pctL(hits / Math.max(verified.length, 1), lang)})
          </span>
        </div>
        <p className="mt-1 text-sm text-ink-2">{t.pastIntro}</p>
        <div className="mt-4">
          <ForecastChart
            data={chart}
            labels={{
              range: t.range80,
              normal: t.heatNormal,
              forecast: t.forecast,
              observed: t.observed,
              notYet: t.pending,
              mm: lang === "bn" ? "মিমি" : "mm",
            }}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <details>
            <summary className="cursor-pointer text-ink-2">{t.showTable}</summary>
            <div className="mt-2 max-h-72 overflow-auto">
              <table className="w-full text-left tabular">
                <thead className="sticky top-0 bg-surface text-muted">
                  <tr>
                    <th className="py-1 pr-4 font-medium">{t.month}</th>
                    <th className="py-1 pr-4 font-medium">{t.forecast}</th>
                    <th className="py-1 pr-4 font-medium">{t.range80}</th>
                    <th className="py-1 pr-4 font-medium">{t.heatNormal}</th>
                    <th className="py-1 font-medium">{t.observed}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...forecasts].reverse().map((x) => (
                    <tr key={x.target_month} className="border-t border-line">
                      <td className="py-1 pr-4">{monthL(x.target_month, lang, "short")}</td>
                      <td className="py-1 pr-4">{num(x.rainfall.expected_mm, lang)}</td>
                      <td className="py-1 pr-4">
                        {num(x.rainfall.interval_80_mm[0], lang)}–{num(x.rainfall.interval_80_mm[1], lang)}
                      </td>
                      <td className="py-1 pr-4">{num(x.rainfall.normal_mm, lang)}</td>
                      <td className="py-1">{x.observed ? num(x.observed.precip_mm, lang) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <a
            href={`/download/forecasts.csv?city=${encodeURIComponent(f.city)}`}
            className="text-accent underline"
          >
            {t.downloadCsv}
          </a>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold">{t.spiTitle}</h2>
          <p className="mt-1 text-sm text-ink-2">{t.spiIntro}</p>
          <div className="mt-4">
            <SpiChart data={spi} droughtLabel={lang === "bn" ? "খরা" : "drought"} />
          </div>
        </Card>
        <Card>
          <h2 className="font-semibold">
            {t.trackTitle} {name}
          </h2>
          <p className="mt-1 text-sm text-ink-2">
            {t.trackIntro} {num(v.n, lang)} {t.months}.
          </p>
          <dl className="mt-4 space-y-3 text-sm">
            {[
              [t.rainError, mmL(v.rainfall_mae_mm, lang)],
              [t.ifNormal, mmL(v.normal_mae_mm, lang)],
              [t.rainSkill, signedPctL(v.rainfall_skill, lang)],
              [t.coverage, pctL(v.interval_coverage, lang)],
              [t.droughtMonths, pctL(v.drought_rate, lang)],
              [t.droughtSkill,
                v.drought_brier_skill === null ? "—" : signedPctL(v.drought_brier_skill, lang)],
            ].map(([k, val]) => (
              <div key={k} className="flex justify-between gap-4">
                <dt className="text-ink-2">{k}</dt>
                <dd className="font-semibold tabular">{val}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      {issued.length > 0 && (
        <Card>
          <h2 className="font-semibold">{t.logTitle}</h2>
          <p className="mt-1 text-sm text-ink-2">{t.logIntro}</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm tabular">
              <thead className="text-muted">
                <tr>
                  <th className="py-1 pr-4 font-medium">{t.month}</th>
                  <th className="py-1 pr-4 font-medium">{t.issued}</th>
                  <th className="py-1 pr-4 font-medium">{t.forecast}</th>
                  <th className="py-1 pr-4 font-medium">{t.droughtChance}</th>
                  <th className="py-1 font-medium">{t.observed}</th>
                </tr>
              </thead>
              <tbody>
                {issued.map((i) => (
                  <tr key={i.target_month} className="border-t border-line">
                    <td className="py-1 pr-4">{monthL(i.target_month, lang, "short")}</td>
                    <td className="py-1 pr-4">{i.issued_at.slice(0, 10)}</td>
                    <td className="py-1 pr-4">
                      {mmL(i.rainfall.expected_mm, lang)} ({num(i.rainfall.interval_80_mm[0], lang)}–
                      {num(i.rainfall.interval_80_mm[1], lang)})
                    </td>
                    <td className="py-1 pr-4">{pctL(i.drought.probability, lang)}</td>
                    <td className="py-1">
                      {i.observed
                        ? `${mmL(i.observed.precip_mm, lang)}, ${i.observed.inside_interval ? t.inside : t.outside}`
                        : t.pending}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
