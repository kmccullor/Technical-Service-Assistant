import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(req: NextRequest) {
  try {
    const auth = req.headers.get('authorization') || ''
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: { 'Authorization': auth }
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    return NextResponse.json(data ?? { detail: text || 'Profile failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Profile proxy error', error: e?.message }, { status: 500 })
  }
}
