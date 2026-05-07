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


# PR-CONN-MCP-CATALOG-SKILL-BUNDLES (2026-05-03): officiality is the
# trust signal that drives the marketplace badge + the install-time
# friction (community/unverified plugins surface a "Review source
# before install" CTA, official ones surface a clean install button).
#
# Tier semantics (from CONNECTIONS_MCP_PLUGIN_ECOSYSTEM_RESEARCH.md):
#   * official        -- MCP steering group reference servers
#                        (modelcontextprotocol/servers main branch)
#   * vendor-official -- First-party MCP shipped by the app's vendor
#                        (e.g. github/github-mcp-server)
#   * vendor-blessed  -- Community but vendor-affiliated org (e.g.
#                        supabase-community/supabase-mcp)
#   * verified        -- Manually reviewed by Daena, third-party
#   * community       -- Third-party, surfaced with caveat
#   * archived        -- Was reference, no longer maintained by MCP
#                        org but still installable
#   * coming-soon     -- No MCP shipping yet; render Setup Guide only
Officiality = Literal[
    "official",
    "vendor-official",
    "vendor-blessed",
    "verified",
    "community",
    "archived",
    "coming-soon",
]


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

    # ────────────────────────────────────────────────────────────────
    # PR-CONN-MCP-CATALOG-SKILL-BUNDLES (2026-05-03): Plugin-bundle
    # metadata. All optional with safe defaults so existing entries
    # need only opt-in fields they care about.
    # ────────────────────────────────────────────────────────────────

    # Trust tier from research (default community = surface "Review
    # source before install" CTA). See Officiality docstring above.
    officiality: Officiality = "community"

    # Plugin-bundle composition (Codex inspiration).
    # default_skills: skill NAMES this plugin provides once connected.
    # Skills are descriptive metadata -- they do NOT execute
    # autonomously. Per founder rule: skills become "available" only
    # when lifecycle == callable; the UI surfaces them as "Skill ready.
    # Requires <plugin> connection." until then.
    default_skills: tuple[str, ...] = ()

    # Composer seed prompts ("Try: ..."). Codex pattern.
    suggested_prompts: tuple[str, ...] = ()

    # High-level permission summary for the install dialog. Not a per-
    # tool breakdown -- the operator-facing "this plugin can read your
    # email and send messages" preview. Mirrors Codex's
    # interface.capabilities = ["Read","Write"].
    permissions_summary: tuple[str, ...] = ()

    # Plugins that bundle multiple MCP servers. Most have one (often
    # equal to the catalog id); Cloudflare-style multi-endpoint
    # plugins list each.
    mcp_servers: tuple[str, ...] = ()

    # Source attribution -- transparency about where this curation came
    # from. URLs to vendor docs, official repos, MCP registry entries.
    # Required by tests for any non-coming-soon entry.
    source_refs: tuple[str, ...] = ()

    # ISO8601 timestamp of when a human last verified this entry's
    # vendor status. Drives the "freshness" pill on the marketplace
    # card -- entries older than 90 days could be flagged for re-check.
    last_verified_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert tuples to lists for JSON serialization.
        for key in (
            "capabilities",
            "required_env_vars",
            "compatible_os",
            "default_skills",
            "suggested_prompts",
            "permissions_summary",
            "mcp_servers",
            "source_refs",
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
        officiality="vendor-official",
        source_refs=("https://docs.anthropic.com/claude-code",),
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
        officiality="vendor-official",
        source_refs=("https://github.com/openai/codex",),
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
        officiality="vendor-official",
        source_refs=("https://github.com/google-gemini/gemini-cli",),
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
        officiality="vendor-official",
        source_refs=("https://docs.anthropic.com",),
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
        officiality="vendor-official",
        source_refs=("https://platform.openai.com/docs",),
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
        officiality="vendor-official",
        source_refs=("https://ai.google.dev",),
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
        officiality="vendor-official",
        source_refs=("https://docs.perplexity.ai",),
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
        officiality="vendor-official",
        source_refs=("https://console.groq.com/docs",),
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
        officiality="vendor-official",
        source_refs=("https://openrouter.ai/docs",),
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
        officiality="vendor-official",
        source_refs=("https://docs.together.ai",),
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
        officiality="official",
        source_refs=("https://github.com/ollama/ollama",),
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
        officiality="official",
        source_refs=(
            "https://github.com/ggerganov/llama.cpp",
            "https://github.com/vllm-project/vllm",
        ),
    ),
)


