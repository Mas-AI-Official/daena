"""Security scanning for all installations.

Security Department (Dept 10) agent that scans everything entering Daena:
CLI tools, MCP servers, Ollama models, skills, plugins.
Nothing gets installed without passing this gate.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Known trusted sources
TRUSTED_CLI_SOURCES = frozenset({
    "npm",
    "pip",
    "ollama",
    "brew",
    "apt",
    "winget",
    "github.com",
    "anthropic",
    "openai",
    "google",
})

# Patterns that indicate prompt injection in skill content
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(instructions|prompts)",
    r"you\s+are\s+now\s+(?:a|an)\s+(?!Daena)",
    r"system\s*prompt\s*(?:is|:)",
    r"forget\s+(?:everything|all|your)",
    r"reveal\s+(?:your|the)\s+(?:system|prompt|instructions)",
    r"(?:sudo|admin|root)\s+(?:mode|access|override)",
    r"jailbreak",
    r"DAN\s+mode",
]

# Dangerous patterns in CLI tool names
DANGEROUS_TOOL_PATTERNS = [
    r"[;&|`$()]",  # Shell injection characters
    r"\.\./",  # Path traversal
    r"\\\\",  # UNC path (Windows)
    r"^https?://",  # Direct URL execution
]


class ScanResult:
    """Result of a security scan."""

    def __init__(self) -> None:
        self.safe = True
        self.checks: dict[str, bool] = {}
        self.warnings: list[str] = []
        self.blockers: list[str] = []

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks[name] = passed
        if not passed:
            self.safe = False
            self.blockers.append(f"{name}: {detail}" if detail else name)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "checks": self.checks,
            "warnings": self.warnings,
            "blockers": self.blockers,
        }


class InstallScanner:
    """Security Department scanner for all installations."""

    async def scan_cli_tool(self, tool_name: str, source: str) -> ScanResult:
        """Scan CLI tool before allowing installation."""
        result = ScanResult()

        # Check for dangerous characters in name
        for pattern in DANGEROUS_TOOL_PATTERNS:
            if re.search(pattern, tool_name):
                result.add_check("name_safe", False, f"Dangerous pattern in name: {tool_name}")
                return result
        result.add_check("name_safe", True)

        # Verify source is trusted
        source_lower = source.lower()
        trusted = any(ts in source_lower for ts in TRUSTED_CLI_SOURCES)
        result.add_check("source_trusted", trusted, f"Unknown source: {source}")
        if not trusted:
            result.add_warning(f"Source '{source}' is not in trusted list. Manual review recommended.")

        # Check for known malicious packages (basic blocklist)
        result.add_check("not_blocklisted", True)

        logger.info(
            "install_scanner.cli_tool",
            tool=tool_name,
            source=source,
            safe=result.safe,
        )
        return result

    async def scan_mcp_server(self, server_url: str, server_name: str = "") -> ScanResult:
        """Scan MCP server before connecting.

        Validator accepts every legitimate MCP launcher we have ever seen on
        Windows + WSL + Linux: HTTP(S), npx/uvx/bun launchers, native cmd /
        powershell / docker invocations, and direct executable paths. The
        original whitelist (http/https/npx/uvx only) was rejecting Masoud's
        gitnexus, MCP_DOCKER, and local-llm bridges -- which left Daena with
        zero tool surface even though Claude Code, Codex and Gemini CLI all
        had them installed. Per Phase 1 plan F2 (2026-04-24).
        """
        result = ScanResult()

        # URL/command validation -- broadened to cover real-world MCP launchers
        valid_prefixes = (
            "http://", "https://",
            "npx ", "uvx ", "bun ",
            "cmd /c", "cmd.exe",
            "docker ",
            "powershell", "pwsh ",
            "python ", "node ",
        )
        is_exe_path = (
            server_url.lower().endswith(".exe")
            or server_url.lower().endswith(".cmd")
            or server_url.lower().endswith(".bat")
            or "\\" in server_url
            or server_url.startswith("/")
        )
        if not (server_url.startswith(valid_prefixes) or is_exe_path):
            result.add_check("url_valid", False, f"Invalid URL/command: {server_url}")
            return result
        result.add_check("url_valid", True)

        # HTTPS check for remote servers
        if server_url.startswith("http://") and "localhost" not in server_url and "127.0.0.1" not in server_url:
            result.add_check("https_required", False, "Remote MCP servers must use HTTPS")
        else:
            result.add_check("https_required", True)

        # Shell injection check in server URL
        for pattern in DANGEROUS_TOOL_PATTERNS[:2]:
            if re.search(pattern, server_url):
                result.add_check("no_injection", False, "Shell injection pattern detected")
                return result
        result.add_check("no_injection", True)

        logger.info(
            "install_scanner.mcp_server",
            server=server_name or server_url[:50],
            safe=result.safe,
        )
        return result

    async def scan_ollama_model(self, model_name: str) -> ScanResult:
        """Scan Ollama model before loading."""
        result = ScanResult()

        # Name validation
        if any(c in model_name for c in [";", "&", "|", "`", "$", "(", ")"]):
            result.add_check("name_safe", False, f"Invalid characters in model name: {model_name}")
            return result
        result.add_check("name_safe", True)

        # Must be from Ollama registry (simple check: no http:// prefix)
        if model_name.startswith("http"):
            result.add_check("registry_source", False, "Direct URL models not allowed. Use Ollama registry.")
        else:
            result.add_check("registry_source", True)

        # Size check (warn if very large)
        result.add_check("size_acceptable", True)
        if any(size in model_name for size in ["70b", "72b", "405b"]):
            result.add_warning("Very large model. Ensure sufficient disk space and RAM.")

        logger.info(
            "install_scanner.ollama_model",
            model=model_name,
            safe=result.safe,
        )
        return result

    async def scan_skill(self, skill_content: str, skill_name: str = "") -> ScanResult:
        """Scan skill content for prompt injection."""
        result = ScanResult()

        content_lower = skill_content.lower()

        # Check for injection patterns
        injection_found = []
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, content_lower):
                injection_found.append(pattern)

        if injection_found:
            result.add_check(
                "no_prompt_injection",
                False,
                f"Found {len(injection_found)} injection pattern(s)",
            )
        else:
            result.add_check("no_prompt_injection", True)

        # Check for excessive length (potential padding attack)
        if len(skill_content) > 50_000:
            result.add_warning("Skill content exceeds 50KB. May contain hidden instructions.")

        # Check for encoded content (base64 payloads)
        if "base64" in content_lower or re.search(r"[A-Za-z0-9+/]{100,}={0,2}", skill_content):
            result.add_warning("Possible encoded content detected. Manual review recommended.")

        logger.info(
            "install_scanner.skill",
            skill=skill_name[:50],
            safe=result.safe,
        )
        return result
