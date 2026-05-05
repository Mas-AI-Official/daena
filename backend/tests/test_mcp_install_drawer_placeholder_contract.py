"""PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT (Sprint-8 PR-1) -- frontend
contract pinned via source-level grep.

The drawer renders an input form whenever the preview response carries
``unresolved_placeholders``. Without that form, Filesystem MCP cannot
become callable from the UI -- which was the entire blocker behind
this sprint. Pin the wiring at the source level so a future refactor
cannot silently soften it.
"""

from __future__ import annotations

from pathlib import Path

import pytest


DRAWER = (
    Path(__file__).resolve().parents[1].parent
    / "frontend" / "src" / "pages" / "connections" / "MCPInstallDrawer.tsx"
)
HOOK = (
    Path(__file__).resolve().parents[1].parent
    / "frontend" / "src" / "hooks" / "useMarketplace.ts"
)


def test_drawer_state_carries_placeholder_values():
    src = DRAWER.read_text(encoding="utf-8")
    assert "placeholderValues" in src, (
        "MCPInstallDrawer must hold operator-supplied placeholder values"
    )
    assert "setPlaceholderValues" in src
    # Filled values must thread into the apply call body.
    assert "placeholder_values" in src, (
        "drawer must forward placeholder_values to apply"
    )


def test_drawer_renders_input_form_for_each_unresolved_token():
    src = DRAWER.read_text(encoding="utf-8")
    # The form is keyed off preview.unresolved_placeholders.
    assert "unresolved_placeholders" in src
    # Operator-facing testid on the form container.
    assert 'data-testid="mcp-install-placeholder-form"' in src, (
        "placeholder form must have a stable testid for E2E hooks"
    )
    # Per-input testid uses the token name.
    assert "mcp-install-placeholder-input-" in src
    # An "Update preview" button must exist so the operator triggers
    # the re-fetch deliberately.
    assert "mcp-install-placeholder-update" in src


def test_drawer_carries_friendly_label_for_allowed_root():
    """`<ALLOWED_ROOT>` must surface as a human label, not just the
    raw token. Filesystem MCP is the first plugin operators reach;
    the friendly label is part of the local-usable acceptance bar."""
    src = DRAWER.read_text(encoding="utf-8")
    assert "<ALLOWED_ROOT>" in src
    assert "Allowed folder root" in src


def test_hook_types_carry_placeholder_values_and_unresolved_list():
    src = HOOK.read_text(encoding="utf-8")
    assert "placeholder_values?: Record<string, string>" in src, (
        "request body type must accept placeholder_values"
    )
    assert "unresolved_placeholders: string[]" in src, (
        "preview response type must surface unresolved_placeholders"
    )


def test_drawer_does_not_auto_submit_or_default_paths():
    """Hard rule: never auto-fill an Allowed Root value. The operator
    types every value explicitly. This pin matches the brief's
    'do not default to C:\\ or user home'."""
    src = DRAWER.read_text(encoding="utf-8")
    # No hard-coded fallback paths in the drawer. Specifically: the
    # default examples may live in PLACEHOLDER_FRIENDLY for the
    # placeholder= attribute (a hint, not a value), but no useEffect
    # should set placeholderValues to a non-empty string by default.
    bad_substrings = (
        'placeholderValues({"<ALLOWED_ROOT>"',
        "placeholderValues['<ALLOWED_ROOT>'] =",
        "setPlaceholderValue('<ALLOWED_ROOT>', '",
        "setPlaceholderValue(\"<ALLOWED_ROOT>\", \"",
    )
    for needle in bad_substrings:
        assert needle not in src, (
            f"drawer must not auto-fill placeholder values: found {needle!r}"
        )
