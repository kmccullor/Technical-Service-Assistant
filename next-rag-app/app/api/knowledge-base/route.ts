import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { documentChunks } from '@/lib/db/schema'
import { sql } from 'drizzle-orm'

export async function GET(req: NextRequest) {
  try {
    // Get document count and chunk count
    const [stats] = await db
      .select({
        documents: sql<number>`COUNT(DISTINCT ${documentChunks.documentId})::int`,
        chunks: sql<number>`COUNT(*)::int`,
        avgChunkLength: sql<number>`AVG(${documentChunks.contentLength})::int`,
        totalContent: sql<number>`SUM(${documentChunks.contentLength})::bigint`
      })
      .from(documentChunks)

    // Get document titles and counts
    const documentList = await db
      .select({
        documentId: documentChunks.documentId,
        title: sql<string>`MAX(${documentChunks.metadata}->>'document')`,
        chunkCount: sql<number>`COUNT(*)::int`
      })
      .from(documentChunks)
      .groupBy(documentChunks.documentId)
      .orderBy(sql`MAX(${documentChunks.metadata}->>'document')`)

    return Response.json({
      stats: {
        documents: stats.documents,
        chunks: stats.chunks,
        avgChunkLength: stats.avgChunkLength,
        totalContent: Number(stats.totalContent)
      },
      documents: documentList
    })

  } catch (error) {
    console.error('Knowledge base stats error:', error)
    return new Response('Internal server error', { status: 500 })
  }
}