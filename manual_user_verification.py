#!/usr/bin/env python3
"""
Manual User Verification Tool

Since email capabilities are not available, this tool allows administrators
to manually verify users and troubleshoot login issues.

Usage:
    python manual_user_verification.py list                    # List all users
    python manual_user_verification.py verify <email>          # Verify user manually
    python manual_user_verification.py activate <email>        # Activate user account
    python manual_user_verification.py reset-attempts <email>  # Reset failed login attempts
    python manual_user_verification.py unlock <email>          # Unlock locked account
    python manual_user_verification.py debug <email>           # Debug user login issues
"""

import sys
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection settings
DB_CONFIG = {"host": "localhost", "port": 5432, "database": "vector_db", "user": "postgres", "password": "postgres"}


class UserVerificationTool:
    def __init__(self):
        self.conn = None

    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
            print("✅ Connected to database")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            sys.exit(1)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def list_users(self):
        """List all users with their status"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, email, name, status, verified, login_attempts,
                   locked_until, last_login, created_at,
                   password_hash IS NOT NULL as has_password
            FROM users
            ORDER BY id
        """
        )

        users = cursor.fetchall()

        print("\n👥 User List")
        print("=" * 100)
        print(
            f"{'ID':<3} {'Email':<30} {'Name':<20} {'Status':<20} {'Verified':<8} {'Attempts':<8} {'Locked':<6} {'Password'}"
        )
        print("-" * 100)

        for user in users:
            locked = "Yes" if user["locked_until"] and user["locked_until"] > datetime.now() else "No"
            password_status = "✅" if user["has_password"] else "❌"
            verified_status = "✅" if user["verified"] else "❌"

            print(
                f"{user['id']:<3} {user['email']:<30} {user['name']:<20} {user['status']:<20} "
                f"{verified_status:<8} {user['login_attempts']:<8} {locked:<6} {password_status}"
            )

        cursor.close()

    def get_user_details(self, email: str) -> Optional[Dict[str, Any]]:
        """Get detailed user information"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT u.*, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.email = %s
        """,
            (email.lower(),),
        )

        user = cursor.fetchone()
        cursor.close()
        return dict(user) if user else None

    def verify_user(self, email: str):
        """Manually verify a user"""
        user = self.get_user_details(email)
        if not user:
            print(f"❌ User {email} not found")
            return

        cursor = self.conn.cursor()

        try:
            # Update user to verified and active
            cursor.execute(
                """
                UPDATE users
                SET verified = true,
                    status = 'active',
                    updated_at = %s
                WHERE email = %s
            """,
                (datetime.now(), email.lower()),
            )

            # Reset login attempts
            cursor.execute(
                """
                UPDATE users
                SET login_attempts = 0,
                    locked_until = NULL
                WHERE email = %s
            """,
                (email.lower(),),
            )

            self.conn.commit()
            print(f"✅ User {email} has been verified and activated")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to verify user: {e}")
        finally:
            cursor.close()

    def activate_user(self, email: str):
        """Activate a user account"""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET status = 'active',
                    updated_at = %s
                WHERE email = %s
            """,
                (datetime.now(), email.lower()),
            )

            if cursor.rowcount == 0:
                print(f"❌ User {email} not found")
            else:
                self.conn.commit()
                print(f"✅ User {email} has been activated")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to activate user: {e}")
        finally:
            cursor.close()

    def reset_login_attempts(self, email: str):
        """Reset failed login attempts"""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET login_attempts = 0,
                    locked_until = NULL,
                    updated_at = %s
                WHERE email = %s
            """,
                (datetime.now(), email.lower()),
            )

            if cursor.rowcount == 0:
                print(f"❌ User {email} not found")
            else:
                self.conn.commit()
                print(f"✅ Login attempts reset for {email}")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to reset login attempts: {e}")
        finally:
            cursor.close()

    def unlock_user(self, email: str):
        """Unlock a locked user account"""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET locked_until = NULL,
                    login_attempts = 0,
                    updated_at = %s
                WHERE email = %s
            """,
                (datetime.now(), email.lower()),
            )

            if cursor.rowcount == 0:
                print(f"❌ User {email} not found")
            else:
                self.conn.commit()
                print(f"✅ User {email} has been unlocked")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to unlock user: {e}")
        finally:
            cursor.close()

    def debug_user(self, email: str):
        """Debug user login issues"""
        user = self.get_user_details(email)
        if not user:
            print(f"❌ User {email} not found")
            return

        print(f"\n🔍 Debug Information for {email}")
        print("=" * 60)

        # Basic info
        print(f"ID: {user['id']}")
        print(f"Email: {user['email']}")
        print(f"Name: {user['name']}")
        print(f"Role: {user['role_name'] or 'No role assigned'}")
        print(f"Created: {user['created_at']}")
        print(f"Updated: {user['updated_at']}")

        # Account status
        print(f"\n📊 Account Status:")
        print(f"Status: {user['status']}")
        print(f"Verified: {'✅ Yes' if user['verified'] else '❌ No'}")
        print(f"Has Password: {'✅ Yes' if user['password_hash'] else '❌ No'}")

        # Security info
        print(f"\n🔒 Security Information:")
        print(f"Login Attempts: {user['login_attempts']}")
        print(f"Last Login: {user['last_login'] or 'Never'}")

        if user["locked_until"]:
            if user["locked_until"] > datetime.now():
                print(f"Account Locked: ❌ Yes (until {user['locked_until']})")
            else:
                print(f"Account Locked: ✅ No (lock expired)")
        else:
            print(f"Account Locked: ✅ No")

        # Login blocking reasons
        print(f"\n🚫 Potential Login Issues:")
        issues = []

        if user["status"] != "active":
            issues.append(f"❌ Account status is '{user['status']}' (should be 'active')")

        if not user["verified"]:
            issues.append("❌ Email not verified")

        if not user["password_hash"]:
            issues.append("❌ No password set")

        if user["locked_until"] and user["locked_until"] > datetime.now():
            issues.append(f"❌ Account locked until {user['locked_until']}")

        if user["login_attempts"] >= 5:
            issues.append(f"❌ Too many failed login attempts ({user['login_attempts']})")

        if not issues:
            print("✅ No obvious login blocking issues found")
        else:
            for issue in issues:
                print(f"  {issue}")

        # Recommendations
        print(f"\n💡 Recommendations:")
        if not user["verified"] or user["status"] != "active":
            print("  • Run: python manual_user_verification.py verify <email>")
        if user["login_attempts"] > 0:
            print("  • Run: python manual_user_verification.py reset-attempts <email>")
        if user["locked_until"]:
            print("  • Run: python manual_user_verification.py unlock <email>")


def main():
    if len(sys.argv) < 2:
        print("🔧 Manual User Verification Tool")
        print("================================")
        print("Since email verification is not available, use this tool to manually manage users.")
        print("")
        print("Commands:")
        print("  list                    - List all users and their status")
        print("  verify <email>          - Manually verify and activate user")
        print("  activate <email>        - Activate user account")
        print("  reset-attempts <email>  - Reset failed login attempts")
        print("  unlock <email>          - Unlock locked account")
        print("  debug <email>           - Debug user login issues")
        print("")
        print("Examples:")
        print("  python manual_user_verification.py list")
        print("  python manual_user_verification.py verify kevin.mccullor@xylem.com")
        print("  python manual_user_verification.py debug jim.hitchcock@xylem.com")
        sys.exit(1)

    command = sys.argv[1].lower()
    tool = UserVerificationTool()
    tool.connect()

    try:
        if command == "list":
            tool.list_users()

        elif command in ["verify", "activate", "reset-attempts", "unlock", "debug"]:
            if len(sys.argv) < 3:
                print(f"❌ Email address required for {command} command")
                sys.exit(1)

            email = sys.argv[2]

            if command == "verify":
                tool.verify_user(email)
            elif command == "activate":
                tool.activate_user(email)
            elif command == "reset-attempts":
                tool.reset_login_attempts(email)
            elif command == "unlock":
                tool.unlock_user(email)
            elif command == "debug":
                tool.debug_user(email)

        else:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)

    finally:
        tool.close()


if __name__ == "__main__":
    main()
