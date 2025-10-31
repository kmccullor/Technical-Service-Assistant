import { NextRequest, NextResponse } from 'next/server'
import { writeFile, mkdir } from 'fs/promises'
import { join } from 'path'
import { randomUUID } from 'crypto'
import { existsSync } from 'fs'

// Allowed file types for troubleshooting uploads
const ALLOWED_EXTENSIONS = [
  '.txt', '.log', '.csv', '.json', '.sql', '.pdf',
  '.xml', '.conf', '.config', '.ini', '.properties',
  '.out', '.err', '.trace', '.dump', '.png', '.jpg',
  '.jpeg', '.gif', '.bmp', '.tiff', '.webp'
]

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const TEMP_DIR = join(process.cwd(), 'temp-uploads')

interface UploadResponse {
  success: boolean
  sessionId?: string
  fileName?: string
  fileSize?: number
  message?: string
  error?: string
}

export async function POST(request: NextRequest): Promise<NextResponse<UploadResponse>> {
  try {
    // Ensure temp directory exists
    if (!existsSync(TEMP_DIR)) {
      await mkdir(TEMP_DIR, { recursive: true })
    }

    const formData = await request.formData()
    const file = formData.get('file') as File

    if (!file) {
      return NextResponse.json({
        success: false,
        error: 'No file provided'
      }, { status: 400 })
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json({
        success: false,
        error: `File size exceeds maximum limit of ${MAX_FILE_SIZE / 1024 / 1024}MB`
      }, { status: 400 })
    }

    // Validate file extension
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    if (!ALLOWED_EXTENSIONS.includes(fileExtension)) {
      return NextResponse.json({
        success: false,
        error: `File type not supported. Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`
      }, { status: 400 })
    }

    // Generate session ID and save file
    const sessionId = randomUUID()
    const sessionDir = join(TEMP_DIR, sessionId)
    await mkdir(sessionDir, { recursive: true })

    const bytes = await file.arrayBuffer()
    const buffer = Buffer.from(bytes)

    const safeFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_')
    const filePath = join(sessionDir, safeFileName)

    await writeFile(filePath, buffer)

    // Store metadata
    const metadata = {
      originalName: file.name,
      safeFileName,
      size: file.size,
      type: file.type,
      extension: fileExtension,
      uploadTime: new Date().toISOString(),
      sessionId
    }

    await writeFile(
      join(sessionDir, 'metadata.json'),
      JSON.stringify(metadata, null, 2)
    )

    console.log(`Temporary file uploaded: ${file.name} (${file.size} bytes) - Session: ${sessionId}`)

    return NextResponse.json({
      success: true,
      sessionId,
      fileName: file.name,
      fileSize: file.size,
      message: 'File uploaded successfully for temporary analysis'
    })

  } catch (error) {
    console.error('Upload error:', error)
    return NextResponse.json({
      success: false,
      error: 'Failed to upload file'
    }, { status: 500 })
  }
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url)
    const sessionId = searchParams.get('sessionId')

    if (!sessionId) {
      return NextResponse.json({ error: 'Session ID required' }, { status: 400 })
    }

    const sessionDir = join(TEMP_DIR, sessionId)
    if (existsSync(sessionDir)) {
      // Clean up session directory
      const { rmdir } = await import('fs/promises')
      await rmdir(sessionDir, { recursive: true })
      console.log(`Cleaned up temporary session: ${sessionId}`)
    }

    return NextResponse.json({ success: true, message: 'Session cleaned up' })

  } catch (error) {
    console.error('Cleanup error:', error)
    return NextResponse.json({ error: 'Failed to cleanup session' }, { status: 500 })
  }
}
