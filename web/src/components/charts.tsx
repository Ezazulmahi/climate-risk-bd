"use client";

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface ForecastPoint {
  month: string;
  expected: number;
  band: [number, number];
  normal: number;
  observed: number | null;
  live: boolean;
}

export interface SpiPoint {
  month: string;
  spi3: number;
}

const axis = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 12 } };
const tooltipStyle = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--ink)",
    fontSize: 13,
  },
  labelStyle: { color: "var(--ink)", fontWeight: 600 },
  itemStyle: { color: "var(--ink-2)" },
};

const shortMonth = (ym: string) => {
  const [y, m] = ym.split("-");
  return `${"JFMAMJJASOND"[Number(m) - 1]} ${y.slice(2)}`;
};

export interface ForecastLabels {
  range: string;
  normal: string;
  forecast: string;
  observed: string;
  notYet: string;
  mm: string;
}

const EN_LABELS: ForecastLabels = {
  range: "80% range",
  normal: "Normal",
  forecast: "Forecast",
  observed: "Observed",
  notYet: "not yet observed",
  mm: "mm",
};

export function ForecastChart({
  data,
  labels = EN_LABELS,
}: {
  data: ForecastPoint[];
  labels?: ForecastLabels;
}) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="month" tickFormatter={shortMonth} minTickGap={24} {...axis} />
        <YAxis unit={` ${labels.mm}`} width={64} {...axis} />
        <Tooltip
          {...tooltipStyle}
          labelFormatter={(m) => shortMonth(String(m))}
          formatter={(value, name) => {
            if (Array.isArray(value))
              return [`${Math.round(value[0])}–${Math.round(value[1])} ${labels.mm}`, name];
            return [
              value == null ? labels.notYet : `${Math.round(Number(value))} ${labels.mm}`,
              name,
            ];
          }}
        />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} />
        <Area
          dataKey="band"
          name={labels.range}
          stroke="none"
          fill="var(--band)"
          fillOpacity={0.7}
          isAnimationActive={false}
        />
        <Line
          dataKey="normal"
          name={labels.normal}
          stroke="var(--normal)"
          strokeDasharray="4 4"
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          dataKey="expected"
          name={labels.forecast}
          stroke="var(--series-1)"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          dataKey="observed"
          name={labels.observed}
          stroke="none"
          dot={{ r: 3.5, fill: "var(--ink)", stroke: "var(--surface)", strokeWidth: 1.5 }}
          activeDot={{ r: 5 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function SpiChart({
  data,
  droughtLabel = "drought",
}: {
  data: SpiPoint[];
  droughtLabel?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }} barCategoryGap={1}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="month" tickFormatter={shortMonth} minTickGap={32} {...axis} />
        <YAxis domain={[-3, 3]} ticks={[-2, -1, 0, 1, 2]} {...axis} />
        <Tooltip
          {...tooltipStyle}
          cursor={{ fill: "var(--surface-2)" }}
          labelFormatter={(m) => shortMonth(String(m))}
          formatter={(v) => [Number(v).toFixed(2), "SPI-3"]}
        />
        <ReferenceLine
          y={-1}
          stroke="var(--dry)"
          strokeDasharray="4 4"
          label={{ value: droughtLabel, position: "insideBottomLeft", fill: "var(--dry)", fontSize: 11 }}
        />
        <Bar dataKey="spi3" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.month} fill={d.spi3 <= -1 ? "var(--dry)" : d.spi3 < 0 ? "var(--normal)" : "var(--series-1)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
