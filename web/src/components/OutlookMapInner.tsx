"use client";

import "leaflet/dist/leaflet.css";
import Link from "next/link";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { RiskLevel } from "@/lib/api";
import { citySlug } from "@/lib/format";

export interface MapPoint {
  name: string;
  label: string;
  lat: number;
  lon: number;
  risk: RiskLevel;
  probability: number;
  probabilityText: string;
  rainText: string;
  droughtText: string;
}

const COLOR: Record<RiskLevel, string> = {
  low: "#0ca30c",
  elevated: "#fab219",
  high: "#d03b3b",
};

/** Re-measure once the container has its real size (it is 0×0 while the chunk loads). */
function Resize() {
  const map = useMap();
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 200);
    return () => clearTimeout(t);
  }, [map]);
  return null;
}

export default function OutlookMapInner({ points }: { points: MapPoint[] }) {
  return (
    <MapContainer
      center={[23.75, 90.3]}
      zoom={6.5}
      zoomSnap={0.25}
      scrollWheelZoom={false}
      className="h-[420px] w-full rounded-lg"
      aria-label="Map of drought risk by division"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Resize />
      {points.map((p) => (
        <CircleMarker
          key={p.name}
          center={[p.lat, p.lon]}
          radius={8 + 18 * p.probability}
          pathOptions={{ color: "#ffffff", weight: 2, fillColor: COLOR[p.risk], fillOpacity: 0.85 }}
        >
          <Tooltip direction="top" offset={[0, -6]} permanent>
            {p.label}
          </Tooltip>
          <Popup>
            <div className="space-y-1 text-sm">
              <div className="font-semibold">{p.label}</div>
              <div>
                {p.droughtText} <b>{p.probabilityText}</b>
              </div>
              <div>{p.rainText}</div>
              <Link href={`/city/${citySlug(p.name)}`} className="text-[var(--accent)] underline">
                →
              </Link>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
