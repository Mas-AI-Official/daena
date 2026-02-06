
import os
import sys
import subprocess
import shutil

def run_doctor():
    print("🏥 Daena Environment Doctor v1.0")
    print("="*30)
    
    # 1. Check Python Dependencies
    print("🔍 Checking Python dependencies...")
    required_packages = ["fastapi", "uvicorn", "sqlalchemy", "multipart", "PyJWT", "keyring", "cryptography"]
    for pkg in required_packages:
        try:
            __import__(pkg if pkg != "PyJWT" else "jwt")
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} is missing. Attempting to fix...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

    # 2. Check Node/Frontend
    print("🔍 Checking Frontend dependencies...")
    if os.path.exists("frontend"):
        if not os.path.exists("frontend/node_modules"):
            print("  ❌ node_modules missing. Attempting to install...")
            subprocess.check_call(["npm", "install"], cwd="frontend")
        else:
            print("  ✅ node_modules found")
    
    # 3. Check DB
    print("🔍 Checking Database...")
    if os.path.exists("daena.db"):
        print("  ✅ daena.db found")
    else:
        print("  ⚠️ daena.db not found. It will be created on first run.")

    print("="*30)
    print("✨ Environment optimization complete. System ready.")

if __name__ == "__main__":
    run_doctor()
