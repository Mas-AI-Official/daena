#!/usr/bin/env python3
"""
Test Founder Recognition for Daena AI VP
Verifies that Daena properly recognizes the user as Founder/CEO
"""
import asyncio
import sys
import os
from pathlib import Path
import requests
import json

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

async def test_founder_recognition():
    """Test if Daena recognizes the user as founder"""
    print("👑 Testing Daena's Founder Recognition...")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Test questions that should trigger founder recognition
    test_questions = [
        "Who am I?",
        "Do you know who I am?",
        "What is my role in the company?",
        "Who do you report to?",
        "What is the company structure?",
        "Explain the sunflower-honeycomb structure"
    ]
    
    print("🧪 Testing Founder Recognition Questions:")
    print("-" * 40)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{i}. Question: '{question}'")
        
        try:
            response = requests.post(
                f"{base_url}/api/v1/chat",
                json={
                    "message": question,
                    "user_id": "founder",
                    "context": {"role": "founder", "location": "test"}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', data.get('content', 'No response'))
                
                # Check if answer contains founder-related keywords
                founder_keywords = ['founder', 'ceo', 'owner', 'authority', 'report to you', 'your vision']
                has_founder_terms = any(keyword.lower() in answer.lower() for keyword in founder_keywords)
                
                status = "✅ FOUNDER RECOGNIZED" if has_founder_terms else "❌ NO FOUNDER RECOGNITION"
                print(f"   Status: {status}")
                print(f"   Answer: {answer[:100]}...")
                
                if has_founder_terms:
                    print("   🎯 Daena recognizes you as Founder/CEO!")
                else:
                    print("   ⚠️  Daena may not recognize your role")
                    
            else:
                print(f"   ❌ API Error: {response.status_code}")
                print(f"   Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request Error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected Error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Founder Recognition Test Complete!")
    
    # Test chat status
    print("\n📊 Testing Chat System Status:")
    try:
        response = requests.get(f"{base_url}/api/v1/chat/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Chat Status: {data.get('status', 'Unknown')}")
            print(f"   ✅ Daena Available: {data.get('daena_available', 'Unknown')}")
            print(f"   ✅ LLM Available: {data.get('llm_available', 'Unknown')}")
        else:
            print(f"   ❌ Chat Status Error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Chat Status Error: {e}")

async def main():
    """Main test function"""
    print("👑 Daena AI VP - Founder Recognition Test")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/api/v1/", timeout=5)
        if response.status_code != 200:
            print("⚠️  Warning: Backend server may not be running on localhost:8000")
            print("   Start the server with: python main.py")
            return 1
    except:
        print("⚠️  Warning: Cannot connect to backend server on localhost:8000")
        print("   Start the server with: python main.py")
        return 1
    
    try:
        await test_founder_recognition()
        return 0
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 