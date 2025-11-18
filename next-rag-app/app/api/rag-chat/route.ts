import { NextRequest } from 'next/server'
import { buildRerankerUrl } from '@/lib/rerankerConfig'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    console.log('[RAG PROXY] incoming request body:', body)

    const rerankerUrl = buildRerankerUrl('/api/rag-chat')

    console.log('[RAG PROXY] proxying to', rerankerUrl)

    const response = await fetch(rerankerUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': req.headers.get('authorization') || '',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      console.error('[RAG PROXY] reranker response status:', response.status)
      throw new Error(`Reranker error: ${response.status}`)
    }

    // For streaming responses, return the stream directly
    if (body.stream) {
      return new Response(response.body, {
        headers: {
          'Content-Type': response.headers.get('Content-Type') || 'application/json',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    }

    // For non-streaming, return the JSON
    const data = await response.json()
    return new Response(JSON.stringify(data), {
      headers: {
        'Content-Type': 'application/json',
      },
    })

  } catch (error) {
    console.error('RAG chat proxy error:', error)
    return new Response('Internal server error', { status: 500 })
  }
}
