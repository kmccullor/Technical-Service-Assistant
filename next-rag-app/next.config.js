/** @type {import('next').NextConfig} */
const nextConfig = {
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
  }
}

module.exports = nextConfig