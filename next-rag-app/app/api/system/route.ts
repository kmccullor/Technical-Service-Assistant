import { advancedLoadBalancer } from '../../../lib/load-balancer'
import { cachePreWarmer, type PreWarmStats } from '../../../lib/cache-prewarmer'

/**
 * API endpoint for load balancer statistics and health monitoring
 */
export async function GET() {
  try {
    const stats = advancedLoadBalancer.getStats()
    const preWarmStats = cachePreWarmer.getStats()

    return Response.json({
      success: true,
      loadBalancer: stats,
      preWarmer: preWarmStats,
      systemHealth: {
        timestamp: Date.now(),
        healthyInstances: stats.healthyInstances,
        totalInstances: stats.totalInstances,
        healthPercentage: (stats.healthyInstances / stats.totalInstances) * 100,
        averageResponseTime: stats.averageResponseTime,
        errorRate: stats.totalErrors / Math.max(1, stats.totalRequests),
        cacheWarmupStatus: cachePreWarmer.isWarmingUp() ? 'warming' : 'ready'
      }
    })
  } catch (error) {
    console.error('Failed to get load balancer stats:', error)

    return Response.json(
      {
        success: false,
        error: 'Failed to retrieve system statistics',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}

/**
 * API endpoint for triggering manual health checks and warmup
 */
export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { action, instanceUrl } = body

    switch (action) {
      case 'force_health_check':
        await advancedLoadBalancer.forceHealthCheck()
        return Response.json({
          success: true,
          message: 'Health check completed',
          stats: advancedLoadBalancer.getStats()
        })

      case 'trigger_warmup':
        if (cachePreWarmer.isWarmingUp()) {
          return Response.json({
            success: false,
            message: 'Warmup already in progress'
          })
        }

        // Don't await - let it run in background
        cachePreWarmer.triggerWarmup().catch(error => {
          console.error('Background warmup failed:', error)
        })

        return Response.json({
          success: true,
          message: 'Warmup triggered successfully'
        })

      case 'reset_stats':
        advancedLoadBalancer.resetStats()
        return Response.json({
          success: true,
          message: 'Statistics reset successfully'
        })

      case 'set_instance_health':
        if (!instanceUrl) {
          return Response.json(
            { success: false, error: 'instanceUrl required for set_instance_health' },
            { status: 400 }
          )
        }

        const { healthy } = body
        if (typeof healthy !== 'boolean') {
          return Response.json(
            { success: false, error: 'healthy must be a boolean' },
            { status: 400 }
          )
        }

        advancedLoadBalancer.setInstanceHealth(instanceUrl, healthy)
        return Response.json({
          success: true,
          message: `Instance ${instanceUrl} marked as ${healthy ? 'healthy' : 'unhealthy'}`
        })

      default:
        return Response.json(
          { success: false, error: `Unknown action: ${action}` },
          { status: 400 }
        )
    }
  } catch (error) {
    console.error('Load balancer management failed:', error)

    return Response.json(
      {
        success: false,
        error: 'Management operation failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}
