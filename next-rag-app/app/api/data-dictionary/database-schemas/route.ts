import { NextResponse } from 'next/server'

const BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(request: Request) {
  const auth = request.headers.get('authorization') ?? ''
  try {
    const url = new URL(request.url)
    const searchParams = url.searchParams.toString()
    const fetchUrl = `${BASE_URL}/api/data-dictionary/database-schemas${searchParams ? `?${searchParams}` : ''}`

    const response = await fetch(fetchUrl, {
      headers: auth ? { Authorization: auth } : undefined,
    })
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Error proxying database schemas request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
