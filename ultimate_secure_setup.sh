#!/bin/bash
# Ultimate Secure Email Setup - Multiple Security Options
# No plain text passwords anywhere!

echo "🔐 Ultimate Secure Email Setup"
echo "=============================="
echo "✅ Multiple security options available"
echo "✅ No plain text password storage"
echo "✅ Choose your preferred security method"
echo ""

# Check available security backends
echo "🔍 Checking available security options..."

# Check keyring
keyring_available=false
if python3 -c "import keyring; print('Keyring backend:', keyring.get_keyring().__class__.__name__)" 2>/dev/null; then
    keyring_available=true
    echo "✅ System keyring available"
else
    echo "⚠️  System keyring not accessible"
fi

# Check cryptography for file encryption
crypto_available=false
if python3 -c "from cryptography.fernet import Fernet; print('✅ Cryptography available')" 2>/dev/null; then
    crypto_available=true
else
    echo "❌ Cryptography not available"
    echo "   Installing cryptography..."
    pip install cryptography
    crypto_available=true
fi

echo ""
echo "📧 Gmail Account: kmccullor@gmail.com"
echo ""
echo "🔐 Security Options:"
echo "==================="

if [ "$keyring_available" = true ]; then
    echo "1. System Keyring (Recommended for desktop)"
    echo "   - Integrates with OS security"
    echo "   - No master password needed"
    echo "   - Most convenient"
fi

if [ "$crypto_available" = true ]; then
    echo "2. Encrypted File Storage (Recommended for servers)"
    echo "   - Uses master password encryption"
    echo "   - Works on any system"
    echo "   - High security"
fi

echo "3. Environment Variable (Session-only)"
echo "   - Password not stored permanently"
echo "   - Must enter each session"
echo "   - Most secure (no storage)"

echo ""
read -p "Choose security method (1/2/3): " choice

case $choice in
    1)
        if [ "$keyring_available" = true ]; then
            echo ""
            echo "🔐 Setting up System Keyring storage..."
            chmod +x secure_email.py
            python3 secure_email.py store kmccullor@gmail.com
        else
            echo "❌ System keyring not available"
            exit 1
        fi
        ;;
    2)
        echo ""
        echo "🔐 Setting up Encrypted File storage..."
        echo "You'll create a master password to encrypt your email password."
        chmod +x secure_file_email.py
        python3 secure_file_email.py store kmccullor@gmail.com
        ;;
    3)
        echo ""
        echo "🔐 Setting up Environment Variable method..."
        echo "Your password will only exist in memory during this session."
        echo ""
        echo "Enter your Gmail App Password (get from: https://support.google.com/accounts/answer/185833):"
        read -s gmail_password
        export EOD_SENDER_PASSWORD="$gmail_password"
        echo ""
        echo "✅ Password set for this session only"
        echo ""
        echo "🧪 Testing email configuration..."
        EOD_SENDER_EMAIL='kmccullor@gmail.com' \
        EOD_SMTP_SERVER='smtp.gmail.com' \
        EOD_SMTP_PORT='587' \
        EOD_SMTP_USE_TLS='true' \
        python email_eod_report.py --test kmccullor@gmail.com
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

if [ $? -eq 0 ] && [ "$choice" != "3" ]; then
    echo ""
    echo "✅ Password stored securely!"
    echo ""
    echo "🧪 Testing secure email configuration..."
    
    if [ "$choice" = "1" ]; then
        python3 secure_email.py test kmccullor@gmail.com
    elif [ "$choice" = "2" ]; then
        python3 secure_file_email.py test kmccullor@gmail.com
    fi
fi

echo ""
echo "📋 Secure Email Commands:"
echo "========================="
echo ""

if [ "$choice" = "1" ]; then
    echo "📤 Send email (keyring):"
    echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py kmccullor@gmail.com"
    echo ""
    echo "🔧 Manage passwords:"
    echo "   python secure_email.py list"
    echo "   python secure_email.py test kmccullor@gmail.com"
    
elif [ "$choice" = "2" ]; then
    echo "📤 Send email (encrypted file):"
    echo "   # Password will be prompted securely"
    echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py kmccullor@gmail.com"
    echo ""
    echo "🔧 Manage passwords:"
    echo "   python secure_file_email.py list"
    echo "   python secure_file_email.py test kmccullor@gmail.com"
    
elif [ "$choice" = "3" ]; then
    echo "📤 Send email (environment variable):"
    echo "   export EOD_SENDER_PASSWORD='your_app_password'"
    echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py kmccullor@gmail.com"
fi

echo ""
echo "📊 Generate and email daily report:"
echo "   EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py --generate-report kmccullor@gmail.com"
echo ""
echo "⏰ Schedule daily reports (crontab safe - no passwords in crontab!):"
echo "   crontab -e"
echo "   # Add:"
echo "   0 17 * * * cd $(pwd) && EOD_SENDER_EMAIL='kmccullor@gmail.com' EOD_SMTP_SERVER='smtp.gmail.com' python email_eod_report.py --generate-report kmccullor@gmail.com"
echo ""
echo "🔐 Security Summary:"
echo "   ✅ No plain text passwords in files or scripts"
echo "   ✅ No passwords in crontab or command history"
echo "   ✅ Email password retrieved securely when needed"
echo "   ✅ Multiple authentication fallback methods"