#!/usr/bin/env python3
"""
Quick Database Connection Helper

Use this script to get the correct database connection command
instead of guessing database names.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings

def main():
    settings = get_settings()

    if len(sys.argv) > 1 and sys.argv[1] == 'connect':
        # Print the connection command
        print(f"docker exec -it {settings.db_host} psql -U {settings.db_user} -d {settings.db_name}")
    elif len(sys.argv) > 1 and sys.argv[1] == 'tables':
        # Print command to list tables
        print(f'docker exec -it {settings.db_host} psql -U {settings.db_user} -d {settings.db_name} -c "\\dt"')
    elif len(sys.argv) > 1 and sys.argv[1] == 'users':
        # Print command to query users
        query = (
            "SELECT u.id, u.email, u.first_name, u.last_name, u.role_id, "
            "r.name as role_name, u.password_change_required "
            "FROM users u LEFT JOIN roles r ON u.role_id = r.id "
            "ORDER BY u.id;"
        )
        cmd = (
            f"docker exec -it {settings.db_host} psql -U {settings.db_user} "
            f"-d {settings.db_name} -c \"{query}\""
        )
        print(cmd)
    else:
        print("Database Helper Commands:")
        print(f"  Database: {settings.db_name}")
        print(f"  Container: {settings.db_host}")
        print()
        print("Usage:")
        print("  python3 scripts/db_helper.py connect  # Get connection command")
        print("  python3 scripts/db_helper.py tables   # List tables command")
        print("  python3 scripts/db_helper.py users    # Query users command")
        print()
        print("Quick copy-paste commands:")
        print(f"  docker exec -it {settings.db_host} psql -U {settings.db_user} -d {settings.db_name}")

if __name__ == "__main__":
    main()
