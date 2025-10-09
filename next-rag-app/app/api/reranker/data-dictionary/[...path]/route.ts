import { NextRequest, NextResponse } from 'next/server'

const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/')
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${RERANKER_BASE_URL}/api/data-dictionary/${path}${searchParams ? `?${searchParams}` : ''}`

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Data dictionary API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch data from reranker service' },
      { status: 500 }
    )
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/')
  const url = `${RERANKER_BASE_URL}/api/data-dictionary/${path}`
  const body = await request.json()

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Data dictionary API error:', error)
    return NextResponse.json(
      { error: 'Failed to post data to reranker service' },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/')
  const url = `${RERANKER_BASE_URL}/api/data-dictionary/${path}`
  const body = await request.json()

  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Data dictionary API error:', error)
    return NextResponse.json(
      { error: 'Failed to update data in reranker service' },
      { status: 500 }
    )
  }
}