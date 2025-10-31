#!/usr/bin/env python3
"""
Security audit script for the Technical Service Assistant.

This script performs comprehensive security checks including:
- Dependency vulnerability scanning
- Security linting
- Configuration security checks
- Secret detection
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_dependencies() -> bool:
    """Check for vulnerable dependencies using safety and pip-audit."""
    print("🔍 Checking for vulnerable dependencies...")

    success = True

    # Check with safety
    print("  📦 Running safety check...")
    exit_code, stdout, stderr = run_command(["safety", "check"])
    if exit_code != 0:
        print(f"  ❌ Safety found vulnerabilities:\n{stdout}")
        success = False
    else:
        print("  ✅ Safety check passed")

    # Check with pip-audit (optional, may not be installed)
    print("  📦 Running pip-audit check...")
    exit_code, stdout, stderr = run_command(["pip-audit"])
    if exit_code == 127:  # Command not found
        print("  ⚠️  pip-audit not installed, skipping")
    elif exit_code != 0:
        print(f"  ❌ pip-audit found vulnerabilities:\n{stdout}")
        success = False
    else:
        print("  ✅ pip-audit check passed")

    return success


def check_bandit() -> bool:
    """Run bandit security linting."""
    print("🔍 Running bandit security linting...")

    exit_code, stdout, stderr = run_command(["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "json"])

    if exit_code != 0:
        print(f"  ❌ Bandit found security issues:\n{stdout}")
        return False
    else:
        print("  ✅ Bandit security check passed")
        return True


def check_secrets() -> bool:
    """Check for potential secrets in code."""
    print("🔍 Checking for potential secrets...")

    # Look for common patterns that might indicate secrets
    secret_patterns = [
        r'password\s*=\s*["\'][^"\']*["\']',
        r'secret\s*=\s*["\'][^"\']*["\']',
        r'key\s*=\s*["\'][^"\']*["\']',
        r'token\s*=\s*["\'][^"\']*["\']',
    ]

    found_secrets = False

    for pattern in secret_patterns:
        exit_code, stdout, stderr = run_command(["grep", "-r", "-i", pattern, "--include=*.py", "."], cwd=".")

        if stdout and not any(
            skip in stdout for skip in ["test_", "conftest.py", "example", "template", ".env.example"]
        ):
            print(f"  ⚠️  Potential secrets found with pattern '{pattern}':")
            print(f"     {stdout[:500]}...")
            found_secrets = True

    if not found_secrets:
        print("  ✅ No obvious secrets found in code")
        return True
    else:
        print("  ❌ Potential secrets detected - review manually")
        return False


def check_config_security() -> bool:
    """Check configuration files for security issues."""
    print("🔍 Checking configuration security...")

    issues = []

    # Check if .env files exist in repo
    env_files = list(Path(".").glob("*.env"))
    if env_files:
        issues.append(f"❌ Found .env files in repository: {[f.name for f in env_files]}")

    # Check for debug mode in production configs
    config_files = ["config.py", "reranker/config.py"]
    for config_file in config_files:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                content = f.read()
                if "DEBUG" in content and "True" in content:
                    issues.append(f"⚠️  Debug mode may be enabled in {config_file}")

    if issues:
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("  ✅ Configuration security check passed")
        return True


def main() -> int:
    """Run all security checks."""
    print("🔒 Technical Service Assistant - Security Audit")
    print("=" * 60)

    checks = [
        ("Dependencies", check_dependencies),
        ("Bandit Linting", check_bandit),
        ("Secret Detection", check_secrets),
        ("Config Security", check_config_security),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ {name} check failed with error: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("📊 SECURITY AUDIT RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 All security checks passed!")
        return 0
    else:
        print("⚠️  Some security checks failed. Please review and fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
