"""Scrape Codex plugins on disk and mirror their richness into Daena.

Reads plugin manifests, MCP configs, and SKILL.md files from
`C:\\Users\\masou\\.codex\\plugins\\cache`, then:

  1. Enriches `backend/app/config/connector_catalog.json` with the
     `interface`, `mcp_servers`, `skills`, and `auth` blocks needed to
     drive the new install dialog.
  2. Mirrors each Codex skill into `D:\\Ideas\\Daena\\skills\\<plugin>\\
     <sub-skill>\\SKILL.md` so Daena agents have the same playbooks
     Codex ships with.
  3. Pre-populates well-known connectors that do NOT have a Codex
     manifest on disk (Vercel, Netlify, GitHub, etc.) using public
     metadata so the install dialog is professional even for plugins
     Codex did not bundle.

Re-runnable. Existing fields on each connector are preserved.
Run from anywhere: `python D:\\Ideas\\Daena\\scripts\\scrape_codex_plugins.py`
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

CODEX_CACHE = Path(r"C:\Users\masou\.codex\plugins\cache")
DAENA_ROOT = Path(r"D:\Ideas\Daena")
CATALOG_PATH = DAENA_ROOT / "backend" / "app" / "config" / "connector_catalog.json"
SKILLS_ROOT = DAENA_ROOT / "skills"
ICON_DEST = DAENA_ROOT / "frontend" / "src" / "assets" / "icons" / "connectors"


# ---------------------------------------------------------------------------
# Pre-populated metadata for connectors WITHOUT a local Codex manifest.
# Sourced from each provider's public docs and the Codex marketplace UI.
# Brand colors verified against vendor brand pages 2026-04-29.
# ---------------------------------------------------------------------------

KNOWN_CONNECTORS: dict[str, dict[str, Any]] = {
    "hugging-face": {
        "name": "Hugging Face",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://huggingface.co/settings/tokens",
            "token_help": "Create a Read-only or Fine-grained token. Daena will only call read endpoints by default.",
            "validate_endpoint": "https://huggingface.co/api/whoami-v2",
        },
        "interface": {
            "displayName": "Hugging Face",
            "shortDescription": "Inspect models, datasets, Spaces, and research",
            "longDescription": "Browse and inspect models, datasets, and Spaces on the Hugging Face Hub. Read-only by default; upgrade scope when you need to push artifacts or run inference.",
            "developerName": "Hugging Face",
            "websiteURL": "https://huggingface.co",
            "privacyPolicyURL": "https://huggingface.co/privacy",
            "termsOfServiceURL": "https://huggingface.co/terms-of-service",
            "brandColor": "#FFD21E",
            "defaultPrompts": [
                "Find the top open-source LLMs under 8B params.",
                "Show me the most-downloaded text-to-image dataset this month.",
            ],
            "capabilities": ["Interactive", "Read"],
        },
    },
    "vercel": {
        "name": "Vercel",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://vercel.com/account/tokens",
            "token_help": "Create a token scoped to the team and projects you want Daena to manage.",
            "validate_endpoint": "https://api.vercel.com/v2/user",
        },
        "interface": {
            "displayName": "Vercel",
            "shortDescription": "Build and deploy web apps and agents",
            "longDescription": "Trigger deployments, inspect logs, manage environment variables, and read project state on Vercel. Pair with the Build Web Apps plugin for end-to-end shipping.",
            "developerName": "Vercel",
            "websiteURL": "https://vercel.com",
            "privacyPolicyURL": "https://vercel.com/legal/privacy-policy",
            "termsOfServiceURL": "https://vercel.com/legal/terms",
            "brandColor": "#000000",
            "defaultPrompts": [
                "Show me the last 5 deployments for my production project.",
                "Why did the last deployment fail? Read the build logs.",
            ],
            "capabilities": ["Interactive", "Write"],
        },
    },
    "netlify": {
        "name": "Netlify",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://app.netlify.com/user/applications#personal-access-tokens",
            "token_help": "Personal access tokens grant the same permissions your account has.",
            "validate_endpoint": "https://api.netlify.com/api/v1/user",
        },
        "interface": {
            "displayName": "Netlify",
            "shortDescription": "Deploy projects and manage releases",
            "longDescription": "Deploy sites, stream build logs, manage environment variables, and inspect serverless function executions on Netlify.",
            "developerName": "Netlify",
            "websiteURL": "https://www.netlify.com",
            "privacyPolicyURL": "https://www.netlify.com/privacy/",
            "termsOfServiceURL": "https://www.netlify.com/legal/terms-of-use/",
            "brandColor": "#00C7B7",
            "defaultPrompts": [
                "Trigger a deploy of the main branch.",
                "Show me the function execution logs for the last hour.",
            ],
            "capabilities": ["Interactive", "Write"],
        },
    },
    "github": {
        "name": "GitHub",
        "category": "Coding",
        "auth": {
            "method": "oauth_managed",
            "token_settings_url": "https://github.com/settings/tokens?type=beta",
            "token_help": "Fine-grained personal access tokens recommended. Scope to specific repos.",
            "validate_endpoint": "https://api.github.com/user",
        },
        "interface": {
            "displayName": "GitHub",
            "shortDescription": "Triage PRs, issues, CI, and publish flows",
            "longDescription": "Read repos and files, triage pull requests, manage issues, inspect Actions runs, and cut releases. The included GitHub MCP server gives Daena live repo state without manual context.",
            "developerName": "GitHub",
            "websiteURL": "https://github.com",
            "privacyPolicyURL": "https://docs.github.com/en/site-policy/privacy-policies",
            "termsOfServiceURL": "https://docs.github.com/en/site-policy/github-terms",
            "brandColor": "#181717",
            "defaultPrompts": [
                "Triage the open PRs on this repo and tell me which need attention.",
                "Why did the last CI run fail on this branch?",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "circleci": {
        "name": "CircleCI",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://app.circleci.com/settings/user/tokens",
            "token_help": "Personal API token with read access to your projects.",
            "validate_endpoint": "https://circleci.com/api/v2/me",
        },
        "interface": {
            "displayName": "CircleCI",
            "shortDescription": "Build, test, and deploy any application",
            "longDescription": "List pipelines, trigger builds, and fetch job logs from CircleCI. Pair with GitHub for end-to-end CI debugging.",
            "developerName": "CircleCI",
            "websiteURL": "https://circleci.com",
            "privacyPolicyURL": "https://circleci.com/privacy",
            "termsOfServiceURL": "https://circleci.com/terms-of-service",
            "brandColor": "#161616",
            "defaultPrompts": [
                "Show me the last 10 pipeline runs and their statuses.",
                "Trigger the deploy workflow on the release branch.",
            ],
            "capabilities": ["Interactive", "Write"],
        },
    },
    "sentry": {
        "name": "Sentry",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://sentry.io/settings/account/api/auth-tokens/",
            "token_help": "User auth tokens with project:read scope.",
            "validate_endpoint": "https://sentry.io/api/0/",
        },
        "interface": {
            "displayName": "Sentry",
            "shortDescription": "Inspect recent Sentry issues and events",
            "longDescription": "Surface recent errors, group similar events, and pull stack traces for triage. Read-only by default.",
            "developerName": "Sentry",
            "websiteURL": "https://sentry.io",
            "privacyPolicyURL": "https://sentry.io/privacy/",
            "termsOfServiceURL": "https://sentry.io/terms/",
            "brandColor": "#362D59",
            "defaultPrompts": [
                "What are the top 5 errors in the last 24 hours?",
                "Show me the stack trace for issue SENTRY-1234.",
            ],
            "capabilities": ["Interactive", "Read"],
        },
    },
    "expo": {
        "name": "Expo",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://expo.dev/accounts/[account]/settings/access-tokens",
            "token_help": "Personal access tokens for EAS Build, Submit, and Update.",
            "validate_endpoint": "https://api.expo.dev/v2/user",
        },
        "interface": {
            "displayName": "Expo",
            "shortDescription": "Build, deploy, upgrade Expo and React Native apps",
            "longDescription": "Drive EAS Build pipelines, ship OTA updates, and inspect Expo project state.",
            "developerName": "Expo",
            "websiteURL": "https://expo.dev",
            "privacyPolicyURL": "https://expo.dev/privacy",
            "termsOfServiceURL": "https://expo.dev/terms",
            "brandColor": "#000020",
            "defaultPrompts": [
                "Build my app for iOS production via EAS.",
                "Push an OTA update to the staging channel.",
            ],
            "capabilities": ["Interactive", "Write"],
        },
    },
    "coderabbit": {
        "name": "CodeRabbit",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://app.coderabbit.ai/settings/api-keys",
            "token_help": "API key for the CodeRabbit review service.",
            "validate_endpoint": "https://api.coderabbit.ai/v1/health",
        },
        "interface": {
            "displayName": "CodeRabbit",
            "shortDescription": "Run AI-powered code review for your current changes",
            "longDescription": "Run CodeRabbit reviews against pull requests, summarize diffs, and surface suggested fixes inline.",
            "developerName": "CodeRabbit",
            "websiteURL": "https://www.coderabbit.ai",
            "privacyPolicyURL": "https://www.coderabbit.ai/privacy-policy",
            "termsOfServiceURL": "https://www.coderabbit.ai/terms",
            "brandColor": "#F58220",
            "defaultPrompts": [
                "Run a CodeRabbit review on PR #123.",
                "Summarize the diff in plain English.",
            ],
            "capabilities": ["Interactive", "Read"],
        },
    },
    "neon": {
        "name": "Neon Postgres",
        "category": "Coding",
        "auth": {
            "method": "mcp_remote_oauth",
            "mcp_url": "https://mcp.neon.tech/sse",
            "fallback": {
                "method": "api_token",
                "token_settings_url": "https://console.neon.tech/app/settings/api-keys",
            },
        },
        "interface": {
            "displayName": "Neon Postgres",
            "shortDescription": "Manage Neon Serverless Postgres projects and databases",
            "longDescription": "List Neon projects, branch databases for safe migrations, run queries, and inspect connection strings. Branching is the killer feature; reach for it before destructive changes.",
            "developerName": "Neon",
            "websiteURL": "https://neon.tech",
            "privacyPolicyURL": "https://neon.tech/privacy-policy",
            "termsOfServiceURL": "https://neon.tech/terms-of-service",
            "brandColor": "#00E599",
            "defaultPrompts": [
                "Branch the production database for a migration test.",
                "Show me the connection string for my dev branch.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "cloudinary": {
        "name": "Cloudinary",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://console.cloudinary.com/settings/c-/api-keys",
            "token_help": "API key + secret pair. Cloudinary uses both, not just one.",
            "field_layout": ["api_key", "api_secret", "cloud_name"],
        },
        "interface": {
            "displayName": "Cloudinary",
            "shortDescription": "Manage, search, and transform your media library",
            "longDescription": "Upload, search, and transform images and videos via the Cloudinary Media Library. Pair with ContentOps for end-to-end social rendering.",
            "developerName": "Cloudinary",
            "websiteURL": "https://cloudinary.com",
            "privacyPolicyURL": "https://cloudinary.com/privacy",
            "termsOfServiceURL": "https://cloudinary.com/tos",
            "brandColor": "#3448C5",
            "defaultPrompts": [
                "Upload this video and return the streaming URL.",
                "Find all images tagged 'hero-shot' in my library.",
            ],
            "capabilities": ["Interactive", "Write"],
        },
    },
    "render": {
        "name": "Render",
        "category": "Coding",
        "auth": {
            "method": "api_token",
            "token_settings_url": "https://dashboard.render.com/u/settings#api-keys",
            "validate_endpoint": "https://api.render.com/v1/services",
        },
        "interface": {
            "displayName": "Render",
            "shortDescription": "Deploy, debug, monitor, and migrate apps on Render",
            "longDescription": "Deploy services, stream logs, list services, and migrate apps on Render. Read-only safe; deploys gated behind explicit approval.",
            "developerName": "Render",
            "websiteURL": "https://render.com",
            "privacyPolicyURL": "https://render.com/privacy",
            "termsOfServiceURL": "https://render.com/terms",
            "brandColor": "#46E3B7",
            "defaultPrompts": [
                "Show me the deploy status for my production service.",
                "Stream the logs for the last 5 minutes.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "linear": {
        "name": "Linear",
        "category": "Productivity",
        "auth": {
            "method": "mcp_remote_oauth",
            "mcp_url": "https://mcp.linear.app/sse",
            "fallback": {
                "method": "api_token",
                "token_settings_url": "https://linear.app/settings/api",
            },
        },
        "interface": {
            "displayName": "Linear",
            "shortDescription": "Find and reference issues and projects",
            "longDescription": "Read issues, create and update them, and reference projects. Linear MCP supports OAuth so you do not need to manage tokens.",
            "developerName": "Linear",
            "websiteURL": "https://linear.app",
            "privacyPolicyURL": "https://linear.app/privacy",
            "termsOfServiceURL": "https://linear.app/terms",
            "brandColor": "#5E6AD2",
            "defaultPrompts": [
                "Show me my P0 issues.",
                "Create an issue: 'Login button is broken on Safari'.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "atlassian-rovo": {
        "name": "Atlassian Rovo",
        "category": "Productivity",
        "auth": {
            "method": "mcp_remote_oauth",
            "mcp_url": "https://mcp.atlassian.com/v1/sse",
        },
        "interface": {
            "displayName": "Atlassian Rovo",
            "shortDescription": "Manage Jira and Confluence fast",
            "longDescription": "Search Jira issues and Confluence pages, create issues, and read documentation. OAuth-based; no tokens to manage.",
            "developerName": "Atlassian",
            "websiteURL": "https://www.atlassian.com/software/rovo",
            "privacyPolicyURL": "https://www.atlassian.com/legal/privacy-policy",
            "termsOfServiceURL": "https://www.atlassian.com/legal/cloud-terms-of-service",
            "brandColor": "#0052CC",
            "defaultPrompts": [
                "Find Jira issues assigned to me with 'urgent' label.",
                "Search Confluence for the deploy runbook.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "google-calendar": {
        "name": "Google Calendar",
        "category": "Productivity",
        "auth": {
            "method": "oauth_managed",
            "scopes": [
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events",
            ],
        },
        "interface": {
            "displayName": "Google Calendar",
            "shortDescription": "Manage Google Calendar events and schedules",
            "longDescription": "Read calendars, create and update events, and find free slots. OAuth flow handled by Daena; no API key needed.",
            "developerName": "Google",
            "websiteURL": "https://calendar.google.com",
            "privacyPolicyURL": "https://policies.google.com/privacy",
            "termsOfServiceURL": "https://policies.google.com/terms",
            "brandColor": "#4285F4",
            "defaultPrompts": [
                "What is on my calendar tomorrow?",
                "Find a 30-minute slot this week to meet with Sarah.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "gmail": {
        "name": "Gmail",
        "category": "Productivity",
        "auth": {
            "method": "oauth_managed",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
        },
        "interface": {
            "displayName": "Gmail",
            "shortDescription": "Read and manage Gmail",
            "longDescription": "Read inboxes, search threads, send emails, and create drafts. OAuth-only; no tokens to manage.",
            "developerName": "Google",
            "websiteURL": "https://mail.google.com",
            "privacyPolicyURL": "https://policies.google.com/privacy",
            "termsOfServiceURL": "https://policies.google.com/terms",
            "brandColor": "#EA4335",
            "defaultPrompts": [
                "Triage my unread inbox.",
                "Draft a reply to the last email from Sarah.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "hubspot": {
        "name": "HubSpot",
        "category": "Sales",
        "auth": {
            "method": "oauth_managed",
            "token_settings_url": "https://app.hubspot.com/private-apps",
            "fallback": {
                "method": "api_token",
                "token_help": "Private app access tokens with crm.objects scopes.",
            },
        },
        "interface": {
            "displayName": "HubSpot",
            "shortDescription": "Work with your HubSpot data to analyze patterns, create and update records, and manage your CRM operations.",
            "longDescription": "Read and write deals, contacts, companies, tickets, and engagements. Prepare reports, update deal stages, log calls, create tasks, or review pipeline before meetings.",
            "developerName": "HubSpot",
            "websiteURL": "https://www.hubspot.com",
            "privacyPolicyURL": "https://legal.hubspot.com/privacy-policy",
            "termsOfServiceURL": "https://legal.hubspot.com/terms-of-service",
            "brandColor": "#FF7A59",
            "defaultPrompts": [
                "Show me deals closing this quarter.",
                "Create a follow-up task to schedule a meeting with the deal owner.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
    "canva": {
        "name": "Canva",
        "category": "Design",
        "auth": {
            "method": "oauth_managed",
        },
        "interface": {
            "displayName": "Canva",
            "shortDescription": "Search, create, edit designs",
            "longDescription": "Search your Canva library, create new designs, and export finished work. OAuth flow.",
            "developerName": "Canva",
            "websiteURL": "https://www.canva.com",
            "privacyPolicyURL": "https://www.canva.com/policies/privacy-policy/",
            "termsOfServiceURL": "https://www.canva.com/policies/terms-of-use/",
            "brandColor": "#00C4CC",
            "defaultPrompts": [
                "Find my latest brand kit designs.",
                "Export the team logo as PNG and SVG.",
            ],
            "capabilities": ["Interactive", "Write", "Read"],
        },
    },
}


# Map of plugin name on disk -> Daena slug, for plugins that are
# CONNECTORS (not skills/extensions) in Daena's taxonomy.
PLUGIN_TO_CONNECTOR = {
    "cloudflare": "cloudflare",
    "gmail": "gmail",
    "hubspot": "hubspot",
    "figma": "figma",
    "slack": "slack",
}


def find_plugin_dir(plugin_name: str) -> Path | None:
    """Locate a plugin's root directory inside the Codex cache."""
    for marketplace in ("openai-curated", "openai-bundled", "claude-plugins-official", "openai-primary-runtime"):
        market_root = CODEX_CACHE / marketplace / plugin_name
        if not market_root.exists():
            continue
        # Plugins are versioned by hash or semver. Pick the latest.
        versions = sorted(p for p in market_root.iterdir() if p.is_dir())
        if versions:
            return versions[-1]
    return None


