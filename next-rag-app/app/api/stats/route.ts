import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { documents, documentChunks } from '@/lib/db/schema'
import { sql } from 'drizzle-orm'

export async function GET() {
  try {
    // Get document count
    const docCount = await db.select({ 
      count: sql<number>`count(*)::int` 
    }).from(documents)

    // Get chunk count
    const chunkCount = await db.select({ 
      count: sql<number>`count(*)::int` 
    }).from(documentChunks)

    return NextResponse.json({
      documents: docCount[0].count,
      chunks: chunkCount[0].count
    })
  } catch (error) {
    console.error('Error fetching stats:', error)
    return NextResponse.json(
      { error: 'Failed to fetch stats' },
      { status: 500 }
    )
  }
}