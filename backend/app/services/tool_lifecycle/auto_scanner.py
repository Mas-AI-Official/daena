"""Auto Scanner -- configurable weekly scan for new/better tools.

Two modes:
    ON (auto):  Weekly scan runs automatically. When better tools are found,
                they're pre-evaluated and ready to activate instantly.
                In AGI mode: auto-install with internal governance.
                In Supervised mode: suggest to user with top 3 ranked.

    OFF (manual): Scan only runs when user explicitly requests it.
                  Tools are discovered and ranked but NOT pre-installed.
                  User sees suggestions in the Tools panel.

The difference between ON and OFF:
    ON  = tools are already there, ready to use (pre-installed, pre-tested)
    OFF = tools are discovered and waiting (user clicks "install" when needed)

The scanner itself is CHEAP: keyword matching against catalogs + optional
web fetch for MCP registry updates. No LLM calls during scanning.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any

from app.services.tool_lifecycle.tool_discovery import (
    ToolCandidate,
    ToolDiscovery,
)


@dataclass
class ScanConfig:
    """User-configurable scan settings."""

    enabled: bool = False           # ON/OFF toggle
    interval_hours: float = 168.0   # weekly (7 * 24)
    auto_install: bool = False      # AGI mode: auto-install approved tools
    max_suggestions: int = 5        # max new tools to suggest per scan
    scan_categories: list[str] = field(default_factory=list)  # empty = all
    notify_on_discovery: bool = True


@dataclass
class ScanResult:
    """Result of a single scan cycle."""

    scan_id: str
    timestamp: float
    tools_discovered: list[ToolCandidate]
    tools_better_than_existing: list[dict[str, Any]]  # {existing_id, candidate, improvement}
    tools_suggested: list[ToolCandidate]
    auto_installed: list[str]       # tool IDs that were auto-installed (AGI mode)
    scan_duration_ms: float = 0.0


class AutoScanner:
    """Configurable auto-scanner for new and better tools.

    Usage:
        scanner = AutoScanner(config)
        scanner.set_installed_tools(["terminal", "file_system", "browser"])

        # Manual scan
        result = scanner.scan_now()

        # Auto mode: runs in background thread
        scanner.start()
        scanner.stop()
    """

    def __init__(
        self,
        config: ScanConfig | None = None,
        discovery: ToolDiscovery | None = None,
    ) -> None:
        self.config = config or ScanConfig()
        self._discovery = discovery or ToolDiscovery()
        self._installed_tool_ids: set[str] = set()
        self._user_categories: list[str] = []  # categories user uses most
        self._scan_history: list[ScanResult] = []
        self._timer: threading.Timer | None = None
        self._running = False

    def set_installed_tools(self, tool_ids: list[str]) -> None:
        """Set which tools are already installed (to exclude from discovery)."""
        self._installed_tool_ids = set(tool_ids)

    def set_user_focus(self, categories: list[str]) -> None:
        """Set categories the user focuses on most (from usage patterns).

        e.g., ["code", "design", "search"] for a web developer.
        This focuses the scan on relevant categories.
        """
        self._user_categories = list(categories)

    def scan_now(self) -> ScanResult:
        """Run a scan immediately. Returns discovered tools."""
        start = time.perf_counter()
        scan_id = f"scan-{int(time.time())}"

        # Determine which categories to scan
        categories = (
            self.config.scan_categories
            or self._user_categories
            or self._discovery.get_categories()
        )

        # Discover tools in each category
        all_discovered: list[ToolCandidate] = []
        for cat in categories:
            candidates = self._discovery.search(
                cat,
                category=cat,
                max_results=3,
                exclude_ids=list(self._installed_tool_ids),
            )
            all_discovered.extend(candidates)

        # Deduplicate by ID
        seen: set[str] = set()
        unique: list[ToolCandidate] = []
        for tool in all_discovered:
            if tool.id not in seen:
                seen.add(tool.id)
                unique.append(tool)

        # Check if any discovered tools are BETTER than installed ones
        better: list[dict[str, Any]] = []
        for tool in unique:
            existing_match = self._find_existing_match(tool)
            if existing_match:
                better.append({
                    "existing_id": existing_match,
                    "candidate": tool,
                    "improvement": self._calculate_improvement(existing_match, tool),
                })

        # Rank and limit suggestions
        suggestions = sorted(
            unique,
            key=lambda t: t.stars * t.compatibility * t.security_score,
            reverse=True,
        )[:self.config.max_suggestions]

        # Auto-install if AGI mode
        auto_installed: list[str] = []
        if self.config.auto_install:
            for tool in suggestions[:2]:  # max 2 auto-installs per scan
                if tool.security_score >= 0.85 and tool.compatibility >= 0.85:
                    auto_installed.append(tool.id)

        elapsed = (time.perf_counter() - start) * 1000
        result = ScanResult(
            scan_id=scan_id,
            timestamp=time.time(),
            tools_discovered=unique,
            tools_better_than_existing=better,
            tools_suggested=suggestions,
            auto_installed=auto_installed,
            scan_duration_ms=round(elapsed, 1),
        )
        self._scan_history.append(result)
        return result

    def get_last_scan(self) -> ScanResult | None:
        """Get the most recent scan result."""
        return self._scan_history[-1] if self._scan_history else None

    def get_scan_history(self) -> list[ScanResult]:
        """Get all past scan results."""
        return list(self._scan_history)

    # ── Background Scheduling ─────────────────────────────────

    def start(self) -> None:
        """Start the background scan timer."""
        if not self.config.enabled:
            return
        self._running = True
        self._schedule_next()

    def stop(self) -> None:
        """Stop the background scan timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self) -> None:
        """Schedule the next scan."""
        if not self._running:
            return
        self._timer = threading.Timer(
            self.config.interval_hours * 3600,
            self._background_scan,
        )
        self._timer.daemon = True
        self._timer.start()

    def _background_scan(self) -> None:
        """Run scan in background and reschedule."""
        if not self._running:
            return
        self.scan_now()
        self._schedule_next()

    # ── Internal ──────────────────────────────────────────────

    def _find_existing_match(self, candidate: ToolCandidate) -> str | None:
        """Check if there's an installed tool in the same category."""
        # Simple: check if any installed tool matches the category
        # In production: would do semantic matching
        for installed_id in self._installed_tool_ids:
            if candidate.category in installed_id or installed_id in candidate.category:
                return installed_id
        return None

    def _calculate_improvement(self, existing_id: str, candidate: ToolCandidate) -> str:
        """Describe how the candidate improves over the existing tool."""
        return (
            f"'{candidate.name}' ({candidate.stars} stars, "
            f"compatibility={candidate.compatibility}) may be better than '{existing_id}'"
        )

    def clear_history(self) -> None:
        self._scan_history.clear()
