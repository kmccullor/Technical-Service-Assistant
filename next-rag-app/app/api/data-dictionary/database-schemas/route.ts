import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const searchParams = url.searchParams.toString()
    const fetchUrl = `http://reranker:8008/api/data-dictionary/database-schemas${searchParams ? `?${searchParams}` : ''}`
    
    const response = await fetch(fetchUrl)
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying database schemas request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}