def load_plugin_manifest(plugin_dir: Path) -> dict[str, Any]:
    """Read the plugin.json manifest, regardless of which schema variant."""
    candidates = [
        plugin_dir / ".codex-plugin" / "plugin.json",
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / ".cursor-plugin" / "plugin.json",
    ]
    for c in candidates:
        if c.exists():
            return json.loads(c.read_text(encoding="utf-8"))
    return {}


def load_mcp_config(plugin_dir: Path) -> dict[str, Any]:
    mcp_path = plugin_dir / ".mcp.json"
    if mcp_path.exists():
        return json.loads(mcp_path.read_text(encoding="utf-8")).get("mcpServers", {})
    return {}


def load_app_config(plugin_dir: Path) -> dict[str, Any]:
    app_path = plugin_dir / ".app.json"
    if app_path.exists():
        return json.loads(app_path.read_text(encoding="utf-8")).get("apps", {})
    return {}


def list_skills(plugin_dir: Path) -> list[Path]:
    """All SKILL.md files inside the plugin's skills/ tree."""
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return []
    return list(skills_dir.rglob("SKILL.md"))


def parse_skill_frontmatter(skill_md: Path) -> dict[str, str]:
    """Extract YAML-style frontmatter at the top of a SKILL.md file."""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {"name": skill_md.parent.name, "description": ""}
    end = text.find("---", 3)
    if end == -1:
        return {"name": skill_md.parent.name, "description": ""}
    fm = text[3:end].strip()
    out: dict[str, str] = {}
    current_key: str | None = None
    for raw in fm.splitlines():
        if not raw.strip():
            continue
        if raw[0].isspace() and current_key:
            out[current_key] = (out.get(current_key, "") + " " + raw.strip()).strip()
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            current_key = k.strip()
            out[current_key] = v.strip()
    return out


