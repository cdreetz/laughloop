import type { NextConfig } from "next";

const backendUrl = process.env.NEXT_PUBLIC_API_URL;

const nextConfig: NextConfig = {
  // Only proxy /api to localhost in local dev (no NEXT_PUBLIC_API_URL set)
  async rewrites() {
    if (backendUrl) return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
