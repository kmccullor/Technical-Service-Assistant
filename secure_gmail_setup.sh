#!/bin/bash
# Secure Gmail Setup - No Plain Text Passwords
# Uses system keyring for secure password storage

echo "🔐 Secure Gmail Setup for End-of-Day Reports"
echo "============================================="
echo "✅ No plain text passwords stored!"
echo "✅ Uses system keyring encryption"
echo ""

# Check if keyring is available
echo "🔍 Checking secure storage availability..."
python3 -c "import keyring; print('✅ Keyring available:', keyring.get_keyring().__class__.__name__)" 2>/dev/null || {
    echo "❌ Keyring not available. Installing..."
    pip install keyring
}

echo ""
echo "📧 Gmail Account: kmccullor@gmail.com"
echo "🔑 Setting up secure password storage..."
echo ""

# Store Gmail password securely
echo "Please enter your Gmail App Password (16 characters, no spaces):"
echo "📖 Get it from: https://support.google.com/accounts/answer/185833"
python3 secure_email.py store kmccullor@gmail.com

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Password stored securely!"
    echo ""
    
    echo "🧪 Testing secure email configuration..."
    python3 secure_email.py test kmccullor@gmail.com
    
    echo ""
    echo "📋 Secure Email Commands:"
    echo "========================="
    echo ""
    echo "📤 Send test email:"
    echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py kmccullor@gmail.com"
    echo ""
    echo "📊 Generate and email today's report:"
    echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py --generate-report kmccullor@gmail.com"
    echo ""
    echo "⏰ Schedule daily reports (5 PM) - No password in crontab!"
    echo "   crontab -e"
    echo "   # Add this line:"
    echo "   0 17 * * * cd $(pwd) && EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py --generate-report kmccullor@gmail.com"
    echo ""
    echo "🔧 Password Management:"
    echo "   View stored accounts: python secure_email.py list"
    echo "   Update password:      python secure_email.py store kmccullor@gmail.com"
    echo "   Delete password:      python secure_email.py delete kmccullor@gmail.com"
    echo "   Test email:           python secure_email.py test kmccullor@gmail.com"
    echo ""
    echo "🔐 Security Features:"
    echo "   ✅ Password encrypted in system keyring"
    echo "   ✅ No plain text storage"
    echo "   ✅ OS-level security integration"
    echo "   ✅ No environment variables needed"
    
else
    echo "❌ Failed to store password securely"
    exit 1
fi