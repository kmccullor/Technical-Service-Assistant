#!/bin/bash
# One-time setup for automated email reports
# Sets up crontab with environment variable

echo "🔧 Setting up fully automated daily email reports"
echo "=================================================="

# Create environment file for crontab
ENV_FILE="$HOME/.technical-service-env"

echo "📝 Creating environment file: $ENV_FILE"
cat > "$ENV_FILE" << EOF
# Environment variables for Technical Service Assistant
# Created: $(date)
GMAIL_APP_PASSWORD=tmxv lopq grxw geey
PATH=/usr/local/bin:/usr/bin:/bin
SHELL=/bin/bash
EOF

chmod 600 "$ENV_FILE"  # Secure permissions
echo "✅ Environment file created with secure permissions"

# Create the crontab entry
CRON_FILE="/tmp/technical_service_cron"
echo "📅 Creating crontab entry..."

# Get current crontab (if any) and add our job
(crontab -l 2>/dev/null; echo "# Technical Service Assistant - Daily Email Report") > "$CRON_FILE"
echo "0 17 * * * source $ENV_FILE && cd $(pwd) && ./automated_daily_email.sh >> logs/automated_email.log 2>&1" >> "$CRON_FILE"

# Install the crontab
crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "✅ Crontab updated successfully"
echo ""
echo "📋 Automation Summary:"
echo "======================"
echo "⏰ Schedule: Daily at 5:00 PM"
echo "📧 Recipient: kmccullor@gmail.com,kevin.mccullor@xylem.com,jim.hitchcock@xylem.com"
echo "🔐 Password: Stored in $ENV_FILE (secure permissions)"
echo "📝 Logs: logs/automated_email.log"
echo ""
echo "🧪 Test the automation manually:"
echo "   source $ENV_FILE && ./automated_daily_email.sh"
echo ""
echo "📅 View current crontab:"
echo "   crontab -l"
echo ""
echo "🔍 Check logs:"
echo "   tail -f logs/automated_email.log"
echo ""
echo "✅ Fully automated! No manual passwords needed!"
