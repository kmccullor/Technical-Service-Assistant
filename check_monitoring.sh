#!/bin/bash
# Monitoring Stack Status Check
# Provides comprehensive status of Prometheus and Grafana monitoring

echo "🔍 Technical Service Assistant - Monitoring Stack Status"
echo "========================================================"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "📊 Monitoring Services Status:"
echo "=============================="

# Check Prometheus
PROM_HOST="rni-llm-01.lab.sensus.net"
GRAFANA_HOST="rni-llm-01.lab.sensus.net"
PROM_API="http://${PROM_HOST}:9091"
GRAFANA_URL="http://${GRAFANA_HOST}:3001"

if curl -s "http://${PROM_HOST}:9091/-/healthy" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Prometheus${NC} - Running on http://${PROM_HOST}:9091"
else
    echo -e "${RED}❌ Prometheus${NC} - Not accessible"
fi

# Check Grafana
if curl -s "http://${GRAFANA_HOST}:3001/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Grafana${NC} - Running on http://${GRAFANA_HOST}:3001"
    echo "   Default login: admin/admin"
else
    echo -e "${RED}❌ Grafana${NC} - Not accessible"
fi

# Check exporters
echo ""
echo "📈 Metrics Exporters:"
echo "===================="

# Node Exporter
if curl -s http://localhost:9100/metrics | head -1 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Node Exporter${NC} - System metrics (port 9100)"
else
    echo -e "${RED}❌ Node Exporter${NC} - Not accessible"
fi

# Postgres Exporter
if curl -s http://localhost:9187/metrics | head -1 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL Exporter${NC} - Database metrics (port 9187)"
else
    echo -e "${RED}❌ PostgreSQL Exporter${NC} - Not accessible"
fi

# Redis Exporter
if curl -s http://localhost:9121/metrics | head -1 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis Exporter${NC} - Cache metrics (port 9121)"
else
    echo -e "${RED}❌ Redis Exporter${NC} - Not accessible"
fi

# cAdvisor
if curl -s http://localhost:8081/metrics | head -1 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ cAdvisor${NC} - Container metrics (port 8081)"
else
    echo -e "${RED}❌ cAdvisor${NC} - Not accessible"
fi

# Check Prometheus targets
echo ""
echo "🎯 Prometheus Target Status:"
echo "==========================="

TARGETS=$(curl -s "${PROM_API}/api/v1/targets" | jq -r '.data.activeTargets[] | "\(.labels.job):\(.health)"' 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$TARGETS" ]; then
    while IFS=: read -r job health; do
        if [ "$health" = "up" ]; then
            echo -e "${GREEN}✅ $job${NC}"
        else
            echo -e "${RED}❌ $job${NC} ($health)"
        fi
    done <<< "$TARGETS"
else
    echo -e "${YELLOW}⚠️  Could not retrieve target status${NC}"
fi

echo ""
echo "📋 Key Metrics Available:"
echo "========================="
echo "• System Resources (CPU, Memory, Disk)"
echo "• Docker Container Statistics"
echo "• PostgreSQL Database Performance"
echo "• Redis Cache Performance"
echo "• Custom Application Metrics"
echo "• HTTP Request Metrics"
echo ""

echo "🌐 Access URLs:"
echo "==============="
echo "• Prometheus: ${PROM_API}"
echo "• Grafana: ${GRAFANA_URL} (admin/admin)"
echo "• cAdvisor: http://localhost:8081"
echo "• Node Metrics: http://localhost:9100/metrics"
echo ""

echo "📊 Quick Grafana Setup:"
echo "======================="
echo "1. Open ${GRAFANA_URL}"
echo "2. Login with admin/admin"
echo "3. Dashboards are pre-configured and auto-imported"
echo "4. Check 'Technical Service Assistant' folder"
echo ""

echo "🔍 Useful Queries:"
echo "=================="
echo "• System CPU: 100 - (avg(irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)"
echo "• Memory Usage: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
echo "• Container Status: up"
echo "• Database Connections: pg_stat_activity_count"
echo ""

# Check if any containers are down
DOWN_CONTAINERS=$(docker ps -a --filter "name=prometheus|grafana|exporter|cadvisor" --format "table {{.Names}}\t{{.Status}}" | grep -v "Up" | wc -l)

if [ $DOWN_CONTAINERS -gt 1 ]; then  # Subtract 1 for header
    echo -e "${YELLOW}⚠️  Some monitoring containers may be down. Check with:${NC}"
    echo "   docker ps --filter \"name=prometheus|grafana|exporter|cadvisor\""
    echo ""
fi

echo -e "${BLUE}🚀 Monitoring stack is ready for Technical Service Assistant!${NC}"
