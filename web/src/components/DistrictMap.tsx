"use client";

import type { FeatureCollection } from "geojson";
import dynamic from "next/dynamic";
import type { DistrictMapLabels, DistrictValue } from "./DistrictMapInner";

const Inner = dynamic(() => import("./DistrictMapInner"), {
  ssr: false,
  loading: () => <div className="h-[600px] animate-pulse rounded-lg bg-surface-2" />,
});

export default function DistrictMap(props: {
  geojson: FeatureCollection;
  values: Record<string, DistrictValue>;
  labels: DistrictMapLabels;
}) {
  return <Inner {...props} />;
}
