import { NextRequest } from 'next/server'
import { performStreamingRAG } from '@/lib/rag'
import { db } from '@/lib/db'
import { conversations, messages, type NewMessage } from '@/lib/db/schema'

// Remove edge runtime for PostgreSQL compatibility
// export const runtime = 'edge'

interface ChatRequest {
  conversationId?: number
  messages: Array<{
    role: 'user' | 'assistant' | 'system'
    content: string
  }>
  useWebFallback?: boolean
  temperature?: number
  maxTokens?: number
}

export async function POST(req: NextRequest) {
  try {
    const body: ChatRequest = await req.json()
    console.log('Chat API received body:', JSON.stringify(body, null, 2))
    
    const { conversationId, messages: chatMessages, useWebFallback = true, temperature = 0.7, maxTokens = 1024 } = body

    if (!chatMessages || chatMessages.length === 0) {
      console.log('Error: Messages are required')
      return new Response('Messages are required', { status: 400 })
    }

    // Get the latest user message
    const userMessage = chatMessages[chatMessages.length - 1]
    if (userMessage.role !== 'user') {
      console.log('Error: Last message must be from user, got:', userMessage.role)
      return new Response('Last message must be from user', { status: 400 })
    }

    console.log('Processing user message:', userMessage.content)

    // Check if we should use local models or OpenAI
    const useLocalModels = process.env.USE_LOCAL_MODELS === 'true'
    const openaiKey = process.env.OPENAI_API_KEY
    
    console.log('Model configuration:', { useLocalModels, hasOpenaiKey: !!openaiKey })

    if (!useLocalModels && (!openaiKey || openaiKey === 'sk-your-openai-api-key-here')) {
      console.log('Neither local models nor OpenAI API key configured, returning test response')
      
      // Create a simple test response without RAG
      const encoder = new TextEncoder()
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'content',
            content: 'Hello! I\'m your RAG assistant. To enable full functionality, please configure your OpenAI API key in the .env.local file or set USE_LOCAL_MODELS=true. '
          })}\n\n`))
          
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'content', 
            content: 'I can see you have ' + 'documents loaded in the database, but I need either local models or an OpenAI API key to search and answer questions about them.'
          })}\n\n`))
          
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'citations',
            citations: [],
            searchType: 'fallback'
          })}\n\n`))
          
          controller.close()
        }
      })

      return new Response(stream, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        }
      })
    }

    // Perform RAG search and generation
    const ragResult = await performStreamingRAG(userMessage.content, {
      useWebFallback,
      temperature,
      maxTokens,
      confidenceThreshold: 0.3
    })

    // Create or get conversation
    let convId: number = conversationId || 0
    if (!conversationId) {
      const [newConversation] = await db.insert(conversations).values({
        title: userMessage.content.slice(0, 50) + (userMessage.content.length > 50 ? '...' : '')
      }).returning()
      convId = newConversation.id
    }

    // Save user message
    await db.insert(messages).values({
      conversationId: convId,
      role: 'user',
      content: userMessage.content
    })

    // Create streaming response
    const encoder = new TextEncoder()
    let fullResponse = ''

    const stream = new ReadableStream({
      async start(controller) {
        try {
          // Send conversation ID and sources first
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'conversation_id',
            conversationId: convId
          })}\n\n`))

          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'sources',
            sources: ragResult.sources,
            confidence: ragResult.confidence,
            method: ragResult.method
          })}\n\n`))

          // Stream the text response
          for await (const chunk of ragResult.textStream) {
            fullResponse += chunk
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({
              type: 'token',
              token: chunk
            })}\n\n`))
          }

          // Save assistant message
          await db.insert(messages).values({
            conversationId: convId,
            role: 'assistant',
            content: fullResponse,
            citations: ragResult.sources.map(source => ({
              title: source.document.title,
              source: source.document.source,
              content: source.content?.slice(0, 200) + '...'
            }))
          })

          // Send completion
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'done',
            messageId: 'temp-id' // Would be actual ID in real implementation
          })}\n\n`))

          controller.close()
        } catch (error) {
          console.error('Streaming error:', error)
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({
            type: 'error',
            error: 'An error occurred while processing your request'
          })}\n\n`))
          controller.close()
        }
      }
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      }
    })

  } catch (error) {
    console.error('Chat API error:', error)
    return new Response('Internal server error', { status: 500 })
  }
}