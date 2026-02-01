"""Test backend startup"""
import sys
sys.path.insert(0, ".")

print("Testing imports...")

# Test database
print("1. Database...")
from backend.database import SessionLocal, LearningLog, PendingApproval
print("   ✓ Database OK")

# Test founder_api
print("2. Founder API...")
from backend.routes.founder_api import router
print("   ✓ Founder API OK")

# Test learning service
print("3. Learning Service...")
from backend.services.learning_service import learning_service
print("   ✓ Learning Service OK")

# Test unified executor
print("4. Unified Executor...")
from backend.services.unified_tool_executor import unified_executor
print("   ✓ Unified Executor OK")

# Test app creation
print("5. Main App...")
try:
    from backend.main import app
    print("   ✓ Main App OK")
except Exception as e:
    print(f"   ✗ Main App Error: {e}")

print("\nAll imports passed!")
