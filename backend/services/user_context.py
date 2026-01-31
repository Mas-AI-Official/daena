"""
User Context Manager - Remembers users across sessions
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

def _user_context_file() -> Path:
    try:
        from backend.config.settings import get_brain_root
        return get_brain_root() / "user_context.json"
    except Exception:
        return Path(__file__).parent.parent.parent / "local_brain" / "user_context.json"


USER_CONTEXT_FILE = None  # Set on first access


def _get_user_context_file() -> Path:
    global USER_CONTEXT_FILE
    if USER_CONTEXT_FILE is None:
        USER_CONTEXT_FILE = _user_context_file()
    return USER_CONTEXT_FILE

class UserContextManager:
    _instance = None
    
    def __init__(self):
        self.user_data: Dict[str, Any] = {}
        self.load()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = UserContextManager()
        return cls._instance
    
    def load(self):
        """Load user context from file"""
        f = _get_user_context_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists():
            try:
                with open(f, 'r') as fp:
                    self.user_data = json.load(fp)
            except Exception:
                self.user_data = self.get_default_context()
        else:
            self.user_data = self.get_default_context()
            self.save()
    
    def get_default_context(self) -> Dict[str, Any]:
        """Default user context for Masoud"""
        from pathlib import Path
        workspace_root = str(Path(__file__).parent.parent.parent)
        return {
            "name": "Masoud",
            "role": "Founder & CEO",
            "company": "MAS-AI",
            "workspace_path": workspace_root,
            "preferences": {
                "communication_style": "direct and technical",
                "priorities": ["system reliability", "feature completion", "user experience"]
            },
            "access_level": "founder",  # Full access to everything
            "last_seen": datetime.now().isoformat(),
            "conversation_memory": []
        }
    
    def save(self):
        """Save user context to file"""
        try:
            with open(_get_user_context_file(), 'w') as f:
                json.dump(self.user_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save user context: {e}")
    
    def get_user_name(self) -> str:
        return self.user_data.get("name", "User")
    
    def get_user_role(self) -> str:
        return self.user_data.get("role", "User")
    
    def get_company(self) -> str:
        return self.user_data.get("company", "Company")
    
    def update_last_seen(self):
        """Update last seen timestamp"""
        self.user_data["last_seen"] = datetime.now().isoformat()
        self.save()
    
    def add_conversation_context(self, key: str, value: Any):
        """Add to conversation memory"""
        if "conversation_memory" not in self.user_data:
            self.user_data["conversation_memory"] = []
        
        self.user_data["conversation_memory"].append({
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "value": value
        })
        
        # Keep only last 50 items
        self.user_data["conversation_memory"] = self.user_data["conversation_memory"][-50:]
        self.save()
    
    def get_context_summary(self) -> str:
        """Get a context summary for system prompt"""
        name = self.get_user_name()
        role = self.get_user_role()
        company = self.get_company()
        
        return f"""USER CONTEXT:
- Name: {name}
- Role: {role} (Your creator and founder)
- Company: {company}
- Access Level: Full (Founder)
- You should address them as {name} and recognize their authority"""

def get_user_context():
    """Get global user context manager"""
    return UserContextManager.get_instance()
