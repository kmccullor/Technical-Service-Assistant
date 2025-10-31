import { NextRequest, NextResponse } from 'next/server'
import { join } from 'path'
import { readdir, rmdir, stat } from 'fs/promises'
import { existsSync } from 'fs'

interface CleanupStats {
  sessionsDeleted: number
  filesDeleted: number
  totalSizeFreed: number
}

async function getDirectorySize(dirPath: string): Promise<number> {
  let size = 0
  try {
    const items = await readdir(dirPath, { withFileTypes: true })

    for (const item of items) {
      const itemPath = join(dirPath, item.name)

      if (item.isDirectory()) {
        size += await getDirectorySize(itemPath)
      } else {
        const stats = await stat(itemPath)
        size += stats.size
      }
    }
  } catch (error) {
    // Directory might not exist or be inaccessible
  }

  return size
}

export async function POST(request: NextRequest): Promise<NextResponse<CleanupStats>> {
  try {
    const TEMP_DIR = join(process.cwd(), 'temp-uploads')
    const TWO_HOURS_MS = 2 * 60 * 60 * 1000 // 2 hours in milliseconds

    let stats: CleanupStats = {
      sessionsDeleted: 0,
      filesDeleted: 0,
      totalSizeFreed: 0
    }

    if (!existsSync(TEMP_DIR)) {
      return NextResponse.json(stats)
    }

    try {
      const sessions = await readdir(TEMP_DIR)

      for (const sessionId of sessions) {
        const sessionDir = join(TEMP_DIR, sessionId)

        try {
          const sessionStats = await stat(sessionDir)
          const ageMs = Date.now() - sessionStats.mtime.getTime()

          if (ageMs > TWO_HOURS_MS) {
            // Calculate size before deletion
            const dirSize = await getDirectorySize(sessionDir)

            // Count files in directory
            const items = await readdir(sessionDir)

            // Remove the session directory
            await rmdir(sessionDir, { recursive: true })

            stats.sessionsDeleted++
            stats.filesDeleted += items.length
            stats.totalSizeFreed += dirSize

            console.log(`Cleaned up expired session: ${sessionId} (${items.length} files, ${dirSize} bytes)`)
          }
        } catch (sessionError) {
          console.error(`Error processing session ${sessionId}:`, sessionError)
        }
      }

      // Also notify reranker to clean up its in-memory sessions
      try {
        const rerankerBaseUrl = process.env.RERANKER_BASE_URL || 'http://reranker:8008'
        await fetch(`${rerankerBaseUrl}/api/temp-cleanup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
      } catch (rerankerError) {
        console.warn('Could not notify reranker for cleanup:', rerankerError)
      }

      console.log(`Cleanup completed: ${stats.sessionsDeleted} sessions, ${stats.filesDeleted} files, ${(stats.totalSizeFreed / 1024 / 1024).toFixed(2)}MB freed`)

      return NextResponse.json(stats)

    } catch (dirError) {
      console.error('Directory cleanup error:', dirError)
      return NextResponse.json(stats)
    }

  } catch (error) {
    console.error('Cleanup error:', error)
    return NextResponse.json({
      sessionsDeleted: 0,
      filesDeleted: 0,
      totalSizeFreed: 0
    }, { status: 500 })
  }
}

export async function GET(): Promise<NextResponse> {
  try {
    const TEMP_DIR = join(process.cwd(), 'temp-uploads')

    if (!existsSync(TEMP_DIR)) {
      return NextResponse.json({
        sessions: 0,
        totalSize: 0,
        oldestSession: null
      })
    }

    const sessions = await readdir(TEMP_DIR)
    let totalSize = 0
    let oldestTime = Date.now()

    for (const sessionId of sessions) {
      const sessionDir = join(TEMP_DIR, sessionId)

      try {
        const dirSize = await getDirectorySize(sessionDir)
        const sessionStats = await stat(sessionDir)

        totalSize += dirSize
        if (sessionStats.mtime.getTime() < oldestTime) {
          oldestTime = sessionStats.mtime.getTime()
        }
      } catch (error) {
        // Skip inaccessible sessions
      }
    }

    return NextResponse.json({
      sessions: sessions.length,
      totalSize,
      totalSizeMB: (totalSize / 1024 / 1024).toFixed(2),
      oldestSession: sessions.length > 0 ? new Date(oldestTime).toISOString() : null
    })

  } catch (error) {
    console.error('Status check error:', error)
    return NextResponse.json({ error: 'Status check failed' }, { status: 500 })
  }
}
