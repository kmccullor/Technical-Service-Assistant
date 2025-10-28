import { NextRequest } from 'next/server'
import { performStreamingRAG } from '@/lib/rag'
import { db } from '@/lib/db'
import { conversations, messages } from '@/lib/db/schema'
import { and, desc, eq } from 'drizzle-orm'
import { fetchCurrentUser } from '@/lib/server/auth'

// Remove edge runtime for PostgreSQL compatibility
// export const runtime = 'edge'

interface ChatRequest {
  conversationId?: number
  message: string
  displayMessage?: string
  useWebFallback?: boolean
  temperature?: number
  maxTokens?: number
}

export async function POST(req: NextRequest) {
  try {
    const body: ChatRequest = await req.json()
    console.log('Chat API received body:', JSON.stringify(body, null, 2))
    
    const authHeader = req.headers.get('authorization')
    const user = await fetchCurrentUser(authHeader)
    if (!user) {
      return new Response('Unauthorized', { status: 401 })
    }

    const { conversationId, message, displayMessage, useWebFallback = true, temperature = 0.7, maxTokens = 1024 } = body

    if (!message || typeof message !== 'string' || !message.trim()) {
      console.log('Error: Message is required')
      return new Response('Message is required', { status: 400 })
    }

    console.log('Processing user message:', message)

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
    // Load prior conversation history (up to 30 most recent messages)
    const storedUserContent = (displayMessage ?? message).trim()
    const baseTitle = storedUserContent || 'New conversation'
    const conversationTitle = baseTitle.length > 50 ? `${baseTitle.slice(0, 50)}...` : baseTitle

    // Create or get conversation
    let convId: number
    if (conversationId) {
      const existingConversation = await db
        .select({ id: conversations.id })
        .from(conversations)
        .where(and(eq(conversations.id, conversationId), eq(conversations.userId, user.id)))
        .limit(1)

      if (existingConversation.length === 0) {
        return new Response('Conversation not found', { status: 404 })
      }
      convId = conversationId
    } else {
      const [newConversation] = await db
        .insert(conversations)
        .values({
          title: conversationTitle,
          userId: user.id,
        })
        .returning({ id: conversations.id })
      convId = newConversation.id
    }

    const historyRecords = await db
      .select({
        role: messages.role,
        content: messages.content,
        createdAt: messages.createdAt,
      })
      .from(messages)
      .where(eq(messages.conversationId, convId))
      .orderBy(desc(messages.createdAt))
      .limit(30)

    const orderedHistory = historyRecords.reverse()

    const historyText = orderedHistory
      .map((record) => {
        const roleLabel = record.role === 'assistant' ? 'Assistant' : 'User'
        return `${roleLabel}: ${record.content ?? ''}`
      })
      .join('\n')

    const promptSegments = []
    if (historyText) {
      promptSegments.push(`Previous conversation context:\n${historyText}`)
    }
    promptSegments.push(`Current user request:\n${message}`)
    const ragPrompt = promptSegments.join('\n\n')

    const ragResult = await performStreamingRAG(ragPrompt, {
      useWebFallback,
      temperature,
      maxTokens,
      confidenceThreshold: 0.3
    })

    // Save user message
    await db.insert(messages).values({
      conversationId: convId,
      role: 'user',
      content: storedUserContent
    })
    await db
      .update(conversations)
      .set({ updatedAt: new Date() })
      .where(eq(conversations.id, convId))

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
              content: source.content?.slice(0, 200) + '...',
            })),
          })
          await db
            .update(conversations)
            .set({ updatedAt: new Date() })
            .where(eq(conversations.id, convId))

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
