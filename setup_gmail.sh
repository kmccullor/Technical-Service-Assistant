#!/bin/bash
# Gmail Setup for End-of-Day Reports
# Quick setup for kmccullor@gmail.com

echo "📧 Setting up Gmail for End-of-Day Reports"
echo "==========================================="

# Create Gmail configuration
cat > .env.gmail <<EOF
# Gmail Configuration for End-of-Day Reports
# Generated on $(date +%Y-%m-%d)

# Recipient and Sender Configuration
EOD_RECIPIENT_EMAIL=kmccullor@gmail.com
EOD_SENDER_EMAIL=kmccullor@gmail.com
EOD_SENDER_NAME="Technical Service Assistant"

# Gmail SMTP Configuration
EOD_SMTP_SERVER=smtp.gmail.com
EOD_SMTP_PORT=587
EOD_SMTP_USE_TLS=true

# Authentication (Required for Gmail - use App Password)
# EOD_SENDER_PASSWORD=your_gmail_app_password_here

# Email Settings
EOD_EMAIL_SUBJECT="Daily Technical Service Report - \$(date +%Y-%m-%d)"
EOD_EMAIL_FORMAT=html

# Report Configuration
EOD_INCLUDE_PERFORMANCE=true
EOD_INCLUDE_LOGS=true
EOD_INCLUDE_HEALTH=true
EOF

echo "✅ Created .env.gmail configuration file"
echo ""

echo "🧪 Testing Gmail configuration..."
source .env.gmail && python email_eod_report.py --test kmccullor@gmail.com

echo ""
echo "📝 Next Steps:"
echo "1. Get Gmail App Password:"
echo "   - Go to Google Account settings"
echo "   - Security → 2-Step Verification → App passwords"
echo "   - Generate app password for 'Mail'"
echo ""
echo "2. Set your app password:"
echo "   export EOD_SENDER_PASSWORD='your_16_character_app_password'"
echo ""
echo "3. Test sending email:"
echo "   export EOD_SENDER_PASSWORD='your_app_password'"
echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py kmccullor@gmail.com"
echo ""
echo "4. Schedule daily reports (5 PM):"
echo "   crontab -e"
echo "   # Add this line:"
echo "   0 17 * * * cd $(pwd) && EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' EOD_SENDER_PASSWORD='your_app_password' python email_eod_report.py --generate-report kmccullor@gmail.com"
echo ""
echo "🔗 Gmail App Password Setup: https://support.google.com/accounts/answer/185833"
