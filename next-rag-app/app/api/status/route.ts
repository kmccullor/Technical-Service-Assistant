import { NextResponse } from 'next/server'
import { localModelService } from '@/lib/local-models'

export async function GET() {
  try {
    const isLocalMode = process.env.USE_LOCAL_MODELS === 'true'
    const ollamaAvailable = await localModelService.isAvailable()
    const models = ollamaAvailable ? await localModelService.listModels() : []

    const webSearchEnabled = (process.env.WEB_SEARCH_ENABLED === 'true') || (process.env.USE_RERANKER_WEBSEARCH === 'true')

    return NextResponse.json({
      localMode: isLocalMode,
      ollamaAvailable,
      ollamaUrl: process.env.OLLAMA_BASE_URL || 'http://localhost:11434',
      models: {
        embedding: process.env.EMBEDDING_MODEL,
        chat: process.env.CHAT_MODEL,
        available: models
      },
      config: {
        rerankerEnabled: process.env.RERANKER_ENABLED === 'true',
        webSearchEnabled,
        confidenceThreshold: process.env.CONFIDENCE_THRESHOLD
      }
    })
  } catch (error) {
    console.error('Status check error:', error)
    return NextResponse.json(
      { error: 'Failed to check status' },
      { status: 500 }
    )
  }
}