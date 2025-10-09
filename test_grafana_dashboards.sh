#!/bin/bash
# Grafana Dashboard Access Test
# Quick script to verify dashboards are loaded

HOSTNAME="RNI-LLM-01.lab.sensus.net"
GRAFANA_URL="http://$HOSTNAME:3001"

echo "🎯 Testing Grafana Dashboard Access"
echo "===================================="
echo "🌐 Grafana URL: $GRAFANA_URL"
echo ""

# Test basic connectivity
echo "🔌 Testing Grafana connectivity..."
if curl -s --connect-timeout 5 "$GRAFANA_URL/api/health" | grep -q "ok"; then
    echo "✅ Grafana is accessible"
else
    echo "❌ Grafana is not accessible"
    exit 1
fi

echo ""
echo "📊 Available Dashboards:"
echo "========================"

# List dashboard files from container
echo "📁 Dashboard files in container:"
docker exec grafana ls -1 /etc/grafana/provisioning/dashboards/*.json | sed 's|/etc/grafana/provisioning/dashboards/||g' | sed 's|\.json||g' | sort

echo ""
echo "🔍 Access Instructions:"
echo "======================="
echo "1. Open browser to: $GRAFANA_URL"
echo "2. Login with: admin / admin (default)"
echo "3. Look for dashboards in:"
echo "   • Home → Dashboards"
echo "   • Search icon → Browse dashboards"
echo "   • 'Technical Service Assistant' folder"
echo ""
echo "📋 Expected Dashboards:"
echo "   ✓ Technical Service Assistant - System Overview"
echo "   ✓ Technical Service Assistant - AI Services" 
echo "   ✓ Technical Service Assistant - Infrastructure"
echo "   ✓ Database Performance"
echo "   ✓ Routing Analytics"
echo "   ✓ Multimodal Analytics"
echo ""

# Test if we can reach the login page
echo "🧪 Testing login page..."
if curl -s "$GRAFANA_URL/login" | grep -q "Grafana"; then
    echo "✅ Login page accessible"
else
    echo "❌ Login page not accessible"
fi

echo ""
echo "🚀 Next Steps:"
echo "=============="
echo "1. Visit: $GRAFANA_URL"
echo "2. Login with admin/admin"
echo "3. Change password when prompted"
echo "4. Navigate to 'Dashboards' to see your monitoring data"
echo ""
echo "💡 Tip: If dashboards don't appear immediately, try:"
echo "   • Refresh the page"
echo "   • Check 'Configuration' → 'Data Sources' (Prometheus should be configured)"
echo "   • Look in the 'General' folder or search for 'Technical Service'"