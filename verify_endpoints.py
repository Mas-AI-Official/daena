
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000/api/v1"

def check_endpoint(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            print(f"[{response.status}] {method} {url}")
            print("  -> Reachable")
            return True
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {method} {url}")
        print("  -> Reachable (Auth/Client Error)") # 4xx means the route exists
        return True
    except urllib.error.URLError as e:
        print(f"  -> Failed: {e.reason}")
        return False
    except Exception as e:
        print(f"  -> Error: {e}")
        return False

def main():
    print("Verifying critical endpoints...")
    
    # Governance
    check_endpoint(f"{BASE_URL}/governance/stats")
    
    # Audit
    check_endpoint(f"{BASE_URL}/audit/logs")
    
    # Shadow
    check_endpoint(f"{BASE_URL}/shadow/dashboard")
    
    # File System / IDE
    check_endpoint(f"{BASE_URL}/files/structure")

if __name__ == "__main__":
    main()
