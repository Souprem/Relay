import type { NextConfig } from "next";

// A fully static site: `next build` writes out/, which any static host can serve.
// NEXT_PUBLIC_BASE_PATH is left empty locally; a later GitHub Pages build sets it to "/Relay".
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
  reactStrictMode: true,
};

export default nextConfig;
