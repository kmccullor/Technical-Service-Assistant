#!/usr/bin/env python3
"""
Quick User Verification Helper

Simple script to verify users when email is not available.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

def verify_all_pending_users():
    """Verify all users with pending_verification status"""
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='vector_db',
        user='postgres',
        password='postgres',
        cursor_factory=RealDictCursor
    )
    
    cursor = conn.cursor()
    
    try:
        # Get pending users
        cursor.execute("""
            SELECT email, name FROM users 
            WHERE status = 'pending_verification' OR verified = false
        """)
        pending_users = cursor.fetchall()
        
        if not pending_users:
            print("✅ No users need verification")
            return
        
        print(f"📧 Found {len(pending_users)} users needing verification:")
        for user in pending_users:
            print(f"  - {user['email']} ({user['name']})")
        
        # Verify all pending users
        cursor.execute("""
            UPDATE users 
            SET verified = true, 
                status = 'active',
                updated_at = %s
            WHERE status = 'pending_verification' OR verified = false
        """)
        
        conn.commit()
        print(f"✅ Verified and activated {cursor.rowcount} users")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    verify_all_pending_users()