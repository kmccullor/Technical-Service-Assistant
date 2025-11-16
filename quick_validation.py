#!/usr/bin/env python3
"""
Quick validation of optimization deployment
"""

import requests
import time
import json

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://localhost:8008/health", timeout=10)
        return response.status_code == 200
    except:
        return False

def test_streaming_metadata():
    """Test if streaming includes metadata"""
    try:
        # Make a simple streaming request with very short timeout
        response = requests.post(
            "http://localhost:8008/api/rag-chat",
            json={
                "query": "test",
                "stream": True,
                "max_tokens": 10,  # Very short
                "temperature": 0.1
            },
            stream=True,
            timeout=30
        )

        if response.status_code != 200:
            return False

        metadata_found = False
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') in ['sources', 'model']:
                            metadata_found = True
                            break
                    except:
                        continue

        return metadata_found

    except:
        return False

def main():
    print("🔍 Quick Validation of Optimization Deployment")
    print("=" * 50)

    # Test 1: Health
    print("1. Testing health endpoint...")
    health_ok = test_health()
    print(f"   {'✅' if health_ok else '❌'} Health check")

    # Test 2: Streaming metadata
    print("2. Testing streaming with metadata...")
    metadata_ok = test_streaming_metadata()
    print(f"   {'✅' if metadata_ok else '❌'} Streaming metadata")

    # Summary
    print("\n📊 Summary:")
    print(f"   Health: {'✅' if health_ok else '❌'}")
    print(f"   Streaming: {'✅' if metadata_ok else '❌'}")
    print(f"   Overall: {'✅ PASSED' if health_ok and metadata_ok else '❌ FAILED'}")

    return health_ok and metadata_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)