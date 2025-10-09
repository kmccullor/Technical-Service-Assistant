#!/usr/bin/env python3
"""
Alternative Secure Email Manager using encrypted files
For environments where system keyring is not accessible
"""

import os
import sys
import getpass
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class FileBasedSecureManager:
    """Secure password management using encrypted files"""
    
    def __init__(self):
        self.secure_dir = os.path.expanduser("~/.technical-service-assistant")
        self.credentials_file = os.path.join(self.secure_dir, "credentials.enc")
        os.makedirs(self.secure_dir, exist_ok=True)
        os.chmod(self.secure_dir, 0o700)  # Owner only
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _get_master_password(self, prompt="Enter master password: "):
        """Get master password for encryption"""
        return getpass.getpass(prompt)
    
    def _load_credentials(self, master_password):
        """Load and decrypt credentials"""
        if not os.path.exists(self.credentials_file):
            return {}
        
        try:
            with open(self.credentials_file, 'rb') as f:
                data = f.read()
            
            salt = data[:16]
            encrypted_data = data[16:]
            
            key = self._derive_key(master_password, salt)
            fernet = Fernet(key)
            
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        
        except Exception as e:
            print(f"❌ Failed to decrypt credentials: {e}")
            return None
    
    def _save_credentials(self, credentials, master_password):
        """Encrypt and save credentials"""
        try:
            salt = os.urandom(16)
            key = self._derive_key(master_password, salt)
            fernet = Fernet(key)
            
            data = json.dumps(credentials).encode()
            encrypted_data = fernet.encrypt(data)
            
            with open(self.credentials_file, 'wb') as f:
                f.write(salt + encrypted_data)
            
            os.chmod(self.credentials_file, 0o600)  # Owner read/write only
            return True
        
        except Exception as e:
            print(f"❌ Failed to save credentials: {e}")
            return False
    
    def store_password(self, email_account, password=None):
        """Store email password securely"""
        if not password:
            password = getpass.getpass(f"Enter password for {email_account}: ")
        
        master_password = self._get_master_password("Enter master password (for encryption): ")
        
        # Load existing credentials or create new
        credentials = self._load_credentials(master_password)
        if credentials is None:
            # First time or wrong password
            confirm = self._get_master_password("Confirm master password: ")
            if master_password != confirm:
                print("❌ Master passwords don't match")
                return False
            credentials = {}
        
        credentials[email_account] = password
        
        if self._save_credentials(credentials, master_password):
            print(f"✅ Password securely stored for {email_account}")
            print(f"🔐 Encrypted file: {self.credentials_file}")
            return True
        return False
    
    def get_password(self, email_account, master_password=None):
        """Retrieve stored password"""
        if not master_password:
            master_password = self._get_master_password()
        
        credentials = self._load_credentials(master_password)
        if credentials is None:
            return None
        
        password = credentials.get(email_account)
        if password:
            print(f"🔓 Retrieved password for {email_account}")
            return password
        else:
            print(f"❌ No stored password found for {email_account}")
            return None
    
    def list_accounts(self):
        """List stored accounts"""
        master_password = self._get_master_password()
        credentials = self._load_credentials(master_password)
        
        if credentials is None:
            print("❌ Failed to access credentials")
            return []
        
        accounts = list(credentials.keys())
        if accounts:
            print(f"🔐 Stored accounts: {', '.join(accounts)}")
        else:
            print("📭 No stored accounts found")
        
        return accounts
    
    def delete_password(self, email_account):
        """Delete stored password"""
        master_password = self._get_master_password()
        credentials = self._load_credentials(master_password)
        
        if credentials is None:
            return False
        
        if email_account in credentials:
            del credentials[email_account]
            if self._save_credentials(credentials, master_password):
                print(f"🗑️  Password deleted for {email_account}")
                return True
        else:
            print(f"❌ No password found for {email_account}")
        
        return False

def main():
    """Main CLI interface"""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("❌ cryptography package required. Install with: pip install cryptography")
        sys.exit(1)
    
    manager = FileBasedSecureManager()
    
    if len(sys.argv) < 2:
        print("🔐 Secure Email Password Manager (File-based)")
        print("=============================================")
        print("✅ Uses encrypted files with master password")
        print("✅ No plain text storage")
        print("✅ Works without system keyring")
        print("")
        print("Usage:")
        print("  python secure_file_email.py store <email>     - Store password")
        print("  python secure_file_email.py get <email>       - Get password")
        print("  python secure_file_email.py delete <email>    - Delete password")
        print("  python secure_file_email.py list              - List accounts")
        print("  python secure_file_email.py test <email>      - Test email")
        print("")
        print("Examples:")
        print("  python secure_file_email.py store kmccullor@gmail.com")
        print("  python secure_file_email.py test kmccullor@gmail.com")
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
            print("✅ Password retrieved successfully")
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        manager.delete_password(email)
    
    elif command == "list":
        manager.list_accounts()
    
    elif command == "test":
        if len(sys.argv) < 3:
            print("❌ Email address required")
            sys.exit(1)
        email = sys.argv[2]
        
        # Get master password
        master_password = getpass.getpass("Enter master password: ")
        password = manager.get_password(email, master_password)
        
        if password:
            print("🧪 Testing email with stored password...")
            os.environ['EOD_SENDER_PASSWORD'] = password
            if 'gmail' in email.lower():
                os.environ['EOD_SENDER_EMAIL'] = email
                os.environ['EOD_SMTP_SERVER'] = 'smtp.gmail.com'
                os.environ['EOD_SMTP_PORT'] = '587'
                os.environ['EOD_SMTP_USE_TLS'] = 'true'
            
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
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()