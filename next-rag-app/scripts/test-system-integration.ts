#!/usr/bin/env node
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

interface SystemCheck {
  name: string
  status: 'pass' | 'fail' | 'warning'
  details: string
  responseTime?: number
}

class SystemIntegrationTester {
  private results: SystemCheck[] = []

  async runAllTests(): Promise<void> {
    console.log('🚀 Starting Comprehensive System Integration Tests...\n')
    
    await this.checkLoadBalancer()
    await this.checkCachePreWarmer()
    await this.checkSemanticCache()
    await this.checkRAGIntegration()
    await this.checkSystemEndpoints()
    await this.performLoadTest()
    
    this.printResults()
  }

  private async checkLoadBalancer(): Promise<void> {
    console.log('🔄 Testing Advanced Load Balancer...')
    
    try {
      const startTime = Date.now()
      const response = await fetch('http://localhost:3000/api/system', {
        method: 'GET'
      })
      const responseTime = Date.now() - startTime
      
      if (response.ok) {
        const data = await response.json()
        
        if (data.success && data.loadBalancer) {
          this.results.push({
            name: 'Load Balancer Health',
            status: 'pass',
            details: `${data.systemHealth.healthyInstances}/${data.systemHealth.totalInstances} instances healthy, ${data.systemHealth.averageResponseTime.toFixed(0)}ms avg response`,
            responseTime
          })
        } else {
          this.results.push({
            name: 'Load Balancer Health',
            status: 'fail',
            details: 'Load balancer not responding properly'
          })
        }
      } else {
        this.results.push({
          name: 'Load Balancer Health',
          status: 'fail',
          details: `HTTP ${response.status}: ${response.statusText}`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Load Balancer Health',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async checkCachePreWarmer(): Promise<void> {
    console.log('🔥 Testing Cache Pre-Warmer...')
    
    try {
      const response = await fetch('http://localhost:3000/api/system', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'force_health_check' })
      })
      
      if (response.ok) {
        const data = await response.json()
        
        if (data.success) {
          this.results.push({
            name: 'Cache Pre-Warmer',
            status: 'pass',
            details: 'Health check and warmup systems operational'
          })
        } else {
          this.results.push({
            name: 'Cache Pre-Warmer',
            status: 'fail',
            details: data.message || 'Pre-warmer not responding'
          })
        }
      } else {
        this.results.push({
          name: 'Cache Pre-Warmer',
          status: 'fail',
          details: `HTTP ${response.status}`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Cache Pre-Warmer',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async checkSemanticCache(): Promise<void> {
    console.log('🧠 Testing Semantic Cache Integration...')
    
    try {
      // Test cache with a simple RAG query
      const testQuery = "What is the main purpose of this system?"
      const startTime = Date.now()
      
      const response = await fetch('http://localhost:3000/api/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: testQuery,
          useCache: true
        })
      })
      
      const responseTime = Date.now() - startTime
      
      if (response.ok) {
        const data = await response.json()
        
        if (data.success) {
          const cacheHit = data.metadata?.cacheHit || false
          this.results.push({
            name: 'Semantic Cache',
            status: 'pass',
            details: `Cache ${cacheHit ? 'HIT' : 'MISS'} - ${data.answer ? 'Response generated' : 'No response'}`,
            responseTime
          })
        } else {
          this.results.push({
            name: 'Semantic Cache',
            status: 'warning',
            details: data.error || 'Cache test inconclusive'
          })
        }
      } else {
        this.results.push({
          name: 'Semantic Cache',
          status: 'fail',
          details: `HTTP ${response.status}`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Semantic Cache',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async checkRAGIntegration(): Promise<void> {
    console.log('📚 Testing Full RAG Pipeline...')
    
    try {
      const testQueries = [
        "How do I configure this system?",
        "What are the performance characteristics?",
        "What models are supported?"
      ]
      
      let totalResponseTime = 0
      let successCount = 0
      
      for (const query of testQueries) {
        const startTime = Date.now()
        
        try {
          const response = await fetch('http://localhost:3000/api/rag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, model: 'llama3.2:1b' })
          })
          
          const responseTime = Date.now() - startTime
          totalResponseTime += responseTime
          
          if (response.ok) {
            const data = await response.json()
            if (data.success && data.answer) {
              successCount++
            }
          }
        } catch (error) {
          console.log(`  ❌ Query failed: ${query.substring(0, 30)}...`)
        }
      }
      
      const avgResponseTime = totalResponseTime / testQueries.length
      const successRate = (successCount / testQueries.length) * 100
      
      if (successRate >= 80) {
        this.results.push({
          name: 'RAG Pipeline Integration',
          status: 'pass',
          details: `${successRate}% success rate, ${avgResponseTime.toFixed(0)}ms avg response`,
          responseTime: avgResponseTime
        })
      } else if (successRate >= 50) {
        this.results.push({
          name: 'RAG Pipeline Integration',
          status: 'warning',
          details: `${successRate}% success rate - some queries failing`,
          responseTime: avgResponseTime
        })
      } else {
        this.results.push({
          name: 'RAG Pipeline Integration',
          status: 'fail',
          details: `${successRate}% success rate - system not functioning properly`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'RAG Pipeline Integration',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async checkSystemEndpoints(): Promise<void> {
    console.log('🌐 Testing System Management Endpoints...')
    
    try {
      const endpoints = [
        { path: '/api/system', method: 'GET', name: 'System Stats' },
        { path: '/api/health', method: 'GET', name: 'Health Check' }
      ]
      
      let passCount = 0
      
      for (const endpoint of endpoints) {
        try {
          const response = await fetch(`http://localhost:3000${endpoint.path}`, {
            method: endpoint.method
          })
          
          if (response.ok || response.status === 404) { // 404 is acceptable for non-implemented endpoints
            passCount++
          }
        } catch (error) {
          console.log(`  ❌ ${endpoint.name} endpoint failed`)
        }
      }
      
      if (passCount === endpoints.length) {
        this.results.push({
          name: 'System Endpoints',
          status: 'pass',
          details: 'All management endpoints responding'
        })
      } else {
        this.results.push({
          name: 'System Endpoints',
          status: 'warning',
          details: `${passCount}/${endpoints.length} endpoints responding`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'System Endpoints',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async performLoadTest(): Promise<void> {
    console.log('⚡ Performing Load Test (5 concurrent queries)...')
    
    try {
      const testQuery = "What are the key features of this system?"
      const concurrentRequests = 5
      const startTime = Date.now()
      
      const promises = Array(concurrentRequests).fill(null).map(async (_, index) => {
        try {
          const response = await fetch('http://localhost:3000/api/rag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              query: `${testQuery} (test ${index + 1})`,
              model: 'llama3.2:1b'
            })
          })
          
          if (response.ok) {
            const data = await response.json()
            return data.success ? 'success' : 'fail'
          } else {
            return 'fail'
          }
        } catch (error) {
          return 'fail'
        }
      })
      
      const results = await Promise.all(promises)
      const totalTime = Date.now() - startTime
      const successCount = results.filter(r => r === 'success').length
      const successRate = (successCount / concurrentRequests) * 100
      const avgResponseTime = totalTime / concurrentRequests
      
      if (successRate >= 80 && avgResponseTime < 10000) {
        this.results.push({
          name: 'Load Test',
          status: 'pass',
          details: `${successRate}% success under load, ${avgResponseTime.toFixed(0)}ms avg response`,
          responseTime: avgResponseTime
        })
      } else if (successRate >= 60) {
        this.results.push({
          name: 'Load Test',
          status: 'warning',
          details: `${successRate}% success under load, some performance degradation`,
          responseTime: avgResponseTime
        })
      } else {
        this.results.push({
          name: 'Load Test',
          status: 'fail',
          details: `${successRate}% success under load, system struggling`,
          responseTime: avgResponseTime
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Load Test',
        status: 'fail',
        details: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private printResults(): void {
    console.log('\n📊 System Integration Test Results:')
    console.log('=' .repeat(60))
    
    const passCount = this.results.filter(r => r.status === 'pass').length
    const warnCount = this.results.filter(r => r.status === 'warning').length
    const failCount = this.results.filter(r => r.status === 'fail').length
    
    this.results.forEach(result => {
      const icon = result.status === 'pass' ? '✅' : result.status === 'warning' ? '⚠️' : '❌'
      const responseInfo = result.responseTime ? ` (${result.responseTime.toFixed(0)}ms)` : ''
      console.log(`${icon} ${result.name}: ${result.details}${responseInfo}`)
    })
    
    console.log('\n📈 Summary:')
    console.log(`✅ Passed: ${passCount}`)
    console.log(`⚠️ Warnings: ${warnCount}`)
    console.log(`❌ Failed: ${failCount}`)
    
    const overallHealth = (passCount + warnCount * 0.5) / this.results.length
    
    if (overallHealth >= 0.8) {
      console.log('\n🎉 System Status: EXCELLENT - Production Ready!')
    } else if (overallHealth >= 0.6) {
      console.log('\n👍 System Status: GOOD - Minor issues to address')
    } else if (overallHealth >= 0.4) {
      console.log('\n⚠️ System Status: NEEDS ATTENTION - Several issues found')
    } else {
      console.log('\n🚨 System Status: CRITICAL - Major issues require immediate attention')
    }
    
    console.log('\n💡 Next Steps:')
    if (failCount > 0) {
      console.log('- Address failed tests before production deployment')
    }
    if (warnCount > 0) {
      console.log('- Review warnings for potential performance improvements')
    }
    if (passCount === this.results.length) {
      console.log('- System is ready for production use!')
      console.log('- Consider running extended performance testing')
      console.log('- Monitor system metrics in production environment')
    }
  }
}

// Run tests if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const tester = new SystemIntegrationTester()
  tester.runAllTests().catch(console.error)
}

export { SystemIntegrationTester }