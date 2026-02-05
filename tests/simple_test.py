import requests

# Test Daena's natural conversation
url = "http://localhost:8000/api/v1/chat"

# Test 1: First greeting
print("🧪 Test 1: First greeting")
response1 = requests.post(url, json={"message": "Hello", "user_id": "founder"})
if response1.status_code == 200:
    result1 = response1.json()
    print(f"✅ Response: {result1.get('response', 'No response')[:100]}...")
else:
    print(f"❌ Error: {response1.status_code}")

print("\n" + "="*50 + "\n")

# Test 2: Follow-up question
print("🧪 Test 2: Follow-up question")
response2 = requests.post(url, json={"message": "What is your opinion about your structure?", "user_id": "founder"})
if response2.status_code == 200:
    result2 = response2.json()
    response_text = result2.get('response', 'No response')
    print(f"✅ Response: {response_text[:100]}...")
    
    # Check if it starts with "Hey boss!" (should NOT)
    if response_text.startswith("Hey boss!"):
        print("❌ PROBLEM: Response still starts with 'Hey boss!' - not natural!")
    else:
        print("✅ SUCCESS: Response is natural without repetitive greeting!")
else:
    print(f"❌ Error: {response2.status_code}") 