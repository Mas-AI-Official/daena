"""PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH (Sprint-9 PR-2).

Pins the deterministic readiness classifier over the marketplace catalog
+ the Filesystem regression that the audit relies on.

Hard guarantees:

  1. The classifier returns exactly one ReadinessRow per catalog entry.
  2. Every row's status is one of the six declared values; no broken /
     None / unknown leaks.
  3. The Filesystem MCP row stays at status=needs_placeholder with
     <ALLOWED_ROOT> in placeholders_required AND
     execution_path_exists=True. This is the local-beta acceptance
     anchor; if it slides back, Sprint-8 PR-1 + PR-3 are broken.
  4. PHASE2_ALLOWLIST has zero non-read-only entries (Phase 3 floor).
  5. The audit's status mix matches the operator's expectation: at
     least one ready_to_install (proves easy local MCPs are honestly
     surfaced) and zero "broken" (a broken catalog row would mean a
     malformed install command landed without anyone noticing).
  6. Every "ready_to_install" entry can be subjected to install
     preview without error -- the gate the operator hits in the UI.
"""

from __future__ import annotations

import pytest

from app.services.connection_v2.cli_mcp_writer import (
    find_template_placeholders,
    parse_command_template,
    preview_install,
)
from app.services.connection_v2.marketplace_catalog import CATALOG
from app.services.connection_v2.readiness_audit import (
    audit_catalog,
    classify_entry,
    render_markdown_table,
    status_counts,
)


# ──────────────────────────────────────────────────────────────────
# 1. Audit covers every catalog entry, no broken rows
# ──────────────────────────────────────────────────────────────────


def test_audit_covers_every_catalog_entry():
    rows = audit_catalog()
    assert len(rows) == len(CATALOG), (
        f"audit row count {len(rows)} != catalog size {len(CATALOG)}"
    )
    seen = {r.plugin_id for r in rows}
    expected = {e.id for e in CATALOG}
    assert seen == expected


def test_audit_has_no_broken_or_unknown_status_rows():
    """A 'broken' row in the catalog means a malformed install command
    landed. The audit must not surface any -- that's a real bug, not
    just a UX wrinkle. Test enforces zero tolerance."""
    rows = audit_catalog()
    broken = [r for r in rows if r.status == "broken"]
    assert broken == [], (
        f"catalog has broken rows: {[(r.plugin_id, r.rationale) for r in broken]}"
    )
    valid_statuses = {
        "ready_to_install", "needs_token", "needs_placeholder",
        "setup_guide_only", "coming_soon", "broken",
    }
    for r in rows:
        assert r.status in valid_statuses, (
            f"{r.plugin_id} has invalid status {r.status!r}"
        )


# ──────────────────────────────────────────────────────────────────
# 2. Filesystem regression (anchor for local-beta acceptance)
# ──────────────────────────────────────────────────────────────────


def test_filesystem_remains_needs_placeholder_with_executable_path():
    """The local-beta acceptance pivot. If Filesystem stops being
    classified as needs_placeholder OR loses execution_path_exists,
    Sprint-8 PR-1+PR-3 are silently broken."""
    rows = audit_catalog()
    fs = next(r for r in rows if r.plugin_id == "mcp-filesystem")
    assert fs.status == "needs_placeholder", fs.rationale
    assert "<ALLOWED_ROOT>" in fs.placeholders_required
    assert fs.execution_path_exists is True, (
        "Filesystem must keep its mcp_tool execution path armed; "
        "if this fails, find_files would silently regress to planned-only"
    )
    assert fs.probe_implementation_exists is True


# ──────────────────────────────────────────────────────────────────
# 3. Phase 3 floor still holds (writes blocked)
# ──────────────────────────────────────────────────────────────────


def test_phase3_writes_floor_holds_through_audit():
    from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST
    write_entries = [e for e in PHASE2_ALLOWLIST if not e.read_only]
    assert write_entries == [], (
        "Phase 3 leak: PHASE2_ALLOWLIST contains non-read-only entries: "
        f"{[(e.plugin_id, e.skill_id) for e in write_entries]}"
    )


