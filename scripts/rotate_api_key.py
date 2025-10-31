#!/usr/bin/env python3
"""API Key Rotation Utility

Generates a new random API key and (optionally) updates the running environment.

Usage:
    python scripts/rotate_api_key.py                 # Just print a new key
    python scripts/rotate_api_key.py --length 56     # Custom length (pre-entropy base64 len)
    python scripts/rotate_api_key.py --export        # Append to .env (commented) for manual activation
    python scripts/rotate_api_key.py --apply         # Directly rewrite .env API_KEY=... (backup previous)

NOTES:
 - This does NOT restart containers; do that manually (docker compose up -d)
 - For production, prefer a secret manager (Vault, AWS Secrets Manager, Azure Key Vault)
 - Keys are generated with os.urandom via secrets.token_urlsafe
"""
from __future__ import annotations

import argparse
import secrets
import time
from pathlib import Path

DEFAULT_LENGTH = 48  # token_urlsafe length parameter (approx >64 chars output)
ENV_FILE = Path(".env")
BACKUP_SUFFIX = time.strftime("%Y%m%d_%H%M%S")


def generate_api_key(length: int = DEFAULT_LENGTH) -> str:
    return f"tsa_{secrets.token_urlsafe(length)}"


def backup_env_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_path = path.with_name(path.name + f".bak.{BACKUP_SUFFIX}")
    backup_path.write_text(path.read_text())
    return backup_path


def update_env_file_apply(path: Path, new_key: str) -> None:
    lines = []
    replaced = False
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("API_KEY="):
                lines.append(f"API_KEY={new_key}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"API_KEY={new_key}")
    path.write_text("\n".join(lines) + "\n")


def append_env_export(path: Path, new_key: str) -> None:
    with path.open("a") as f:
        f.write(f"\n# Rotated candidate API key generated {BACKUP_SUFFIX}\n# API_KEY={new_key}\n")


def main():
    parser = argparse.ArgumentParser(description="Rotate API key utility")
    parser.add_argument(
        "--length",
        type=int,
        default=DEFAULT_LENGTH,
        help="token_urlsafe length parameter (default: 48)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Append commented API_KEY line to .env for manual activation",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Immediately replace API_KEY in .env (backs up previous)",
    )
    args = parser.parse_args()

    new_key = generate_api_key(args.length)
    print(f"New API Key (store securely):\n{new_key}\n")

    if args.export and args.apply:
        print("Choose either --export or --apply, not both.")
        return

    if args.export:
        append_env_export(ENV_FILE, new_key)
        print(f"Appended commented key to {ENV_FILE}")
    elif args.apply:
        backup = backup_env_file(ENV_FILE)
        if backup:
            print(f"Backed up existing .env -> {backup.name}")
        update_env_file_apply(ENV_FILE, new_key)
        print(f"Updated API_KEY in {ENV_FILE}. Restart services to apply.")
    else:
        print("No file changes made (preview mode). Use --export or --apply to persist.")

    print("\nNext Steps:")
    print(" 1. If applied, restart stack: docker compose up -d")
    print(" 2. Update any clients to use the new X-API-Key header")
    print(" 3. Remove any old keys from scripts / CI secrets")


if __name__ == "__main__":
    main()
