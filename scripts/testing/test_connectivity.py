import socket

import psycopg2
import requests

from config import get_settings
from utils.logging_config import setup_logging

settings = get_settings()

# Setup standardized Log4 logging
logger = setup_logging(program_name="test_connectivity", log_level="INFO", console_output=True)

SERVICES = [
    {"name": "PGVector (Postgres)", "host": "localhost", "port": 5432},
    {"name": "Ollama Server 1", "host": "localhost", "port": 11434},
    {"name": "Ollama Server 2", "host": "localhost", "port": 11435},
    {"name": "Ollama Server 3", "host": "localhost", "port": 11436},
    {"name": "Ollama Server 4", "host": "localhost", "port": 11437},
    {"name": "Reranker Service", "host": "localhost", "port": 8008},
    {"name": "Frontend", "host": "localhost", "port": 8080},
]

# Optionally test using Docker hostnames
DOCKER_HOSTNAMES = [
    {"name": "PGVector (Postgres)", "host": "pgvector", "port": 5432},
    {"name": "Ollama Server 1", "host": "ollama-server-1", "port": 11434},
    {"name": "Ollama Server 2", "host": "ollama-server-2", "port": 11434},
    {"name": "Ollama Server 3", "host": "ollama-server-3", "port": 11434},
    {"name": "Ollama Server 4", "host": "ollama-server-4", "port": 11434},
    {"name": "Ollama Server 5", "host": "ollama-server-5", "port": 11434},
    {"name": "Ollama Server 6", "host": "ollama-server-6", "port": 11434},
    {"name": "Ollama Server 7", "host": "ollama-server-7", "port": 11434},
    {"name": "Ollama Server 8", "host": "ollama-server-8", "port": 11434},
    {"name": "Reranker Service", "host": "reranker", "port": 8008},
    {"name": "Frontend", "host": "frontend", "port": 8080},
]

# Use centralized database configuration
POSTGRES_USER = settings.db_user
POSTGRES_PASSWORD = settings.db_password
POSTGRES_DB = settings.db_name


def test_tcp(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def test_postgres(host, port):
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, host=host, port=port, connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False


def test_http(host, port, path="/"):
    url = f"http://{host}:{port}{path}"
    try:
        r = requests.get(url, timeout=3)
        return r.status_code < 500
    except Exception:
        return False


def main():
    print("Testing local connectivity:")
    for svc in SERVICES:
        print(f"- {svc['name']} ({svc['host']}:{svc['port']}): ", end="")
        if test_tcp(svc["host"], svc["port"]):
            print("TCP OK", end=", ")
            if svc["name"].startswith("Supabase") or svc["name"].startswith("PGVector"):
                if test_postgres(svc["host"], svc["port"]):
                    print("Postgres OK", end=", ")
                else:
                    print("Postgres FAIL", end=", ")
            else:
                if test_http(svc["host"], svc["port"]):
                    print("HTTP OK", end=", ")
                else:
                    print("HTTP FAIL", end=", ")
        else:
            print("TCP FAIL", end=", ")
        print()

    print("\nTesting Docker hostname connectivity:")
    for svc in DOCKER_HOSTNAMES:
        print(f"- {svc['name']} ({svc['host']}:{svc['port']}): ", end="")
        if test_tcp(svc["host"], svc["port"]):
            print("TCP OK", end=", ")
            if svc["name"].startswith("PGVector") or "Postgres" in svc["name"]:
                if test_postgres(svc["host"], svc["port"]):
                    print("Postgres OK", end=", ")
                else:
                    print("Postgres FAIL", end=", ")
            else:
                if test_http(svc["host"], svc["port"]):
                    print("HTTP OK", end=", ")
                else:
                    print("HTTP FAIL", end=", ")
        else:
            print("TCP FAIL", end=", ")
        print()

    print("\nDone. If any tests failed, check Docker Compose logs and network settings.")


if __name__ == "__main__":
    main()
