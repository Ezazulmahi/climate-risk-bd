"use client";

import dynamic from "next/dynamic";
import type { MapPoint } from "./OutlookMapInner";

// Leaflet touches `window` at import time, so the map renders only in the browser.
const Inner = dynamic(() => import("./OutlookMapInner"), {
  ssr: false,
  loading: () => <div className="h-[420px] animate-pulse rounded-lg bg-surface-2" />,
});

export default function OutlookMap({ points }: { points: MapPoint[] }) {
  return <Inner points={points} />;
}