# Filesystem MCP servers
_FILESYSTEM: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-filesystem",
        display_name="Filesystem",
        vendor="MCP Steering Group",
        category="filesystem",
        kind="mcp_server",
        short_description="Reference filesystem MCP — sandboxed read/write within allowed roots.",
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
        officiality="official",
        default_skills=("find_files", "read_file", "summarize_directory"),
        permissions_summary=("Read", "Write"),
        mcp_servers=("server-filesystem",),
        source_refs=(
            "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
        ),
        last_verified_at="2026-05-03",
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
        short_description="Official Microsoft Playwright MCP — 60+ tools for accessibility-snapshot browser automation.",
        capabilities=(
            "Accessibility-snapshot interaction",
            "Tabs + navigation",
            "Network mocking",
            "Storage management",
            "DevTools tracing",
            "Vision (coords) mode",
            "PDF + screenshots",
            "Test assertions",
        ),
        install_method="npm",
        command_template="npx -y @playwright/mcp@latest",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/microsoft/playwright-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-playwright",
        setup_notes=(
            "Browser tools open pages and click elements. Daena does not "
            "bypass anti-bot systems and never claims stealth or evasion. "
            "Browsers run in your local environment with explicit consent. "
            "Env: PLAYWRIGHT_MCP_BROWSER, PLAYWRIGHT_MCP_HEADLESS, "
            "PLAYWRIGHT_MCP_USER_DATA_DIR (optional persistent profile)."
        ),
        officiality="vendor-official",
        default_skills=(
            "open_page",
            "inspect_ui",
            "fill_form_safe",
            "capture_screenshot",
            "run_smoke_test",
        ),
        suggested_prompts=(
            "Open the staging dashboard and report what you see.",
            "Run a smoke test against the login flow.",
        ),
        permissions_summary=("Read", "Write", "Network"),
        mcp_servers=("playwright-mcp",),
        source_refs=(
            "https://github.com/microsoft/playwright-mcp",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-chrome-devtools",
        display_name="Chrome DevTools",
        vendor="Google (Chrome team)",
        category="browser",
        kind="browser_tool",
        short_description="Official Chrome DevTools MCP — 33+ tools for perf, debugging, snapshots.",
        capabilities=(
            "Input automation + navigation",
            "Performance tracing",
            "Network inspection",
            "Console messages",
            "Lighthouse audits",
            "Memory snapshots",
            "Emulation + extensions",
        ),
        install_method="npm",
        command_template="npx -y chrome-devtools-mcp@latest",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/ChromeDevTools/chrome-devtools-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-chrome-devtools",
        setup_notes=(
            "Requires Chrome / Chromium running with --remote-debugging-port. "
            "Best for inspect-and-observe workflows. Env: "
            "CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS, "
            "CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS."
        ),
        officiality="vendor-official",
        default_skills=(
            "inspect_dom",
            "read_network",
            "analyze_perf",
            "capture_screenshot",
        ),
        suggested_prompts=(
            "Profile the page load and report bottlenecks.",
            "Capture a Lighthouse audit for accessibility.",
        ),
        permissions_summary=("Read", "Network"),
        mcp_servers=("chrome-devtools-mcp",),
        source_refs=(
            "https://github.com/ChromeDevTools/chrome-devtools-mcp",
        ),
        last_verified_at="2026-05-03",
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
        vendor="GitHub",
        category="code_platform",
        kind="mcp_server",
        short_description="Triage PRs, issues, search repos via GitHub's official MCP.",
        capabilities=(
            "Search repositories",
            "List + create issues",
            "Read file contents",
            "Create pull requests",
            "Inspect Actions runs",
            "Read Code Security + Dependabot",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-github",
        required_env_vars=("GITHUB_PERSONAL_ACCESS_TOKEN",),
        auth_type="token",
        official_url="https://github.com/github/github-mcp-server",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-github",
        setup_notes=(
            "GitHub now ships an official MCP at github/github-mcp-server. "
            "Local: pass GITHUB_PERSONAL_ACCESS_TOKEN. Remote OAuth-backed "
            "endpoint also available at https://api.githubcopilot.com/mcp/."
        ),
        officiality="vendor-official",
        default_skills=(
            "triage_issues",
            "review_pull_request",
            "summarize_repo",
            "draft_release_notes",
            "inspect_ci_failure",
        ),
        suggested_prompts=(
            "Triage the open issues in this repo by priority.",
            "Review the latest pull request and summarize concerns.",
            "Draft release notes for the last 10 merged PRs.",
        ),
        permissions_summary=("Read", "Write", "Network"),
        mcp_servers=("github-mcp-server",),
        source_refs=(
            "https://github.com/github/github-mcp-server",
            "https://api.githubcopilot.com/mcp/",
            "https://registry.modelcontextprotocol.io/",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-cloudflare",
        display_name="Cloudflare",
        vendor="Cloudflare",
        category="code_platform",
        kind="mcp_server",
        short_description="6 official Cloudflare MCP endpoints: docs, bindings, observability, radar, browser, AI gateway.",
        capabilities=(
            "Search Cloudflare docs",
            "Manage Workers bindings (R2 / KV / D1 / AI)",
            "Read logs + analytics",
            "Internet traffic insights (Radar)",
            "Headless browser fetch + screenshots",
            "Inspect AI Gateway prompt logs",
        ),
        install_method="manual",
        command_template="https://mcp.cloudflare.com/mcp",
        required_env_vars=("CLOUDFLARE_API_TOKEN",),
        auth_type="oauth",
        official_url="https://developers.cloudflare.com/agents/model-context-protocol/mcp-servers-for-cloudflare/",
        risk_level="high",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-cloudflare",
        setup_notes=(
            "Cloudflare ships 6 hosted MCP endpoints. Primary: "
            "https://mcp.cloudflare.com/mcp. OAuth via Cloudflare account. "
            "Avoid Global API Key tokens; use scoped tokens only."
        ),
        officiality="vendor-official",
        default_skills=(
            "inspect_dns",
            "review_workers",
            "check_security_headers",
            "summarize_zone_config",
        ),
        suggested_prompts=(
            "Show DNS records for my domain.",
            "Summarize traffic patterns in the last 7 days.",
            "Review my Workers bindings for security issues.",
        ),
        permissions_summary=("Read", "Write", "Network"),
        mcp_servers=(
            "cloudflare-docs",
            "cloudflare-bindings",
            "cloudflare-observability",
            "cloudflare-radar",
            "cloudflare-browser",
            "cloudflare-ai-gateway",
        ),
        source_refs=(
            "https://github.com/cloudflare/mcp-server-cloudflare",
            "https://developers.cloudflare.com/agents/model-context-protocol/mcp-servers-for-cloudflare/",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-sentry",
        display_name="Sentry",
        vendor="Sentry",
        category="code_platform",
        kind="mcp_server",
        short_description="Official Sentry MCP for issue triage, error analysis, and Seer AI search.",
        capabilities=(
            "List recent issues",
            "Get event detail",
            "Search events with NL",
            "Trace release regressions",
            "Seer AI analysis",
        ),
        install_method="npm",
        command_template="npx -y @sentry/mcp-server",
        required_env_vars=("SENTRY_AUTH_TOKEN", "SENTRY_HOST"),
        auth_type="oauth",
        official_url="https://docs.sentry.io/product/sentry-mcp/",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-sentry",
        setup_notes=(
            "Hosted endpoint: https://mcp.sentry.dev/mcp (OAuth device-code). "
            "Self-hosted: SENTRY_AUTH_TOKEN + SENTRY_HOST. Required scopes: "
            "org:read, project:read/write, team:read/write, event:write."
        ),
        officiality="vendor-official",
        default_skills=(
            "summarize_errors",
            "trace_release_regression",
            "create_bug_task",
        ),
        suggested_prompts=(
            "Summarize the top errors in production this week.",
            "Did the latest release introduce any new errors?",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("sentry-mcp",),
        source_refs=(
            "https://docs.sentry.io/product/sentry-mcp/",
            "https://mcp.sentry.dev/mcp",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-vercel",
        display_name="Vercel",
        vendor="Vercel",
        category="code_platform",
        kind="mcp_server",
        short_description="Official Vercel MCP for deployment management + log analysis.",
        capabilities=(
            "Search Vercel docs",
            "List projects",
            "Inspect deployments",
            "Analyze deployment logs",
            "Manage env vars",
        ),
        install_method="manual",
        command_template="https://mcp.vercel.com",
        required_env_vars=(),
        auth_type="oauth",
        official_url="https://vercel.com/docs/agent-resources/vercel-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-vercel",
        setup_notes=(
            "Hosted at https://mcp.vercel.com (OAuth via MCP Authorization "
            "2025-06-18 spec, Streamable HTTP). Allowlisted clients only "
            "(Claude, Codex, Cursor, Daena requires registration)."
        ),
        officiality="vendor-official",
        default_skills=(
            "summarize_deployment",
            "inspect_logs",
            "review_env_config",
        ),
        suggested_prompts=(
            "Show me the failed deployments in the last 24 hours.",
            "Summarize the production log for the latest deploy.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("vercel-mcp",),
        source_refs=(
            "https://vercel.com/docs/agent-resources/vercel-mcp",
            "https://mcp.vercel.com",
        ),
        last_verified_at="2026-05-03",
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
    _entry(
        id="mcp-gitlab",
        display_name="GitLab",
        vendor="GitLab community",
        category="code_platform",
        kind="mcp_server",
        short_description="Triage MRs, issues, search projects via GitLab API.",
        capabilities=(
            "Search projects",
            "List + create issues",
            "Read file contents",
            "Manage merge requests",
        ),
        install_method="coming-soon",
        command_template="",
        required_env_vars=("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_API_URL"),
        auth_type="token",
        official_url="https://docs.gitlab.com/ee/api/",
        risk_level="medium",
        probe_type="none",
        matches_v2_slug="",
        setup_notes=(
            "Community GitLab MCP coming soon. Generate a PAT at "
            "gitlab.com/-/profile/personal_access_tokens; scope to api + "
            "read_repository."
        ),
    ),
    _entry(
        id="mcp-jira",
        display_name="Atlassian (Jira + Confluence)",
        vendor="Atlassian",
        category="code_platform",
        kind="mcp_server",
        short_description="Official Atlassian Rovo MCP — Jira tickets + Confluence pages.",
        capabilities=(
            "Search Jira issues",
            "Bulk-create Jira work items",
            "Search + create Confluence pages",
            "Permission-aware queries",
        ),
        install_method="manual",
        command_template="https://mcp.atlassian.com/v1/sse",
        required_env_vars=(),
        auth_type="oauth",
        official_url="https://www.atlassian.com/platform/remote-mcp-server",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-atlassian",
        setup_notes=(
            "Atlassian Rovo MCP. Streamable HTTP at "
            "https://mcp.atlassian.com/v1/sse. OAuth-managed; admin can "
            "customize allowed-AI-domains. Free tier: 500 req/hr."
        ),
        officiality="vendor-official",
        default_skills=(
            "triage_tickets",
            "summarize_sprint",
            "draft_release_notes",
            "find_blockers",
        ),
        suggested_prompts=(
            "Triage the open tickets in this sprint by priority.",
            "Summarize the last two weeks of work for standup.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("atlassian-rovo-mcp",),
        source_refs=(
            "https://www.atlassian.com/platform/remote-mcp-server",
            "https://mcp.atlassian.com/v1/sse",
        ),
        last_verified_at="2026-05-03",
    ),
)


# Communication MCPs
_COMMUNICATION: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-slack",
        display_name="Slack",
        vendor="Slack",
        category="communication",
        kind="mcp_server",
        short_description="Official Slack MCP (hosted-only, requires workspace admin approval).",
        capabilities=(
            "Search messages, files, users, channels",
            "Send messages",
            "Read history + threads",
            "Create + read canvases",
            "Profile info",
        ),
        install_method="manual",
        command_template="https://mcp.slack.com/mcp",
        required_env_vars=("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://docs.slack.dev/ai/slack-mcp-server/",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-slack",
        setup_notes=(
            "Hosted-only at https://mcp.slack.com/mcp. Workspace admin must "
            "approve MCP integration before users can connect. OAuth scopes: "
            "search:read.*, chat:write, channels:history, groups:history, "
            "mpim:history, im:history, canvases:read/write, users:read."
        ),
        officiality="vendor-official",
        default_skills=(
            "summarize_channel",
            "draft_reply",
            "find_decisions",
            "extract_tasks",
        ),
        suggested_prompts=(
            "Summarize what was discussed in #engineering today.",
            "Find decisions made in this thread.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("slack-mcp",),
        source_refs=(
            "https://docs.slack.dev/ai/slack-mcp-server/",
            "https://mcp.slack.com/mcp",
        ),
        last_verified_at="2026-05-03",
    ),
)


# Productivity MCPs
_PRODUCTIVITY: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-notion",
        display_name="Notion",
        vendor="Notion",
        category="productivity",
        kind="mcp_server",
        short_description="Official Notion MCP — pages, databases, search, comments.",
        capabilities=(
            "Search pages",
            "Read + create + update pages",
            "Query + create databases",
            "Comments + teams + users",
        ),
        install_method="manual",
        command_template="",
        required_env_vars=(),
        auth_type="oauth",
        official_url="https://developers.notion.com/docs/mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-notion",
        setup_notes=(
            "Notion ships an official OAuth-managed hosted MCP. "
            "Connect via the Notion integrations panel."
        ),
        officiality="vendor-official",
        default_skills=(
            "find_page",
            "summarize_database",
            "extract_action_items",
            "update_page",
        ),
        suggested_prompts=(
            "Find pages mentioning the Q2 roadmap.",
            "Summarize the action items from yesterday's meeting notes.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("notion-mcp",),
        source_refs=(
            "https://developers.notion.com/docs/mcp",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-linear",
        display_name="Linear",
        vendor="Linear",
        category="productivity",
        kind="mcp_server",
        short_description="Official Linear MCP — issues, projects, cycles.",
        capabilities=(
            "List + find issues",
            "Create + update issues",
            "List projects + cycles",
            "Comments",
        ),
        install_method="manual",
        command_template="https://mcp.linear.app/mcp",
        required_env_vars=(),
        auth_type="oauth",
        official_url="https://linear.app/docs/mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-linear",
        setup_notes=(
            "Hosted at https://mcp.linear.app/mcp. OAuth 2.1 with dynamic "
            "client registration. Add via: claude mcp add --transport http "
            "linear-server https://mcp.linear.app/mcp."
        ),
        officiality="vendor-official",
        default_skills=(
            "triage_issues",
            "summarize_cycle",
            "draft_status_update",
            "find_blockers",
        ),
        suggested_prompts=(
            "Triage the open issues in the Daena project by priority.",
            "Draft a status update for this cycle's work.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("linear-mcp",),
        source_refs=(
            "https://linear.app/docs/mcp",
            "https://mcp.linear.app/mcp",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-google-drive",
        display_name="Google Drive (MCP)",
        vendor="Anthropic (archived ref)",
        category="productivity",
        kind="mcp_server",
        short_description="Archived reference Drive MCP — search + read files (read-only by default).",
        capabilities=("Search files", "Read file content", "List folders"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-gdrive",
        required_env_vars=("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET"),
        auth_type="oauth",
        official_url="https://github.com/modelcontextprotocol/servers-archived/tree/main/src/gdrive",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-gdrive",
        setup_notes=(
            "Reference Drive MCP is archived (no longer maintained by MCP "
            "org). Still installable. For a managed flow, use Apps -> "
            "Google Drive OAuth instead."
        ),
        officiality="archived",
        default_skills=(
            "find_documents",
            "summarize_file",
            "compare_docs",
            "extract_tables",
        ),
        permissions_summary=("Read",),
        mcp_servers=("server-gdrive",),
        source_refs=(
            "https://github.com/modelcontextprotocol/servers-archived/tree/main/src/gdrive",
        ),
        last_verified_at="2026-05-03",
    ),
)


# Design MCPs
_DESIGN: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-figma",
        display_name="Figma (Dev Mode)",
        vendor="Figma",
        category="design",
        kind="mcp_server",
        short_description="Official Figma Dev Mode MCP (beta) — code generation, image extraction, variables.",
        capabilities=(
            "Generate React/Tailwind code from designs",
            "Extract images + variables",
            "List components",
            "Code Connect mapping",
            "Write to Figma + FigJam canvases",
        ),
        install_method="manual",
        command_template="https://mcp.figma.com/mcp",
        required_env_vars=(),
        auth_type="oauth",
        official_url="https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Dev-Mode-MCP-Server",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-figma",
        setup_notes=(
            "Figma's official Dev Mode MCP. Remote: https://mcp.figma.com/mcp "
            "(free during beta, all seats). Desktop variant requires Dev/Full "
            "seat on a paid plan. Per-client OAuth setup."
        ),
        officiality="vendor-official",
        default_skills=(
            "inspect_design",
            "summarize_components",
            "generate_frontend_plan",
        ),
        suggested_prompts=(
            "Generate React + Tailwind for the selected frame.",
            "Summarize the components used in this file.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("figma-dev-mode-mcp",),
        source_refs=(
            "https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Dev-Mode-MCP-Server",
            "https://mcp.figma.com/mcp",
        ),
        last_verified_at="2026-05-03",
    ),
)


# Database MCPs
_DATA_STORAGE: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-postgres",
        display_name="Postgres",
        vendor="MCP Steering Group (archived)",
        category="data_storage",
        kind="mcp_server",
        short_description="Archived reference Postgres MCP — read-only schema + query exploration.",
        capabilities=("List tables", "Describe schema", "Run SELECT", "EXPLAIN"),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-postgres <DATABASE_URL>",
        required_env_vars=("POSTGRES_URL",),
        auth_type="api_key",
        official_url="https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-postgres",
        setup_notes=(
            "Reference Postgres MCP is now archived (still installable). "
            "Pass a connection string with read-only credentials. Use a "
            "dedicated read-only role; do NOT pass admin creds. Consider "
            "Neon or Supabase first-party MCPs which include Postgres tools."
        ),
        officiality="archived",
        default_skills=("describe_schema", "safe_query", "explain_query"),
        permissions_summary=("Read",),
        mcp_servers=("server-postgres",),
        source_refs=(
            "https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-sqlite",
        display_name="SQLite",
        vendor="MCP Steering Group (archived)",
        category="data_storage",
        kind="mcp_server",
        short_description="Archived reference SQLite MCP — local DB read/write.",
        capabilities=("List tables", "Run query", "Schema inspection"),
        install_method="manual",
        command_template="uvx mcp-server-sqlite --db-path <PATH>",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-sqlite",
        setup_notes="Reference SQLite MCP archived. Python (uvx). Pass --db-path.",
        officiality="archived",
        default_skills=("describe_schema", "safe_query", "explain_query"),
        permissions_summary=("Read", "Write"),
        mcp_servers=("mcp-server-sqlite",),
        source_refs=(
            "https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite",
        ),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-mongodb",
        display_name="MongoDB",
        vendor="MongoDB Inc.",
        category="data_storage",
        kind="mcp_server",
        short_description="Vendor-blessed MongoDB MCP — query + inspect collections.",
        capabilities=("List collections", "Query documents", "Inspect indexes"),
        install_method="npm",
        command_template="npx -y mongodb-mcp-server",
        required_env_vars=("MONGODB_URI",),
        auth_type="api_key",
        official_url="https://www.mongodb.com",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-mongodb",
        setup_notes=(
            "MongoDB Inc. has shipped a vendor-blessed MCP. Pass connection "
            "string with read-only credentials when possible."
        ),
        officiality="vendor-blessed",
        default_skills=("describe_collections", "safe_query"),
        permissions_summary=("Read",),
        mcp_servers=("mongodb-mcp-server",),
        source_refs=("https://www.mongodb.com",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-supabase",
        display_name="Supabase",
        vendor="Supabase",
        category="data_storage",
        kind="mcp_server",
        short_description="Vendor-blessed Supabase MCP — Postgres + Auth + Storage + Functions.",
        capabilities=(
            "Run SQL on Supabase Postgres",
            "Inspect schemas + tables",
            "Manage Storage buckets",
            "Inspect Auth users",
        ),
        install_method="npm",
        command_template="npx -y supabase-mcp",
        required_env_vars=("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
        auth_type="api_key",
        official_url="https://github.com/supabase-community/supabase-mcp",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-supabase",
        setup_notes=(
            "Vendor-blessed via supabase-community org. Use a service role "
            "key only in server-side / admin contexts."
        ),
        officiality="vendor-blessed",
        default_skills=("describe_schema", "safe_query", "summarize_storage"),
        permissions_summary=("Read", "Write"),
        mcp_servers=("supabase-mcp",),
        source_refs=("https://github.com/supabase-community/supabase-mcp",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-neon",
        display_name="Neon",
        vendor="Neon",
        category="data_storage",
        kind="mcp_server",
        short_description="Official Neon MCP — serverless Postgres branches + Postgres tools.",
        capabilities=(
            "List + create branches",
            "Run SQL on a branch",
            "Inspect schemas",
        ),
        install_method="npm",
        command_template="npx -y @neondatabase/mcp-server-neon",
        required_env_vars=("NEON_API_KEY",),
        auth_type="api_key",
        official_url="https://github.com/neondatabase/mcp-server-neon",
        risk_level="medium",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-neon",
        setup_notes="Vendor-published from neondatabase org. Ideal for branching workflows.",
        officiality="vendor-official",
        default_skills=("describe_schema", "safe_query", "list_branches"),
        permissions_summary=("Read", "Write"),
        mcp_servers=("mcp-server-neon",),
        source_refs=("https://github.com/neondatabase/mcp-server-neon",),
        last_verified_at="2026-05-03",
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
        short_description="Official Stripe MCP — 20+ tools for payments, subs, invoicing, docs.",
        capabilities=(
            "Customers, invoices, subscriptions",
            "Payment intents, products, pricing",
            "Refunds + disputes + analytics",
            "Docs search",
        ),
        install_method="npm",
        command_template="npx -y @stripe/mcp@latest",
        required_env_vars=("STRIPE_SECRET_KEY",),
        auth_type="oauth",
        official_url="https://docs.stripe.com/mcp",
        risk_level="high",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-stripe",
        setup_notes=(
            "Hosted: https://mcp.stripe.com (OAuth recommended). Local: "
            "use a RESTRICTED API key (stripe.com/docs/keys#restricted). "
            "Default to read-only scopes; never paste live secret keys."
        ),
        officiality="vendor-official",
        default_skills=(
            "summarize_payments",
            "inspect_customer",
            "reconcile_subscriptions",
        ),
        suggested_prompts=(
            "Summarize this month's payment activity.",
            "Show all subscriptions for customer X.",
        ),
        permissions_summary=("Read", "Write"),
        mcp_servers=("stripe-mcp",),
        source_refs=(
            "https://docs.stripe.com/mcp",
            "https://mcp.stripe.com",
        ),
        last_verified_at="2026-05-03",
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
    _entry(
        id="mcp-huggingface",
        display_name="Hugging Face",
        vendor="Hugging Face",
        category="research",
        kind="mcp_server",
        short_description="Official HF MCP — search models / datasets / spaces / papers, fetch docs.",
        capabilities=(
            "Search models, datasets, spaces",
            "Paper search",
            "Hub repo details",
            "Doc search + fetch",
            "Spaces invocation",
        ),
        install_method="manual",
        command_template="https://huggingface.co/mcp",
        required_env_vars=("HF_TOKEN",),
        auth_type="api_key",
        official_url="https://github.com/huggingface/hf-mcp-server",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-huggingface",
        setup_notes=(
            "Hosted at https://huggingface.co/mcp. Settings UI at "
            "huggingface.co/settings/mcp. Public catalog calls are anonymous; "
            "HF_TOKEN required for private repos (read scope sufficient)."
        ),
        officiality="vendor-official",
        default_skills=(
            "find_model",
            "summarize_dataset",
            "compare_models",
            "inspect_paper",
        ),
        suggested_prompts=(
            "Find a recent embedding model under 1B parameters.",
            "Summarize this paper for me.",
        ),
        permissions_summary=("Read",),
        mcp_servers=("huggingface-mcp",),
        source_refs=(
            "https://github.com/huggingface/hf-mcp-server",
            "https://huggingface.co/docs/hub/en/hf-mcp-server",
        ),
        last_verified_at="2026-05-03",
    ),
)


# Dev tools MCPs
_DEV_TOOLS: tuple[CatalogEntry, ...] = (
    _entry(
        id="mcp-fetch",
        display_name="Fetch",
        vendor="MCP Steering Group",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference fetch MCP — HTTP GET + HTML→markdown extraction.",
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
        officiality="official",
        permissions_summary=("Network",),
        mcp_servers=("server-fetch",),
        source_refs=("https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-brave-search",
        display_name="Brave Search",
        vendor="Brave",
        category="dev_tools",
        kind="mcp_server",
        short_description="Brave-shipped web search MCP (replaced the archived reference server).",
        capabilities=("Web search", "News search"),
        install_method="npm",
        command_template="npx -y brave-search-mcp",
        required_env_vars=("BRAVE_API_KEY",),
        auth_type="api_key",
        official_url="https://brave.com/search/api",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-brave-search",
        setup_notes="Get a free API key at api.search.brave.com.",
        officiality="vendor-official",
        permissions_summary=("Network",),
        mcp_servers=("brave-search-mcp",),
        source_refs=("https://brave.com/search/api",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-time",
        display_name="Time",
        vendor="MCP Steering Group",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference time MCP — current time + timezone conversion.",
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
        officiality="official",
        mcp_servers=("server-time",),
        source_refs=("https://github.com/modelcontextprotocol/servers/tree/main/src/time",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-git",
        display_name="Git",
        vendor="MCP Steering Group",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference git MCP (Python) — local repo inspection.",
        capabilities=("Git log", "Git diff", "Git blame", "Show commit"),
        install_method="manual",
        command_template="uvx mcp-server-git --repository <path>",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-git",
        setup_notes="Python-based (uvx). Pass --repository <path>. Read-only by default.",
        officiality="official",
        permissions_summary=("Read",),
        mcp_servers=("mcp-server-git",),
        source_refs=("https://github.com/modelcontextprotocol/servers/tree/main/src/git",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-memory",
        display_name="Memory",
        vendor="MCP Steering Group",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference KG-based memory MCP for cross-tool persistent recall.",
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
        officiality="official",
        mcp_servers=("server-memory",),
        source_refs=("https://github.com/modelcontextprotocol/servers/tree/main/src/memory",),
        last_verified_at="2026-05-03",
    ),
    _entry(
        id="mcp-sequential-thinking",
        display_name="Sequential Thinking",
        vendor="MCP Steering Group",
        category="dev_tools",
        kind="mcp_server",
        short_description="Reference reasoning-scaffold MCP — step-by-step structured thinking.",
        capabilities=(
            "Structured chain-of-thought",
            "Branching plan revision",
            "Step replay",
        ),
        install_method="npm",
        command_template="npx -y @modelcontextprotocol/server-sequential-thinking",
        required_env_vars=(),
        auth_type="none",
        official_url="https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
        risk_level="low",
        probe_type="mcp_initialize",
        matches_v2_slug="mcp-sequential-thinking",
        setup_notes=(
            "Reference reasoning helper. Daena already has its own Council + "
            "Quintessence reasoning layer; this MCP is for cross-tool parity."
        ),
        officiality="official",
        mcp_servers=("server-sequential-thinking",),
        source_refs=(
            "https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
        ),
        last_verified_at="2026-05-03",
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
        short_description="Send + search + draft emails via Gmail OAuth (Daena-managed).",
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
            "then use the OAuth flow to grant Gmail access. Google has not "
            "shipped a first-party Gmail MCP -- Daena's OAuth integration "
            "is the canonical path."
        ),
        officiality="verified",
        default_skills=(
            "summarize_unread",
            "draft_reply",
            "extract_action_items",
            "search_email_context",
        ),
        suggested_prompts=(
            "Summarize unread emails from this week.",
            "Draft a reply to the latest message from <person>.",
            "Extract action items from emails this morning.",
        ),
        permissions_summary=("Read", "Write"),
        source_refs=("https://developers.google.com/gmail/api",),
        last_verified_at="2026-05-03",
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
        officiality="verified",
        default_skills=(
            "list_today",
            "find_free_time",
            "schedule_meeting",
            "summarize_week",
        ),
        suggested_prompts=(
            "What does my afternoon look like?",
            "Find a 30-minute slot tomorrow with X.",
        ),
        permissions_summary=("Read", "Write"),
        source_refs=("https://developers.google.com/calendar",),
        last_verified_at="2026-05-03",
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
        officiality="verified",
        default_skills=(
            "find_documents",
            "summarize_file",
            "compare_docs",
            "extract_tables",
        ),
        suggested_prompts=(
            "Find docs about the Q2 launch plan.",
            "Summarize the Drive file titled <name>.",
        ),
        permissions_summary=("Read", "Write"),
        source_refs=("https://developers.google.com/drive",),
        last_verified_at="2026-05-03",
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
        officiality="vendor-official",
        source_refs=("https://docs.github.com/en/apps/oauth-apps",),
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
        officiality="vendor-official",
        source_refs=("https://www.figma.com/developers/api",),
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
        officiality="vendor-official",
        source_refs=("https://api.slack.com/apps",),
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
        officiality="vendor-official",
        source_refs=("https://www.canva.dev/docs/connect",),
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