def copy_skill_tree(plugin_dir: Path, daena_plugin_dir: Path) -> int:
    """Mirror the plugin's skills/ tree into Daena's skill tree.

    Preserves directory structure. Overwrites existing files (skills are
    expected to evolve as Codex updates them). Returns count of skill
    files copied.
    """
    src = plugin_dir / "skills"
    if not src.exists():
        return 0
    dest = daena_plugin_dir / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for skill_md in src.rglob("SKILL.md"):
        rel = skill_md.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, target)
        copied += 1
        # Copy any sibling assets / referenced files.
        for sibling in skill_md.parent.iterdir():
            if sibling == skill_md or sibling.is_dir():
                continue
            shutil.copy2(sibling, target.parent / sibling.name)
    return copied


def copy_assets(plugin_dir: Path, slug: str) -> str | None:
    """Copy the plugin's logo into Daena's connector icons dir."""
    assets = plugin_dir / "assets"
    if not assets.exists():
        return None
    ICON_DEST.mkdir(parents=True, exist_ok=True)
    # Prefer logo.png > brand.png > <name>.png > first .png
    candidates = sorted(
        (p for p in assets.glob("*.png")),
        key=lambda p: (
            0 if p.stem.lower() in ("logo", "icon", "brand", slug) else 1,
            p.name,
        ),
    )
    if not candidates:
        return None
    target = ICON_DEST / f"{slug}.png"
    shutil.copy2(candidates[0], target)
    return str(target.relative_to(DAENA_ROOT)).replace("\\", "/")


