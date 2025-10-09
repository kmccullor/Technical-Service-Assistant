import { NextRequest, NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({ 
    status: 'API is working',
    timestamp: new Date().toISOString(),
    openai_configured: process.env.OPENAI_API_KEY !== 'sk-your-openai-api-key-here'
  })
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    console.log('Test endpoint received:', body)
    
    return NextResponse.json({
      received: body,
      status: 'success',
      message: 'Test endpoint working'
    })
  } catch (error) {
    console.error('Test endpoint error:', error)
    return NextResponse.json(
      { error: 'Failed to process request' },
      { status: 500 }
    )
  }
}