# ──────────────────────────────────────────────────────────────────
# 4. Status mix is honest
# ──────────────────────────────────────────────────────────────────


def test_audit_has_at_least_one_ready_to_install_entry():
    """If no entry classifies as ready_to_install, either the catalog
    has zero zero-config MCPs (which would make the local-beta unfair)
    OR the classifier is misbehaving."""
    rows = audit_catalog()
    ready = [r for r in rows if r.status == "ready_to_install"]
    assert len(ready) >= 1, (
        "no ready_to_install entries -- the operator has nothing to "
        "one-click install. Investigate the classifier or catalog."
    )


def test_audit_includes_known_zero_input_mcps():
    """The catalog has well-known one-click MCPs (mcp-time, mcp-fetch,
    mcp-memory, mcp-sequential-thinking). Pin them so a future catalog
    edit that accidentally adds env vars / placeholders to them gets
    caught."""
    rows = audit_catalog()
    by_id = {r.plugin_id: r for r in rows}
    for pid in ("mcp-time", "mcp-fetch", "mcp-memory", "mcp-sequential-thinking"):
        assert by_id[pid].status == "ready_to_install", (
            f"{pid} should be ready_to_install but is {by_id[pid].status!r}: "
            f"{by_id[pid].rationale}"
        )


def test_audit_renders_markdown_table_with_every_entry():
    rows = audit_catalog()
    table = render_markdown_table(rows)
    for row in rows:
        assert row.plugin_id in table


# ──────────────────────────────────────────────────────────────────
# 5. Ready-to-install entries can actually preview a Claude Desktop
#    install without error -- the gate the operator hits in the UI.
# ──────────────────────────────────────────────────────────────────


def test_every_ready_to_install_entry_previews_cleanly(tmp_path, monkeypatch):
    """Sanity: classifier and writer must agree. If the classifier
    says 'ready_to_install' but preview_install rejects the entry,
    the operator clicks Install and gets a 422 -- worst possible UX."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from app.services.connection_v2.cli_mcp_writer import reset_target_cache
    reset_target_cache()

    rows = audit_catalog()
    ready = [r for r in rows if r.status == "ready_to_install"]
    catalog_by_id = {e.id: e for e in CATALOG}
    for r in ready:
        entry = catalog_by_id[r.plugin_id]
        report = preview_install(
            target="claude_desktop", entry=entry, allow_create=True,
        )
        assert report.failure_reason is None, (
            f"{r.plugin_id} classified ready_to_install but preview failed: "
            f"{report.failure_reason}"
        )
        assert report.apply_allowed is True, (
            f"{r.plugin_id} preview said apply_allowed=False: "
            f"action={report.action!r}"
        )


# ──────────────────────────────────────────────────────────────────
# 6. classify_entry is pure (no I/O, deterministic)
# ──────────────────────────────────────────────────────────────────


def test_classify_entry_is_deterministic():
    entry = next(e for e in CATALOG if e.id == "mcp-filesystem")
    a = classify_entry(entry)
    b = classify_entry(entry)
    assert a == b


# ──────────────────────────────────────────────────────────────────
# 7. Improved failure messages on probe (Sprint-9 PR-2 polish)
# ──────────────────────────────────────────────────────────────────


def test_probe_binary_not_found_message_actions_npx_and_uvx():
    """The probe's binary-not-found path must spell out what to install
    so the operator isn't left guessing. We pin the message bodies in
    source so a future copy edit can't silently revert."""
    from pathlib import Path
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "services" / "connection_v2" / "probes" / "mcp_server_probe.py"
    ).read_text(encoding="utf-8")
    assert "Install Node.js" in src and "npx is on PATH" in src
    assert "Install uv" in src or "uvx is on PATH" in src
    assert "Install Docker" in src


def test_probe_initialize_timeout_message_suggests_retry():
    from pathlib import Path
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "services" / "connection_v2" / "probes" / "mcp_server_probe.py"
    ).read_text(encoding="utf-8")
    # The timeout copy must point at the warm-up path so the operator
    # retries instead of assuming the MCP is broken.
    assert "first run" in src or "warming" in src.lower()
    assert "retry" in src.lower()
