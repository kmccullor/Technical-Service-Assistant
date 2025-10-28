import { NextRequest, NextResponse } from 'next/server'

const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const auth = req.headers.get('authorization') || ''

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (auth) {
      headers['Authorization'] = auth
    }

    const response = await fetch(`${RERANKER_BASE_URL}/api/documents/list`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })

    const text = await response.text()
    let data: any = null
    try {
      data = JSON.parse(text)
    } catch (_) {}

    return NextResponse.json(
      data ?? { detail: text || 'Failed to fetch documents' },
      { status: response.status }
    )
  } catch (error) {
    console.error('Documents list proxy failed:', error)
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { detail: 'Documents proxy error', error: message },
      { status: 500 }
    )
  }
}
