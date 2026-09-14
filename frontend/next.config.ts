import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Expose the backend URL to the browser.
  // Set NEXT_PUBLIC_API_BASE in Vercel to the deployed Render backend URL.
  // Falls back to localhost for local development.
  env: {
    NEXT_PUBLIC_API_BASE:
      process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
