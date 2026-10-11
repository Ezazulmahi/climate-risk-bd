export function monthLabel(ym: string, style: "long" | "short" = "long"): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-GB", {
    month: style,
    year: "numeric",
    timeZone: "UTC",
  });
}

export const mm = (v: number) => `${Math.round(v).toLocaleString("en-GB")} mm`;

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;

export const signedPct = (v: number, digits = 1) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)}%`;

export const signedMm = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(Math.round(v))} mm`;

export function citySlug(name: string): string {
  return encodeURIComponent(name.toLowerCase());
}

/** YYYY-MM string `months` before the given one. */
export function monthsBefore(ym: string, months: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 - months, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}
