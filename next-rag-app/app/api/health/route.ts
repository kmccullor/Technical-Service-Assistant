export async function GET() {
  try {
    return Response.json({
      success: true,
      message: 'System health endpoint operational',
      timestamp: Date.now(),
      ollamaContainers: {
        total: 4,
        ports: [11434, 11435, 11436, 11437]
      }
    })
  } catch (error) {
    return Response.json(
      {
        success: false,
        error: 'Health check failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}
