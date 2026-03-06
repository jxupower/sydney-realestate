import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow images from Domain and OnTheHouse CDNs
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.domain.com.au" },
      { protocol: "https", hostname: "**.onthehouse.com.au" },
    ],
  },
  // Expose API URL to browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
