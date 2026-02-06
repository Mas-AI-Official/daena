
import urllib.request
import urllib.error
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_login():
    print("Testing Login...")
    url = f"{BASE_URL}/auth/login"
    data = json.dumps({"user_id": "masoud", "password": "any"}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                res_body = response.read().decode('utf-8')
                token = json.loads(res_body).get("access_token")
                print(f"✅ Login Successful. Token: {token[:10]}...")
                return token
            else:
                print(f"❌ Login Failed: {response.status}")
                return None
    except urllib.error.HTTPError as e:
        print(f"❌ Login Failed: {e.code} {e.reason}")
        return None
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return None

def test_models(token):
    print("\nTesting Models Registry...")
    url = f"{BASE_URL}/models/registry"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                res_body = response.read().decode('utf-8')
                data = json.loads(res_body)
                models = data.get("registry", {}).get("models", [])
                print(f"✅ Models Registry Accessible. Found {len(models)} models.")
                for m in models:
                    print(f"   - {m['name']} ({m['tier']})")
                    
                # Try Active
                print(f"   - Active Model: {data.get('primary')}")
            else:
                 print(f"❌ Models Registry Failed: {response.status}")
    except Exception as e:
        print(f"❌ Models Error: {e}")

def test_departments(token):
    print("\nTesting Departments...")
    url = f"{BASE_URL}/departments"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                 print(f"✅ Departments Accessible.")
                 # Could read and parse, but seeing 200 is enough
            else:
                 print(f"❌ Departments Failed: {response.status}")
    except Exception as e:
        print(f"❌ Departments Error: {e}")

if __name__ == "__main__":
    token = test_login()
    if token:
        test_models(token)
        test_departments(token)
