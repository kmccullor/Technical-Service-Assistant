#!/bin/bash
# Monitoring Access URLs - Using Hostname for External Access
# This script provides the correct URLs for accessing monitoring services

HOSTNAME="RNI-LLM-01.lab.sensus.net"

echo "🖥️  Monitoring Dashboard Access URLs"
echo "======================================="
echo "🌐 Using hostname: $HOSTNAME"
echo ""

echo "📊 Core Monitoring Services:"
echo "  • Grafana Dashboard:     http://$HOSTNAME:3001"
echo "  • Prometheus Metrics:    http://$HOSTNAME:9091"
echo "  • Prometheus Targets:    http://$HOSTNAME:9091/targets"
echo ""

echo "📈 Application Services:"
echo "  • Technical Service UI:  http://$HOSTNAME:8080"
echo "  • Reranker API:          http://$HOSTNAME:8008"
echo "  • SearXNG Search:        http://$HOSTNAME:8888"
echo ""

echo "🔍 Metrics Exporters:"
echo "  • Node Exporter:         http://$HOSTNAME:9100/metrics"
echo "  • Postgres Exporter:     http://$HOSTNAME:9187/metrics"
echo "  • Redis Exporter:        http://$HOSTNAME:9121/metrics"
echo "  • cAdvisor:              http://$HOSTNAME:8081"
echo ""

echo "🤖 Ollama AI Services:"
echo "  • Ollama Instance 1:     http://$HOSTNAME:11434"
echo "  • Ollama Instance 2:     http://$HOSTNAME:11435"
echo "  • Ollama Instance 3:     http://$HOSTNAME:11436"
echo "  • Ollama Instance 4:     http://$HOSTNAME:11437"
echo ""

echo "🧪 Health Check Commands:"
echo "=========================="
echo "# Check all monitoring services"
echo "curl -s http://$HOSTNAME:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'"
echo ""
echo "# Test Grafana"
echo "curl -s http://$HOSTNAME:3001/api/health"
echo ""
echo "# Test Prometheus"
echo "curl -s http://$HOSTNAME:9090/-/healthy"
echo ""

echo "🔧 Quick Service Status:"
echo "========================"

# Check key services
services=(
    "3001:Grafana"
    "9090:Prometheus" 
    "8008:Reranker"
    "9100:Node-Exporter"
    "9187:Postgres-Exporter"
    "11434:Ollama-1"
    "11435:Ollama-2"
    "11436:Ollama-3"
    "11437:Ollama-4"
)

for service in "${services[@]}"; do
    port=$(echo $service | cut -d: -f1)
    name=$(echo $service | cut -d: -f2)
    
    if timeout 2 bash -c "echo >/dev/tcp/$HOSTNAME/$port" 2>/dev/null; then
        echo "  ✅ $name (port $port)"
    else
        echo "  ❌ $name (port $port)"
    fi
done

echo ""
echo "🚀 Access your monitoring at: http://$HOSTNAME:3001"
echo "   Default Grafana login: admin/admin"