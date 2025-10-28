/** @type {import('next').NextConfig} */
const RERANKER_INTERNAL_URL = process.env.RERANKER_INTERNAL_URL || 'http://reranker:8008';

const nextConfig = {
  poweredByHeader: false,
  experimental: {
    serverComponentsExternalPackages: ['pg', 'pgvector']
  },
  output: 'standalone',
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      'pg-native': false,
    }
    return config
  },
  env: {
    DATABASE_URL: process.env.DATABASE_URL,
    // Expose optional backend URL for client-side code (AuthContext) when direct calls are preferred
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || '',
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Cache-Control', value: 'no-store' },
        ],
      },
    ];
  },
  // NOTE: We now define explicit API route proxies under app/api/auth/* so a rewrite is unnecessary.
  // Leaving rewrites disabled avoids double proxying when running behind another reverse proxy.
  // async rewrites() { ... }
};

module.exports = nextConfig;
