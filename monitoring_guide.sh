#!/bin/bash
# Comprehensive Monitoring Setup Guide
# Explains hostname vs service name usage in containerized monitoring

HOSTNAME="RNI-LLM-01.lab.sensus.net"
PROMETHEUS_PORT="9091"  # External port mapping

echo "🐳 Container Networking vs External Access"
echo "==========================================="
echo ""

echo "📡 Two Types of Network Access:"
echo "-------------------------------"
echo ""
echo "1. 🔗 Container-to-Container (Internal):"
echo "   • Uses Docker service names (e.g., 'prometheus', 'grafana')"
echo "   • Defined in docker-compose.yml"
echo "   • Automatic DNS resolution within Docker network"
echo "   • Used for: Grafana → Prometheus, Prometheus → exporters"
echo ""
echo "2. 🌐 External Access (Host Network):"
echo "   • Uses hostname: $HOSTNAME"
echo "   • Maps to host ports via docker-compose port mappings"
echo "   • Used for: Browser access, external monitoring, APIs"
echo ""

echo "🔧 Current Configuration:"
echo "========================="
echo ""
echo "📊 Internal Service Communication:"
echo "  • Grafana datasource: http://prometheus:9090"
echo "  • Prometheus targets: Use service names (reranker:8008, etc.)"
echo "  • Container network: technical-service-assistant_default"
echo ""
echo "🌐 External Access URLs:"
echo "  • Grafana UI:      http://$HOSTNAME:3001"
echo "  • Prometheus UI:   http://$HOSTNAME:$PROMETHEUS_PORT"
echo "  • Reranker API:    http://$HOSTNAME:8008"
echo ""

echo "🚀 Testing Both Access Methods:"
echo "==============================="

# Test internal container communication
echo "🔗 Testing internal container communication..."
if docker exec grafana wget -q --spider http://prometheus:9090/-/healthy 2>/dev/null; then
    echo "  ✅ Grafana → Prometheus (internal): Working"
else
    echo "  ❌ Grafana → Prometheus (internal): Failed"
fi

# Test external access
echo "🌐 Testing external access..."
if timeout 3 bash -c "echo >/dev/tcp/$HOSTNAME/$PROMETHEUS_PORT" 2>/dev/null; then
    echo "  ✅ External Prometheus access: Working"
else
    echo "  ❌ External Prometheus access: Failed"
fi

if timeout 3 bash -c "echo >/dev/tcp/$HOSTNAME/3001" 2>/dev/null; then
    echo "  ✅ External Grafana access: Working"
else
    echo "  ❌ External Grafana access: Failed"
fi

echo ""
echo "📋 Service Status Summary:"
echo "=========================="

# Check Prometheus targets
echo "🎯 Prometheus Targets Status:"
if curl -s http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/targets 2>/dev/null | grep -q "up"; then
    target_count=$(curl -s http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets | length' 2>/dev/null || echo "unknown")
    echo "  ✅ Prometheus monitoring $target_count targets"
    
    # Show target health
    echo "  📊 Target Health:"
    curl -s http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets[] | "    • \(.labels.job): \(.health)"' 2>/dev/null | head -10
else
    echo "  ❌ Prometheus targets not accessible"
fi

echo ""
echo "🎯 Key Access Points:"
echo "===================="
echo "🖥️  Primary Monitoring Dashboard:"
echo "   http://$HOSTNAME:3001"
echo ""
echo "🔍 Prometheus Metrics & Targets:"
echo "   http://$HOSTNAME:9090"
echo "   http://$HOSTNAME:9090/targets"
echo ""
echo "📊 Individual Service Metrics:"
echo "   • Node metrics:     http://$HOSTNAME:9100/metrics"
echo "   • Postgres metrics: http://$HOSTNAME:9187/metrics"
echo "   • Container metrics: http://$HOSTNAME:8081/metrics"
echo ""

echo "⚙️  Configuration Files:"
echo "========================"
echo "📁 monitoring/prometheus/prometheus.yml  - Prometheus config (uses service names)"
echo "📁 monitoring/grafana/provisioning/      - Grafana config (uses service names)"
echo "📁 docker-compose.yml                    - Port mappings for external access"
echo ""

echo "🔐 Security Note:"
echo "================="
echo "• Internal communication uses encrypted container network"
echo "• External access should be secured with reverse proxy/SSL in production"
echo "• Default Grafana credentials: admin/admin (change in production)"
echo ""

echo "✅ Monitoring stack ready!"
echo "🚀 Start monitoring: http://$HOSTNAME:3001"