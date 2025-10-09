import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const response = await fetch('http://reranker:8008/api/data-dictionary/extract-schema', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    })
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Error proxying schema extraction request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}