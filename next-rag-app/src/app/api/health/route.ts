import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Basic health check - you can add more sophisticated checks here
    return NextResponse.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'next-rag-app'
    });
  } catch (error) {
    return NextResponse.json(
      { status: 'unhealthy', error: 'Service check failed' },
      { status: 503 }
    );
  }
}
