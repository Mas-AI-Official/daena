import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def check_departments():
    print("Checking /departments...")
    try:
        response = requests.get(f"{BASE_URL}/departments", params={"limit": 5})
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success. Found {data.get('total_count')} departments.")
            for d in data.get('departments', []):
                print(f" - {d['name']} (Agents: {d.get('agents_count', 0)})")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def check_skills():
    print("\nChecking /skills...")
    try:
        response = requests.get(f"{BASE_URL}/skills")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success. Found {len(data.get('skills', []))} skills.")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    check_departments()
    check_skills()
