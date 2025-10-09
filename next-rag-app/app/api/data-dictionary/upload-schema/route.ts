import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const formData = await request.formData()
    
    // Forward the form data to the backend
    const response = await fetch('http://reranker:8008/api/data-dictionary/upload-schema', {
      method: 'POST',
      body: formData
    })
    
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Error proxying schema upload request:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}