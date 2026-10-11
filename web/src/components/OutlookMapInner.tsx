"use client";

import "leaflet/dist/leaflet.css";
import Link from "next/link";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import type { RiskLevel } from "@/lib/api";
import { citySlug } from "@/lib/format";

export interface MapPoint {
  name: string;
  lat: number;
  lon: number;
  risk: RiskLevel;
  probability: number;
  expected: number;
  normal: number;
}

const COLOR: Record<RiskLevel, string> = {
  low: "#0ca30c",
  elevated: "#fab219",
  high: "#d03b3b",
};

export default function OutlookMapInner({ points }: { points: MapPoint[] }) {
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const bounds: [[number, number], [number, number]] = points.length
    ? [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]]
    : [[20.7, 88.0], [26.6, 92.7]]; // Bangladesh
  return (
    <MapContainer
      bounds={bounds}
      boundsOptions={{ padding: [48, 48] }}
      scrollWheelZoom={false}
      className="h-[420px] w-full rounded-lg"
      aria-label="Map of drought risk by division"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {points.map((p) => (
        <CircleMarker
          key={p.name}
          center={[p.lat, p.lon]}
          radius={8 + 18 * p.probability}
          pathOptions={{ color: "#ffffff", weight: 2, fillColor: COLOR[p.risk], fillOpacity: 0.85 }}
        >
          <Tooltip direction="top" offset={[0, -6]} permanent>
            {p.name}
          </Tooltip>
          <Popup>
            <div className="space-y-1 text-sm">
              <div className="font-semibold">{p.name}</div>
              <div>
                Drought probability <b>{Math.round(p.probability * 100)}%</b>
              </div>
              <div>
                Expected {Math.round(p.expected)} mm (normal {Math.round(p.normal)} mm)
              </div>
              <Link href={`/city/${citySlug(p.name)}`} className="text-[var(--accent)] underline">
                Details →
              </Link>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
