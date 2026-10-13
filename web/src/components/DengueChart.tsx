"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface DenguePoint {
  city: string;
  target_date: string;
  target_cases: number;
  pred_persistence: number;
  pred_seasonal_ratio: number;
  pred_ridge: number;
}

export interface DengueLabels {
  observed: string;
  persistence: string;
  seasonal: string;
  ridge: string;
  cases: string;
}

const axis = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 12 } };

export default function DengueChart({
  series,
  cities,
  cityLabels,
  labels,
}: {
  series: DenguePoint[];
  cities: string[];
  cityLabels: Record<string, string>;
  labels: DengueLabels;
}) {
  const [city, setCity] = useState(cities.includes("Dhaka") ? "Dhaka" : cities[0]);
  const data = series.filter((s) => s.city === city);
  return (
    <div>
      <label className="text-sm text-ink-2">
        <span className="mr-2">{cityLabels.__division ?? "Division"}</span>
        <select
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="rounded-md border border-line bg-surface px-2 py-1 text-ink"
        >
          {cities.map((c) => (
            <option key={c} value={c}>
              {cityLabels[c] ?? c}
            </option>
          ))}
        </select>
      </label>
      <div className="mt-4">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="target_date" minTickGap={24} {...axis} />
            <YAxis
              {...axis}
              width={64}
              tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : String(v))}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                color: "var(--ink)",
                fontSize: 13,
              }}
              formatter={(v) => [`${Math.round(Number(v)).toLocaleString()} ${labels.cases}`]}
            />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
            <Line
              dataKey="target_cases"
              name={labels.observed}
              stroke="var(--ink)"
              strokeWidth={0}
              dot={{ r: 3.5, fill: "var(--ink)", stroke: "var(--surface)", strokeWidth: 1.5 }}
              isAnimationActive={false}
            />
            <Line
              dataKey="pred_seasonal_ratio"
              name={labels.seasonal}
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="pred_ridge"
              name={labels.ridge}
              stroke="var(--series-2)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="pred_persistence"
              name={labels.persistence}
              stroke="var(--normal)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
