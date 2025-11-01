#!/usr/bin/env python3
"""
Password Reset Tool

Tool to reset user passwords when needed for troubleshooting.
"""

import sys
from datetime import datetime

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor


def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def reset_password(email: str, new_password: str):
    """Reset user password"""
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="vector_db",
        user="postgres",
        password="postgres",
        cursor_factory=RealDictCursor,
    )

    cursor = conn.cursor()

    try:
        # Check if user exists
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email.lower(),))
        user = cursor.fetchone()

        if not user:
            print(f"❌ User {email} not found")
            return

        # Hash new password
        password_hash = hash_password(new_password)

        # Update password
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s,
                updated_at = %s,
                login_attempts = 0,
                locked_until = NULL,
                password_change_required = true
            WHERE email = %s
        """,
            (password_hash, datetime.now(), email.lower()),
        )

        conn.commit()
        print(f"✅ Password reset for {email}")
        print(f"📝 New password: {new_password}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()


def main():
    if len(sys.argv) != 3:
        print("🔐 Password Reset Tool")
        print("Usage: python reset_password.py <email> <new_password>")
        print("Example: python reset_password.py kevin.mccullor@xylem.com newpassword123")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    reset_password(email, password)


if __name__ == "__main__":
    main()
