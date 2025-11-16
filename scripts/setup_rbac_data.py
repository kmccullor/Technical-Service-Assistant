#!/usr/bin/env python3
"""
RBAC Data Setup Script

Creates default roles, permissions, and admin user for the RBAC system.
This script should be run after the RBAC migration has been applied.

Usage:
    python scripts/setup_rbac_data.py
"""

import os
import sys

import bcrypt
import psycopg2

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


def get_db_connection():
    """Get database connection using config settings."""
    settings = get_settings()
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def setup_default_roles():
    """Create default roles: admin, employee, guest."""
    conn = get_db_connection()
    cursor = conn.cursor()

    roles = [
        {"name": "admin", "description": "Full system access with user management capabilities", "is_system": False},
        {"name": "employee", "description": "Standard user with chat and document access", "is_system": False},
        {"name": "guest", "description": "Limited read-only access", "is_system": False},
    ]

    for role in roles:
        cursor.execute(
            """
            INSERT INTO roles (name, description, is_system)
            VALUES (%(name)s, %(description)s, %(is_system)s)
            ON CONFLICT (name) DO NOTHING
        """,
            role,
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Default roles created successfully")


def setup_default_permissions():
    """Create default permissions for the system."""
    conn = get_db_connection()
    cursor = conn.cursor()

    permissions = [
        # User management
        ("users", "create", "Create new users"),
        ("users", "read", "View user information"),
        ("users", "update", "Update user information"),
        ("users", "delete", "Delete users"),
        # Role management
        ("roles", "create", "Create new roles"),
        ("roles", "read", "View role information"),
        ("roles", "update", "Update role information"),
        ("roles", "delete", "Delete roles"),
        ("roles", "assign", "Assign roles to users"),
        # Document management
        ("documents", "upload", "Upload documents"),
        ("documents", "read", "View documents"),
        ("documents", "delete", "Delete documents"),
        # Chat functionality
        ("chat", "use", "Use chat functionality"),
        ("chat", "history", "Access chat history"),
        ("chat", "export", "Export chat conversations"),
        # System administration
        ("system", "monitor", "Monitor system performance"),
        ("system", "configure", "Configure system settings"),
        ("system", "backup", "Create system backups"),
        # Analytics and reporting
        ("analytics", "view", "View analytics dashboards"),
        ("analytics", "export", "Export analytics data"),
    ]

    inserted = 0
    for resource, action, description in permissions:
        permission_name = f"{resource}:{action}"
        cursor.execute(
            """
            INSERT INTO permissions (name, resource, action, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (resource, action) DO UPDATE
            SET description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """,
            (permission_name, resource, action, description),
        )
        if cursor.fetchone():
            inserted += 1
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM permissions")
    total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    print(f"✅ Permissions ensured (inserted/updated: {inserted}, total now: {total})")


def setup_role_permissions():
    """Assign permissions to default roles."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Admin gets all permissions
    cursor.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """
    )

    # Employee permissions
    employee_permissions = [
        ("documents", "read"),
        ("chat", "use"),
        ("chat", "history"),
        ("chat", "export"),
        ("analytics", "view"),
    ]

    for resource, action in employee_permissions:
        cursor.execute(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = 'employee' AND p.resource = %s AND p.action = %s
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """,
            (resource, action),
        )

    # Guest permissions (very limited)
    guest_permissions = [
        ("documents", "read"),
        ("chat", "use"),
    ]

    for resource, action in guest_permissions:
        cursor.execute(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = 'guest' AND p.resource = %s AND p.action = %s
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """,
            (resource, action),
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Role permissions assigned successfully")


def create_admin_user(email: str = None, password: str = None):
    """Create default admin user."""
    if email is None:
        email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@technical-service.local")
    if password is None:
        password = os.getenv("DEFAULT_ADMIN_PASSWORD", "H+Z5QZ736Kyp4aFF")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Hash the password
    password_hash = hash_password(password)

    # Create admin user
    cursor.execute(
        """
        INSERT INTO users (email, password_hash, name, first_name, last_name, status, verified)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
    """,
        (email, password_hash, "System Administrator", "System", "Administrator", "active", True),
    )

    result = cursor.fetchone()
    if result:
        user_id = result[0]

        # Assign admin role
        cursor.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT %s, r.id
            FROM roles r
            WHERE r.name = 'admin'
            ON CONFLICT (user_id, role_id) DO NOTHING
        """,
            (user_id,),
        )

        conn.commit()
        print(f"✅ Admin user created successfully: {email}")
        print(f"   Password: {password}")
        print("   ⚠️  IMPORTANT: Change the default password after first login!")
    else:
        print(f"ℹ️  Admin user already exists: {email}")

    cursor.close()
    conn.close()


def main():
    """Main setup function."""
    print("🚀 Setting up RBAC data...")

    try:
        # Test database connection
        conn = get_db_connection()
        conn.close()
        print("✅ Database connection successful")

        # Setup data
        setup_default_roles()
        setup_default_permissions()
        setup_role_permissions()
        create_admin_user()

        print("\n🎉 RBAC setup completed successfully!")
        print("\nDefault Admin Credentials:")
        print("  Email: admin@technical-service.local")
        print("  Password: admin123!")
        print("\n⚠️  SECURITY: Change the default password immediately after first login!")

    except Exception as e:
        print(f"❌ Error setting up RBAC data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