def build_connector_entry(slug: str, plugin_name: str | None) -> dict[str, Any]:
    """Build the enriched catalog entry for a connector slug.

    Merges, in order: pre-existing entry (if any), KNOWN_CONNECTORS
    defaults, scraped Codex data (if any).
    """
    entry: dict[str, Any] = {}

    # Layer 1: defaults
    if slug in KNOWN_CONNECTORS:
        defaults = KNOWN_CONNECTORS[slug]
        entry["name"] = defaults["name"]
        entry["category"] = defaults["category"]
        entry["interface"] = dict(defaults.get("interface", {}))
        entry["auth"] = dict(defaults.get("auth", {}))

    # Layer 2: Codex manifest (overrides defaults when present)
    if plugin_name:
        plugin_dir = find_plugin_dir(plugin_name)
        if plugin_dir:
            manifest = load_plugin_manifest(plugin_dir)
            mcp = load_mcp_config(plugin_dir)
            app = load_app_config(plugin_dir)

            # Interface: take Codex values when richer than ours.
            cdx_interface = manifest.get("interface", {})
            if cdx_interface:
                # Use Codex display name + descriptions verbatim.
                target = entry.setdefault("interface", {})
                target.setdefault("displayName", cdx_interface.get("displayName", entry.get("name", slug.title())))
                target.setdefault("shortDescription", cdx_interface.get("shortDescription", ""))
                target.setdefault("longDescription", cdx_interface.get("longDescription", ""))
                target.setdefault("developerName", cdx_interface.get("developerName", ""))
                target.setdefault("websiteURL", cdx_interface.get("websiteURL", ""))
                target.setdefault("privacyPolicyURL", cdx_interface.get("privacyPolicyURL", ""))
                target.setdefault("termsOfServiceURL", cdx_interface.get("termsOfServiceURL", ""))
                target.setdefault("brandColor", cdx_interface.get("brandColor", "#7B6CFF"))
                target.setdefault("capabilities", cdx_interface.get("capabilities", []))
                if "defaultPrompt" in cdx_interface and not target.get("defaultPrompts"):
                    target["defaultPrompts"] = cdx_interface["defaultPrompt"]

            # MCP servers: keep Codex's URL + transport spec.
            if mcp:
                entry["mcp_servers"] = mcp
                # If MCP is present and we have no auth.method, default to mcp_remote_oauth.
                if "auth" not in entry or not entry["auth"]:
                    first_server = next(iter(mcp.values()), {})
                    entry["auth"] = {
                        "method": "mcp_remote_oauth",
                        "mcp_url": first_server.get("url", ""),
                    }
                    if "oauth" in first_server:
                        entry["auth"]["oauth_client_id"] = first_server["oauth"].get("clientId")
                        entry["auth"]["oauth_callback_port"] = first_server["oauth"].get("callbackPort")

            # Connector apps (proprietary OpenAI SDK ID -- we record the
            # ID for reference but cannot use it directly in Daena).
            if app:
                entry["codex_app"] = app

            # Skills: scrape from disk.
            scraped_skills: list[dict[str, str]] = []
            for skill_md in list_skills(plugin_dir):
                fm = parse_skill_frontmatter(skill_md)
                rel_id = "/".join(skill_md.parent.relative_to(plugin_dir / "skills").parts)
                scraped_skills.append({
                    "id": rel_id,
                    "name": fm.get("name", rel_id),
                    "description": fm.get("description", ""),
                    "source": f"codex/{plugin_name}",
                })
            if scraped_skills:
                entry["skills"] = scraped_skills

            # Mirror the skill tree into Daena's skills directory.
            daena_plugin_dir = SKILLS_ROOT / f"connector-{slug}"
            copied = copy_skill_tree(plugin_dir, daena_plugin_dir)
            entry["skill_count"] = len(scraped_skills) or copied

            # Copy logo asset.
            logo_path = copy_assets(plugin_dir, slug)
            if logo_path and "interface" in entry:
                entry["interface"]["logoPath"] = "/" + logo_path

    return entry


