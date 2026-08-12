/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["localhost", "lh3.googleusercontent.com", "avatars.githubusercontent.com"],
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
      {
        source: "/api/ai/:path*",
        destination: `${process.env.NEXT_PUBLIC_AI_URL || "http://localhost:8001"}/api/v1/:path*`,
      },
    ]
  },
}

module.exports = nextConfig