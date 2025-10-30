import { NextRequest, NextResponse } from 'next/server'

const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const res = await fetch(`${RERANKER_BASE_URL}/api/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const text = await res.text()
    let data: any = null
    try { data = JSON.parse(text) } catch (_) {}
    return NextResponse.json(data ?? { detail: text || 'Failed to reset password' }, { status: res.status })
  } catch (error: any) {
    return NextResponse.json(
      { detail: 'Reset password proxy error', error: error?.message },
      { status: 500 },
    )
  }
}
