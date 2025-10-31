import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const response = await fetch('http://reranker:8008/api/data-dictionary/health')
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying health request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
