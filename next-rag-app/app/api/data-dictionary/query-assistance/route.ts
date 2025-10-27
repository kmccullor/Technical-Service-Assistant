import { NextResponse } from 'next/server'

const BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(request: Request) {
  const auth = request.headers.get('authorization') ?? ''
  try {
    const body = await request.json()
    const response = await fetch(`${BASE_URL}/api/data-dictionary/query-assistance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(auth ? { Authorization: auth } : {}),
      },
      body: JSON.stringify(body)
    })
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Error proxying query assistance request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
