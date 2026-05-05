"""PR-AUDIT-VIEWER-PLUGIN-FILTER (Sprint-10 PR-5, 2026-05-05).

Source-grep tests pinning the new audit-viewer plugin filter +
plugin-invocation detail panel. The audit page is a thick React
component with a lot of state; rather than spin up an E2E browser
in this PR, we pin the structural invariants in source so a future
refactor that drops the panel / drops the filter / leaks credentials
fails the unit suite immediately.
"""

from __future__ import annotations

from pathlib import Path


_AUDIT_PAGE = (
    Path(__file__).resolve().parents[1].parent
    / "frontend" / "src" / "pages" / "GovernanceAuditPage.tsx"
)


def test_audit_page_exposes_plugin_filter_state():
    src = _AUDIT_PAGE.read_text(encoding="utf-8")
    assert "filterPlugin" in src
    assert "setFilterPlugin" in src
    assert "audit-filter-plugin" in src  # testid for live snapshot


def test_audit_page_filter_implies_plugin_skill_invocation():
    """When filterPlugin is set, the audit list must auto-narrow to
    plugin.skill_invocation rows for that plugin_id. Pinned by the
    literal action_type guard in the filtered useMemo."""
    src = _AUDIT_PAGE.read_text(encoding="utf-8")
    assert "filterPlugin" in src and "plugin.skill_invocation" in src
    # Plugin filter must reference both the action_type AND the
    # plugin_id field so the operator's choice actually narrows.
    assert "plugin_id" in src


def test_audit_page_renders_plugin_invocation_detail_panel():
    """The detail panel for plugin.skill_invocation rows must surface
    the brief-mandated fields: plugin, skill, status, read-only flag,
    audit id."""
    src = _AUDIT_PAGE.read_text(encoding="utf-8")
    assert "audit-detail-plugin-panel" in src
    # The panel renders these literal labels (or close variants).
    assert "Plugin Invocation" in src
    for label in ("Plugin", "Skill", "Status", "Mode", "Audit id"):
        assert label in src, f"missing label {label!r}"


def test_audit_page_hides_plugin_keys_from_generic_dump():
    """Plugin invocation keys are surfaced in the dedicated panel,
    not in the generic 'Additional Details' dump (which would
    duplicate). Pinned by the shownKeys allowlist."""
    src = _AUDIT_PAGE.read_text(encoding="utf-8")
    # The shownKeys Set must include plugin_id / skill_id / outcome /
    # read_only so the generic Additional Details renderer skips them.
    for key in ("plugin_id", "skill_id", "outcome", "read_only"):
        assert f"'{key}'" in src, f"shownKeys missing {key!r}"


def test_audit_page_no_secret_render():
    """Defense-in-depth: the audit page source must not render any of
    the credential field names. The audit row's action_params
    technically could carry a key with that name; we never want it
    surfaced visually."""
    src = _AUDIT_PAGE.read_text(encoding="utf-8")
    # The page should never include logic that pulls these field
    # names out of params for display. Source-grep: a future PR
    # adding ``params.access_token`` to the visible render block
    # would fail.
    forbidden_renderers = (
        "params.access_token", "params.refresh_token",
        "params.api_key", "params.client_secret",
        "params.bearer", "params.password",
    )
    for r in forbidden_renderers:
        assert r not in src, (
            f"audit page renders a credential-shaped field: {r!r}"
        )
