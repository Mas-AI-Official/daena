"""
CMP Tool Registry - Dynamic plugin system for external service connections
Scalable to 1000+ tools without code changes
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path


class CredentialFieldType(str, Enum):
    STRING = "string"
    PASSWORD = "password"
    EMAIL = "email"
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    URL = "url"
    JSON = "json"


class CredentialField(BaseModel):
    name: str
    label: str
    type: CredentialFieldType
    required: bool = True
    placeholder: Optional[str] = None
    help_text: Optional[str] = None


class CMPToolCategory(str, Enum):
    EMAIL = "email"
    COMMUNICATION = "communication"
    AI_LLM = "ai_llm"
    DATABASE = "database"
    CLOUD_STORAGE = "cloud_storage"
    PRODUCTIVITY = "productivity"
    CRM = "crm"
    ANALYTICS = "analytics"
    AUTOMATION = "automation"
    OTHER = "other"


class CMPToolDefinition(BaseModel):
    id: str
    name: str
    category: CMPToolCategory
    description: str
    icon: str  # Font Awesome class or URL
    color: str  # Hex color for UI
    credentials: List[CredentialField]
    actions: List[str]  # Available actions (send, read, create, etc.)
    enabled: bool = True
    verified: bool = False  # Has been tested and works
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CMPToolRegistry:
    """
    Dynamic registry for CMP tools.
    Supports hot-reloading and plugin discovery.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent.parent
            storage_path = project_root / "local_brain" / "cmp_tools"
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.tools: Dict[str, CMPToolDefinition] = {}
        self._load_builtin_tools()
    
    def _load_builtin_tools(self):
        """Load built-in tool definitions"""
        builtin_tools = [
            # Email
            CMPToolDefinition(
                id="gmail",
                name="Gmail",
                category=CMPToolCategory.EMAIL,
                description="Google Gmail email service",
                icon="fab fa-google",
                color="#EA4335",
                credentials=[
                    CredentialField(name="email", label="Email Address", type=CredentialFieldType.EMAIL),
                    CredentialField(name="app_password", label="App Password", type=CredentialFieldType.PASSWORD, 
                                  help_text="Generate at: https://myaccount.google.com/apppasswords")
                ],
                actions=["send", "read", "search", "archive"]
            ),
            
            # AI/LLM
            CMPToolDefinition(
                id="gemini",
                name="Google Gemini",
                category=CMPToolCategory.AI_LLM,
                description="Google Gemini AI (via AntiGravity API)",
                icon="fas fa-brain",
                color="#4285F4",
                credentials=[
                    CredentialField(name="api_key", label="API Key", type=CredentialFieldType.API_KEY,
                                  placeholder="AIza...")
                ],
                actions=["generate", "chat", "analyze"]
            ),
            
            CMPToolDefinition(
                id="chatgpt",
                name="ChatGPT (OpenAI)",
                category=CMPToolCategory.AI_LLM,
                description="OpenAI ChatGPT API",
                icon="fas fa-robot",
                color="#10A37F",
                credentials=[
                    CredentialField(name="api_key", label="API Key", type=CredentialFieldType.API_KEY,
                                  placeholder="sk-...")
                ],
                actions=["chat", "completion", "embedding"]
            ),
            
            # Communication
            CMPToolDefinition(
                id="slack",
                name="Slack",
                category=CMPToolCategory.COMMUNICATION,
                description="Slack team messaging",
                icon="fab fa-slack",
                color="#4A154B",
                credentials=[
                    CredentialField(name="bot_token", label="Bot Token", type=CredentialFieldType.API_KEY,
                                  placeholder="xoxb-..."),
                    CredentialField(name="workspace_url", label="Workspace URL", type=CredentialFieldType.URL,
                                  placeholder="https://your-workspace.slack.com")
                ],
                actions=["send_message", "read_messages", "create_channel"]
            ),
            
            # Database
            CMPToolDefinition(
                id="postgresql",
                name="PostgreSQL",
                category=CMPToolCategory.DATABASE,
                description="PostgreSQL database",
                icon="fas fa-database",
                color="#336791",
                credentials=[
                    CredentialField(name="host", label="Host", type=CredentialFieldType.STRING),
                    CredentialField(name="port", label="Port", type=CredentialFieldType.STRING, placeholder="5432"),
                    CredentialField(name="database", label="Database", type=CredentialFieldType.STRING),
                    CredentialField(name="username", label="Username", type=CredentialFieldType.STRING),
                    CredentialField(name="password", label="Password", type=CredentialFieldType.PASSWORD)
                ],
                actions=["query", "insert", "update", "delete"]
            ),
            
            # Cloud Storage
            CMPToolDefinition(
                id="google_drive",
                name="Google Drive",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="Google Drive cloud storage",
                icon="fab fa-google-drive",
                color="#4285F4",
                credentials=[
                    CredentialField(name="service_account_json", label="Service Account JSON", 
                                  type=CredentialFieldType.JSON,
                                  help_text="Download from Google Cloud Console")
                ],
                actions=["upload", "download", "list", "share"]
            ),
            
            # n8n (Self-Hosted Automation)
            CMPToolDefinition(
                id="n8n",
                name="n8n",
                category=CMPToolCategory.AUTOMATION,
                description="Self-hosted workflow automation",
                icon="fas fa-project-diagram",
                color="#FF6D5A",
                credentials=[
                    CredentialField(name="instance_url", label="n8n Instance URL", type=CredentialFieldType.URL,
                                  placeholder="https://n8n.yourdomain.com"),
                    CredentialField(name="api_key", label="API Key", type=CredentialFieldType.API_KEY)
                ],
                actions=["trigger_workflow", "list_workflows", "get_execution"]
            ),

            # --- NEW TOOLS ---

            # Development
            CMPToolDefinition(
                id="github",
                name="GitHub",
                category=CMPToolCategory.PRODUCTIVITY,
                description="Code hosting and collaboration",
                icon="fab fa-github",
                color="#181717",
                credentials=[
                    CredentialField(name="access_token", label="Personal Access Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_issue", "get_repo", "list_prs", "trigger_action"]
            ),
            CMPToolDefinition(
                id="gitlab",
                name="GitLab",
                category=CMPToolCategory.PRODUCTIVITY,
                description="DevOps lifecycle tool",
                icon="fab fa-gitlab",
                color="#FC6D26",
                credentials=[
                    CredentialField(name="access_token", label="Access Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_issue", "get_project", "list_pipelines"]
            ),

            # Project Management
            CMPToolDefinition(
                id="jira",
                name="Jira Software",
                category=CMPToolCategory.PRODUCTIVITY,
                description="Issue and project tracking",
                icon="fab fa-jira",
                color="#0052CC",
                credentials=[
                    CredentialField(name="domain", label="Domain", type=CredentialFieldType.URL, placeholder="https://your-domain.atlassian.net"),
                    CredentialField(name="email", label="Email", type=CredentialFieldType.EMAIL),
                    CredentialField(name="api_token", label="API Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_issue", "get_issue", "search_issues"]
            ),
            CMPToolDefinition(
                id="trello",
                name="Trello",
                category=CMPToolCategory.PRODUCTIVITY,
                description="Kanban-style project management",
                icon="fab fa-trello",
                color="#0079BF",
                credentials=[
                    CredentialField(name="api_key", label="API Key", type=CredentialFieldType.API_KEY),
                    CredentialField(name="token", label="Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_card", "get_board", "move_card"]
            ),
            CMPToolDefinition(
                id="asana",
                name="Asana",
                category=CMPToolCategory.PRODUCTIVITY,
                description="Work management platform",
                icon="fas fa-tasks",
                color="#F06A6A",
                credentials=[
                    CredentialField(name="access_token", label="Personal Access Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_task", "get_project", "list_tasks"]
            ),
            CMPToolDefinition(
                id="notion",
                name="Notion",
                category=CMPToolCategory.PRODUCTIVITY,
                description="All-in-one workspace",
                icon="fas fa-book",
                color="#000000",
                credentials=[
                    CredentialField(name="api_key", label="Internal Integration Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_page", "query_database", "append_block"]
            ),

            # Communication
            CMPToolDefinition(
                id="discord",
                name="Discord",
                category=CMPToolCategory.COMMUNICATION,
                description="Voice, video and text chat",
                icon="fab fa-discord",
                color="#5865F2",
                credentials=[
                    CredentialField(name="bot_token", label="Bot Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["send_message", "get_channel", "add_role"]
            ),
            CMPToolDefinition(
                id="telegram",
                name="Telegram",
                category=CMPToolCategory.COMMUNICATION,
                description="Cloud-based messaging app",
                icon="fab fa-telegram",
                color="#26A5E4",
                credentials=[
                    CredentialField(name="bot_token", label="Bot Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["send_message", "get_updates"]
            ),
            CMPToolDefinition(
                id="zoom",
                name="Zoom",
                category=CMPToolCategory.COMMUNICATION,
                description="Video conferencing",
                icon="fas fa-video",
                color="#2D8CFF",
                credentials=[
                    CredentialField(name="api_key", label="API Key", type=CredentialFieldType.API_KEY),
                    CredentialField(name="api_secret", label="API Secret", type=CredentialFieldType.PASSWORD)
                ],
                actions=["create_meeting", "list_recordings"]
            ),

            # CRM & Sales
            CMPToolDefinition(
                id="salesforce",
                name="Salesforce",
                category=CMPToolCategory.CRM,
                description="Customer relationship management",
                icon="fab fa-salesforce",
                color="#00A1E0",
                credentials=[
                    CredentialField(name="instance_url", label="Instance URL", type=CredentialFieldType.URL),
                    CredentialField(name="access_token", label="Access Token", type=CredentialFieldType.OAUTH_TOKEN)
                ],
                actions=["create_lead", "get_contact", "update_opportunity"]
            ),
            CMPToolDefinition(
                id="hubspot",
                name="HubSpot",
                category=CMPToolCategory.CRM,
                description="Inbound marketing and sales",
                icon="fab fa-hubspot",
                color="#FF7A59",
                credentials=[
                    CredentialField(name="access_token", label="Private App Access Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_contact", "get_company", "list_deals"]
            ),

            # E-commerce & Payments
            CMPToolDefinition(
                id="stripe",
                name="Stripe",
                category=CMPToolCategory.OTHER,
                description="Online payment processing",
                icon="fab fa-stripe",
                color="#635BFF",
                credentials=[
                    CredentialField(name="secret_key", label="Secret Key", type=CredentialFieldType.API_KEY)
                ],
                actions=["create_charge", "get_customer", "list_subscriptions"]
            ),
            CMPToolDefinition(
                id="shopify",
                name="Shopify",
                category=CMPToolCategory.OTHER,
                description="E-commerce platform",
                icon="fab fa-shopify",
                color="#96BF48",
                credentials=[
                    CredentialField(name="shop_url", label="Shop URL", type=CredentialFieldType.URL),
                    CredentialField(name="access_token", label="Admin API Access Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["get_product", "create_order", "list_customers"]
            ),

            # Social Media
            CMPToolDefinition(
                id="twitter",
                name="X (Twitter)",
                category=CMPToolCategory.COMMUNICATION,
                description="Social networking service",
                icon="fab fa-twitter",
                color="#1DA1F2",
                credentials=[
                    CredentialField(name="bearer_token", label="Bearer Token", type=CredentialFieldType.API_KEY)
                ],
                actions=["post_tweet", "search_tweets", "get_user"]
            ),
            CMPToolDefinition(
                id="linkedin",
                name="LinkedIn",
                category=CMPToolCategory.COMMUNICATION,
                description="Professional networking",
                icon="fab fa-linkedin",
                color="#0A66C2",
                credentials=[
                    CredentialField(name="access_token", label="Access Token", type=CredentialFieldType.OAUTH_TOKEN)
                ],
                actions=["share_post", "get_profile"]
            ),

            # Cloud & Infrastructure
            CMPToolDefinition(
                id="aws",
                name="AWS",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="Amazon Web Services",
                icon="fab fa-aws",
                color="#FF9900",
                credentials=[
                    CredentialField(name="access_key", label="Access Key ID", type=CredentialFieldType.STRING),
                    CredentialField(name="secret_key", label="Secret Access Key", type=CredentialFieldType.PASSWORD),
                    CredentialField(name="region", label="Region", type=CredentialFieldType.STRING, placeholder="us-east-1")
                ],
                actions=["s3_upload", "ec2_start", "lambda_invoke"]
            ),
            CMPToolDefinition(
                id="azure",
                name="Microsoft Azure",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="Cloud computing services",
                icon="fab fa-microsoft",
                color="#0078D4",
                credentials=[
                    CredentialField(name="subscription_id", label="Subscription ID", type=CredentialFieldType.STRING),
                    CredentialField(name="client_id", label="Client ID", type=CredentialFieldType.STRING),
                    CredentialField(name="client_secret", label="Client Secret", type=CredentialFieldType.PASSWORD),
                    CredentialField(name="tenant_id", label="Tenant ID", type=CredentialFieldType.STRING)
                ],
                actions=["blob_upload", "vm_start", "function_invoke"]
            ),
            
            # Analytics
            CMPToolDefinition(
                id="google_analytics",
                name="Google Analytics 4",
                category=CMPToolCategory.ANALYTICS,
                description="Web analytics service",
                icon="fas fa-chart-pie",
                color="#E37400",
                credentials=[
                    CredentialField(name="property_id", label="Property ID", type=CredentialFieldType.STRING),
                    CredentialField(name="service_account_json", label="Service Account JSON", type=CredentialFieldType.JSON)
                ],
                actions=["get_report", "get_realtime"]
            ),
            
            # Local & Workspace Tools
            CMPToolDefinition(
                id="cursor_ide",
                name="Cursor IDE",
                category=CMPToolCategory.PRODUCTIVITY,
                description="AI Code Editor",
                icon="fas fa-terminal",
                color="#00D9FF",
                credentials=[
                    CredentialField(name="path", label="Project Path", type=CredentialFieldType.STRING)
                ],
                actions=["open_file", "list_files"]
            ),
            CMPToolDefinition(
                id="vscode",
                name="VS Code",
                category=CMPToolCategory.PRODUCTIVITY,
                description="Visual Studio Code",
                icon="fab fa-microsoft",
                color="#007ACC",
                credentials=[
                    CredentialField(name="path", label="Project Path", type=CredentialFieldType.STRING)
                ],
                actions=["open_file", "list_files"]
            ),
            CMPToolDefinition(
                id="local_folder",
                name="Local Folder",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="Local directory access",
                icon="fas fa-folder-open",
                color="#FFA500",
                credentials=[
                    CredentialField(name="path", label="Folder Path", type=CredentialFieldType.STRING)
                ],
                actions=["list_files", "read_file"]
            ),
            CMPToolDefinition(
                id="external_drive",
                name="External Drive",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="External USB/HDD/SSD",
                icon="fas fa-hdd",
                color="#808080",
                credentials=[
                    CredentialField(name="drive_letter", label="Drive Letter (e.g. E:)", type=CredentialFieldType.STRING)
                ],
                actions=["mount", "unmount", "list_files"]
            ),
            CMPToolDefinition(
                id="gcloud",
                name="Google Cloud Platform",
                category=CMPToolCategory.CLOUD_STORAGE,
                description="Google Cloud Infrastructure",
                icon="fab fa-google",
                color="#4285F4",
                credentials=[
                    CredentialField(name="project_id", label="Project ID", type=CredentialFieldType.STRING),
                    CredentialField(name="service_account_json", label="Service Account JSON", type=CredentialFieldType.JSON)
                ],
                actions=["list_instances", "storage_bucket"]
            )
        ]
        
        for tool in builtin_tools:
            self.tools[tool.id] = tool
    
    def register_tool(self, tool: CMPToolDefinition):
        """Register a new tool"""
        self.tools[tool.id] = tool
        self._save_to_disk(tool)
    
    def get_tool(self, tool_id: str) -> Optional[CMPToolDefinition]:
        """Get tool definition by ID"""
        return self.tools.get(tool_id)
    
    def list_tools(self, category: Optional[CMPToolCategory] = None) -> List[CMPToolDefinition]:
        """List all tools, optionally filtered by category"""
        tools = list(self.tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda x: x.name)
    
    def search_tools(self, query: str) -> List[CMPToolDefinition]:
        """Search tools by name or description"""
        query_lower = query.lower()
        return [
            tool for tool in self.tools.values()
            if query_lower in tool.name.lower() or query_lower in tool.description.lower()
        ]
    
    def enable_tool(self, tool_id: str):
        """Enable a tool"""
        if tool_id in self.tools:
            self.tools[tool_id].enabled = True
            self.tools[tool_id].updated_at = datetime.utcnow()
    
    def disable_tool(self, tool_id: str):
        """Disable a tool"""
        if tool_id in self.tools:
            self.tools[tool_id].enabled = False
            self.tools[tool_id].updated_at = datetime.utcnow()
    
    def _save_to_disk(self, tool: CMPToolDefinition):
        """Save tool definition to disk"""
        try:
            tool_file = self.storage_path / f"{tool.id}.json"
            tool_file.write_text(tool.json(indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Failed to save tool {tool.id}: {e}")


# Global singleton
cmp_registry = CMPToolRegistry()
