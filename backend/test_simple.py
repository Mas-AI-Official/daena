#!/usr/bin/env python3
"""Simple test script to verify server functionality."""
import requests
import time

def test_server():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Daena server endpoints...")
    
    # Test basic health
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        print(f"✅ Health endpoint: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
    
    # Test AI capabilities
    try:
        response = requests.get(f"{base_url}/api/v1/ai/capabilities", timeout=5)
        print(f"✅ AI Capabilities: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Agents: {data.get('capabilities', {}).get('agents', 'N/A')}")
            print(f"   Departments: {data.get('capabilities', {}).get('departments', 'N/A')}")
    except Exception as e:
        print(f"❌ AI Capabilities failed: {e}")
    
    # Test events endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/events/stream", timeout=5)
        print(f"✅ Events endpoint: {response.status_code}")
    except Exception as e:
        print(f"❌ Events endpoint failed: {e}")
    
    # Test test-events
    try:
        response = requests.get(f"{base_url}/test-events", timeout=5)
        print(f"✅ Test-events: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Test-events failed: {e}")

if __name__ == "__main__":
    test_server() 