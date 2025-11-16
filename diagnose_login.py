#!/usr/bin/env python3
"""
Frontend Login Diagnosis Script

This script helps diagnose login issues by testing various aspects
of the authentication flow.
"""


import os
import requests


def test_backend_health():
    """Test if backend services are healthy."""
    print("🔍 Testing Backend Health")
    print("-" * 30)

    # Test reranker health
    try:
        response = requests.get("http://localhost:8008/health", timeout=5)
        if response.status_code == 200:
            print("✅ Reranker: Healthy")
        else:
            print(f"❌ Reranker: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Reranker: Connection failed - {e}")

    # Test frontend health via nginx
    try:
        response = requests.get("http://localhost:80", timeout=5, allow_redirects=False)
        if response.status_code == 301:
            print("✅ Frontend: Redirecting to HTTPS (nginx working)")
        elif response.status_code == 200:
            print("✅ Frontend: Responsive")
        else:
            print(f"❌ Frontend: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Frontend: Connection failed - {e}")


def test_api_login():
    """Test API login functionality."""
    print("\n🔑 Testing API Login")
    print("-" * 20)

    # Test backend API directly
    try:
        response = requests.post(
            "http://localhost:8008/api/auth/login",
            json={"email": "admin@employee.com", "password": "admin123"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Backend API: Login successful")
            print(f"   User: {data['user']['email']}")
            print(f"   Role: {data['user'].get('role_name', 'admin')}")
        else:
            print(f"❌ Backend API: Status {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Backend API: Failed - {e}")

    # Test frontend proxy via nginx
    try:
        response = requests.post(
            "http://localhost:80/api/auth/login",
            json={"email": "admin@employee.com", "password": "admin123"},
            timeout=10,
            allow_redirects=False,
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Frontend Proxy: Login successful")
            print(f"   User: {data['user']['email']}")
        else:
            print(f"❌ Frontend Proxy: Status {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Frontend Proxy: Failed - {e}")


def test_cors_headers():
    """Test CORS headers on frontend."""
    print("\n🌐 Testing CORS Configuration")
    print("-" * 25)

    try:
        response = requests.options("http://localhost:80/api/auth/login")
        headers = response.headers

        print(f"Access-Control-Allow-Origin: {headers.get('Access-Control-Allow-Origin', 'Not set')}")
        print(f"Access-Control-Allow-Methods: {headers.get('Access-Control-Allow-Methods', 'Not set')}")
        print(f"Access-Control-Allow-Headers: {headers.get('Access-Control-Allow-Headers', 'Not set')}")

    except Exception as e:
        print(f"❌ CORS test failed: {e}")


def main():
    print("🔧 Frontend Login Diagnosis")
    print("=" * 50)

    test_backend_health()
    test_api_login()
    test_cors_headers()

    print("\n📋 Diagnosis Complete")
    print("=" * 50)
    print("If all tests pass but browser login fails, try:")
    print("1. Clear browser cache and localStorage")
    print("2. Open browser developer tools and check console errors")
    print("3. Disable browser extensions temporarily")
    print("4. Try incognito/private browsing mode")
    app_url = os.getenv("APP_URL", "https://rni-llm-01.lab.sensus.net")
    print(f"5. Test the standalone page: {app_url}/admin_login_test.html")


if __name__ == "__main__":
    main()
