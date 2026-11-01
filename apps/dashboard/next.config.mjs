/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export: the demo needs no server, so it can be hosted on S3 + CloudFront.
  output: "export",
  poweredByHeader: false,
};

export default nextConfig;
