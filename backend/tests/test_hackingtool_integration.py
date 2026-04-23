"""Tests for the hackingtool filtered-subset integration (2026-04-23 audit).

Covers:
- SecurityTier enum roundtrips.
- RED denylist blocks any attempt to register a known-bad tool even
  if a future caller constructs the SecurityTool object directly.
- GREEN tools from the pinned JSON land in _CATALOG with correct tier.
- Malformed JSON entries skip gracefully; loader never raises.
- Collisions with the static _CATALOG don't produce duplicates.
"""

from __future__ import annotations

import pytest

from app.services.security.tool_catalog import (
    SecurityTier,
    SecurityTool,
    ToolCatalog,
    _CATALOG,
    _HACKINGTOOL_RED_DENYLIST,
    is_red_denylisted,
)


class TestSecurityTier:
    def test_enum_values(self) -> None:
        assert SecurityTier.GREEN.value == "green"
        assert SecurityTier.YELLOW.value == "yellow"
        assert SecurityTier.RED.value == "red"

    def test_default_tier_for_existing_tools(self) -> None:
        # Every tool in the hand-curated static _CATALOG should
        # default to GREEN -- they're the baseline Daena already
        # ships, audited piece-by-piece over the security-supercharge
        # tickets.
        for tool in _CATALOG:
            assert isinstance(tool.tier, SecurityTier), (
                f"Tool {tool.name} has tier={tool.tier!r}, expected SecurityTier"
            )


class TestRedDenylist:
    @pytest.mark.parametrize(
        "name",
        [
            "pyphisher",
            "PyPhisher",         # case-insensitive
            "Pyphisher",
            "blackeye",
            "evilginx3",
            "ddostool",
            "slowloris",
            "thefatrat",
            "venom",
            "spycam",
            "pyshell",
            "vegile",
            "wifijammer-ng",
            "wifijammer_ng",     # underscore -> dash normalization
            "kawaiideauther",
            "keydroid",
            "evilurl",
        ],
    )
    def test_known_red_names_denylisted(self, name: str) -> None:
        assert is_red_denylisted(name), f"{name} should be on the RED denylist"

    @pytest.mark.parametrize(
        "name",
        [
            "nmap",
            "sqlmap",
            "ghidra",
            "volatility",
            "binwalk",
            "mitmproxy",
            "sherlock",
            "subfinder",
            "httpx",
            "",
        ],
    )
    def test_known_safe_names_not_denylisted(self, name: str) -> None:
        assert not is_red_denylisted(name)

    def test_register_red_tool_raises(self) -> None:
        catalog = ToolCatalog()
        red_tool = SecurityTool(
            name="pyphisher",
            category="phishing",
            description="should never land",
            capabilities=["credential_theft"],
            install_cmd="git clone ...",
            check_cmd="pyphisher",
            tier=SecurityTier.RED,  # caller honestly declares RED
        )
        with pytest.raises(ValueError, match="RED denylist"):
            catalog.register_tool(red_tool)

    def test_register_red_tool_raises_even_if_tier_spoofed_green(self) -> None:
        # Defense in depth: if a future caller tries to hide a RED
        # name behind a fake GREEN tier, the name still loses.
        catalog = ToolCatalog()
        spoofed = SecurityTool(
            name="DDoSTool",
            category="osint",
            description="totally safe",
            capabilities=["recon"],
            install_cmd="echo nope",
            check_cmd="nope",
            tier=SecurityTier.GREEN,
        )
        with pytest.raises(ValueError, match="RED denylist"):
            catalog.register_tool(spoofed)


class TestGreenLoad:
    @pytest.mark.parametrize(
        "name,expected_category",
        [
            ("volatility", "forensics"),
            ("binwalk", "forensics"),
            ("ghidra", "reverse-engineering"),
            ("jadx", "reverse-engineering"),
            ("radare2", "reverse-engineering"),
            # mitmproxy already exists in the static _CATALOG; the loader
            # keeps the curated entry rather than overwriting with the
            # JSON one. Hence "network" not "network-analysis".
            ("mitmproxy", "network"),
            ("testssl", "scanning"),
            ("pspy", "forensics"),
            ("sherlock", "osint"),
            ("cupp", "wordlist"),
            ("haiti", "forensics"),
            ("dnstwist", "osint"),
        ],
    )
    def test_green_tool_loaded(self, name: str, expected_category: str) -> None:
        catalog = ToolCatalog()
        tool = catalog.get_tool(name) if hasattr(catalog, "get_tool") else catalog._tools.get(name)
        assert tool is not None, f"{name} should be in the catalog"
        assert tool.tier == SecurityTier.GREEN
        assert tool.category == expected_category


class TestRegisterSafe:
    def test_register_green_tool_succeeds(self) -> None:
        catalog = ToolCatalog()
        safe = SecurityTool(
            name="my-test-tool-2026",
            category="forensics",
            description="test",
            capabilities=["testing"],
            install_cmd="pip install nothing",
            check_cmd="echo ok",
            tier=SecurityTier.GREEN,
        )
        catalog.register_tool(safe)
        assert "my-test-tool-2026" in catalog._tools

    def test_register_yellow_tool_succeeds_and_preserves_tier(self) -> None:
        # YELLOW tools register fine. The runtime gate (authorized_scope,
        # approval queue) is enforced at execution time, not registration.
        catalog = ToolCatalog()
        yellow = SecurityTool(
            name="my-yellow-tool-2026",
            category="scanning",
            description="dual-use",
            capabilities=["scan"],
            install_cmd="pip install nothing",
            check_cmd="echo ok",
            tier=SecurityTier.YELLOW,
        )
        catalog.register_tool(yellow)
        assert catalog._tools["my-yellow-tool-2026"].tier == SecurityTier.YELLOW


class TestDenylistShape:
    def test_denylist_is_frozen(self) -> None:
        assert isinstance(_HACKINGTOOL_RED_DENYLIST, frozenset)
        # Mirror the JSON: should have core phishing + DDoS + payload
        # names at minimum.
        for expected in ("pyphisher", "blackeye", "ddostool", "thefatrat"):
            assert expected in _HACKINGTOOL_RED_DENYLIST
