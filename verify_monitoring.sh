#!/bin/bash
# Comprehensive Monitoring Configuration Verification
# Verifies Prometheus and Grafana are properly configured

HOSTNAME="RNI-LLM-01.lab.sensus.net"
PROMETHEUS_PORT="9091"
GRAFANA_PORT="3001"

echo "🔍 Technical Service Assistant - Monitoring Verification"
echo "========================================================"
echo "🌐 Host: $HOSTNAME"
echo ""

# Function to test HTTP endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    local status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    if [ "$status" = "$expected_status" ]; then
        echo "  ✅ $name: HTTP $status"
        return 0
    else
        echo "  ❌ $name: HTTP $status (expected $expected_status)"
        return 1
    fi
}

echo "🚀 Service Connectivity Tests"
echo "============================="

# Test Prometheus
echo "📊 Prometheus (Port $PROMETHEUS_PORT):"
test_endpoint "Health Check" "http://$HOSTNAME:$PROMETHEUS_PORT/-/healthy"
test_endpoint "Metrics API" "http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/query?query=up"
test_endpoint "Targets API" "http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/targets"

echo ""

# Test Grafana
echo "📈 Grafana (Port $GRAFANA_PORT):"
test_endpoint "Health Check" "http://$HOSTNAME:$GRAFANA_PORT/api/health"
test_endpoint "Login Page" "http://$HOSTNAME:$GRAFANA_PORT/login"

echo ""

# Test monitoring targets
echo "🎯 Monitoring Targets Status"
echo "============================"

TARGETS_JSON=$(curl -s "http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/targets" 2>/dev/null)
if [ $? -eq 0 ] && echo "$TARGETS_JSON" | grep -q "activeTargets"; then
    echo "📊 Active Prometheus Targets:"
    echo "$TARGETS_JSON" | jq -r '.data.activeTargets[] | "  \(if .health == "up" then "✅" else "❌" end) \(.labels.job) (\(.labels.instance // "no-instance")): \(.health)"' 2>/dev/null | sort
    
    echo ""
    echo "📈 Target Summary:"
    UP_COUNT=$(echo "$TARGETS_JSON" | jq '[.data.activeTargets[] | select(.health == "up")] | length' 2>/dev/null)
    TOTAL_COUNT=$(echo "$TARGETS_JSON" | jq '.data.activeTargets | length' 2>/dev/null)
    echo "  • Total Targets: $TOTAL_COUNT"
    echo "  • Healthy: $UP_COUNT"
    echo "  • Unhealthy: $((TOTAL_COUNT - UP_COUNT))"
else
    echo "❌ Could not retrieve Prometheus targets"
fi

echo ""

# Test key metrics availability
echo "📊 Key Metrics Verification"
echo "==========================="

test_metrics() {
    local metric=$1
    local description=$2
    
    local result=$(curl -s "http://$HOSTNAME:$PROMETHEUS_PORT/api/v1/query?query=$metric" 2>/dev/null | jq -r '.data.result | length' 2>/dev/null)
    if [ "$result" -gt 0 ] 2>/dev/null; then
        echo "  ✅ $description ($result series)"
    else
        echo "  ❌ $description (no data)"
    fi
}

test_metrics "up" "Service Up Status"
test_metrics "node_cpu_seconds_total" "CPU Metrics"
test_metrics "node_memory_MemAvailable_bytes" "Memory Metrics"
test_metrics "pg_up" "PostgreSQL Metrics"
test_metrics "container_cpu_usage_seconds_total" "Container Metrics"

echo ""

# Check Grafana configuration
echo "📋 Grafana Configuration"
echo "========================"

echo "🔧 Container Status:"
docker ps --filter "name=grafana" --format "  ✅ {{.Names}}: {{.Status}}"

echo ""
echo "🔌 Environment Variables:"
docker exec grafana env 2>/dev/null | grep ^GF_ | sed 's/^/  • /'

echo ""
echo "📁 Provisioned Resources:"
echo "  📊 Dashboards:"
docker exec grafana find /etc/grafana/provisioning/dashboards -name "*.json" 2>/dev/null | sed 's/^/    • /' || echo "    ❌ No dashboard files found"

echo "  🔗 Data Sources:"
docker exec grafana find /etc/grafana/provisioning/datasources -name "*.yml" -o -name "*.yaml" 2>/dev/null | sed 's/^/    • /' || echo "    ❌ No datasource files found"

echo ""

# Service accessibility summary
echo "🌐 External Access URLs"
echo "======================="
echo "📊 Primary Monitoring:"
echo "  • Grafana Dashboard:  http://$HOSTNAME:$GRAFANA_PORT"
echo "  • Prometheus Metrics: http://$HOSTNAME:$PROMETHEUS_PORT"
echo ""
echo "🔍 Direct Service Access:"
echo "  • Node Exporter:      http://$HOSTNAME:9100/metrics"
echo "  • Postgres Exporter:  http://$HOSTNAME:9187/metrics"
echo "  • Container Metrics:  http://$HOSTNAME:8081/metrics"
echo "  • Reranker API:       http://$HOSTNAME:8008"
echo ""
echo "🤖 AI Services:"
echo "  • Ollama Instance 1:  http://$HOSTNAME:11434"
echo "  • Ollama Instance 2:  http://$HOSTNAME:11435"
echo "  • Ollama Instance 3:  http://$HOSTNAME:11436"
echo "  • Ollama Instance 4:  http://$HOSTNAME:11437"

echo ""
echo "📝 Next Steps:"
echo "============="
echo "1. 🌐 Access Grafana: http://$HOSTNAME:$GRAFANA_PORT"
echo "2. 🔐 Login: admin/admin (default credentials)"
echo "3. 📊 Import dashboards or create new ones"
echo "4. 🎯 Check Prometheus targets: http://$HOSTNAME:$PROMETHEUS_PORT/targets"
echo "5. ⚙️  Configure alerts and notifications as needed"

echo ""
echo "✅ Monitoring verification complete!"