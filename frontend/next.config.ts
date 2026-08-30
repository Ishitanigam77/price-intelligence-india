import type { NextConfig } from "next";

const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.clerk.accounts.dev https://*.clerk.com https://clerk.accounts.dev",
  "worker-src 'self' blob:",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: https: blob:",
  "font-src 'self' https://fonts.gstatic.com data:",
  [
    "connect-src 'self'",
    apiOrigin,
    "https://*.clerk.accounts.dev",
    "https://*.clerk.com",
    "https://clerk.accounts.dev",
    "wss://*.clerk.accounts.dev",
    "wss://*.clerk.com",
  ]
    .filter(Boolean)
    .join(" "),
  "frame-src https://*.clerk.accounts.dev https://*.clerk.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Required for the production frontend image (`frontend/Dockerfile` copies `.next/standalone`).
  // Does not change runtime routing or page behavior; `next start` continues to work locally.
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
