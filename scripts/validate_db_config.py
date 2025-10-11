#!/usr/bin/env python3
"""
Database Configuration Validator

Validates that the correct database name is being used and provides
helpful error messages if attempting to use incorrect database names.
"""

import sys
from config import get_settings

def validate_db_config():
    """Validate database configuration and provide guidance."""
    settings = get_settings()

    print("🔍 Database Configuration Validation")
    print("=" * 50)

    # Check correct database name
    if settings.db_name == "vector_db":
        print(f"✅ Database Name: {settings.db_name} (CORRECT)")
    else:
        print(f"❌ Database Name: {settings.db_name} (INCORRECT)")
        print(f"   Expected: vector_db")
        print(f"   Please check your DB_NAME environment variable")
        return False

    # Show full config
    print(f"📍 Host: {settings.db_host}")
    print(f"🔌 Port: {settings.db_port}")
    print(f"👤 User: {settings.db_user}")
    print(f"🗄️  Database: {settings.db_name}")

    # Provide connection examples
    print("\n📖 Connection Examples:")
    print(
        "   Docker CLI: docker exec -it {host} psql -U {user} -d {db}".format(
            host=settings.db_host,
            user=settings.db_user,
            db=settings.db_name,
        )
    )
    print(
        "   List tables: docker exec -it {host} psql -U {user} -d {db} -c '\\dt'".format(
            host=settings.db_host,
            user=settings.db_user,
            db=settings.db_name,
        )
    )

    return True

def main():
    """Main validation function."""
    if validate_db_config():
        print("\n✅ Database configuration is valid!")
        sys.exit(0)
    else:
        print("\n❌ Database configuration has issues!")
        sys.exit(1)

if __name__ == "__main__":
    main()
