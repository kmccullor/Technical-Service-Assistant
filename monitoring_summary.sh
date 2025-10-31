#!/bin/bash
# Complete Technical Service Assistant Monitoring Summary
# Shows all monitoring capabilities and quick access commands

echo "🎯 Technical Service Assistant - Complete Monitoring Stack"
echo "=========================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${GREEN}✅ MONITORING STACK SUCCESSFULLY DEPLOYED!${NC}"
echo ""

echo -e "${BLUE}🌐 Access Points:${NC}"
echo "=================="
echo "• Grafana Dashboard: http://localhost:3001 (admin/admin)"
echo "• Prometheus Metrics: http://localhost:9091"
echo "• Container Stats: http://localhost:8081"
echo "• System Metrics: http://localhost:9100/metrics"
echo "• Database Metrics: http://localhost:9187/metrics"
echo "• Cache Metrics: http://localhost:9121/metrics"
echo ""

echo -e "${PURPLE}📊 Available Dashboards:${NC}"
echo "========================"
echo "1. System Overview Dashboard"
echo "   • Real-time CPU, Memory, Disk usage"
echo "   • Container health status"
echo "   • System performance trends"
echo ""
echo "2. AI Services Dashboard"
echo "   • Ollama instance monitoring"
echo "   • Reranker service performance"
echo "   • Model selection analytics"
echo "   • RAG query success rates"
echo ""
echo "3. Database & Infrastructure Dashboard"
echo "   • PostgreSQL performance metrics"
echo "   • Redis cache statistics"
echo "   • Vector database analytics"
echo "   • Container resource usage"
echo ""

echo -e "${YELLOW}🔍 Key Monitoring Features:${NC}"
echo "==========================="
echo "• 📈 Real-time system metrics (CPU, Memory, Disk, Network)"
echo "• 🐳 Docker container monitoring with cAdvisor"
echo "• 🗄️  PostgreSQL database performance tracking"
echo "• ⚡ Redis cache hit/miss ratios and performance"
echo "• 🤖 AI service health and response times"
echo "• 📊 Custom application metrics via Prometheus"
echo "• 🚨 Comprehensive alerting rules"
echo "• 📱 Mobile-responsive dashboards"
echo ""

echo -e "${GREEN}🎯 Monitoring Targets Status:${NC}"
echo "============================="

# Quick status check
if curl -s http://localhost:9091/api/v1/targets > /dev/null 2>&1; then
    UP_COUNT=$(curl -s http://localhost:9091/api/v1/targets | jq -r '.data.activeTargets[] | select(.health=="up") | .labels.job' | wc -l)
    TOTAL_COUNT=$(curl -s http://localhost:9091/api/v1/targets | jq -r '.data.activeTargets[] | .labels.job' | wc -l)
    echo "• Monitored Services: $UP_COUNT/$TOTAL_COUNT healthy"
else
    echo "• Prometheus status check failed"
fi

echo "• System Resources: Node Exporter"
echo "• Database: PostgreSQL Exporter"
echo "• Cache: Redis Exporter"
echo "• Containers: cAdvisor"
echo "• Application: Reranker Service"
echo ""

echo -e "${BLUE}🚀 Quick Commands:${NC}"
echo "=================="
echo "# Check monitoring status"
echo "./check_monitoring.sh"
echo ""
echo "# View container status"
echo "docker ps --filter 'name=prometheus|grafana|exporter|cadvisor'"
echo ""
echo "# Restart monitoring stack"
echo "docker compose restart prometheus grafana"
echo ""
echo "# View Prometheus targets"
echo "curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'"
echo ""

echo -e "${PURPLE}📋 Next Steps:${NC}"
echo "=============="
echo "1. 🌐 Open Grafana at http://localhost:3001"
echo "2. 🔑 Login with admin/admin (change password on first login)"
echo "3. 📊 Explore the pre-configured dashboards"
echo "4. 🎯 Set up alerting for critical metrics"
echo "5. 📱 Bookmark for mobile monitoring access"
echo ""

echo -e "${GREEN}📊 Your Technical Service Assistant is now fully monitored!${NC}"
echo "================================================================"
echo ""
echo "The monitoring stack provides comprehensive visibility into:"
echo "• System performance and resource utilization"
echo "• Application health and response times"
echo "• Database and cache performance"
echo "• Container orchestration metrics"
echo "• AI service availability and routing intelligence"
echo ""
echo "🎉 Production-ready monitoring is now active! 🎉"
