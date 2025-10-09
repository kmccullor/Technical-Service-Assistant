import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { conversations } from '@/lib/db/schema'
import { desc } from 'drizzle-orm'

export async function GET() {
  try {
    const recentConversations = await db
      .select()
      .from(conversations)
      .orderBy(desc(conversations.createdAt))
      .limit(20)

    return NextResponse.json(recentConversations)
  } catch (error) {
    console.error('Error fetching conversations:', error)
    return NextResponse.json(
      { error: 'Failed to fetch conversations' },
      { status: 500 }
    )
  }
}