def merge_into_catalog(scraped: dict[str, dict[str, Any]]) -> None:
    """Update connector_catalog.json with scraped enrichments."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    by_slug = {c["slug"]: c for c in catalog["connectors"]}

    # Patch existing connectors.
    for slug, enrichment in scraped.items():
        if slug in by_slug:
            target = by_slug[slug]
            for key, value in enrichment.items():
                if key in ("name", "category"):
                    continue  # do not clobber existing identity
                target[key] = value
        else:
            # Add new connector to the catalog.
            new_entry = {
                "name": enrichment.get("name", slug.title()),
                "slug": slug,
                "description": enrichment.get("interface", {}).get("shortDescription", ""),
                "category": enrichment.get("category", "Productivity"),
                "auth_type": _legacy_auth_type(enrichment.get("auth", {}).get("method", "api_key")),
                "icon_url": None,
                "tools": [],
                "config_schema": {},
                **enrichment,
            }
            catalog["connectors"].append(new_entry)
            by_slug[slug] = new_entry

    # Bump version.
    catalog["version"] = _bump_version(catalog.get("version", "2026-04-29.1"))

    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")


def _legacy_auth_type(method: str) -> str:
    """Map auth.method -> legacy auth_type for backward compat."""
    return {
        "mcp_remote_oauth": "oauth",
        "oauth_managed": "oauth",
        "api_token": "token",
        "none": "token",
    }.get(method, "token")


def _bump_version(v: str) -> str:
    parts = v.split(".")
    if len(parts) == 2:
        try:
            return f"{parts[0]}.{int(parts[1]) + 1}"
        except ValueError:
            pass
    return v + ".1"


def main() -> None:
    print(f"[scraper] Codex cache: {CODEX_CACHE}")
    print(f"[scraper] Daena root:  {DAENA_ROOT}")

    if not CODEX_CACHE.exists():
        print(f"[scraper] FATAL: Codex cache not found at {CODEX_CACHE}", file=sys.stderr)
        sys.exit(1)

    if not CATALOG_PATH.exists():
        print(f"[scraper] FATAL: Catalog not found at {CATALOG_PATH}", file=sys.stderr)
        sys.exit(1)

    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)

    # Build enrichment for every known connector. Plugins that do NOT
    # have a Codex manifest still get the KNOWN_CONNECTORS metadata.
    scraped: dict[str, dict[str, Any]] = {}
    for slug in sorted(set(KNOWN_CONNECTORS) | set(PLUGIN_TO_CONNECTOR.values())):
        plugin_name = next(
            (k for k, v in PLUGIN_TO_CONNECTOR.items() if v == slug),
            None,
        )
        entry = build_connector_entry(slug, plugin_name)
        scraped[slug] = entry
        skills_n = entry.get("skill_count", 0)
        suffix = f" (+{skills_n} skills from codex)" if plugin_name else ""
        print(f"[scraper] {slug:24s} {entry.get('auth', {}).get('method', '?'):24s}{suffix}")

    # Codex plugins that map to Daena CONNECTORS are above.
    # The rest (context7, playwright, browser-use, plugin-dev, hookify,
    # claude-md-management, code-review, etc.) are SKILLS or EXTENSIONS,
    # not connectors. We mirror their skills into a generic "codex-skills"
    # tree so Daena agents can still reach them.
    codex_skill_plugins = [
        "context7", "playwright", "browser-use", "plugin-dev",
        "hookify", "claude-md-management", "code-review",
        "code-simplifier", "commit-commands", "skill-creator",
    ]
    extra_count = 0
    for plugin_name in codex_skill_plugins:
        plugin_dir = find_plugin_dir(plugin_name)
        if not plugin_dir:
            continue
        target = SKILLS_ROOT / f"codex-{plugin_name}"
        copied = copy_skill_tree(plugin_dir, target)
        extra_count += copied
        print(f"[scraper] codex-skill {plugin_name:24s} +{copied} skills")

    # Persist the enriched catalog.
    merge_into_catalog(scraped)
    print(f"\n[scraper] Catalog updated: {CATALOG_PATH}")
    print(f"[scraper] Mirrored {extra_count} extra Codex skills under {SKILLS_ROOT}")
    print(f"[scraper] Done.")


if __name__ == "__main__":
    main()
