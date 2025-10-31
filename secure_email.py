#!/usr/bin/env python3
"""
Secure Email Password Manager for Technical Service Assistant
Encrypts and stores email passwords securely using system keyring
"""

import getpass
import os
import sys

import keyring
from keyring.errors import KeyringError


class SecureEmailManager:
    """Secure password management for email configuration"""

    SERVICE_NAME = "technical-service-assistant"

    def __init__(self):
        self.available_backends = self._check_keyring_backends()

    def _check_keyring_backends(self):
        """Check available keyring backends"""
        try:
            backend = keyring.get_keyring()
            print(f"🔐 Using keyring backend: {backend.__class__.__name__}")
            return True
        except Exception as e:
            print(f"⚠️  Warning: Keyring backend issue: {e}")
            return False

    def store_password(self, email_account, password=None):
        """Securely store email password"""
        if not password:
            password = getpass.getpass(f"Enter password for {email_account}: ")

        try:
            keyring.set_password(self.SERVICE_NAME, email_account, password)
            print(f"✅ Password securely stored for {email_account}")
            return True
        except KeyringError as e:
            print(f"❌ Failed to store password: {e}")
            return False

    def get_password(self, email_account):
        """Retrieve stored password"""
        try:
            password = keyring.get_password(self.SERVICE_NAME, email_account)
            if password:
                print(f"🔓 Retrieved password for {email_account}")
                return password
            else:
                print(f"❌ No stored password found for {email_account}")
                return None
        except KeyringError as e:
            print(f"❌ Failed to retrieve password: {e}")
            return None

    def delete_password(self, email_account):
        """Delete stored password"""
        try:
            keyring.delete_password(self.SERVICE_NAME, email_account)
            print(f"🗑️  Password deleted for {email_account}")
            return True
        except KeyringError as e:
            print(f"❌ Failed to delete password: {e}")
            return False

    def list_stored_accounts(self):
        """List accounts with stored passwords (if backend supports it)"""
        print("📋 Checking for stored email accounts...")

        # Common email accounts to check
        common_accounts = ["kmccullor@gmail.com", "kevin.mccullor@xylem.com", "technical-service-assistant@localhost"]

        stored_accounts = []
        for account in common_accounts:
            if self.get_password(account):
                stored_accounts.append(account)

        if stored_accounts:
            print(f"🔐 Found stored passwords for: {', '.join(stored_accounts)}")
        else:
            print("📭 No stored passwords found")

        return stored_accounts


def main():
    """Main CLI interface"""
    manager = SecureEmailManager()

    if len(sys.argv) < 2:
        print("🔐 Secure Email Password Manager")
        print("================================")
        print("Usage:")
        print("  python secure_email.py store <email>     - Store password for email")
        print("  python secure_email.py get <email>       - Get password for email")
        print("  python secure_email.py delete <email>    - Delete stored password")
        print("  python secure_email.py list              - List stored accounts")
        print("  python secure_email.py test <email>      - Test email with stored password")
        print("")
        print("Examples:")
        print("  python secure_email.py store kmccullor@gmail.com")
        print("  python secure_email.py test kmccullor@gmail.com")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "store":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        manager.store_password(email)

    elif command == "get":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        password = manager.get_password(email)
        if password:
            # Don't print password for security
            print("✅ Password retrieved successfully")

    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        manager.delete_password(email)

    elif command == "list":
        manager.list_stored_accounts()

    elif command == "test":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        password = manager.get_password(email)
        if password:
            print("🧪 Testing email with stored password...")
            # Set environment variables and run email test
            os.environ["EOD_SENDER_PASSWORD"] = password
            if "gmail" in email.lower():
                os.environ["EOD_SENDER_EMAIL"] = email
                os.environ["EOD_SMTP_SERVER"] = "smtp.gmail.com"
                os.environ["EOD_SMTP_PORT"] = "587"
                os.environ["EOD_SMTP_USE_TLS"] = "true"

            # Import and run email test
            try:
                from email_eod_report import EODEmailSender

                sender = EODEmailSender()
                result = sender.send_report(email, test_mode=True)
                if result:
                    print("✅ Email test successful!")
                else:
                    print("❌ Email test failed")
            except ImportError:
                print("❌ email_eod_report.py not found")
        else:
            print("❌ No password stored for this account")

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
