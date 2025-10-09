import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    if (r.ok) return NextResponse.json(data, { status: r.status })
    return NextResponse.json(data ?? { detail: text || 'Verification failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Verify email proxy error', error: e?.message }, { status: 500 })
  }
}
