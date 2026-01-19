"""
Diagnostic script to check database state for failing tests
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, ChatSession, CouncilCategory, CouncilMember
from sqlalchemy import func

def check_chat_sessions():
    """Check all department chat sessions in database"""
    db = SessionLocal()
    try:
        print("\n" + "="*60)
        print("CHAT SESSIONS DIAGNOSTIC")
        print("="*60)
        
        # Get all department sessions
        dept_sessions = db.query(ChatSession).filter(
            ChatSession.scope_type == "department",
            ChatSession.is_active == True
        ).all()
        
        print(f"\nTotal department sessions: {len(dept_sessions)}")
        
        if dept_sessions:
            print("\nDepartment Sessions:")
            for s in dept_sessions[:10]:  # Show first 10
                print(f"  - Session ID: {s.session_id[:16]}...")
                print(f"    scope_id: '{s.scope_id}' (type: {type(s.scope_id)})")
                print(f"    scope_type: '{s.scope_type}'")
                print(f"    title: '{s.title}'")
                print(f"    category: '{s.category}'")
                print(f"    is_active: {s.is_active}")
                print(f"    created_at: {s.created_at}")
                print()
        else:
            print("  No department sessions found!")
        
        # Group by scope_id
        if dept_sessions:
            from collections import Counter
            scope_ids = [str(s.scope_id) for s in dept_sessions if s.scope_id]
            scope_counts = Counter(scope_ids)
            print(f"\nSessions by scope_id:")
            for scope_id, count in scope_counts.most_common(10):
                print(f"  '{scope_id}': {count} sessions")
        
        # Get all sessions (any scope)
        all_sessions = db.query(ChatSession).filter(ChatSession.is_active == True).all()
        print(f"\nTotal active sessions (all types): {len(all_sessions)}")
        
    finally:
        db.close()

def check_councils():
    """Check all councils in database"""
    db = SessionLocal()
    try:
        print("\n" + "="*60)
        print("COUNCILS DIAGNOSTIC")
        print("="*60)
        
        # Get all categories
        categories = db.query(CouncilCategory).all()
        print(f"\nTotal council categories: {len(categories)}")
        
        if categories:
            print("\nCouncil Categories:")
            for cat in categories:
                members = db.query(CouncilMember).filter(
                    CouncilMember.category_id == cat.id
                ).all()
                print(f"  - ID: {cat.id}")
                print(f"    Name: '{cat.name}'")
                print(f"    Enabled: {cat.enabled}")
                print(f"    Members: {len(members)}")
                print(f"    Metadata: {cat.metadata_json}")
                if members:
                    print(f"    Member names: {[m.name for m in members[:3]]}")
                print()
        else:
            print("  No council categories found!")
        
        # Get all members
        all_members = db.query(CouncilMember).all()
        print(f"Total council members: {len(all_members)}")
        
        if all_members:
            print("\nSample Members:")
            for m in all_members[:5]:
                print(f"  - {m.name} (category_id: {m.category_id}, enabled: {m.enabled})")
        
    finally:
        db.close()

def test_session_creation():
    """Test creating a session and immediately querying it"""
    from backend.services.chat_service import chat_service
    from backend.database import SessionLocal
    
    db = SessionLocal()
    try:
        print("\n" + "="*60)
        print("SESSION CREATION TEST")
        print("="*60)
        
        # Create a test session
        test_dept_id = "engineering"
        print(f"\nCreating session with scope_id='{test_dept_id}'...")
        session = chat_service.create_session(
            db=db,
            title="Test Session",
            category="test",
            scope_type="department",
            scope_id=test_dept_id
        )
        print(f"Created session: {session.session_id}")
        print(f"  scope_id: '{session.scope_id}' (type: {type(session.scope_id)})")
        
        # Immediately query for it
        print(f"\nQuerying for sessions with scope_id='{test_dept_id}'...")
        sessions = chat_service.get_department_sessions(db, test_dept_id)
        print(f"Found {len(sessions)} sessions")
        
        if sessions:
            for s in sessions:
                print(f"  - {s.session_id[:16]}... (scope_id: '{s.scope_id}')")
        else:
            print("  No sessions found!")
            
            # Try direct query
            print("\nTrying direct query...")
            direct = db.query(ChatSession).filter(
                ChatSession.scope_type == "department",
                ChatSession.is_active == True,
                ChatSession.scope_id == test_dept_id
            ).all()
            print(f"Direct query found {len(direct)} sessions")
            
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Running diagnostics...")
    check_chat_sessions()
    check_councils()
    test_session_creation()
    print("\n✅ Diagnostics complete!")



