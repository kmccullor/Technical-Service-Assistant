#!/bin/bash
# Test Gmail Configuration for Enhanced EOD Reports
# Run this to validate your setup before the cron job executes

echo "🔍 Testing Enhanced EOD Email Configuration"
echo "=========================================="

cd /home/kmccullor/Projects/Technical-Service-Assistant

# Check if environment file exists
if [ -f "$HOME/.technical-service-env" ]; then
    echo "✅ Environment file found: $HOME/.technical-service-env"
    source "$HOME/.technical-service-env"
else
    echo "❌ Environment file not found: $HOME/.technical-service-env"
    echo "   Create it with: echo 'export GMAIL_APP_PASSWORD=\"your-app-password\"' > ~/.technical-service-env"
    exit 1
fi

# Check if Gmail password is set
if [ -z "$GMAIL_APP_PASSWORD" ]; then
    echo "❌ GMAIL_APP_PASSWORD not set in environment file"
    echo "   Add to ~/.technical-service-env: export GMAIL_APP_PASSWORD=\"your-16-char-password\""
    exit 1
else
    echo "✅ Gmail app password configured: ${GMAIL_APP_PASSWORD:0:4}***"
fi

# Test the enhanced email system
echo ""
echo "🧪 Testing enhanced EOD email system..."
echo "----------------------------------------"

# Test mode first (no actual email sent)
echo "Testing Gmail SMTP connection and authentication..."
EOD_SENDER_PASSWORD="$GMAIL_APP_PASSWORD" python email_eod_report.py --test kmccullor@gmail.com

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configuration test passed!"
    echo ""
    echo "🚀 Ready to send actual enhanced report? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "📧 Sending enhanced EOD report with live monitoring data..."
        EOD_SENDER_PASSWORD="$GMAIL_APP_PASSWORD" python email_eod_report.py kmccullor@gmail.com

        if [ $? -eq 0 ]; then
            echo "🎉 Success! Check your Gmail for the enhanced report"
            echo "   Report includes: System health, monitoring metrics, documentation stats"
        else
            echo "❌ Failed to send enhanced report"
        fi
    else
        echo "ℹ️  Test complete. Run the command above manually when ready."
    fi
else
    echo "❌ Configuration test failed"
    exit 1
fi

echo ""
echo "📋 Your Cron Job Status:"
echo "------------------------"
crontab -l | grep "automated_daily_email.sh" || echo "No cron job found"

echo ""
echo "💡 Next Steps:"
echo "- Your cron runs daily at 8 PM (20:00)"
echo "- Enhanced reports include live monitoring data"
echo "- Logs saved to: logs/automated_email.log"
echo "- Manual test: ./automated_daily_email.sh"
