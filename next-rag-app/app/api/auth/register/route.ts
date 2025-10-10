import { NextRequest, NextResponse } from 'next/server'

// Explicit proxy for user self-registration. Always run inside docker where 'reranker' hostname resolves.
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch (_) {}
    return NextResponse.json(data ?? { detail: text || 'Registration failed' }, { status: r.status })
  } catch (e: any) {
    return NextResponse.json({ detail: 'Registration proxy error', error: e?.message }, { status: 500 })
  }
}
