"""
Seed Integration Catalog
Pre-populates the integration catalog with popular apps.
Run with: python -m backend.scripts.seed_integration_catalog
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal, IntegrationCatalog, create_tables
import uuid


INTEGRATIONS = [
    # ============================================================
    # Communication
    # ============================================================
    {
        "key": "slack",
        "name": "Slack",
        "category": "communication",
        "auth_type": "oauth2",
        "icon_url": "/icons/slack.svg",
        "color": "#4A154B",
        "oauth_auth_url": "https://slack.com/oauth/v2/authorize",
        "oauth_token_url": "https://slack.com/api/oauth.v2.access",
        "oauth_scopes": ["chat:write", "channels:read", "users:read"],
        "oauth_client_id_env": "SLACK_CLIENT_ID",
        "oauth_client_secret_env": "SLACK_CLIENT_SECRET",
        "default_risk_level": "medium",
        "description": "Team messaging and collaboration",
        "is_featured": True
    },
    {
        "key": "discord",
        "name": "Discord",
        "category": "communication",
        "auth_type": "api_key",
        "icon_url": "/icons/discord.svg",
        "color": "#5865F2",
        "api_key_fields": ["bot_token"],
        "default_risk_level": "medium",
        "description": "Community chat and voice"
    },
    {
        "key": "telegram",
        "name": "Telegram",
        "category": "communication",
        "auth_type": "api_key",
        "icon_url": "/icons/telegram.svg",
        "color": "#0088cc",
        "api_key_fields": ["bot_token"],
        "default_risk_level": "low",
        "description": "Messaging platform"
    },
    {
        "key": "microsoft_teams",
        "name": "Microsoft Teams",
        "category": "communication",
        "auth_type": "oauth2",
        "icon_url": "/icons/teams.svg",
        "color": "#5558AF",
        "oauth_auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "oauth_token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "oauth_scopes": ["Chat.ReadWrite", "ChannelMessage.Send"],
        "default_risk_level": "medium",
        "description": "Enterprise team collaboration"
    },
    
    # ============================================================
    # Development
    # ============================================================
    {
        "key": "github",
        "name": "GitHub",
        "category": "development",
        "auth_type": "oauth2",
        "icon_url": "/icons/github.svg",
        "color": "#333333",
        "oauth_auth_url": "https://github.com/login/oauth/authorize",
        "oauth_token_url": "https://github.com/login/oauth/access_token",
        "oauth_scopes": ["repo", "read:user", "read:org"],
        "oauth_client_id_env": "GITHUB_CLIENT_ID",
        "oauth_client_secret_env": "GITHUB_CLIENT_SECRET",
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Code repository and collaboration",
        "is_featured": True
    },
    {
        "key": "gitlab",
        "name": "GitLab",
        "category": "development",
        "auth_type": "oauth2",
        "icon_url": "/icons/gitlab.svg",
        "color": "#FC6D26",
        "oauth_auth_url": "https://gitlab.com/oauth/authorize",
        "oauth_token_url": "https://gitlab.com/oauth/token",
        "oauth_scopes": ["api", "read_user"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "DevOps platform"
    },
    {
        "key": "jira",
        "name": "Jira",
        "category": "development",
        "auth_type": "oauth2",
        "icon_url": "/icons/jira.svg",
        "color": "#0052CC",
        "oauth_auth_url": "https://auth.atlassian.com/authorize",
        "oauth_token_url": "https://auth.atlassian.com/oauth/token",
        "oauth_scopes": ["read:jira-work", "write:jira-work"],
        "default_risk_level": "medium",
        "description": "Issue tracking"
    },
    {
        "key": "linear",
        "name": "Linear",
        "category": "development",
        "auth_type": "api_key",
        "icon_url": "/icons/linear.svg",
        "color": "#5E6AD2",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "Issue tracking for high-performing teams"
    },
    
    # ============================================================
    # Productivity
    # ============================================================
    {
        "key": "notion",
        "name": "Notion",
        "category": "productivity",
        "auth_type": "api_key",
        "icon_url": "/icons/notion.svg",
        "color": "#000000",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "Workspace and documents",
        "is_featured": True
    },
    {
        "key": "google_workspace",
        "name": "Google Workspace",
        "category": "productivity",
        "auth_type": "oauth2",
        "icon_url": "/icons/google.svg",
        "color": "#4285F4",
        "oauth_auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "oauth_token_url": "https://oauth2.googleapis.com/token",
        "oauth_scopes": [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar.readonly"
        ],
        "oauth_client_id_env": "GOOGLE_CLIENT_ID",
        "oauth_client_secret_env": "GOOGLE_CLIENT_SECRET",
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Gmail, Drive, Calendar",
        "is_featured": True
    },
    {
        "key": "trello",
        "name": "Trello",
        "category": "productivity",
        "auth_type": "api_key",
        "icon_url": "/icons/trello.svg",
        "color": "#0079BF",
        "api_key_fields": ["api_key", "api_token"],
        "default_risk_level": "low",
        "description": "Project management"
    },
    {
        "key": "asana",
        "name": "Asana",
        "category": "productivity",
        "auth_type": "oauth2",
        "icon_url": "/icons/asana.svg",
        "color": "#F06A6A",
        "oauth_auth_url": "https://app.asana.com/-/oauth_authorize",
        "oauth_token_url": "https://app.asana.com/-/oauth_token",
        "oauth_scopes": ["default"],
        "default_risk_level": "medium",
        "description": "Team project management"
    },
    {
        "key": "airtable",
        "name": "Airtable",
        "category": "productivity",
        "auth_type": "api_key",
        "icon_url": "/icons/airtable.svg",
        "color": "#18BFFF",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "Spreadsheet database"
    },
    
    # ============================================================
    # CRM/Sales
    # ============================================================
    {
        "key": "hubspot",
        "name": "HubSpot",
        "category": "crm",
        "auth_type": "api_key",
        "icon_url": "/icons/hubspot.svg",
        "color": "#FF7A59",
        "api_key_fields": ["api_key"],
        "default_risk_level": "high",
        "description": "Marketing and CRM"
    },
    {
        "key": "salesforce",
        "name": "Salesforce",
        "category": "crm",
        "auth_type": "oauth2",
        "icon_url": "/icons/salesforce.svg",
        "color": "#00A1E0",
        "oauth_auth_url": "https://login.salesforce.com/services/oauth2/authorize",
        "oauth_token_url": "https://login.salesforce.com/services/oauth2/token",
        "oauth_scopes": ["api", "refresh_token"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Enterprise CRM"
    },
    {
        "key": "pipedrive",
        "name": "Pipedrive",
        "category": "crm",
        "auth_type": "api_key",
        "icon_url": "/icons/pipedrive.svg",
        "color": "#3C994A",
        "api_key_fields": ["api_token"],
        "default_risk_level": "medium",
        "description": "Sales CRM"
    },
    
    # ============================================================
    # E-commerce
    # ============================================================
    {
        "key": "shopify",
        "name": "Shopify",
        "category": "ecommerce",
        "auth_type": "api_key",
        "icon_url": "/icons/shopify.svg",
        "color": "#96BF48",
        "api_key_fields": ["shop_domain", "api_key", "api_password"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Online store platform"
    },
    {
        "key": "stripe",
        "name": "Stripe",
        "category": "ecommerce",
        "auth_type": "api_key",
        "icon_url": "/icons/stripe.svg",
        "color": "#635BFF",
        "api_key_fields": ["secret_key"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Payment processing"
    },
    {
        "key": "woocommerce",
        "name": "WooCommerce",
        "category": "ecommerce",
        "auth_type": "api_key",
        "icon_url": "/icons/woocommerce.svg",
        "color": "#7F54B3",
        "api_key_fields": ["store_url", "consumer_key", "consumer_secret"],
        "default_risk_level": "high",
        "description": "WordPress e-commerce"
    },
    
    # ============================================================
    # Infrastructure
    # ============================================================
    {
        "key": "aws",
        "name": "AWS",
        "category": "infrastructure",
        "auth_type": "api_key",
        "icon_url": "/icons/aws.svg",
        "color": "#FF9900",
        "api_key_fields": ["access_key_id", "secret_access_key", "region"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "Amazon Web Services"
    },
    {
        "key": "vercel",
        "name": "Vercel",
        "category": "infrastructure",
        "auth_type": "api_key",
        "icon_url": "/icons/vercel.svg",
        "color": "#000000",
        "api_key_fields": ["token"],
        "default_risk_level": "medium",
        "description": "Deployment platform"
    },
    {
        "key": "cloudflare",
        "name": "Cloudflare",
        "category": "infrastructure",
        "auth_type": "api_key",
        "icon_url": "/icons/cloudflare.svg",
        "color": "#F38020",
        "api_key_fields": ["api_token"],
        "default_risk_level": "high",
        "description": "CDN and security"
    },
    
    # ============================================================
    # Database
    # ============================================================
    {
        "key": "mongodb",
        "name": "MongoDB",
        "category": "database",
        "auth_type": "api_key",
        "icon_url": "/icons/mongodb.svg",
        "color": "#47A248",
        "api_key_fields": ["connection_string"],
        "default_risk_level": "high",
        "requires_approval": True,
        "description": "NoSQL database"
    },
    {
        "key": "supabase",
        "name": "Supabase",
        "category": "database",
        "auth_type": "api_key",
        "icon_url": "/icons/supabase.svg",
        "color": "#3ECF8E",
        "api_key_fields": ["url", "anon_key", "service_role_key"],
        "default_risk_level": "high",
        "description": "Open source Firebase alternative"
    },
    
    # ============================================================
    # AI/ML
    # ============================================================
    {
        "key": "openai",
        "name": "OpenAI",
        "category": "ai",
        "auth_type": "api_key",
        "icon_url": "/icons/openai.svg",
        "color": "#412991",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "GPT models and APIs",
        "is_featured": True
    },
    {
        "key": "anthropic",
        "name": "Anthropic",
        "category": "ai",
        "auth_type": "api_key",
        "icon_url": "/icons/anthropic.svg",
        "color": "#D4A574",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "Claude models"
    },
    {
        "key": "pinecone",
        "name": "Pinecone",
        "category": "ai",
        "auth_type": "api_key",
        "icon_url": "/icons/pinecone.svg",
        "color": "#000000",
        "api_key_fields": ["api_key", "environment"],
        "default_risk_level": "low",
        "description": "Vector database"
    },
    {
        "key": "replicate",
        "name": "Replicate",
        "category": "ai",
        "auth_type": "api_key",
        "icon_url": "/icons/replicate.svg",
        "color": "#000000",
        "api_key_fields": ["api_token"],
        "default_risk_level": "medium",
        "description": "ML model hosting"
    },
    
    # ============================================================
    # Webhooks / Custom
    # ============================================================
    {
        "key": "webhook",
        "name": "Webhook",
        "category": "custom",
        "auth_type": "webhook",
        "icon_url": "/icons/webhook.svg",
        "color": "#6B7280",
        "api_key_fields": ["url", "secret"],
        "default_risk_level": "medium",
        "description": "Custom HTTP webhooks"
    },
    {
        "key": "n8n",
        "name": "n8n",
        "category": "automation",
        "auth_type": "api_key",
        "icon_url": "/icons/n8n.svg",
        "color": "#EA4B71",
        "api_key_fields": ["instance_url", "api_key"],
        "default_risk_level": "medium",
        "description": "Workflow automation"
    },
    {
        "key": "zapier",
        "name": "Zapier",
        "category": "automation",
        "auth_type": "api_key",
        "icon_url": "/icons/zapier.svg",
        "color": "#FF5733",
        "api_key_fields": ["api_key"],
        "default_risk_level": "medium",
        "description": "App automation"
    }
]


def seed_catalog():
    """Seed the integration catalog with popular apps."""
    
    create_tables()
    db = SessionLocal()
    
    added = 0
    updated = 0
    
    for integration_data in INTEGRATIONS:
        # Check if exists
        existing = db.query(IntegrationCatalog).filter(
            IntegrationCatalog.key == integration_data["key"]
        ).first()
        
        if not existing:
            # Create new
            catalog = IntegrationCatalog(
                id=str(uuid.uuid4()),
                **integration_data
            )
            db.add(catalog)
            print(f"  ✅ Added: {integration_data['name']}")
            added += 1
        else:
            # Update existing
            for key, value in integration_data.items():
                if key != 'id':
                    setattr(existing, key, value)
            print(f"  🔄 Updated: {integration_data['name']}")
            updated += 1
    
    db.commit()
    db.close()
    
    print(f"\n📦 Catalog seeding complete!")
    print(f"   Added: {added}, Updated: {updated}, Total: {len(INTEGRATIONS)}")


if __name__ == "__main__":
    print("🔧 Seeding Integration Catalog...")
    seed_catalog()
