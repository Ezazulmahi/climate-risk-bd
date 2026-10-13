import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image; Vercel ignores this.
  output: "standalone",
  // React's dev-only double mount breaks Leaflet maps ("Map container is being
  // reused"); production renders are unaffected either way.
  reactStrictMode: false,
};

export default nextConfig;
