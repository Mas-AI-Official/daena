"""
Integration Registry System
Manages all available integrations for Daena, Agents, and Councils
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from enum import Enum

class AuthType(Enum):
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    NONE = "none"

class IntegrationCategory(Enum):
    AI = "ai"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    STORAGE = "storage"
    DATABASE = "database"
    SEARCH = "search"
    SOCIAL = "social"
    CALENDAR = "calendar"
    WEB = "web"
    BROWSER = "browser"

class IntegrationStatus(Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    CONFIGURED = "configured"
    ACTIVE = "active"
    ERROR = "error"

class IntegrationRegistry:
    """Central registry for all integrations"""
    
    _instance = None
    
    def __init__(self):
        self.integrations: Dict[str, Dict[str, Any]] = {}
        self.active_integrations: Dict[str, Any] = {}
        self.config_path = Path(__file__).parent.parent.parent / "config" / "integrations_config.json"
        self.load_config()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = IntegrationRegistry()
        return cls._instance
    
    def load_config(self):
        """Load integration configuration from JSON"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.integrations = config.get("integrations", {})
            except Exception as e:
                print(f"Error loading integrations config: {e}")
                self.integrations = self.get_default_integrations()
        else:
            self.integrations = self.get_default_integrations()
            self.save_config()
    
    def save_config(self):
        """Save integration configuration to JSON"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                json.dump({"integrations": self.integrations}, f, indent=2)
        except Exception as e:
            print(f"Error saving integrations config: {e}")
    
    def get_default_integrations(self) -> Dict[str, Dict[str, Any]]:
        """Default integration definitions"""
        return {
            # AI & ML
            "openai": {
                "name": "OpenAI",
                "category": "ai",
                "auth_type": "api_key",
                "capabilities": ["chat", "completion", "image_generation", "speech_to_text", "text_to_speech"],
                "icon": "fas fa-brain",
                "color": "#10A37F",
                "status": "available",
                "description": "GPT-4o, DALL-E, Whisper AI models"
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "category": "ai",
                "auth_type": "api_key",
                "capabilities": ["chat", "completion"],
                "icon": "fas fa-robot",
                "color": "#D97757",
                "status": "available",
                "description": "Claude 3.5 Sonnet AI assistant"
            },
            "google_gemini": {
                "name": "Google Gemini",
                "category": "ai",
                "auth_type": "api_key",
                "capabilities": ["chat", "completion", "multimodal"],
                "icon": "fab fa-google",
                "color": "#4285F4",
                "status": "available",
                "description": "Gemini 2.0 Flash AI model"
            },
            
            # Communication
            "gmail": {
                "name": "Gmail",
                "category": "communication",
                "auth_type": "oauth2",
                "capabilities": ["read_emails", "send_emails", "search", "labels"],
                "icon": "fas fa-envelope",
                "color": "#EA4335",
                "status": "available",
                "description": "Gmail email integration"
            },
            "slack": {
                "name": "Slack",
                "category": "communication",
                "auth_type": "api_key",
                "capabilities": ["send_message", "read_channels", "file_upload"],
                "icon": "fab fa-slack",
                "color": "#4A154B",
                "status": "available",
                "description": "Slack workspace messaging"
            },
            "telegram": {
                "name": "Telegram",
                "category": "communication",
                "auth_type": "api_key",
                "capabilities": ["send_message", "receive_updates", "bot_commands"],
                "icon": "fab fa-telegram",
                "color": "#0088cc",
                "status": "available",
                "description": "Telegram bot integration"
            },
            
            # Productivity
            "google_sheets": {
                "name": "Google Sheets",
                "category": "productivity",
                "auth_type": "oauth2",
                "capabilities": ["read", "write", "query", "create"],
                "icon": "fas fa-table",
                "color": "#34A853",
                "status": "available",
                "description": "Google Sheets spreadsheet operations"
            },
            "notion": {
                "name": "Notion",
                "category": "productivity",
                "auth_type": "api_key",
                "capabilities": ["read_database", "create_page", "update_page"],
                "icon": "fas fa-book",
                "color": "#000000",
                "status": "available",
                "description": "Notion workspace integration"
            },
            "airtable": {
                "name": "Airtable",
                "category": "productivity",
                "auth_type": "api_key",
                "capabilities": ["read_records", "create_records", "update_records"],
                "icon": "fas fa-database",
                "color": "#FFBF00",
                "status": "available",
                "description": "Airtable database operations"
            },
            
            # Storage
            "google_drive": {
                "name": "Google Drive",
                "category": "storage",
                "auth_type": "oauth2",
                "capabilities": ["upload", "download", "list", "search"],
                "icon": "fab fa-google-drive",
                "color": "#4285F4",
                "status": "available",
                "description": "Google Drive file storage"
            },
            "s3": {
                "name": "AWS S3",
                "category": "storage",
                "auth_type": "api_key",
                "capabilities": ["upload", "download", "list", "delete"],
                "icon": "fab fa-aws",
                "color": "#FF9900",
                "status": "available",
                "description": "Amazon S3 cloud storage"
            },
            
            # Database
            "supabase": {
                "name": "Supabase",
                "category": "database",
                "auth_type": "api_key",
                "capabilities": ["query", "insert", "update", "delete", "vector_search"],
                "icon": "fas fa-database",
                "color": "#3ECF8E",
                "status": "available",
                "description": "Supabase PostgreSQL + Vector DB"
            },
            "pinecone": {
                "name": "Pinecone",
                "category": "database",
                "auth_type": "api_key",
                "capabilities": ["upsert", "query", "delete", "vector_search"],
                "icon": "fas fa-vector-square",
                "color": "#7C3AED",
                "status": "available",
                "description": "Pinecone vector database"
            },
            
            # Search
            "serpapi": {
                "name": "SerpAPI",
                "category": "search",
                "auth_type": "api_key",
                "capabilities": ["google_search", "image_search", "news_search"],
                "icon": "fas fa-search",
                "color": "#4285F4",
                "status": "available",
                "description": "Google Search API"
            },
            "perplexity": {
                "name": "Perplexity AI",
                "category": "search",
                "auth_type": "api_key",
                "capabilities": ["ai_search", "research"],
                "icon": "fas fa-brain",
                "color": "#20808D",
                "status": "available",
                "description": "AI-powered search and research"
            },
            
            # Browser (already exists)
            "browser": {
                "name": "Browser Automation",
                "category": "browser",
                "auth_type": "none",
                "capabilities": ["navigate", "click", "fill", "screenshot", "scrape"],
                "icon": "fas fa-window-maximize",
                "color": "#00D9FF",
                "status": "active",
                "description": "Playwright browser automation"
            }
        }
    
    def list_all(self, category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all integrations with optional filters"""
        result = []
        for integration_id, config in self.integrations.items():
            if category and config.get("category") != category:
                continue
            if status and config.get("status") != status:
                continue
            result.append({
                "id": integration_id,
                **config
            })
        return result
    
    def get(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get specific integration details"""
        if integration_id in self.integrations:
            return {
                "id": integration_id,
                **self.integrations[integration_id]
            }
        return None
    
    def update_status(self, integration_id: str, status: str):
        """Update integration status"""
        if integration_id in self.integrations:
            self.integrations[integration_id]["status"] = status
            self.save_config()
    
    def register_active(self, integration_id: str, instance: Any):
        """Register an active integration instance"""
        self.active_integrations[integration_id] = instance
        self.update_status(integration_id, "active")
    
    def get_active(self, integration_id: str) -> Optional[Any]:
        """Get active integration instance"""
        return self.active_integrations.get(integration_id)
    
    def deactivate(self, integration_id: str):
        """Deactivate an integration"""
        if integration_id in self.active_integrations:
            del self.active_integrations[integration_id]
        self.update_status(integration_id, "configured")

def get_integration_registry():
    """Get global integration registry instance"""
    return IntegrationRegistry.get_instance()
