import type { ReactNode } from "react";
import type { RiskLevel } from "@/lib/api";

const RISK: Record<RiskLevel, { label: string; icon: string; color: string }> = {
  low: { label: "Low", icon: "●", color: "var(--good)" },
  elevated: { label: "Elevated", icon: "▲", color: "var(--warning)" },
  high: { label: "High", icon: "◆", color: "var(--critical)" },
};

/** Status always ships as icon + label; color never carries the meaning alone. */
export function RiskBadge({ level }: { level: RiskLevel }) {
  const r = RISK[level];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-xs font-medium">
      <span aria-hidden style={{ color: r.color }}>
        {r.icon}
      </span>
      {r.label} drought risk
    </span>
  );
}

export const riskColor = (level: RiskLevel) => RISK[level].color;

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-sm text-ink-2">{sub}</div>}
    </div>
  );
}

/** Horizontal bar showing the 80% range, the expected value and the normal on one scale. */
export function RangeBar({
  lower,
  upper,
  expected,
  normal,
  max,
}: {
  lower: number;
  upper: number;
  expected: number;
  normal: number;
  max: number;
}) {
  const x = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div
      className="relative mt-3 h-6"
      role="img"
      aria-label={`80% range ${Math.round(lower)} to ${Math.round(upper)} mm, expected ${Math.round(expected)} mm, normal ${Math.round(normal)} mm`}
    >
      <div className="absolute inset-x-0 top-1/2 h-px bg-[var(--axis)]" />
      <div
        className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full"
        style={{ left: x(lower), width: `calc(${x(upper)} - ${x(lower)})`, background: "var(--band)" }}
      />
      <div
        className="absolute top-0 h-full w-0.5 rounded"
        style={{ left: x(normal), background: "var(--normal)" }}
        title="Normal"
      />
      <div
        className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
        style={{ left: x(expected), background: "var(--series-1)", borderColor: "var(--surface)" }}
        title="Expected"
      />
    </div>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <Card className="border-[var(--critical)]">
      <h2 className="font-semibold">The forecast service is unavailable</h2>
      <p className="mt-2 text-sm text-ink-2">{message}</p>
      <p className="mt-2 text-sm text-ink-2">
        Start the API with <code>uvicorn climrisk.api:app</code> and publish data with{" "}
        <code>python -m climrisk db-sync</code>.
      </p>
    </Card>
  );
}
