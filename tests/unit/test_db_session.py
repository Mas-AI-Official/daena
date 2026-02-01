"""Test DB session to see if it blocks"""
import sys
sys.path.insert(0, "D:/Ideas/Daena_old_upgrade_20251213")

from backend.database import SessionLocal
from backend.services.chat_service import chat_service

print("Testing DB session...")

try:
    db = SessionLocal()
    print("SessionLocal() created")
    
    # Test create session
    session = chat_service.create_session(
        db=db,
        title="Test session",
        category="general",
        scope_type="general"
    )
    print(f"Session created: {session.session_id}")
    
    # Test add message
    chat_service.add_message(db, session.session_id, "user", "Test message")
    print("Message added")
    
    db.close()
    print("DB closed")
    print("\n✅ DB operations work - not blocking")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
