#!/bin/bash
# Quick Email Demo for End of Day Reports

echo "📧 Email End of Day Report - Quick Demo"
echo "======================================"
echo ""

# Check if we have the required files
if [[ ! -f "email_eod_report.py" ]]; then
    echo "❌ ERROR: email_eod_report.py not found"
    exit 1
fi

if [[ ! -f "logs/daily_report_$(date +%Y%m%d).md" ]]; then
    echo "⚠️  No report found for today. Let me generate one first..."
    ./scripts/end_of_day.sh --automated
    echo ""
fi

echo "🎯 Available Options:"
echo ""
echo "1. 📧 Test email configuration (no actual email sent)"
echo "2. 🔧 Run interactive email setup"
echo "3. 📤 Send today's report to an email address"
echo "4. 📋 Show configuration instructions"
echo ""

read -p "Choose an option (1-4): " choice

case $choice in
    1)
        echo ""
        read -p "Enter test email address: " test_email
        echo ""
        echo "🧪 Testing email configuration..."
        python email_eod_report.py --test "$test_email"
        ;;
    
    2)
        echo ""
        echo "🔧 Running interactive email setup..."
        ./setup_email.sh
        ;;
    
    3)
        echo ""
        read -p "Enter recipient email address: " recipient_email
        echo ""
        echo "📧 Setting up environment..."
        
        if [[ -z "${EOD_SENDER_EMAIL:-}" ]]; then
            read -p "Enter your email address (sender): " sender_email
            export EOD_SENDER_EMAIL="$sender_email"
        fi
        
        if [[ -z "${EOD_SENDER_PASSWORD:-}" ]]; then
            echo "📋 For Gmail: Use App Password, not regular password"
            read -s -p "Enter your email password: " sender_password
            export EOD_SENDER_PASSWORD="$sender_password"
            echo ""
        fi
        
        echo ""
        echo "📤 Sending today's report..."
        if python email_eod_report.py "$recipient_email"; then
            echo ""
            echo "✅ SUCCESS: Report sent to $recipient_email"
        else
            echo ""
            echo "❌ FAILED: Check your email configuration"
        fi
        ;;
    
    4)
        echo ""
        echo "📋 Email Configuration Instructions:"
        echo ""
        echo "1. Set Environment Variables:"
        echo "   export EOD_SENDER_EMAIL='your.email@company.com'"
        echo "   export EOD_SENDER_PASSWORD='your_app_password'"
        echo "   export EOD_EMAIL='recipient@company.com'"
        echo ""
        echo "2. Test Configuration:"
        echo "   python email_eod_report.py --test recipient@company.com"
        echo ""
        echo "3. Send Report:"
        echo "   python email_eod_report.py recipient@company.com"
        echo ""
        echo "4. Add to Crontab:"
        echo "   crontab -e"
        echo "   # Add environment variables and job:"
        echo "   EOD_SENDER_EMAIL=your.email@company.com"
        echo "   EOD_SENDER_PASSWORD=your_app_password"
        echo "   EOD_EMAIL=recipient@company.com"
        echo "   0 17 * * 1-5 $(pwd)/scripts/end_of_day.sh"
        echo ""
        echo "📧 Gmail Users:"
        echo "   - Enable 2FA in Google Account"
        echo "   - Generate App Password in Security settings"
        echo "   - Use App Password (not regular password)"
        ;;
    
    *)
        echo "Invalid option. Please choose 1-4."
        exit 1
        ;;
esac

echo ""
echo "🎉 Demo complete!"
echo ""
echo "📚 For more information:"
echo "   - Full guide: CRONTAB_SETUP_GUIDE.md"
echo "   - Interactive setup: ./setup_email.sh"
echo "   - Test script: python email_eod_report.py --test your@email.com"