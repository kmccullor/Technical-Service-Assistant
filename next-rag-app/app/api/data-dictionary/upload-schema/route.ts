import { NextResponse } from 'next/server'

const BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(request: Request) {
  const auth = request.headers.get('authorization') ?? ''
  try {
    const formData = await request.formData()

    // Forward the form data to the backend
    const response = await fetch(`${BASE_URL}/api/data-dictionary/upload-schema`, {
      method: 'POST',
      headers: auth ? { Authorization: auth } : undefined,
      body: formData
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Error proxying schema upload request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
