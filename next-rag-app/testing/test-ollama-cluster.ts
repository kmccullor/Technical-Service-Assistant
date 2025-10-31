#!/usr/bin/env node

import { advancedLoadBalancer } from '../lib/load-balancer'
import { localModelService, type ChatMessage } from '../lib/local-models'
import { cachePreWarmer } from '../lib/cache-prewarmer'

interface TestResult {
  test: string
  status: 'PASS' | 'FAIL' | 'WARN'
  details: string
  responseTime?: number
  error?: string
}

class OllamaClusterTester {
  private results: TestResult[] = []

  async runAllTests(): Promise<void> {
    console.log('🚀 Testing 4-Container Ollama Cluster with Advanced Load Balancing\n')

    await this.testDirectContainerAccess()
    await this.testLoadBalancerHealth()
    await this.testModelAvailability()
    await this.testLoadBalancing()
    await this.testEmbeddingGeneration()
    await this.testChatGeneration()
    await this.testCachePreWarmer()
    await this.testFailoverScenario()

    this.printResults()
  }

  /**
   * Test direct access to all 4 Ollama containers
   */
  async testDirectContainerAccess(): Promise<void> {
    console.log('🔍 Testing direct access to all 4 Ollama containers...')

    const containers = [
      { name: 'ollama-1', url: 'http://localhost:11434' },
      { name: 'ollama-2', url: 'http://localhost:11435' },
      { name: 'ollama-3', url: 'http://localhost:11436' },
      { name: 'ollama-4', url: 'http://localhost:11437' }
    ]

    for (const container of containers) {
      try {
        const startTime = Date.now()
        const response = await fetch(`${container.url}/api/tags`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000)
        })
        const responseTime = Date.now() - startTime

        if (response.ok) {
          const data = await response.json()
          const modelCount = data.models?.length || 0

          this.results.push({
            test: `${container.name} Access`,
            status: 'PASS',
            details: `Responding with ${modelCount} models`,
            responseTime
          })
        } else {
          this.results.push({
            test: `${container.name} Access`,
            status: 'FAIL',
            details: `HTTP ${response.status}: ${response.statusText}`
          })
        }
      } catch (error) {
        this.results.push({
          test: `${container.name} Access`,
          status: 'FAIL',
          details: 'Container not responding',
          error: error instanceof Error ? error.message : 'Unknown error'
        })
      }
    }
  }

  /**
   * Test load balancer health and statistics
   */
  async testLoadBalancerHealth(): Promise<void> {
    console.log('⚖️ Testing load balancer health monitoring...')

    try {
      // Force health check
      await advancedLoadBalancer.forceHealthCheck()

      // Get statistics
      const stats = advancedLoadBalancer.getStats()

      const healthyPercentage = (stats.healthyInstances / stats.totalInstances) * 100

      if (healthyPercentage >= 75) {
        this.results.push({
          test: 'Load Balancer Health',
          status: 'PASS',
          details: `${stats.healthyInstances}/${stats.totalInstances} instances healthy (${healthyPercentage.toFixed(0)}%)`
        })
      } else if (healthyPercentage >= 50) {
        this.results.push({
          test: 'Load Balancer Health',
          status: 'WARN',
          details: `${stats.healthyInstances}/${stats.totalInstances} instances healthy - degraded performance`
        })
      } else {
        this.results.push({
          test: 'Load Balancer Health',
          status: 'FAIL',
          details: `Only ${stats.healthyInstances}/${stats.totalInstances} instances healthy`
        })
      }

      console.log('📊 Load Balancer Stats:')
      stats.instanceDetails.forEach(instance => {
        console.log(`  ${instance.url}: ${instance.healthy ? '✅' : '❌'} ${instance.responseTime.toFixed(0)}ms (score: ${instance.score.toFixed(3)})`)
      })

    } catch (error) {
      this.results.push({
        test: 'Load Balancer Health',
        status: 'FAIL',
        details: 'Load balancer health check failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test model availability across all instances
   */
  async testModelAvailability(): Promise<void> {
    console.log('🤖 Testing model availability...')

    try {
      const models = await localModelService.listModels()

      const requiredModels = ['llama3.2:1b', 'nomic-embed-text']
      const availableRequired = requiredModels.filter(model =>
        models.some(available => available.includes(model.split(':')[0]))
      )

      if (availableRequired.length === requiredModels.length) {
        this.results.push({
          test: 'Model Availability',
          status: 'PASS',
          details: `All required models available (${models.length} total models)`
        })
      } else {
        this.results.push({
          test: 'Model Availability',
          status: 'WARN',
          details: `${availableRequired.length}/${requiredModels.length} required models available`
        })
      }

      console.log(`📋 Available models: ${models.join(', ')}`)

    } catch (error) {
      this.results.push({
        test: 'Model Availability',
        status: 'FAIL',
        details: 'Failed to list models',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test intelligent load balancing across instances
   */
  async testLoadBalancing(): Promise<void> {
    console.log('🔄 Testing intelligent load balancing...')

    try {
      const requestCount = 8 // More requests than instances to test routing
      const promises: Promise<string>[] = []

      // Make multiple concurrent requests
      for (let i = 0; i < requestCount; i++) {
        promises.push(advancedLoadBalancer.getBestInstance())
      }

      const startTime = Date.now()
      const instances = await Promise.all(promises)
      const responseTime = Date.now() - startTime

      // Count distribution
      const distribution = instances.reduce((acc, instance) => {
        acc[instance] = (acc[instance] || 0) + 1
        return acc
      }, {} as Record<string, number>)

      const uniqueInstances = Object.keys(distribution).length
      const maxRequests = Math.max(...Object.values(distribution))
      const minRequests = Math.min(...Object.values(distribution))
      const balanceRatio = minRequests / maxRequests

      if (uniqueInstances >= 2 && balanceRatio >= 0.5) {
        this.results.push({
          test: 'Load Balancing',
          status: 'PASS',
          details: `Good distribution across ${uniqueInstances} instances (balance ratio: ${balanceRatio.toFixed(2)})`,
          responseTime
        })
      } else if (uniqueInstances >= 2) {
        this.results.push({
          test: 'Load Balancing',
          status: 'WARN',
          details: `Uneven distribution across ${uniqueInstances} instances`,
          responseTime
        })
      } else {
        this.results.push({
          test: 'Load Balancing',
          status: 'FAIL',
          details: `Only using ${uniqueInstances} instance(s) - no load balancing`,
          responseTime
        })
      }

      console.log('📊 Request distribution:', Object.entries(distribution).map(([url, count]) =>
        `${url.split('//')[1]}: ${count} requests`
      ).join(', '))

    } catch (error) {
      this.results.push({
        test: 'Load Balancing',
        status: 'FAIL',
        details: 'Load balancing test failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test embedding generation with load balancing
   */
  async testEmbeddingGeneration(): Promise<void> {
    console.log('🔢 Testing embedding generation...')

    try {
      const testTexts = [
        'This is a test document about machine learning.',
        'Performance optimization is crucial for production systems.',
        'Load balancing distributes requests across multiple servers.'
      ]

      const startTime = Date.now()
      const embeddings = await localModelService.generateEmbeddings(testTexts)
      const responseTime = Date.now() - startTime

      const validEmbeddings = embeddings.filter(emb => Array.isArray(emb) && emb.length > 0)

      if (validEmbeddings.length === testTexts.length) {
        const avgDimensions = validEmbeddings.reduce((sum, emb) => sum + emb.length, 0) / validEmbeddings.length

        this.results.push({
          test: 'Embedding Generation',
          status: 'PASS',
          details: `Generated ${validEmbeddings.length} embeddings (${avgDimensions} dimensions avg)`,
          responseTime
        })
      } else {
        this.results.push({
          test: 'Embedding Generation',
          status: 'FAIL',
          details: `Only ${validEmbeddings.length}/${testTexts.length} embeddings generated successfully`
        })
      }

    } catch (error) {
      this.results.push({
        test: 'Embedding Generation',
        status: 'FAIL',
        details: 'Embedding generation failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test chat generation with caching and load balancing
   */
  async testChatGeneration(): Promise<void> {
    console.log('💬 Testing chat generation...')

    try {
      const testMessages: ChatMessage[] = [
        { role: 'user', content: 'What is load balancing?' }
      ]

      const startTime = Date.now()
      const response1 = await localModelService.generateChatResponse(testMessages, 'llama3.2:1b', {
        temperature: 0.1,
        max_tokens: 100
      })
      const firstResponseTime = Date.now() - startTime

      // Test caching by making the same request
      const cacheStartTime = Date.now()
      const response2 = await localModelService.generateChatResponse(testMessages, 'llama3.2:1b', {
        temperature: 0.1,
        max_tokens: 100
      })
      const cacheResponseTime = Date.now() - cacheStartTime

      if (response1 && response1.length > 10) {
        const cacheWorking = cacheResponseTime < firstResponseTime * 0.5 // Cache should be much faster

        this.results.push({
          test: 'Chat Generation',
          status: 'PASS',
          details: `Response generated (${response1.length} chars), cache ${cacheWorking ? 'working' : 'not detected'}`,
          responseTime: firstResponseTime
        })

        console.log(`💬 Sample response: "${response1.substring(0, 100)}${response1.length > 100 ? '...' : ''}"`)
        console.log(`⚡ First request: ${firstResponseTime}ms, Cached request: ${cacheResponseTime}ms`)
      } else {
        this.results.push({
          test: 'Chat Generation',
          status: 'FAIL',
          details: 'No valid response generated'
        })
      }

    } catch (error) {
      this.results.push({
        test: 'Chat Generation',
        status: 'FAIL',
        details: 'Chat generation failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test cache pre-warmer functionality
   */
  async testCachePreWarmer(): Promise<void> {
    console.log('🔥 Testing cache pre-warmer...')

    try {
      const preWarmerStats = cachePreWarmer.getStats()
      const isWarming = cachePreWarmer.isWarmingUp()

      if (preWarmerStats.totalWarmupAttempts > 0 || preWarmerStats.successfulWarmups > 0) {
        this.results.push({
          test: 'Cache Pre-Warmer',
          status: 'PASS',
          details: `${preWarmerStats.successfulWarmups} successful warmups, currently ${isWarming ? 'warming' : 'idle'}`
        })
      } else {
        // Trigger a manual warmup to test functionality
        console.log('  Triggering manual warmup test...')

        if (!isWarming) {
          // Don't await - just trigger it
          cachePreWarmer.triggerWarmup().catch(() => {})

          this.results.push({
            test: 'Cache Pre-Warmer',
            status: 'WARN',
            details: 'No warmup history found, manual warmup triggered'
          })
        } else {
          this.results.push({
            test: 'Cache Pre-Warmer',
            status: 'PASS',
            details: 'Pre-warmer is currently active'
          })
        }
      }

    } catch (error) {
      this.results.push({
        test: 'Cache Pre-Warmer',
        status: 'FAIL',
        details: 'Pre-warmer test failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Test failover scenario by simulating instance failure
   */
  async testFailoverScenario(): Promise<void> {
    console.log('🛡️ Testing failover scenario...')

    try {
      const stats = advancedLoadBalancer.getStats()

      if (stats.healthyInstances <= 1) {
        this.results.push({
          test: 'Failover Scenario',
          status: 'WARN',
          details: 'Cannot test failover - only 1 healthy instance available'
        })
        return
      }

      // Get an instance to "fail"
      const healthyInstance = stats.instanceDetails.find(i => i.healthy)?.url

      if (healthyInstance) {
        console.log(`  Simulating failure of ${healthyInstance}...`)

        // Manually mark instance as unhealthy
        advancedLoadBalancer.setInstanceHealth(healthyInstance, false)

        // Try to get instances - should avoid the "failed" one
        const instances = await Promise.all([
          advancedLoadBalancer.getBestInstance(),
          advancedLoadBalancer.getBestInstance(),
          advancedLoadBalancer.getBestInstance()
        ])

        const usedFailedInstance = instances.some(instance => instance === healthyInstance)

        // Restore the instance
        advancedLoadBalancer.setInstanceHealth(healthyInstance, true)

        if (!usedFailedInstance) {
          this.results.push({
            test: 'Failover Scenario',
            status: 'PASS',
            details: 'Successfully avoided failed instance and used healthy alternatives'
          })
        } else {
          this.results.push({
            test: 'Failover Scenario',
            status: 'FAIL',
            details: 'Failover did not work - still routing to failed instance'
          })
        }
      } else {
        this.results.push({
          test: 'Failover Scenario',
          status: 'FAIL',
          details: 'No healthy instances found for failover test'
        })
      }

    } catch (error) {
      this.results.push({
        test: 'Failover Scenario',
        status: 'FAIL',
        details: 'Failover test failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Print comprehensive test results
   */
  private printResults(): void {
    console.log('\n' + '='.repeat(80))
    console.log('📊 4-Container Ollama Cluster Test Results')
    console.log('='.repeat(80))

    const passCount = this.results.filter(r => r.status === 'PASS').length
    const warnCount = this.results.filter(r => r.status === 'WARN').length
    const failCount = this.results.filter(r => r.status === 'FAIL').length

    this.results.forEach(result => {
      const icon = result.status === 'PASS' ? '✅' : result.status === 'WARN' ? '⚠️' : '❌'
      const responseTime = result.responseTime ? ` (${result.responseTime}ms)` : ''
      const error = result.error ? ` | Error: ${result.error}` : ''

      console.log(`${icon} ${result.test}: ${result.details}${responseTime}${error}`)
    })

    console.log('\n📈 Summary:')
    console.log(`✅ Passed: ${passCount}`)
    console.log(`⚠️ Warnings: ${warnCount}`)
    console.log(`❌ Failed: ${failCount}`)
    console.log(`📊 Total Tests: ${this.results.length}`)

    const successRate = (passCount / this.results.length) * 100
    const overallHealth = (passCount + warnCount * 0.5) / this.results.length

    console.log(`🎯 Success Rate: ${successRate.toFixed(1)}%`)

    if (overallHealth >= 0.9) {
      console.log('\n🎉 Cluster Status: EXCELLENT - Production Ready!')
      console.log('   All systems operational with optimal performance')
    } else if (overallHealth >= 0.7) {
      console.log('\n👍 Cluster Status: GOOD - Ready for Use')
      console.log('   Minor issues detected but system is functional')
    } else if (overallHealth >= 0.5) {
      console.log('\n⚠️ Cluster Status: NEEDS ATTENTION')
      console.log('   Several issues found that should be addressed')
    } else {
      console.log('\n🚨 Cluster Status: CRITICAL')
      console.log('   Major issues require immediate attention')
    }

    console.log('\n🔧 Cluster Configuration:')
    console.log('   • 4 Ollama containers (ports 11434-11437)')
    console.log('   • Advanced load balancing with health monitoring')
    console.log('   • Intelligent caching and pre-warming')
    console.log('   • Automatic failover and recovery')

    if (failCount === 0 && warnCount <= 1) {
      console.log('\n🚀 Ready for production workloads!')
    } else {
      console.log('\n💡 Recommendations:')
      if (failCount > 0) {
        console.log('   - Address failed tests before production use')
        console.log('   - Check container logs: docker logs <container-name>')
      }
      if (warnCount > 0) {
        console.log('   - Review warnings for optimization opportunities')
        console.log('   - Monitor performance metrics in production')
      }
    }
  }
}

// Run tests if called directly
if (import.meta.url === `file://${process.argv[1]}` || process.argv[1].endsWith('test-ollama-cluster.ts')) {
  const tester = new OllamaClusterTester()
  tester.runAllTests().catch(error => {
    console.error('❌ Test suite failed:', error)
    process.exit(1)
  })
}

export { OllamaClusterTester }
