"use client";

import "leaflet/dist/leaflet.css";
import type { Feature, FeatureCollection } from "geojson";
import type { Layer, PathOptions } from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import { CATEGORY_COLOR } from "@/lib/colors";

export interface DistrictValue {
  category: string | null;
  prob: number | null;
  spi3: number | null;
  precip: number | null;
  normal: number | null;
}

export interface DistrictMapLabels {
  current: string;
  outlook: string;
  noDrought: string;
  outlookLegend: string;
  rainfall: string;
  normal: string;
  chance: string;
  categories: Record<string, string>;
}

// One-hue (orange) sequential ramp for probability, light = low.
const PROB_BINS: [number, string, string][] = [
  [0.1, "#fde5d8", "< 10%"],
  [0.25, "#f9b99a", "10–25%"],
  [0.4, "#f08c5f", "25–40%"],
  [0.6, "#eb6834", "40–60%"],
  [1.01, "#b94a1e", "≥ 60%"],
];

/** Re-measure once the container has its real size (it is 0×0 while the chunk loads). */
function Resize() {
  const map = useMap();
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 200);
    return () => clearTimeout(t);
  }, [map]);
  return null;
}

const probColor = (p: number) => PROB_BINS.find(([ub]) => p < ub)?.[1] ?? PROB_BINS[4][1];

export default function DistrictMapInner({
  geojson,
  values,
  labels,
}: {
  geojson: FeatureCollection;
  values: Record<string, DistrictValue>;
  labels: DistrictMapLabels;
}) {
  const [view, setView] = useState<"current" | "outlook">("current");

  const style = useMemo(
    () =>
      (feature?: Feature): PathOptions => {
        const v = values[feature?.properties?.name];
        const fill =
          view === "current"
            ? v?.category
              ? CATEGORY_COLOR[v.category]
              : "transparent"
            : v?.prob != null
              ? probColor(v.prob)
              : "transparent";
        return { color: "#6f6e69", weight: 0.8, fillColor: fill, fillOpacity: 0.75 };
      },
    [values, view],
  );

  const onEach = (feature: Feature, layer: Layer) => {
    const name = feature.properties?.name as string;
    const v = values[name];
    const cat = v?.category ? `${v.category} · ${labels.categories[v.category]}` : labels.noDrought;
    const rows = [
      `<b>${name}</b>`,
      cat,
      v?.spi3 != null ? `SPI-3 ${v.spi3.toFixed(2)}` : "",
      v?.precip != null && v?.normal != null
        ? `${labels.rainfall} ${Math.round(v.precip)} mm (${labels.normal} ${Math.round(v.normal)} mm)`
        : "",
      v?.prob != null ? `${labels.chance} ${Math.round(v.prob * 100)}%` : "",
    ].filter(Boolean);
    layer.bindTooltip(rows.join("<br/>"), { sticky: true });
  };

  return (
    <div>
      <div className="mb-3 inline-flex rounded-full border border-line p-0.5 text-sm" role="tablist">
        {(["current", "outlook"] as const).map((v) => (
          <button
            key={v}
            role="tab"
            aria-selected={view === v}
            onClick={() => setView(v)}
            className={`rounded-full px-3 py-1 ${view === v ? "bg-surface-2 font-medium text-ink" : "text-ink-2"}`}
          >
            {v === "current" ? labels.current : labels.outlook}
          </button>
        ))}
      </div>
      <MapContainer
        center={[23.65, 90.35]}
        zoom={6.75}
        zoomSnap={0.25}
        scrollWheelZoom={false}
        className="h-[560px] w-full rounded-lg"
        aria-label="Map of drought by district"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Boundaries: geoBoundaries (BBS/OCHA) · Rainfall: CHIRPS'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON key={view} data={geojson} style={style} onEachFeature={onEach} />
        <Resize />
      </MapContainer>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="Legend">
        {view === "current"
          ? [["", labels.noDrought], ...Object.entries(labels.categories)].map(([code, label]) => (
              <span key={code || "none"} className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block h-3 w-4 rounded-sm border border-line"
                  style={{ background: code ? CATEGORY_COLOR[code] : "transparent" }}
                />
                {code ? `${code} ${label}` : label}
              </span>
            ))
          : [
              <span key="title" className="font-medium">
                {labels.outlookLegend}:
              </span>,
              ...PROB_BINS.map(([, color, text]) => (
                <span key={text} className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-3 w-4 rounded-sm border border-line"
                    style={{ background: color }}
                  />
                  {text}
                </span>
              )),
            ]}
      </div>
    </div>
  );
}
