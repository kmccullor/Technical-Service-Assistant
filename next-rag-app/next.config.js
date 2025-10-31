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
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          { key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https:;" },
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
