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
  heat: null | {
    expected_days: number;
    normal_days: number;
    recent_decade_days: number;
    threshold_c: number;
  };
  observed: null | {
    precip_mm: number;
    spi3: number | null;
    spi3_category: string;
    drought: boolean;
    inside_interval: boolean;
    heatwave_days: number | null;
  };
  model_version: string;
}

export interface Issued {
  city: string;
  target_month: string;
  issued_at: string;
  issued_through: string;
  model_version: string;
  rainfall: { expected_mm: number; interval_80_mm: [number, number]; normal_mm: number };
  drought: { probability: number; usual_probability: number; risk_level: RiskLevel };
  observed: null | {
    precip_mm: number;
    spi3: number | null;
    inside_interval: boolean;
    drought: boolean;
  };
}

export interface Driver {
  label: string;
  features: string[];
  effect: number;
  value: number | null;
  typical: number;
}

export interface Explanation {
  city: string;
  probability: number;
  drivers: Driver[];
}

export interface DistrictRow {
  district: string;
  month: string;
  precip_mm: number | null;
  normal_mm: number | null;
  spi1: number | null;
  spi3: number | null;
  spi6: number | null;
  spi12: number | null;
  category: "D0" | "D1" | "D2" | "D3" | "D4" | null;
  drought_prob_next: number | null;
  lat?: number;
  lon?: number;
}

export interface DistrictStatus {
  month: string;
  categories: { code: string; label: string; spi_at_or_below: number }[];
  districts: DistrictRow[];
}

export interface DistrictEval {
  n_test: number;
  base_rate_train: number;
  drought_rate_test: number;
  brier: number;
  brier_base_rate: number;
  brier_skill: number;
}

export interface HeatEval {
  n_test: number;
  mean_observed_days: number;
  mean_normal_days: number;
  mae_days: { normal: number; recent: number; model: number };
  skill_vs_normal: number;
  skill_vs_recent: number;
  skill_vs_recent_95ci: [number, number];
}

export interface ValidationRow {
  city: string;
  era5_over_chirps_total: number;
  monthly_corr: number;
  anomaly_corr: number;
  spi3_corr: number;
  drought_agreement: number;
  drought_kappa: number;
}

export interface DengueBacktest {
  source: string;
  train_months: number;
  test_months: number;
  test_period: [string, string];
  scores: Record<
    "persistence" | "seasonal_ratio" | "ridge",
    { mae_log: number; mae_cases: number; direction_accuracy: number | null;
      skill_vs_persistence_log?: number }
  >;
  series: {
    city: string;
    target_date: string;
    target_cases: number;
    pred_persistence: number;
    pred_seasonal_ratio: number;
    pred_ridge: number;
  }[];
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

/** Raw passthrough for downloads (CSV, RSS) proxied by route handlers. */
export async function getRaw(path: string, params?: Record<string, string | undefined>) {
  const url = new URL(API_URL + path);
  for (const [k, v] of Object.entries(params ?? {})) if (v) url.searchParams.set(k, v);
  return fetch(url, { cache: "no-store" });
}

export const api = {
  health: () => get<Health>("/health"),
  cities: () => get<City[]>("/cities"),
  latest: () => get<Forecast[]>("/forecasts/latest"),
  forecasts: (city: string, start?: string) => get<Forecast[]>("/forecasts", { city, start }),
  history: (city: string, start?: string) => get<Observation[]>("/history", { city, start }),
  verification: (city?: string) => get<Verification>("/verification", { city }),
  metrics: () => get<Metrics>("/metrics"),
  issued: (city?: string) => get<Issued[]>("/issued", { city }),
  explain: (city: string) => get<Explanation>("/explain", { city }),
  districts: (month?: string) => get<DistrictStatus>("/districts", { month }),
  districtGeojson: () => get<GeoJSON.FeatureCollection>("/districts/geojson"),
  districtEval: () => get<DistrictEval>("/districts/evaluation"),
  districtHistory: (name: string, start?: string) =>
    get<DistrictRow[]>(`/districts/${encodeURIComponent(name)}`, { start }),
  heatEval: () => get<HeatEval>("/heat/evaluation"),
  validation: () => get<ValidationRow[]>("/validation"),
  dengue: () => get<DengueBacktest>("/dengue"),
};
