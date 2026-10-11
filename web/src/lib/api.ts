import "server-only";

// Server-side client for the FastAPI backend. API_URL is never sent to the browser:
// pages fetch on the server and pass plain data to client components.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type RiskLevel = "low" | "elevated" | "high";

export interface Forecast {
  city: string;
  target_month: string;
  issued_through: string;
  split: "validation" | "test" | "live";
  rainfall: {
    expected_mm: number;
    interval_80_mm: [number, number];
    normal_mm: number;
    anomaly_mm: number;
  };
  drought: { probability: number; usual_probability: number; risk_level: RiskLevel };
  observed: null | {
    precip_mm: number;
    spi3: number | null;
    spi3_category: string;
    drought: boolean;
    inside_interval: boolean;
  };
  model_version: string;
}

export interface City {
  name: string;
  lat: number;
  lon: number;
}

export interface Observation {
  month: string;
  precip_mm: number | null;
  normal_mm: number | null;
  anomaly_mm: number | null;
  spi3: number | null;
  t2m: number | null;
  rh2m: number | null;
}

export interface Verification {
  split: string;
  city: string | null;
  n: number;
  rainfall_mae_mm: number;
  normal_mae_mm: number;
  rainfall_skill: number;
  interval_coverage: number;
  drought_rate: number;
  drought_brier: number;
  drought_brier_skill: number | null;
}

export interface Health {
  status: string;
  model_version: string | null;
  data_through: string | null;
}

interface RegMetrics {
  mae_mm: number;
  rmse_mm: number;
  mae_skill_vs_climatology: number;
  mae_skill_95ci?: [number, number];
}

interface ClfMetrics {
  roc_auc: number;
  pr_auc: number;
  brier: number;
  brier_skill_vs_climatology: number;
  brier_skill_vs_ensemble: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface Metrics {
  model_version: string;
  test_period: [string, string];
  n_test: number;
  drought_rate_test: number;
  regression: Record<"climatology" | "ridge" | "hgb", RegMetrics>;
  interval: {
    nominal_coverage: number;
    empirical_coverage: number;
    mean_width_mm: number;
    coverage_by_season: Record<string, number>;
  };
  classification: Record<"climatology" | "ensemble" | "logistic" | "hgb", ClfMetrics>;
  error_by_season: { season: string; abs_err_hgb: number; abs_err_clim: number; skill: number }[];
  largest_errors: {
    city: string;
    target_date: string;
    target_precip_mm: number;
    clim_precip_mean_next: number;
    predicted_mm: number;
    err_hgb: number;
  }[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(API_URL + path);
  for (const [k, v] of Object.entries(params ?? {})) if (v) url.searchParams.set(k, v);
  let res: Response;
  try {
    // Forecasts change once a month; a short revalidation keeps pages fast without going stale.
    res = await fetch(url, { next: { revalidate: 300 } });
  } catch {
    throw new ApiError(503, `Cannot reach the forecast API at ${API_URL}`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/health"),
  cities: () => get<City[]>("/cities"),
  latest: () => get<Forecast[]>("/forecasts/latest"),
  forecasts: (city: string, start?: string) => get<Forecast[]>("/forecasts", { city, start }),
  history: (city: string, start?: string) => get<Observation[]>("/history", { city, start }),
  verification: (city?: string) => get<Verification>("/verification", { city }),
  metrics: () => get<Metrics>("/metrics"),
};
