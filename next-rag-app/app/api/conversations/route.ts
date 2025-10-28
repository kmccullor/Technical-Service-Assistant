import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { conversations } from '@/lib/db/schema'
import { and, desc, eq, gte } from 'drizzle-orm'
import { fetchCurrentUser } from '@/lib/server/auth'

export async function GET(req: NextRequest) {
  try {
    const authHeader = req.headers.get('authorization')
    const user = await fetchCurrentUser(authHeader)
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const limitParam = Number.parseInt(req.nextUrl.searchParams.get('limit') ?? '', 10)
    const limit = Number.isFinite(limitParam) ? Math.min(Math.max(limitParam, 1), 30) : 30
    const cutoffDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)

    const recentConversations = await db
      .select({
        id: conversations.id,
        title: conversations.title,
        createdAt: conversations.createdAt,
        updatedAt: conversations.updatedAt,
        lastReviewedAt: conversations.lastReviewedAt,
      })
      .from(conversations)
      .where(
        and(
          eq(conversations.userId, user.id),
          gte(conversations.createdAt, cutoffDate)
        )
      )
      .orderBy(desc(conversations.updatedAt), desc(conversations.createdAt))
      .limit(limit)

    return NextResponse.json(recentConversations)
  } catch (error) {
    console.error('Error fetching conversations:', error)
    return NextResponse.json(
      { error: 'Failed to fetch conversations' },
      { status: 500 }
    )
  }
}
