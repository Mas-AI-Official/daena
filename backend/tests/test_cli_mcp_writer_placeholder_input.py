"""PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT (Sprint-8 PR-1).

Pins the contract of the placeholder substitution layer used by
``preview_install`` / ``apply_install`` to resolve operator-supplied
``<TOKEN>`` values (e.g. ``<ALLOWED_ROOT>``) before the writer touches
any CLI config file.

Hard guarantees:

  1. ``find_template_placeholders`` enumerates every ``<UPPER_TOKEN>``
     in a raw catalog template (the UI's first-render contract).
  2. ``resolve_command_template`` rejects shell metacharacters /
     newlines / shell-expansion sequences in supplied values.
  3. shlex-quoting is automatic for values with whitespace so the final
     parsed command stays single-token.
  4. Unresolved placeholders are reported on the preview report even
     when other failures (target_unsupported, config_path_missing) come
     first -- the UI must always know what to ask the operator.
  5. Once placeholders are filled, ``preview_install`` reaches the
     happy path (action="create" / "update") and the proposed_block's
     args carry the substituted value.
  6. ``apply_install`` consumes the same substitution table and writes
     the resolved command to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.connection_v2.cli_mcp_writer import (
    FAIL_PLACEHOLDER_UNRESOLVED,
    FAIL_PLACEHOLDER_VALUE_INVALID,
    apply_install,
    find_template_placeholders,
    preview_install,
    resolve_command_template,
    reset_target_cache,
)
from app.services.connection_v2.marketplace_catalog import CATALOG


def _filesystem_entry():
    entry = next((e for e in CATALOG if e.id == "mcp-filesystem"), None)
    assert entry is not None
    return entry


# ──────────────────────────────────────────────────────────────────
# 1. Raw template scan
# ──────────────────────────────────────────────────────────────────


def test_find_template_placeholders_returns_filesystem_token():
    entry = _filesystem_entry()
    tokens = find_template_placeholders(entry.command_template)
    assert "<ALLOWED_ROOT>" in tokens


def test_find_template_placeholders_accepts_both_cases_but_rejects_short_or_non_id():
    # Sprint-9 PR-2 widened the detector to accept both <UPPER> and
    # <lower> tokens so the catalog can use whichever convention is
    # closest to vendor docs (e.g. uvx examples that say
    # "--repository <path>"). The detector still enforces identifier
    # shape (alpha-leading, alnum/_/-) and a min length of 2 so a
    # stray "<a>" or HTML-looking string never registers.
    assert find_template_placeholders("npx -y <lower> <UPPER>") == ["<lower>", "<UPPER>"]
    assert find_template_placeholders("npx --repo <path>") == ["<path>"]
    # Single-char and digit-leading rejected.
    assert find_template_placeholders("echo <a>") == []
    assert find_template_placeholders("echo <2X>") == []
    # Empty / no placeholders.
    assert find_template_placeholders("echo hi") == []


# ──────────────────────────────────────────────────────────────────
# 2. resolve_command_template safety
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", [
    "rm -rf /;",       # ; metachar
    "x | y",           # | metachar
    "x && y",          # & metachar
    "$(whoami)",       # shell expansion
    "${HOME}",         # parameter expansion
    "x\nrm -rf /",     # newline injection
    "<INNER>",         # angle injection (no nested placeholders)
    "back`tick",       # backtick
])
def test_resolve_rejects_unsafe_values(bad):
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>", {"<ALLOWED_ROOT>": bad},
    )
    assert err is not None
    assert err.startswith(FAIL_PLACEHOLDER_VALUE_INVALID)
    assert applied == []


def test_resolve_accepts_simple_path():
    import shlex
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"<ALLOWED_ROOT>": "D:/Ideas/Daena"},
    )
    assert err is None
    assert applied == ["<ALLOWED_ROOT>"]
    # Always shlex.quote -- the round-trip parse is the contract.
    assert shlex.split(out, posix=True) == ["npx", "-y", "pkg", "D:/Ideas/Daena"]


def test_resolve_preserves_windows_backslashes():
    """Windows paths use backslashes; POSIX shlex.split treats those as
    escape chars unless the value is single-quoted. The substitution
    layer MUST quote so the literal path round-trips through shlex."""
    import shlex
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"<ALLOWED_ROOT>": r"D:\Ideas\Daena"},
    )
    assert err is None
    tokens = shlex.split(out, posix=True)
    assert tokens[-1] == r"D:\Ideas\Daena"


def test_resolve_quotes_paths_with_spaces():
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"<ALLOWED_ROOT>": "C:/My Projects/Daena"},
    )
    assert err is None
    assert applied == ["<ALLOWED_ROOT>"]
    # shlex.quote wraps in single quotes for posix; the round-trip
    # parse below proves the result still tokenizes to one arg.
    import shlex
    assert shlex.split(out, posix=True) == [
        "npx", "-y", "pkg", "C:/My Projects/Daena",
    ]


def test_resolve_accepts_bare_key_form():
    """Operator may supply 'ALLOWED_ROOT' instead of '<ALLOWED_ROOT>'."""
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"ALLOWED_ROOT": "D:/x"},
    )
    assert err is None
    assert applied == ["<ALLOWED_ROOT>"]
    assert out.endswith("D:/x")


def test_resolve_empty_value_rejected():
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"<ALLOWED_ROOT>": "   "},
    )
    assert err is not None
    assert err.startswith(FAIL_PLACEHOLDER_VALUE_INVALID)


def test_resolve_no_values_returns_template_unchanged():
    template = "npx -y pkg <ALLOWED_ROOT>"
    out, applied, err = resolve_command_template(template, None)
    assert err is None
    assert out == template
    assert applied == []


def test_resolve_extra_unknown_key_is_ignored():
    """A key the template does not reference must not error -- forms can
    carry stale fields."""
    out, applied, err = resolve_command_template(
        "npx -y pkg <ALLOWED_ROOT>",
        {"<ALLOWED_ROOT>": "D:/x", "<UNUSED>": "ignored"},
    )
    assert err is None
    assert "D:/x" in out
    assert applied == ["<ALLOWED_ROOT>"]


# ──────────────────────────────────────────────────────────────────
# 3. preview_install surfaces unresolved_placeholders ALWAYS
# ──────────────────────────────────────────────────────────────────


def test_preview_without_values_reports_unresolved_placeholder(tmp_path, monkeypatch):
    """First-render path: operator opens the drawer with no values yet.
    The preview must (a) refuse apply, (b) carry the placeholder list
    so the UI knows what input fields to render."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    reset_target_cache()
    entry = _filesystem_entry()
    report = preview_install(
        target="claude_desktop", entry=entry, allow_create=True,
        placeholder_values=None,
    )
    assert report.apply_allowed is False
    assert report.failure_reason is not None
    assert report.failure_reason.startswith(FAIL_PLACEHOLDER_UNRESOLVED)
    assert "<ALLOWED_ROOT>" in report.unresolved_placeholders


