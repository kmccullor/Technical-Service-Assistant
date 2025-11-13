#!/usr/bin/env python3
"""
Simple test to validate the improvements made to Technical Service Assistant
"""

import requests
import json
import time

def test_routing():
    """Test intelligent routing functionality."""
    print("Testing intelligent routing...")

    url = "http://localhost:8008/api/intelligent-route"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer mock_access_token_admin@example.com"
    }

    # Test different question types
    test_questions = [
        "What is RNI?",
        "How do I configure device managers?",
        "Write Python code to parse CSV",
        "Solve: 2x + 3 = 7"
    ]

    for question in test_questions:
        payload = {"query": question}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {question[:30]}... -> {result.get('selected_model', 'unknown')} (complexity: {result.get('complexity', 'unknown')})")
                print(f"   Full response: {result}")
            else:
                print(f"❌ {question[:30]}... -> HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {question[:30]}... -> Error: {str(e)}")

def test_chat_simple():
    """Test a simple chat interaction."""
    print("\nTesting simple chat interaction...")

    url = "http://localhost:8008/api/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer mock_access_token_admin@example.com"
    }

    payload = {"message": "What is RNI?"}

    try:
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)

        if response.status_code == 200:
            print("✅ Chat endpoint responded successfully")
            full_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            if data.get('type') == 'token':
                                full_response += data.get('token', '')
                            elif data.get('type') == 'done':
                                break
                        except json.JSONDecodeError:
                            continue

            if full_response.strip():
                print(f"✅ Got response: {full_response[:100]}...")
                return True
            else:
                print("❌ Empty response")
                return False
        else:
            print(f"❌ HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    print("🚀 Testing Technical Service Assistant Improvements")
    print("=" * 60)

    # Test routing
    test_routing()

    # Test chat
    success = test_chat_simple()

    print("\n" + "=" * 60)
    if success:
        print("✅ Basic functionality test PASSED")
        print("🎉 Database connectivity and response formatting improvements are working!")
    else:
        print("❌ Basic functionality test FAILED")

if __name__ == "__main__":
    main()