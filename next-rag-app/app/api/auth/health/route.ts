import { NextResponse } from 'next/server'

// Lightweight proxy health endpoint so the frontend AuthContext can always
// perform a same-origin health check without relying on rewrites.
// If the backend is unreachable we still return a degraded response instead of throwing.
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET() {
  try {
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/health`, { cache: 'no-store' })
    if (!r.ok) {
      // Surface upstream status but never fail catastrophically.
      return NextResponse.json({ status: 'degraded', upstream_status: r.status }, { status: 200 })
    }
    const data = await r.json().catch(() => ({}))
    return NextResponse.json({ status: 'ok', upstream: data }, { status: 200 })
  } catch (e: any) {
    return NextResponse.json({ status: 'offline', error: e?.message || 'unreachable' }, { status: 200 })
  }
}
