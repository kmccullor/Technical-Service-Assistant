#!/bin/bash
# Quick Gmail Test - kmccullor@gmail.com
# This script tests Gmail email functionality

echo "📧 Testing Gmail Email Configuration"
echo "===================================="
echo "📍 Account: kmccullor@gmail.com"
echo "📤 SMTP: smtp.gmail.com:587 (TLS)"
echo ""

echo "🧪 Running test mode (no actual email sent)..."
EOD_SENDER_EMAIL="kmccullor@gmail.com" \
EOD_RECIPIENT_EMAIL="kmccullor@gmail.com" \
EOD_SMTP_SERVER="smtp.gmail.com" \
EOD_SMTP_PORT="587" \
EOD_SMTP_USE_TLS="true" \
python email_eod_report.py --test kmccullor@gmail.com

echo ""
echo "📝 To send actual email:"
echo "1. Get Gmail App Password from: https://support.google.com/accounts/answer/185833"
echo "2. Run this command:"
echo ""
echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' \\"
echo "   EOD_SMTP_SERVER='smtp.gmail.com' \\"
echo "   EOD_SENDER_PASSWORD='your_16_char_app_password' \\"
echo "   python email_eod_report.py kmccullor@gmail.com"
echo ""
echo "📋 To generate and email today's report:"
echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' \\"
echo "   EOD_SMTP_SERVER='smtp.gmail.com' \\"
echo "   EOD_SENDER_PASSWORD='your_app_password' \\"
echo "   python email_eod_report.py --generate-report kmccullor@gmail.com"
echo ""
echo "⏰ For daily 5 PM reports, add to crontab:"
echo "   crontab -e"
echo "   # Add:"
echo "   0 17 * * * cd $(pwd) && EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' EOD_SENDER_PASSWORD='your_app_password' python email_eod_report.py --generate-report kmccullor@gmail.com"