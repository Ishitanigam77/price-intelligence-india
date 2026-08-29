import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Required for the production frontend image (`frontend/Dockerfile` copies `.next/standalone`).
  // Does not change runtime routing or page behavior; `next start` continues to work locally.
  output: "standalone",
};

export default nextConfig;
