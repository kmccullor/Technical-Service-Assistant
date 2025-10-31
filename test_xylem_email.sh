#!/bin/bash
# Quick Email Test for Xylem Corporate Setup
# This script tests email functionality for kevin.mccullor@xylem.com

set -e

echo "📧 Testing Xylem Corporate Email Configuration"
echo "=================================================="

# Load configuration
source .env.email 2>/dev/null || echo "⚠️  Warning: .env.email not found, using defaults"

# Set corporate email settings
export EOD_SENDER_EMAIL="no-relay@RNI-LLM-01.lab.sensus.net"
export EOD_RECIPIENT_EMAIL="kevin.mccullor@xylem.com"
export EOD_SMTP_SERVER="sensus.xylem.com"
export EOD_SMTP_PORT="587"
export EOD_SMTP_USE_TLS="true"

echo "📍 Configuration:"
echo "   From: $EOD_SENDER_EMAIL"
echo "   To: $EOD_RECIPIENT_EMAIL"
echo "   SMTP: $EOD_SMTP_SERVER:$EOD_SMTP_PORT"
echo "   TLS: $EOD_SMTP_USE_TLS"
echo ""

echo "🧪 Running test mode (no actual email sent)..."
python email_eod_report.py --test kevin.mccullor@xylem.com

echo ""
echo "📝 To send actual email, you have two options:"
echo "   1. For no-auth corporate relay:"
echo "      export EOD_SENDER_PASSWORD=''"
echo "      python email_eod_report.py kevin.mccullor@xylem.com"
echo ""
echo "   2. For authenticated corporate email:"
echo "      export EOD_SENDER_PASSWORD='your_password'"
echo "      python email_eod_report.py kevin.mccullor@xylem.com"
echo ""
echo "📋 To generate and email today's report:"
echo "   python email_eod_report.py --generate-report kevin.mccullor@xylem.com"
echo ""
echo "⏰ To schedule daily reports, add to crontab:"
echo "   0 17 * * * cd $(pwd) && source .env.email && python email_eod_report.py --generate-report kevin.mccullor@xylem.com"
