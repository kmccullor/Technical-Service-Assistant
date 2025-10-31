#!/bin/bash
# Final Monitoring Configuration Summary
# Shows current monitoring setup status

HOSTNAME="RNI-LLM-01.lab.sensus.net"

echo "🎯 Technical Service Assistant - Monitoring Setup Complete"
echo "=========================================================="
echo "🌐 Host: $HOSTNAME"
echo "📅 Configured: $(date)"
echo ""

echo "✅ PROMETHEUS & GRAFANA STATUS"
echo "=============================="

# Check services
echo "🚀 Core Services:"
if curl -s "http://$HOSTNAME:9091/-/healthy" >/dev/null 2>&1; then
    echo "  ✅ Prometheus: Running (Port 9091)"
    echo "     URL: http://$HOSTNAME:9091"
else
    echo "  ❌ Prometheus: Not accessible"
fi

if curl -s "http://$HOSTNAME:3001/api/health" >/dev/null 2>&1; then
    echo "  ✅ Grafana: Running (Port 3001)"
    echo "     URL: http://$HOSTNAME:3001"
    echo "     Login: admin/admin"
else
    echo "  ❌ Grafana: Not accessible"
fi

echo ""

# Active targets
echo "📊 ACTIVE MONITORING TARGETS"
echo "============================"
TARGET_DATA=$(curl -s "http://$HOSTNAME:9091/api/v1/targets" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$TARGET_DATA" | jq -r '.data.activeTargets[] | "\(if .health == "up" then "✅" else "❌" end) \(.labels.job): \(.labels.instance // "internal") - \(.health)"' 2>/dev/null | sort

    echo ""
    UP_COUNT=$(echo "$TARGET_DATA" | jq '[.data.activeTargets[] | select(.health == "up")] | length' 2>/dev/null)
    TOTAL_COUNT=$(echo "$TARGET_DATA" | jq '.data.activeTargets | length' 2>/dev/null)
    echo "📈 Summary: $UP_COUNT/$TOTAL_COUNT targets healthy"
else
    echo "❌ Cannot retrieve target status"
fi

echo ""

# What's being monitored
echo "🔍 MONITORING COVERAGE"
echo "======================"
echo "🖥️  System Metrics:"
echo "  • CPU, Memory, Disk usage (node-exporter)"
echo "  • Container resources (cAdvisor)"
echo ""
echo "🗄️  Database Metrics:"
echo "  • PostgreSQL performance (postgres-exporter)"
echo "  • Redis cache metrics (redis-exporter)"
echo ""
echo "🤖 Application Metrics:"
echo "  • Reranker API health & performance"
echo "  • PDF processor status"
echo "  • RAG application health"
echo ""
echo "🔧 Infrastructure:"
echo "  • Docker container health"
echo "  • Network connectivity"
echo "  • Service availability"

echo ""

# Dashboards
echo "📊 GRAFANA DASHBOARDS"
echo "====================="
DASHBOARD_COUNT=$(docker exec grafana find /etc/grafana/provisioning/dashboards -name "*.json" 2>/dev/null | wc -l)
echo "📋 Available Dashboards: $DASHBOARD_COUNT"
docker exec grafana find /etc/grafana/provisioning/dashboards -name "*.json" 2>/dev/null | sed 's/.*\///;s/\.json$//' | sed 's/^/  📊 /'

echo ""

# Access information
echo "🌐 ACCESS INFORMATION"
echo "===================="
echo "🖥️  Primary Monitoring Interface:"
echo "   http://$HOSTNAME:3001"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "🔍 Prometheus Query Interface:"
echo "   http://$HOSTNAME:9091"
echo ""
echo "📊 Direct Metrics Endpoints:"
echo "   • System: http://$HOSTNAME:9100/metrics"
echo "   • Database: http://$HOSTNAME:9187/metrics"
echo "   • Containers: http://$HOSTNAME:8081/metrics"
echo "   • Cache: http://$HOSTNAME:9121/metrics"

echo ""

# Network configuration summary
echo "🔧 NETWORK CONFIGURATION"
echo "========================"
echo "🐳 Container Network:"
echo "  • Internal communication via service names"
echo "  • Docker network bridge: technical-service-assistant_default"
echo ""
echo "🌐 External Access:"
echo "  • Hostname: $HOSTNAME"
echo "  • Port mappings defined in docker-compose.yml"
echo "  • Firewall: Ensure ports 3001, 9091 are accessible"

echo ""

# Monitoring best practices
echo "📝 MONITORING BEST PRACTICES"
echo "============================"
echo "1. 🔐 Security:"
echo "   • Change default Grafana password in production"
echo "   • Consider reverse proxy with SSL/TLS"
echo "   • Restrict network access as needed"
echo ""
echo "2. 📊 Dashboard Usage:"
echo "   • Create custom dashboards for your specific needs"
echo "   • Set up alerts for critical metrics"
echo "   • Use Grafana's notification channels"
echo ""
echo "3. 🎯 Performance:"
echo "   • Monitor key application metrics"
echo "   • Set up alerting for high resource usage"
echo "   • Track AI service response times"
echo ""
echo "4. 📈 Scaling:"
echo "   • Monitor container resource usage"
echo "   • Track database performance"
echo "   • Set up capacity planning alerts"

echo ""
echo "✅ MONITORING SETUP COMPLETE!"
echo "============================="
echo "🚀 Your Technical Service Assistant now has comprehensive"
echo "   monitoring with Prometheus and Grafana configured for:"
echo ""
echo "   • Real-time system metrics"
echo "   • Application performance monitoring"
echo "   • Database health tracking"
echo "   • Container resource monitoring"
echo "   • Custom alerting capabilities"
echo ""
echo "🎯 Next: Visit http://$HOSTNAME:3001 to start monitoring!"
