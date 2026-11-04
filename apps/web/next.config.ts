import type { NextConfig } from "next";

const config: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next-v1",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; connect-src 'self'; img-src 'self' data: blob:; font-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
          },
        ],
      },
    ];
  },
};
export default config;
