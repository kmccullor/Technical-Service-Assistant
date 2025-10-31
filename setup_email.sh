#!/bin/bash
# Email Configuration Setup for End of Day Reports
# This script helps configure email settings for automated reports

echo "📧 Email Configuration Setup for Technical Service Assistant"
echo "=========================================================="
echo ""

# Check if email script exists
if [[ ! -f "email_eod_report.py" ]]; then
    echo "❌ ERROR: email_eod_report.py not found"
    echo "   Please run this script from the project root directory"
    exit 1
fi

# Function to prompt for input
prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local current_value="${!var_name}"

    if [[ -n "$current_value" ]]; then
        read -p "$prompt [$current_value]: " input
        if [[ -z "$input" ]]; then
            input="$current_value"
        fi
    else
        read -p "$prompt: " input
    fi

    eval "$var_name=\"$input\""
}

# Get current environment variables
CURRENT_SENDER=${EOD_SENDER_EMAIL:-}
CURRENT_PASSWORD=${EOD_SENDER_PASSWORD:-}
CURRENT_RECIPIENT=${EOD_EMAIL:-}
CURRENT_SMTP_SERVER=${SMTP_SERVER:-}
CURRENT_SMTP_PORT=${SMTP_PORT:-587}

echo "🔧 Current Configuration:"
echo "   Sender Email: ${CURRENT_SENDER:-'Not set'}"
echo "   Sender Password: ${CURRENT_PASSWORD:+'***set***'}"
echo "   Recipient Email: ${CURRENT_RECIPIENT:-'Not set'}"
echo "   SMTP Server: ${CURRENT_SMTP_SERVER:-'Auto-detect'}"
echo "   SMTP Port: $CURRENT_SMTP_PORT"
echo ""

read -p "Do you want to configure email settings? (y/n): " configure
if [[ "$configure" != "y" && "$configure" != "Y" ]]; then
    echo "Configuration cancelled."
    exit 0
fi

echo ""
echo "📝 Email Configuration:"
echo ""

# Get sender email
prompt_input "Sender email address (your email)" "CURRENT_SENDER"

# Get sender password
if [[ -z "$CURRENT_PASSWORD" ]]; then
    echo ""
    echo "📋 Password Information:"
    echo "   • Gmail: Use App Password (not your regular password)"
    echo "   • Outlook/Hotmail: Use App Password or regular password"
    echo "   • Corporate email: Use your regular password"
    echo ""
    read -s -p "Sender email password (hidden input): " CURRENT_PASSWORD
    echo ""
fi

# Get recipient email
prompt_input "Recipient email address (who receives reports)" "CURRENT_RECIPIENT"

# Advanced SMTP settings
echo ""
read -p "Configure advanced SMTP settings? (y/n): " advanced
if [[ "$advanced" == "y" || "$advanced" == "Y" ]]; then
    prompt_input "SMTP server (leave blank for auto-detect)" "CURRENT_SMTP_SERVER"
    prompt_input "SMTP port" "CURRENT_SMTP_PORT"
fi

echo ""
echo "🧪 Testing email configuration..."

# Set environment variables for test
export EOD_SENDER_EMAIL="$CURRENT_SENDER"
export EOD_SENDER_PASSWORD="$CURRENT_PASSWORD"
export EOD_EMAIL="$CURRENT_RECIPIENT"
if [[ -n "$CURRENT_SMTP_SERVER" ]]; then
    export SMTP_SERVER="$CURRENT_SMTP_SERVER"
fi
if [[ -n "$CURRENT_SMTP_PORT" ]]; then
    export SMTP_PORT="$CURRENT_SMTP_PORT"
fi

# Test email
if python email_eod_report.py --test "$CURRENT_RECIPIENT"; then
    echo ""
    echo "✅ Email test successful!"
    echo ""

    # Generate environment setup
    echo "🔧 Environment Setup:"
    echo "Add these lines to your ~/.bashrc or crontab:"
    echo ""
    echo "export EOD_SENDER_EMAIL=\"$CURRENT_SENDER\""
    echo "export EOD_SENDER_PASSWORD=\"$CURRENT_PASSWORD\""
    echo "export EOD_EMAIL=\"$CURRENT_RECIPIENT\""
    if [[ -n "$CURRENT_SMTP_SERVER" ]]; then
        echo "export SMTP_SERVER=\"$CURRENT_SMTP_SERVER\""
    fi
    if [[ "$CURRENT_SMTP_PORT" != "587" ]]; then
        echo "export SMTP_PORT=\"$CURRENT_SMTP_PORT\""
    fi
    echo ""

    # Generate crontab example
    echo "📅 Crontab Example (with email):"
    echo ""
    echo "# Add these environment variables to your crontab:"
    echo "EOD_SENDER_EMAIL=$CURRENT_SENDER"
    echo "EOD_SENDER_PASSWORD=$CURRENT_SENDER_PASSWORD"
    echo "EOD_EMAIL=$CURRENT_RECIPIENT"
    if [[ -n "$CURRENT_SMTP_SERVER" ]]; then
        echo "SMTP_SERVER=$CURRENT_SMTP_SERVER"
    fi
    if [[ "$CURRENT_SMTP_PORT" != "587" ]]; then
        echo "SMTP_PORT=$CURRENT_SMTP_PORT"
    fi
    echo ""
    echo "# Daily end-of-day report with email (Monday-Friday at 5 PM)"
    echo "0 17 * * 1-5 $(pwd)/scripts/end_of_day.sh"
    echo ""

    # Offer to save configuration
    read -p "Save configuration to .env file? (y/n): " save_env
    if [[ "$save_env" == "y" || "$save_env" == "Y" ]]; then
        cat > .env << EOF
# Email Configuration for End of Day Reports
EOD_SENDER_EMAIL="$CURRENT_SENDER"
EOD_SENDER_PASSWORD="$CURRENT_PASSWORD"
EOD_EMAIL="$CURRENT_RECIPIENT"
EOF
        if [[ -n "$CURRENT_SMTP_SERVER" ]]; then
            echo "SMTP_SERVER=\"$CURRENT_SMTP_SERVER\"" >> .env
        fi
        if [[ "$CURRENT_SMTP_PORT" != "587" ]]; then
            echo "SMTP_PORT=\"$CURRENT_SMTP_PORT\"" >> .env
        fi

        echo "✅ Configuration saved to .env file"
        echo "   Source it with: source .env"
    fi

    echo ""
    echo "🎉 Email configuration complete!"
    echo "   Test sending a report: python email_eod_report.py $CURRENT_RECIPIENT"

else
    echo ""
    echo "❌ Email test failed. Please check your configuration."
    echo ""
    echo "Common issues:"
    echo "• Gmail: Enable 2FA and use App Password"
    echo "• Corporate email: Check SMTP server settings"
    echo "• Firewall: Ensure SMTP ports are not blocked"
fi
