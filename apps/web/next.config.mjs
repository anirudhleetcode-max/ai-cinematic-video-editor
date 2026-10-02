import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: here,
  webpack: (config) => {
    config.resolve.alias["@"] = here;
    return config;
  },
};
export default nextConfig;
