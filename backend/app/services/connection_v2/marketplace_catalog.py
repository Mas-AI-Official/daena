"""Curated connection marketplace catalog.

PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): Daena's Connections page
needs a "what's available" surface that does NOT depend on the operator
having pre-configured every connector. The V2 truth surface (in
``seeders.py`` + ``probes/``) tells us what is actually working;
this module tells us what we know how to support.

The catalog is hand-curated, source-tree-versioned, and reviewed in
PR. No external fetch, no auto-install, no secret reads. Every entry
captures install metadata + auth requirements so the UI can render
honest lifecycle states (Available -> Installed -> Configured ->
Reachable -> Callable -> Enabled), each one mapped onto the V2 truth
ladder.

See ``docs/Ultraview/CONNECTIONS_MARKETPLACE_RESEARCH.md`` for the
sourcing decisions behind individual entries.

Honesty contract (per project Rule 17):
* ``required_env_vars`` is NAMES ONLY. Reading the value is forbidden.
* ``install_method`` may be ``"coming-soon"``; the UI surfaces a
  Setup Guide CTA, never a fake Install button.
* ``probe_type`` aligns with the V2 probe registry. Probes that have
  not landed yet return ``probe_unavailable`` -- the UI shows
  "Probe not yet implemented" instead of fake-green.
* ``official_url`` is required so the operator can verify the source
  before configuring credentials.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


# ──────────────────────────────────────────────────────────────────
# Type aliases
# ──────────────────────────────────────────────────────────────────


CatalogKind = Literal[
    "mcp_server",      # Stdio/HTTP MCP server
    "oauth_app",       # OAuth 2.0 app integration
    "browser_tool",    # Browser automation (Playwright, DevTools, ...)
    "computer_use",    # Full desktop / OS control
    "cli_runtime",     # Local CLI (claude, codex, gemini, ...)
    "api_provider",    # Cloud LLM provider (OpenAI, Anthropic, ...)
    "local_model",     # Local model endpoint (Ollama, vLLM, ...)
    "skill_pack",      # Capability bundle, not directly callable
]

CatalogCategory = Literal[
    "filesystem",
    "browser",
    "computer_use",
    "code_platform",
    "communication",
    "productivity",
    "design",
    "data_storage",
    "payment",
    "research",
    "local_llm",
    "ai_provider",
    "dev_tools",
    "cli_runtime",
]

InstallMethod = Literal[
    "npm",            # `npx -y <package>` install
    "docker",         # `docker run <image>` install
    "local",          # Already on the host, just import
    "manual",         # Operator follows a setup guide
    "subscription",   # Auth via vendor's CLI
    "built-in",       # Ships with Daena, no install
    "coming-soon",    # Catalog stub; install plan not yet implemented
]

AuthType = Literal[
    "none",
    "oauth",
    "api_key",
    "token",
    "subscription",
]

ProbeType = Literal[
    "mcp_initialize",
    "oauth_token",
    "http_get",
    "binary_check",
    "skill_pack_only",
    "none",
]

RiskLevel = Literal["low", "medium", "high"]

CompatibleOs = Literal["windows", "wsl", "docker", "mac", "linux"]


# ──────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CatalogEntry:
    """One marketplace entry. Immutable; reviewed in PR."""

    # Identity
    id: str                                 # stable, e.g. "mcp-github"
    display_name: str
    vendor: str                             # e.g. "Anthropic", "Google", "Daena"
    category: CatalogCategory
    kind: CatalogKind

    # Description
    short_description: str
    capabilities: tuple[str, ...] = ()      # human strings, e.g. "Read repo files"

    # Install plan (NEVER executed by Daena automatically)
    install_method: InstallMethod = "coming-soon"
    command_template: str = ""              # e.g. "npx -y @modelcontextprotocol/server-github"
    required_env_vars: tuple[str, ...] = () # NAMES only. Never values.
    auth_type: AuthType = "none"

    # Reference + safety
    official_url: str = ""
    risk_level: RiskLevel = "medium"
    probe_type: ProbeType = "none"
    compatible_os: tuple[CompatibleOs, ...] = ("windows", "wsl", "mac", "linux")

    # V2 row matcher: optional substring/exact slug pattern that maps
    # to a V2 row's slug (lowercase, hyphenated). The matcher service
    # uses this to merge catalog metadata with live truth state.
    matches_v2_slug: str = ""

    # Notes shown in the install drawer (kept short; no marketing copy)
    setup_notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert tuples to lists for JSON serialization.
        for key in (
            "capabilities",
            "required_env_vars",
            "compatible_os",
        ):
            d[key] = list(d[key])
        return d


@dataclass(frozen=True)
class CategoryDefinition:
    """Display metadata for a category. Drives the UI sidebar."""

    id: CatalogCategory
    display_name: str
    short_description: str

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────
# Categories (display order)
# ──────────────────────────────────────────────────────────────────


CATEGORIES: tuple[CategoryDefinition, ...] = (
    CategoryDefinition(
        id="cli_runtime",
        display_name="CLI Runtimes",
        short_description="Subscription-backed AI CLIs (Claude Code, Codex, Gemini)",
    ),
    CategoryDefinition(
        id="ai_provider",
        display_name="AI Providers",
        short_description="Cloud LLM API providers (OpenAI, Anthropic, Google, ...)",
    ),
    CategoryDefinition(
        id="local_llm",
        display_name="Local LLM Endpoints",
        short_description="Ollama, vLLM, llama-server -- run models on your hardware",
    ),
    CategoryDefinition(
        id="browser",
        display_name="Browser Tools",
        short_description="Playwright + DevTools MCPs for web automation",
    ),
    CategoryDefinition(
        id="computer_use",
        display_name="Computer Use",
        short_description="Desktop / OS automation with explicit operator approval",
    ),
    CategoryDefinition(
        id="filesystem",
        display_name="Filesystem",
        short_description="Read / write local files via permissioned MCP servers",
    ),
    CategoryDefinition(
        id="code_platform",
        display_name="Code Platforms",
        short_description="GitHub, GitLab, Cloudflare, Sentry, Vercel, Netlify",
    ),
    CategoryDefinition(
        id="communication",
        display_name="Communication",
        short_description="Slack, Discord -- messaging and channel automation",
    ),
    CategoryDefinition(
        id="productivity",
        display_name="Productivity",
        short_description="Notion, Linear, Calendar, Drive, Gmail",
    ),
    CategoryDefinition(
        id="design",
        display_name="Design",
        short_description="Figma, Canva -- design-tool integrations",
    ),
    CategoryDefinition(
        id="data_storage",
        display_name="Data + Storage",
        short_description="Postgres, SQLite, MongoDB, Redis -- DB MCP servers",
    ),
    CategoryDefinition(
        id="payment",
        display_name="Payment",
        short_description="Stripe, Shopify -- billing + commerce integrations",
    ),
    CategoryDefinition(
        id="research",
        display_name="Research",
        short_description="Perplexity, scholarly search, evidence synthesis",
    ),
    CategoryDefinition(
        id="dev_tools",
        display_name="Dev Tools",
        short_description="Fetch, time, memory, sequentialthinking, git",
    ),
)


# ──────────────────────────────────────────────────────────────────
# Catalog entries
# ──────────────────────────────────────────────────────────────────


def _entry(**kwargs) -> CatalogEntry:
    """Builder helper -- tuple-conversion for list inputs."""
    for key in ("capabilities", "required_env_vars", "compatible_os"):
        if key in kwargs and isinstance(kwargs[key], list):
            kwargs[key] = tuple(kwargs[key])
    return CatalogEntry(**kwargs)


# CLI Runtimes (subscription-backed CLIs Daena can shell out to)
_CLI_RUNTIMES: tuple[CatalogEntry, ...] = (
    _entry(
        id="cli-claude-code",
        display_name="Claude Code",
        vendor="Anthropic",
        category="cli_runtime",
        kind="cli_runtime",
        short_description="Anthropic's official CLI for Claude. Uses Pro / Max subscription auth.",
        capabilities=(
            "Multi-turn coding sessions",
            "Subagents + extended thinking",
            "Native MCP client",
        ),
        install_method="local",
        command_template="claude --bare",
        required_env_vars=(),
        auth_type="subscription",
        official_url="https://docs.anthropic.com/claude-code",
        risk_level="medium",
        probe_type="binary_check",
        matches_v2_slug="cli-claude_code",
        setup_notes="Install: npm install -g @anthropic-ai/claude-code. Auth: claude login.",
    ),
    _entry(
        id="cli-codex",
        display_name="Codex CLI",
        vendor="OpenAI",
        category="cli_runtime",
        kind="cli_runtime",
        short_description="OpenAI Codex CLI. Subscription auth via ChatGPT Plus / Pro.",
        capabilities=(
            "Code generation",
            "Async background runs",
            "Native MCP client",
        ),
        install_method="local",
        command_template="codex --bare",
        required_env_vars=(),
        auth_type="subscription",
        official_url="https://github.com/openai/codex",
        risk_level="medium",
        probe_type="binary_check",
        matches_v2_slug="cli-codex",
        setup_notes="Install: see official Codex CLI repo. Auth: codex login.",
    ),
    _entry(
        id="cli-gemini",
        display_name="Gemini CLI",
        vendor="Google",
        category="cli_runtime",
        kind="cli_runtime",
        short_description="Google's Gemini CLI. Free tier available.",
        capabilities=(
            "Multi-modal queries",
            "Web grounding",
            "Native MCP client",
        ),
        install_method="local",
        command_template="gemini --bare",
        required_env_vars=(),
        auth_type="subscription",
        official_url="https://github.com/google-gemini/gemini-cli",
        risk_level="medium",
        probe_type="binary_check",
        matches_v2_slug="cli-gemini_cli",
        setup_notes="Install: npm install -g @google/gemini-cli. Auth: gemini auth.",
    ),
)


# Cloud AI providers (API-key auth)
_AI_PROVIDERS: tuple[CatalogEntry, ...] = (
    _entry(
        id="provider-anthropic",
        display_name="Anthropic API",
        vendor="Anthropic",
        category="ai_provider",
        kind="api_provider",
        short_description="Direct API access to Claude models.",
        capabilities=("Chat completion", "Vision", "Tool use", "Extended thinking"),
        install_method="manual",
        command_template="",
        required_env_vars=("ANTHROPIC_API_KEY",),
        auth_type="api_key",
        official_url="https://docs.anthropic.com",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="anthropic",
        setup_notes="Add ANTHROPIC_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-openai",
        display_name="OpenAI API",
        vendor="OpenAI",
        category="ai_provider",
        kind="api_provider",
        short_description="GPT-4, GPT-5, o1, o3 model access via API key.",
        capabilities=("Chat completion", "Function calling", "Vision", "Reasoning models"),
        install_method="manual",
        command_template="",
        required_env_vars=("OPENAI_API_KEY",),
        auth_type="api_key",
        official_url="https://platform.openai.com/docs",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="openai",
        setup_notes="Add OPENAI_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-google-gemini",
        display_name="Google Gemini API",
        vendor="Google",
        category="ai_provider",
        kind="api_provider",
        short_description="Gemini 1.5 / 2.0 Pro + Flash via API key.",
        capabilities=("Multi-modal", "Long context", "Function calling"),
        install_method="manual",
        command_template="",
        required_env_vars=("GEMINI_API_KEY",),
        auth_type="api_key",
        official_url="https://ai.google.dev",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="gemini",
        setup_notes="Add GEMINI_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-perplexity",
        display_name="Perplexity API",
        vendor="Perplexity",
        category="ai_provider",
        kind="api_provider",
        short_description="Online research-grade chat with web grounding.",
        capabilities=("Live web search", "Citations", "Sonar models"),
        install_method="manual",
        command_template="",
        required_env_vars=("PERPLEXITY_API_KEY",),
        auth_type="api_key",
        official_url="https://docs.perplexity.ai",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="perplexity",
        setup_notes="Add PERPLEXITY_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-groq",
        display_name="Groq API",
        vendor="Groq",
        category="ai_provider",
        kind="api_provider",
        short_description="Ultra-low-latency Llama / Mixtral inference.",
        capabilities=("Fast inference", "Function calling"),
        install_method="manual",
        command_template="",
        required_env_vars=("GROQ_API_KEY",),
        auth_type="api_key",
        official_url="https://console.groq.com/docs",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="groq",
        setup_notes="Add GROQ_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-openrouter",
        display_name="OpenRouter",
        vendor="OpenRouter",
        category="ai_provider",
        kind="api_provider",
        short_description="Unified gateway to 100+ models with one key.",
        capabilities=("Model marketplace", "Pay-per-token", "Routing"),
        install_method="manual",
        command_template="",
        required_env_vars=("OPENROUTER_API_KEY",),
        auth_type="api_key",
        official_url="https://openrouter.ai/docs",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="openrouter",
        setup_notes="Add OPENROUTER_API_KEY in Settings -> API Keys.",
    ),
    _entry(
        id="provider-together",
        display_name="Together AI",
        vendor="Together",
        category="ai_provider",
        kind="api_provider",
        short_description="OSS LLM hosting + fine-tuning.",
        capabilities=("OSS models", "Fine-tuning", "Embeddings"),
        install_method="manual",
        command_template="",
        required_env_vars=("TOGETHER_API_KEY",),
        auth_type="api_key",
        official_url="https://docs.together.ai",
        risk_level="low",
        probe_type="http_get",
        matches_v2_slug="together",
        setup_notes="Add TOGETHER_API_KEY in Settings -> API Keys.",
    ),
)


# Local LLM endpoints
_LOCAL_LLMS: tuple[CatalogEntry, ...] = (
    _entry(
        id="local-ollama",
        display_name="Ollama",
        vendor="Ollama",
        category="local_llm",
        kind="local_model",
        short_description="Run open-weight LLMs locally over an OpenAI-compatible API.",
        capabilities=("Local inference", "Model pull / push", "Many model families"),
        install_method="manual",
        command_template="",
        required_env_vars=("OLLAMA_BASE_URL",),
        auth_type="none",
        official_url="https://ollama.com",
        risk_level="low",
        probe_type="http_get",
        compatible_os=("windows", "wsl", "mac", "linux", "docker"),
        matches_v2_slug="local-ollama",
        setup_notes=(
            "Install Ollama from ollama.com. Daena reads OLLAMA_BASE_URL "
            "(default http://127.0.0.1:11434). Note: Daena prefers llama-server."
        ),
    ),
    _entry(
        id="local-vllm",
        display_name="vLLM / llama-server",
        vendor="Daena-default",
        category="local_llm",
        kind="local_model",
        short_description="OpenAI-compatible local server (llama.cpp, vLLM, LM Studio).",
        capabilities=(
            "OpenAI-compatible API",
            "GGUF / safetensors",
            "Hot-swap models",
        ),
        install_method="manual",
        command_template="",
        required_env_vars=("VLLM_BASE_URL",),
        auth_type="none",
        official_url="https://github.com/ggerganov/llama.cpp",
        risk_level="low",
        probe_type="http_get",
        compatible_os=("windows", "wsl", "mac", "linux", "docker"),
        matches_v2_slug="local-vllm",
        setup_notes=(
            "Daena's preferred local runtime. Launch via "
            "backend/start-llama-server.ps1 or any vLLM / LM Studio "
            "OpenAI-compatible endpoint."
        ),
    ),
)


# Filesystem MCP servers
_FILESYSTEM: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-filesystem",
        display_name="Filesystem",
        vendor="Anthropic",
        category="filesystem",
        kind="mcp_server",
        short_description="Permissioned filesystem read / write inside operator-allowed roots.",
        capabilities=(
            "List directory",
            "Read file",
            "Write file",
            "Move file",
            "Search files",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-filesystem",
        setup_notes=(
            "Pass an allowed root directory as the last arg. The server "
            "refuses operations outside that root."
        ),
    ),
)


# Browser MCP servers
_BROWSER: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-playwright",
        display_name="Playwright",
        vendor="Microsoft",
        category="browser",
        kind="browser_tool",
        short_description="Browser automation via Playwright. Open, click, fill, observe.",
        capabilities=(
            "Navigate",
            "Click + type",
            "Take screenshot",
            "Read network requests",
            "Wait for selector",
        ),
        install_method="npm",
        command_template="npx -y @microsoft/playwright-mcp",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/microsoft/playwright-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-playwright",
        setup_notes=(
            "Browser tools open pages and click elements. Daena does not "
            "bypass anti-bot systems and never claims stealth or evasion. "
            "Browsers run in your local environment with explicit consent."
        ),
    ),
    _entry(
        id="mcp-chrome-devtools",
        display_name="Chrome DevTools",
        vendor="Google",
        category="browser",
        kind="browser_tool",
        short_description="Talk to Chrome via DevTools protocol -- inspect, profile, snapshot.",
        capabilities=(
            "DOM snapshot",
            "Network inspection",
            "Console messages",
            "Performance trace",
        ),
        install_method="npm",
        command_template="npx -y chrome-devtools-mcp",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/ChromeDevTools/chrome-devtools-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-chrome-devtools",
        setup_notes=(
            "Requires Chrome / Chromium running with --remote-debugging-port. "
            "Best for inspect-and-observe workflows."
        ),
    ),
    _entry(
        id="mcp-browserbase",
        display_name="Browserbase",
        vendor="Browserbase",
        category="browser",
        kind="browser_tool",
        short_description="Cloud-hosted browser sessions (paid). Setup guide only.",
        capabilities=(
            "Cloud browser",
            "Session persistence",
            "Geolocated proxies",
        ),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"),
        auth_type="api_key",
        official_url="https://www.browserbase.com",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes=(
            "Cloud browser provider. Daena does NOT enable anti-bot evasion; "
            "sign up at browserbase.com and follow their install steps."
        ),
    ),
)


# Computer-use entries (high-risk, opt-in)
_COMPUTER_USE: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-desktop-commander",
        display_name="Desktop Commander",
        vendor="Wonderwhy-er",
        category="computer_use",
        kind="computer_use",
        short_description="Full desktop control: terminal, processes, files. High risk.",
        capabilities=(
            "Run shell commands",
            "Manage processes",
            "Move + delete files",
            "Read system state",
        ),
        install_method="npm",
        command_template="npx -y @wonderwhy-er/desktop-commander",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/wonderwhy-er/DesktopCommanderMCP",
        risk_level="high",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-desktop-commander",
        setup_notes=(
            "Desktop Commander grants the model control over your terminal "
            "and filesystem. Enable only with full operator awareness; "
            "Asset Shield + governance gates still apply."
        ),
    ),
    _entry(
        id="mcp-windows",
        display_name="Windows MCP",
        vendor="Community",
        category="computer_use",
        kind="computer_use",
        short_description="Windows-specific automation (PowerShell, registry, services).",
        capabilities=(
            "Run PowerShell",
            "Inspect services",
            "Manage scheduled tasks",
        ),
        install_method="manual",
        command_template="",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/CursorTouch/Windows-MCP",
        risk_level="high",
        probe_type="mcp_initialize",
        compatible_os=("windows",),
        matches_v2_slug="mcp-windows-mcp",
        setup_notes="Windows-only. Follow the linked install guide manually.",
    ),
)


# Code platform MCPs
_CODE_PLATFORM: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-github",
        display_name="GitHub",
        vendor="Anthropic",
        category="code_platform",
        kind="mcp_server",
        short_description="Triage PRs, issues, search repos via GitHub MCP.",
        capabilities=(
            "Search repositories",
            "List + create issues",
            "Read file contents",
            "Create pull requests",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-github",
        required_env_vars=("GITHUB_PERSONAL_ACCESS_TOKEN",),
        auth_type="token",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/github",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-github",
        setup_notes=(
            "Create a fine-grained PAT at github.com/settings/personal-access-tokens. "
            "Scope to specific repos. Set GITHUB_PERSONAL_ACCESS_TOKEN in env."
        ),
    ),
    _entry(
        id="mcp-cloudflare",
        display_name="Cloudflare",
        vendor="Cloudflare",
        category="code_platform",
        kind="mcp_server",
        short_description="Cloudflare platform guidance + DNS / Workers / R2 admin.",
        capabilities=(
            "List zones",
            "Update DNS",
            "Deploy Workers",
            "Inspect R2 buckets",
        ),
        install_method="npm",
        command_template="npx -y @cloudflare/mcp-server-cloudflare",
        required_env_vars=("CLOUDFLARE_API_TOKEN",),
        auth_type="token",
        official_url="https://github.com/cloudflare/mcp-server-cloudflare",
        risk_level="high",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-cloudflare",
        setup_notes=(
            "Create a scoped API token at dash.cloudflare.com/profile/api-tokens. "
            "Avoid Global API Key tokens; use scoped tokens only."
        ),
    ),
    _entry(
        id="mcp-sentry",
        display_name="Sentry",
        vendor="Sentry",
        category="code_platform",
        kind="mcp_server",
        short_description="Inspect Sentry issues, events, and releases.",
        capabilities=(
            "List recent issues",
            "Get event detail",
            "Search events",
        ),
        install_method="npm",
        command_template="npx -y @sentry/mcp-server",
        required_env_vars=("SENTRY_AUTH_TOKEN", "SENTRY_ORG"),
        auth_type="token",
        official_url="https://docs.sentry.io",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-sentry",
        setup_notes="Create an Internal Integration token in your Sentry org settings.",
    ),
    _entry(
        id="mcp-vercel",
        display_name="Vercel",
        vendor="Vercel",
        category="code_platform",
        kind="mcp_server",
        short_description="Deploy + inspect Vercel projects.",
        capabilities=("List projects", "Trigger deploy", "Read logs", "Manage env vars"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("VERCEL_TOKEN",),
        auth_type="token",
        official_url="https://vercel.com/docs",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Vercel official MCP not yet GA. Use the V1 plugin until then.",
    ),
    _entry(
        id="mcp-netlify",
        display_name="Netlify",
        vendor="Netlify",
        category="code_platform",
        kind="mcp_server",
        short_description="Deploy + inspect Netlify sites.",
        capabilities=("List sites", "Trigger deploy", "Manage env vars"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("NETLIFY_AUTH_TOKEN",),
        auth_type="token",
        official_url="https://docs.netlify.com",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Netlify MCP coming soon. Use the V1 plugin for now.",
    ),
)


# Communication MCPs
_COMMUNICATION: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-slack",
        display_name="Slack",
        vendor="Anthropic",
        category="communication",
        kind="mcp_server",
        short_description="Read channels, search messages, post to threads.",
        capabilities=(
            "Search messages",
            "Send message to channel",
            "List channels",
            "Read channel history",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-slack",
        required_env_vars=("SLACK_BOT_TOKEN", "SLACK_TEAM_ID"),
        auth_type="token",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-slack",
        setup_notes=(
            "Create a Slack app at api.slack.com/apps. Add bot scopes: "
            "channels:read, chat:write, channels:history. Install to workspace."
        ),
    ),
)


# Productivity MCPs
_PRODUCTIVITY: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-notion",
        display_name="Notion",
        vendor="Anthropic",
        category="productivity",
        kind="mcp_server",
        short_description="Search + read + write Notion pages and databases.",
        capabilities=(
            "Search pages",
            "Read page",
            "Create page",
            "Query database",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-notion",
        required_env_vars=("NOTION_API_KEY",),
        auth_type="token",
        official_url="https://developers.notion.com",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-notion",
        setup_notes=(
            "Create an Internal Integration at notion.so/my-integrations. "
            "Share the relevant pages / databases with the integration."
        ),
    ),
    _entry(
        id="mcp-linear",
        display_name="Linear",
        vendor="Linear community",
        category="productivity",
        kind="mcp_server",
        short_description="Find + create + update Linear issues.",
        capabilities=("List issues", "Create issue", "Update issue", "List projects"),
        install_method="npm",
        command_template="npx -y mcp-linear",
        required_env_vars=("LINEAR_API_KEY",),
        auth_type="api_key",
        official_url="https://developers.linear.app",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-linear",
        setup_notes="Create a personal API key at linear.app/settings/api.",
    ),
    _entry(
        id="mcp-google-drive",
        display_name="Google Drive",
        vendor="Anthropic",
        category="productivity",
        kind="mcp_server",
        short_description="Search + read Google Drive files (read-only by default).",
        capabilities=("Search files", "Read file content", "List folders"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-gdrive",
        required_env_vars=("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/gdrive",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-gdrive",
        setup_notes=(
            "Create OAuth client credentials in Google Cloud Console. "
            "Or connect via Apps -> Google Drive (managed OAuth)."
        ),
    ),
)


# Design MCPs
_DESIGN: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-figma",
        display_name="Figma",
        vendor="Figma",
        category="design",
        kind="mcp_server",
        short_description="Design-to-code workflows via Figma's developer API.",
        capabilities=("Get file tree", "List components", "Export assets"),
        install_method="npm",
        command_template="npx -y figma-mcp",
        required_env_vars=("FIGMA_PERSONAL_ACCESS_TOKEN",),
        auth_type="token",
        official_url="https://www.figma.com/developers/api",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-figma",
        setup_notes="Generate a personal access token at figma.com/settings/personal-access-tokens.",
    ),
)


# Database MCPs
_DATA_STORAGE: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-postgres",
        display_name="Postgres",
        vendor="Anthropic",
        category="data_storage",
        kind="mcp_server",
        short_description="Read-only Postgres access for schema + query exploration.",
        capabilities=("List tables", "Describe schema", "Run SELECT", "EXPLAIN"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-postgres <DATABASE_URL>",
        required_env_vars=("POSTGRES_URL",),
        auth_type="api_key",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-postgres",
        setup_notes=(
            "Pass a connection string with read-only credentials. "
            "Use a dedicated read-only role; do NOT pass admin creds."
        ),
    ),
    _entry(
        id="mcp-sqlite",
        display_name="SQLite",
        vendor="Anthropic",
        category="data_storage",
        kind="mcp_server",
        short_description="Read + write a local SQLite database file.",
        capabilities=("List tables", "Run query", "Schema inspection"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-sqlite <PATH>",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-sqlite",
        setup_notes="Pass the SQLite file path as last arg.",
    ),
    _entry(
        id="mcp-mongodb",
        display_name="MongoDB",
        vendor="Community",
        category="data_storage",
        kind="mcp_server",
        short_description="Query + inspect MongoDB collections.",
        capabilities=("List collections", "Query documents", "Inspect indexes"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("MONGODB_URI",),
        auth_type="api_key",
        official_url="https://www.mongodb.com",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Community MongoDB MCP. Verify before use.",
    ),
    _entry(
        id="mcp-redis",
        display_name="Redis",
        vendor="Community",
        category="data_storage",
        kind="mcp_server",
        short_description="Inspect Redis keys + execute read commands.",
        capabilities=("Get key", "List keys", "Inspect TTL"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("REDIS_URL",),
        auth_type="api_key",
        official_url="https://redis.io",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Community Redis MCP. Verify before use.",
    ),
)


# Payment MCPs
_PAYMENT: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-stripe",
        display_name="Stripe",
        vendor="Stripe",
        category="payment",
        kind="mcp_server",
        short_description="List charges + subscriptions, create invoices.",
        capabilities=("List charges", "List subscriptions", "Create invoice"),
        install_method="npm",
        command_template="npx -y @stripe/mcp-server",
        required_env_vars=("STRIPE_SECRET_KEY",),
        auth_type="api_key",
        official_url="https://docs.stripe.com",
        risk_level="high",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-stripe",
        setup_notes=(
            "Use a restricted API key (stripe.com/docs/keys#restricted). "
            "Default to read-only scopes; never paste live secret keys."
        ),
    ),
    _entry(
        id="mcp-shopify",
        display_name="Shopify",
        vendor="Shopify",
        category="payment",
        kind="mcp_server",
        short_description="Read products, orders, customers from Shopify.",
        capabilities=("List products", "List orders", "Inspect customers"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_SHOP_DOMAIN"),
        auth_type="token",
        official_url="https://shopify.dev",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Shopify MCP coming soon. Use Shopify Admin API directly for now.",
    ),
)


# Research MCPs
_RESEARCH: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-perplexity",
        display_name="Perplexity Search",
        vendor="Perplexity",
        category="research",
        kind="mcp_server",
        short_description="Web-grounded search returning citations.",
        capabilities=("Live web search", "Citations", "Sonar reasoning"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("PERPLEXITY_API_KEY",),
        auth_type="api_key",
        official_url="https://docs.perplexity.ai",
        risk_level="low",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Use the Perplexity API provider directly until MCP lands.",
    ),
)


# Dev tools MCPs
_DEV_TOOLS: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-fetch",
        display_name="Fetch",
        vendor="Anthropic",
        category="dev_tools",
        kind="mcp_server",
        short_description="HTTP GET to retrieve web content as markdown.",
        capabilities=("Fetch URL", "Markdown extraction"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-fetch",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-fetch",
        setup_notes="No setup required. Daena governance gates external HTTP egress.",
    ),
    _entry(
        id="mcp-brave-search",
        display_name="Brave Search",
        vendor="Anthropic",
        category="dev_tools",
        kind="mcp_server",
        short_description="Web search via Brave Search API.",
        capabilities=("Web search", "News search"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-brave-search",
        required_env_vars=("BRAVE_API_KEY",),
        auth_type="api_key",
        official_url="https://brave.com/search/api",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-brave-search",
        setup_notes="Get a free API key at api.search.brave.com.",
    ),
    _entry(
        id="mcp-time",
        display_name="Time",
        vendor="Anthropic",
        category="dev_tools",
        kind="mcp_server",
        short_description="Current time + timezone conversion.",
        capabilities=("Get current time", "Timezone conversion"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-time",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-time",
        setup_notes="No setup required.",
    ),
    _entry(
        id="mcp-git",
        display_name="Git",
        vendor="Anthropic",
        category="dev_tools",
        kind="mcp_server",
        short_description="Local git repo inspection (log, diff, blame).",
        capabilities=("Git log", "Git diff", "Git blame", "Show commit"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-git",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-git",
        setup_notes="Read-only by default; safe for repo exploration.",
    ),
    _entry(
        id="mcp-memory",
        display_name="Memory",
        vendor="Anthropic",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference knowledge-graph memory provider for MCP clients.",
        capabilities=("Add memory", "Query memory graph", "Cross-session recall"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-memory",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-memory",
        setup_notes="Daena's NBMF is the canonical memory; this MCP is for cross-tool sharing.",
    ),
)


# OAuth-backed Apps (the catalog mirrors oauth_service.OAUTH_PROVIDERS)
_OAUTH_APPS: tuple[CatalogEntry, ...] = (
    _entry(
        id="app-gmail",
        display_name="Gmail",
        vendor="Google",
        category="productivity",
        kind="oauth_app",
        short_description="Send + search + draft emails via Gmail OAuth.",
        capabilities=("Search emails", "Read email", "Send email", "Create draft"),
        install_method="local",
        command_template="",
        required_env_vars=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://developers.google.com/gmail/api",
        risk_level="medium",
        probe_type="oauth_token",
        matches_v2_slug="oauth-gmail",
        setup_notes=(
            "Configure GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in Settings, "
            "then use the OAuth flow to grant Gmail access."
        ),
    ),
    _entry(
        id="app-google-calendar",
        display_name="Google Calendar",
        vendor="Google",
        category="productivity",
        kind="oauth_app",
        short_description="Manage events + find free time via Calendar OAuth.",
        capabilities=("List events", "Create event", "Update event", "Find free time"),
        install_method="local",
        command_template="",
        required_env_vars=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://developers.google.com/calendar",
        risk_level="medium",
        probe_type="oauth_token",
        matches_v2_slug="oauth-google-calendar",
        setup_notes="Reuses GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET from Gmail.",
    ),
    _entry(
        id="app-google-drive",
        display_name="Google Drive",
        vendor="Google",
        category="productivity",
        kind="oauth_app",
        short_description="Search + read Drive files via OAuth.",
        capabilities=("Search files", "Read file", "List folders", "Upload file"),
        install_method="local",
        command_template="",
        required_env_vars=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://developers.google.com/drive",
        risk_level="medium",
        probe_type="oauth_token",
        matches_v2_slug="oauth-google-drive",
        setup_notes="Reuses GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET from Gmail.",
    ),
    _entry(
        id="app-github",
        display_name="GitHub (OAuth)",
        vendor="GitHub",
        category="code_platform",
        kind="oauth_app",
        short_description="OAuth-managed GitHub access (alternative to PAT).",
        capabilities=("Repos", "Issues", "PRs", "User"),
        install_method="local",
        command_template="",
        required_env_vars=("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://docs.github.com/en/apps/oauth-apps",
        risk_level="medium",
        probe_type="oauth_token",
        matches_v2_slug="oauth-github",
        setup_notes=(
            "Create an OAuth App at github.com/settings/developers. "
            "Set the callback URL to your Daena instance's OAuth callback."
        ),
    ),
    _entry(
        id="app-figma",
        display_name="Figma (OAuth)",
        vendor="Figma",
        category="design",
        kind="oauth_app",
        short_description="OAuth-managed Figma file access.",
        capabilities=("Read files", "Read file variables"),
        install_method="local",
        command_template="",
        required_env_vars=("FIGMA_CLIENT_ID", "FIGMA_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://www.figma.com/developers/api",
        risk_level="low",
        probe_type="oauth_token",
        matches_v2_slug="oauth-figma",
        setup_notes="Create an OAuth app at figma.com/developers/apps.",
    ),
    _entry(
        id="app-slack",
        display_name="Slack (OAuth)",
        vendor="Slack",
        category="communication",
        kind="oauth_app",
        short_description="OAuth-managed Slack workspace access.",
        capabilities=("Channels", "Messages", "Users"),
        install_method="local",
        command_template="",
        required_env_vars=("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://api.slack.com/apps",
        risk_level="medium",
        probe_type="oauth_token",
        matches_v2_slug="oauth-slack",
        setup_notes="Create a Slack app, add the OAuth callback URL, install to a workspace.",
    ),
    _entry(
        id="app-canva",
        display_name="Canva",
        vendor="Canva",
        category="design",
        kind="oauth_app",
        short_description="Read Canva designs + content via OAuth.",
        capabilities=("Read designs", "Read design metadata"),
        install_method="local",
        command_template="",
        required_env_vars=("CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://www.canva.dev/docs/connect",
        risk_level="low",
        probe_type="oauth_token",
        matches_v2_slug="oauth-canva",
        setup_notes="Create an OAuth app via the Canva developer portal.",
    ),
    _entry(
        id="app-notion-oauth",
        display_name="Notion (OAuth)",
        vendor="Notion",
        category="productivity",
        kind="oauth_app",
        short_description="OAuth-managed Notion workspace access.",
        capabilities=("Read pages", "Search", "Update pages"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://developers.notion.com/docs/authorization",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="OAuth flow not yet wired in oauth_service. Use Notion MCP with API key for now.",
    ),
    _entry(
        id="app-stripe-oauth",
        display_name="Stripe (Connect)",
        vendor="Stripe",
        category="payment",
        kind="oauth_app",
        short_description="Stripe Connect OAuth (multi-account).",
        capabilities=("Read account data", "Process events"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("STRIPE_CONNECT_CLIENT_ID",),
        auth_type="oauth",
        official_url="https://stripe.com/docs/connect",
        risk_level="high",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="Stripe Connect OAuth not yet wired. Use Stripe MCP with API key for now.",
    ),
    _entry(
        id="app-cloudflare-oauth",
        display_name="Cloudflare (OAuth)",
        vendor="Cloudflare",
        category="code_platform",
        kind="oauth_app",
        short_description="OAuth-managed Cloudflare account access.",
        capabilities=("Zones", "Workers", "DNS"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("CLOUDFLARE_CLIENT_ID", "CLOUDFLARE_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://developers.cloudflare.com",
        risk_level="high",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="OAuth not yet wired. Use Cloudflare MCP with scoped API token for now.",
    ),
    _entry(
        id="app-sentry-oauth",
        display_name="Sentry (OAuth)",
        vendor="Sentry",
        category="code_platform",
        kind="oauth_app",
        short_description="OAuth-managed Sentry org access.",
        capabilities=("Issues", "Events", "Releases"),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("SENTRY_CLIENT_ID", "SENTRY_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://docs.sentry.io/api",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes="OAuth not yet wired. Use Sentry MCP with internal-integration token for now.",
    ),
)


# ──────────────────────────────────────────────────────────────────
# Aggregate catalog
# ──────────────────────────────────────────────────────────────────


CATALOG: tuple[CatalogEntry, ...] = (
    *_CLI_RUNTIMES,
    *_AI_PROVIDERS,
    *_LOCAL_LLMS,
    *_BROWSER,
    *_COMPUTER_USE,
    *_FILESYSTEM,
    *_CODE_PLATFORM,
    *_COMMUNICATION,
    *_PRODUCTIVITY,
    *_DESIGN,
    *_DATA_STORAGE,
    *_PAYMENT,
    *_RESEARCH,
    *_DEV_TOOLS,
    *_OAUTH_APPS,
)


# Quick-lookup map (id -> entry)
CATALOG_BY_ID: dict[str, CatalogEntry] = {e.id: e for e in CATALOG}


# ──────────────────────────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────────────────────────


def list_catalog() -> list[dict]:
    """Return the full catalog as a JSON-friendly list."""
    return [e.to_dict() for e in CATALOG]


def list_categories() -> list[dict]:
    """Return display metadata for every catalog category."""
    return [c.to_dict() for c in CATEGORIES]


def get_entry(entry_id: str) -> CatalogEntry | None:
    return CATALOG_BY_ID.get(entry_id)


def entries_by_category(category: str) -> list[CatalogEntry]:
    return [e for e in CATALOG if e.category == category]


def entries_by_kind(kind: str) -> list[CatalogEntry]:
    return [e for e in CATALOG if e.kind == kind]


def install_plan_for(entry: CatalogEntry) -> dict:
    """Render a Setup-Guide plan that the operator executes manually.

    NEVER includes secret values. NEVER suggests a path that runs an
    arbitrary remote script. The plan is a flat list of human-readable
    steps + a single command_template (when applicable) that the
    operator copy-pastes into their own terminal.
    """
    steps: list[dict] = []

    if entry.install_method == "coming-soon":
        steps.append({
            "kind": "info",
            "text": "This connector is in the catalog but not yet installable through Daena.",
        })
        steps.append({
            "kind": "link",
            "text": "Read the official setup guide",
            "url": entry.official_url,
        })
        if entry.required_env_vars:
            steps.append({
                "kind": "env",
                "text": f"Required env vars (NAMES only): {', '.join(entry.required_env_vars)}",
            })
        return {
            "entry_id": entry.id,
            "install_method": entry.install_method,
            "steps": steps,
            "executable": False,
        }

    if entry.command_template:
        steps.append({
            "kind": "command",
            "text": "Run this command in your terminal (Daena does NOT execute it for you):",
            "command": entry.command_template,
        })

    if entry.required_env_vars:
        steps.append({
            "kind": "env",
            "text": (
                f"Set these environment variables before launching (NAMES only -- "
                f"never paste values here): {', '.join(entry.required_env_vars)}"
            ),
        })

    if entry.auth_type == "oauth":
        steps.append({
            "kind": "auth",
            "text": "After install, configure OAuth credentials in Settings -> Apps.",
        })
    elif entry.auth_type == "api_key":
        steps.append({
            "kind": "auth",
            "text": "After install, paste the API key in Settings -> API Keys.",
        })
    elif entry.auth_type == "token":
        steps.append({
            "kind": "auth",
            "text": "After install, paste the token in Settings -> API Keys.",
        })
    elif entry.auth_type == "subscription":
        steps.append({
            "kind": "auth",
            "text": "Authenticate via the vendor's CLI (e.g. claude login, codex login).",
        })

    if entry.official_url:
        steps.append({
            "kind": "link",
            "text": "Vendor's official documentation",
            "url": entry.official_url,
        })

    if entry.setup_notes:
        steps.append({
            "kind": "note",
            "text": entry.setup_notes,
        })

    return {
        "entry_id": entry.id,
        "install_method": entry.install_method,
        "steps": steps,
        "executable": False,
    }


__all__ = [
    "CATALOG",
    "CATALOG_BY_ID",
    "CATEGORIES",
    "CatalogEntry",
    "CategoryDefinition",
    "entries_by_category",
    "entries_by_kind",
    "get_entry",
    "install_plan_for",
    "list_catalog",
    "list_categories",
]
