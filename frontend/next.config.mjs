/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lets a second dev server (e.g. the end-to-end test) run beside your usual one without sharing .next/
  distDir: process.env.NEXT_DIST_DIR || ".next",
  poweredByHeader: false,
};
export default nextConfig;