def test_preview_with_unsafe_value_reports_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    reset_target_cache()
    entry = _filesystem_entry()
    report = preview_install(
        target="claude_desktop", entry=entry, allow_create=True,
        placeholder_values={"<ALLOWED_ROOT>": "/x; rm -rf /"},
    )
    assert report.apply_allowed is False
    assert report.failure_reason is not None
    assert report.failure_reason.startswith(FAIL_PLACEHOLDER_VALUE_INVALID)
    # Even on rejection the UI still gets the placeholder list so the
    # form re-renders with the same fields.
    assert "<ALLOWED_ROOT>" in report.unresolved_placeholders


# ──────────────────────────────────────────────────────────────────
# 4. preview_install + apply_install happy path with substitution
# ──────────────────────────────────────────────────────────────────


def test_preview_with_resolved_placeholder_reaches_create_action(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    reset_target_cache()
    entry = _filesystem_entry()
    report = preview_install(
        target="claude_desktop", entry=entry, allow_create=True,
        placeholder_values={"<ALLOWED_ROOT>": str(tmp_path)},
    )
    assert report.apply_allowed is True
    assert report.failure_reason is None
    assert report.unresolved_placeholders == []
    assert report.proposed_block is not None
    args = report.proposed_block.get("args", [])
    # The resolved path must appear verbatim in the args list. tmp_path
    # is rendered as a forward-slash string by Path.__str__ on some
    # Windows runs and backslash on others; normalize both sides.
    expected = str(tmp_path)
    assert any(a == expected or a.replace("\\", "/") == expected.replace("\\", "/") for a in args), args


def test_apply_with_resolved_placeholder_writes_substituted_command(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    reset_target_cache()
    entry = _filesystem_entry()
    report = apply_install(
        target="claude_desktop", entry=entry, allow_create=True,
        placeholder_values={"<ALLOWED_ROOT>": str(tmp_path)},
    )
    assert report.action in ("created", "create_file"), report
    assert report.failure_reason is None
    cfg_path = Path(report.config_path)
    assert cfg_path.exists()
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    block = raw.get("mcpServers", {}).get("filesystem")
    assert block is not None, raw
    # The resolved value must end up in the args list -- never the
    # literal placeholder.
    args = block.get("args", [])
    assert "<ALLOWED_ROOT>" not in args
    expected = str(tmp_path)
    assert any(
        a == expected or a.replace("\\", "/") == expected.replace("\\", "/")
        for a in args
    ), args
