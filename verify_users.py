#!/usr/bin/env python3
"""
Quick User Verification Helper

Simple script to verify users when email is not available.
"""

import logging

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def verify_all_pending_users():
    """Verify all users with pending_verification status"""
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
        # Get pending users
        cursor.execute(
            """
            SELECT email, name FROM users
            WHERE status = 'pending_verification' OR verified = false
        """
        )
        pending_users = cursor.fetchall()

        if not pending_users:
            logger.info("✅ No users need verification")
            return

        logger.info(f"📧 Found {len(pending_users)} users needing verification:")
        for user in pending_users:
            logger.info(f"  - {user['email']} ({user['name']})")

        # Verify all pending users
        cursor.execute(
            """
            UPDATE users
            SET verified = true,
                status = 'active',
                updated_at = %s
            WHERE status = 'pending_verification' OR verified = false
        """
        )

        conn.commit()
        logger.info(f"✅ Verified and activated {cursor.rowcount} users")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    verify_all_pending_users()
