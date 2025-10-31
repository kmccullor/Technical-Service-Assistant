import { NextRequest, NextResponse } from 'next/server'
import { join } from 'path'

interface AnalyzeRequest {
  sessionId: string
  query: string
  maxResults?: number
}

interface AnalyzeResponse {
  sessionId: string
  query: string
  fileName: string
  results: Array<{
    content: string
    similarity: number
    rank: number
  }>
  confidence: number
  response: string
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body: AnalyzeRequest = await request.json()
    const { sessionId, query, maxResults = 5 } = body

    if (!sessionId || !query) {
      return NextResponse.json(
        { error: 'Session ID and query are required' },
        { status: 400 }
      )
    }

    // First, process the uploaded file if not already processed
    const tempDir = join(process.cwd(), 'temp-uploads', sessionId)
    const metadataPath = join(tempDir, 'metadata.json')

    try {
      const { readFile } = await import('fs/promises')
      const metadata = JSON.parse(await readFile(metadataPath, 'utf-8'))
      const filePath = join(tempDir, metadata.safeFileName)

      // Send file to reranker for processing
      const rerankerBaseUrl = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

      // First, process the document
      const processResponse = await fetch(`${rerankerBaseUrl}/api/temp-process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          file_path: filePath,
          file_name: metadata.originalName
        })
      })

      if (!processResponse.ok) {
        const errorText = await processResponse.text()
        console.error('Processing failed:', errorText)
        return NextResponse.json(
          { error: 'Failed to process document' },
          { status: 500 }
        )
      }

      // Then analyze the document
      const analyzeResponse = await fetch(`${rerankerBaseUrl}/api/temp-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          query,
          max_results: maxResults
        })
      })

      if (!analyzeResponse.ok) {
        const errorText = await analyzeResponse.text()
        console.error('Analysis failed:', errorText)
        return NextResponse.json(
          { error: 'Failed to analyze document' },
          { status: 500 }
        )
      }

      const analysisResult: AnalyzeResponse = await analyzeResponse.json()

      console.log(`Analysis complete for session ${sessionId}: ${query}`)

      return NextResponse.json(analysisResult)

    } catch (fileError) {
      console.error('File access error:', fileError)
      return NextResponse.json(
        { error: 'Session not found or file no longer available' },
        { status: 404 }
      )
    }

  } catch (error) {
    console.error('Analysis error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url)
    const sessionId = searchParams.get('sessionId')

    if (!sessionId) {
      return NextResponse.json({ error: 'Session ID required' }, { status: 400 })
    }

    // Get session info from reranker
    const rerankerBaseUrl = process.env.RERANKER_BASE_URL || 'http://reranker:8008'
    const response = await fetch(`${rerankerBaseUrl}/api/temp-session/${sessionId}`)

    if (!response.ok) {
      return NextResponse.json({ error: 'Session not found' }, { status: 404 })
    }

    const sessionInfo = await response.json()
    return NextResponse.json(sessionInfo)

  } catch (error) {
    console.error('Session info error:', error)
    return NextResponse.json(
      { error: 'Failed to get session info' },
      { status: 500 }
    )
  }
}
