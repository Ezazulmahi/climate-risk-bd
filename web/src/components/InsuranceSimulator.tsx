"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Row {
  month: string;
  spi3: number | null;
}

export interface SimLabels {
  district: string;
  season: string;
  seasons: { aman: string; aus: string; boro: string };
  trigger: string;
  exit: string;
  sum: string;
  yearsPaid: string;
  frequency: string;
  premium: string;
  premiumNote: string;
  worst: string;
  basis: string;
  loading: string;
  payout: string;
  none: string;
}

// The 3-month window that matters for each rice season; SPI-3 is read at its last month.
const SEASON_MONTH = { aman: 9, aus: 5, boro: 3 } as const;
type Season = keyof typeof SEASON_MONTH;

const axis = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 12 } };

export default function InsuranceSimulator({
  districts,
  labels,
  locale,
}: {
  districts: string[];
  labels: SimLabels;
  locale: string;
}) {
  const [district, setDistrict] = useState(districts.includes("Rajshahi") ? "Rajshahi" : districts[0]);
  const [season, setSeason] = useState<Season>("aman");
  const [trigger, setTrigger] = useState(-1.0);
  const [exit, setExit] = useState(-2.0);
  const [sum, setSum] = useState(10000);
  // Loaded history, tagged with its district so a stale response is never shown.
  const [loaded, setLoaded] = useState<{ district: string; rows: Row[] } | null>(null);
  const rows = loaded?.district === district ? loaded.rows : null;

  useEffect(() => {
    let alive = true;
    fetch(`/proxy/districts/${encodeURIComponent(district)}`)
      .then((r) => r.json())
      .then((d: Row[]) => alive && setLoaded({ district, rows: d }))
      .catch(() => alive && setLoaded({ district, rows: [] }));
    return () => {
      alive = false;
    };
  }, [district]);

  const result = useMemo(() => {
    if (!rows) return null;
    const m = SEASON_MONTH[season];
    const years = rows
      .filter((r) => Number(r.month.slice(5)) === m && r.spi3 !== null)
      .map((r) => {
        const spi = r.spi3 as number;
        const frac = Math.min(1, Math.max(0, (trigger - spi) / (trigger - exit)));
        return { year: r.month.slice(0, 4), spi, payout: Math.round(frac * sum) };
      });
    const paid = years.filter((y) => y.payout > 0);
    const avg = years.reduce((a, y) => a + y.payout, 0) / Math.max(years.length, 1);
    const worst = paid.reduce<(typeof years)[number] | null>(
      (w, y) => (w === null || y.payout > w.payout ? y : w),
      null,
    );
    return { years, paid, avg, worst };
  }, [rows, season, trigger, exit, sum]);

  const fmt = (v: number) => Math.round(v).toLocaleString(locale);
  const field = "rounded-md border border-line bg-surface px-2 py-1 text-ink";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-sm text-ink-2">
          {labels.district}
          <select className={`mt-1 block w-full ${field}`} value={district}
            onChange={(e) => setDistrict(e.target.value)}>
            {districts.map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        <label className="text-sm text-ink-2">
          {labels.season}
          <select className={`mt-1 block w-full ${field}`} value={season}
            onChange={(e) => setSeason(e.target.value as Season)}>
            {(Object.keys(SEASON_MONTH) as Season[]).map((s) => (
              <option key={s} value={s}>{labels.seasons[s]}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-ink-2">
          {labels.trigger}: <b className="tabular text-ink">{trigger.toFixed(1)}</b>
          <input type="range" min={-2} max={-0.5} step={0.1} value={trigger}
            onChange={(e) => {
              const v = Number(e.target.value);
              setTrigger(v);
              if (exit >= v) setExit(Math.max(-3, v - 0.5));
            }}
            className="mt-2 block w-full" />
        </label>
        <label className="text-sm text-ink-2">
          {labels.exit}: <b className="tabular text-ink">{exit.toFixed(1)}</b>
          <input type="range" min={-3} max={trigger - 0.1} step={0.1} value={exit}
            onChange={(e) => setExit(Number(e.target.value))} className="mt-2 block w-full" />
        </label>
        <label className="text-sm text-ink-2">
          {labels.sum}
          <input type="number" min={1000} step={1000} value={sum}
            onChange={(e) => setSum(Math.max(0, Number(e.target.value) || 0))}
            className={`mt-1 block w-full tabular ${field}`} />
        </label>
      </div>

      {!result ? (
        <div className="h-64 animate-pulse rounded-lg bg-surface-2" aria-label={labels.loading} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">{labels.yearsPaid}</div>
              <div className="text-2xl font-semibold tabular">
                {fmt(result.paid.length)} / {fmt(result.years.length)}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">{labels.frequency}</div>
              <div className="text-2xl font-semibold tabular">
                {result.paid.length ? (result.years.length / result.paid.length).toFixed(1) : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">{labels.premium}</div>
              <div className="text-2xl font-semibold tabular">৳{fmt(result.avg)}</div>
              <div className="text-xs text-ink-2">
                {((result.avg / Math.max(sum, 1)) * 100).toFixed(1)}% · {labels.premiumNote}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">{labels.worst}</div>
              <div className="text-2xl font-semibold tabular">
                {result.worst ? `${result.worst.year}` : labels.none}
              </div>
              {result.worst && (
                <div className="text-xs text-ink-2 tabular">
                  ৳{fmt(result.worst.payout)} · SPI-3 {result.worst.spi.toFixed(2)}
                </div>
              )}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={result.years} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="year" minTickGap={16} {...axis} />
              <YAxis {...axis} width={64} tickFormatter={(v) => `৳${fmt(Number(v))}`} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)",
                  borderRadius: 8, color: "var(--ink)", fontSize: 13 }}
                formatter={(v, _n, p) => [
                  `৳${fmt(Number(v))} (SPI-3 ${(p.payload as { spi: number }).spi.toFixed(2)})`,
                  labels.payout,
                ]}
                cursor={{ fill: "var(--surface-2)" }}
              />
              <Bar dataKey="payout" fill="var(--dry)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted">{labels.basis}</p>
        </>
      )}
    </div>
  );
}
