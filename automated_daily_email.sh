#!/bin/bash
# Fully Automated Daily Email Report
# Uses environment variable for password (secure for crontab)

cd /home/kmccullor/Projects/Technical-Service-Assistant

echo "[$(date)] 🌅 Starting automated daily email report..."

# Generate the daily report
./scripts/end_of_day.sh --automated

# Check if report was generated
REPORT_FILE="logs/daily_report_$(date +%Y%m%d).md"
if [ ! -f "$REPORT_FILE" ]; then
    echo "[$(date)] ❌ Report file not found: $REPORT_FILE"
    exit 1
fi

# Source environment file to get password
if [ -f "$HOME/.technical-service-env" ]; then
    source "$HOME/.technical-service-env"
fi

# Send email using environment variable for password
if [ -z "$GMAIL_APP_PASSWORD" ]; then
    echo "[$(date)] ❌ GMAIL_APP_PASSWORD environment variable not set"
    echo "Source the environment: source ~/.technical-service-env"
    exit 1
fi

echo "[$(date)] 📧 Sending enhanced daily report via Gmail..."
echo "[$(date)] 📧 Using Gmail password: ${GMAIL_APP_PASSWORD:0:4}***"

# Use enhanced EOD reporting with auto-Gmail detection and monitoring integration
EOD_SENDER_PASSWORD="$GMAIL_APP_PASSWORD" \
python email_eod_report.py "kmccullor@gmail.com" "$REPORT_FILE"

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ Daily report sent successfully to kmccullor@gmail.com"
else
    echo "[$(date)] ❌ Failed to send daily report"
    exit 1
fi
