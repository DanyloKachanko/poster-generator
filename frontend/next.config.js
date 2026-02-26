/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.leonardo.ai',
      },
      {
        protocol: 'https',
        hostname: 'designapi.dovshop.org',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8001',
      },
    ],
  },
  async redirects() {
    return [
      // Root → Create
      { source: '/', destination: '/create', permanent: false },
      // Create module
      { source: '/batch', destination: '/create/batch', permanent: false },
      { source: '/history', destination: '/create/history', permanent: false },
      // Products module
      { source: '/seo', destination: '/products/seo', permanent: false },
      { source: '/sync-etsy', destination: '/products/sync', permanent: false },
      // Publish module
      { source: '/schedule', destination: '/publish', permanent: false },
      { source: '/calendar', destination: '/publish/calendar', permanent: false },
      { source: '/dovshop', destination: '/publish/dovshop', permanent: false },
      // Monitor module
      { source: '/dashboard', destination: '/monitor', permanent: false },
      { source: '/analytics', destination: '/monitor/analytics', permanent: false },
      { source: '/competitors', destination: '/monitor/competitors', permanent: false },
      { source: '/competitors/discover', destination: '/monitor/competitors/discover', permanent: false },
    ];
  },
}

module.exports = nextConfig
