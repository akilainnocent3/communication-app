import type { NextConfig } from "next";

const backend = (process.env.CM_API_ORIGIN || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Django owns trailing slashes; the browser only ever talks to this origin (session + CSRF cookies stay same-origin).
  skipTrailingSlashRedirect: true,
  // The dev-mode "N" badge sits on top of the sidebar account block (and in every E2E screenshot).
  devIndicators: false,
  // Dev server only: allow loading dev assets when browsing via 127.0.0.1 (Playwright, Codespaces port forward).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    proxyTimeout: 120_000,
    // Attachments up to Gmail's 25 MB limit pass through the /api proxy.
    proxyClientMaxBodySize: "30mb",
  },
  async rewrites() {
    return [
      { source: "/api/v1/:path*/", destination: `${backend}/api/v1/:path*/` },
      { source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
