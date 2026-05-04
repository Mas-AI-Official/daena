"""PR-CONN-RUN-FIRST-READONLY-SKILL-FLOW (Sprint-7 PR-4) tests.

Pins the FirstSkillRunBlock <-> Phase 2 allowlist contract:

  1. ``mcp-filesystem`` + ``find_files`` is in the Phase 2 allowlist
     and is read-only. The hero block hard-codes this pair; if anyone
     ever flips its read_only flag or removes it, this test fires.
  2. The component file:
       - lives at the expected path
       - hard-codes the Filesystem -> find_files mapping
       - never bypasses the SkillExecuteModal confirmation
       - never auto-fills folder paths from anywhere outside the modal
       - carries the data-testid hooks the integration smoke expects
  3. The PluginDetailDrawer renders the block.
"""

from __future__ import annotations

from pathlib import Path

from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST


REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCK = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "FirstSkillRunBlock.tsx"
)
DRAWER = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "PluginDetailDrawer.tsx"
)


# ──────────────────────────────────────────────────────────────────
# 1. find_files is allowlisted + read-only
# ──────────────────────────────────────────────────────────────────


def test_find_files_is_phase2_allowlisted():
    """The hero block hard-codes (mcp-filesystem, find_files). If the
    backend allowlist drops it, the hero block would render but fail
    at execute time -- catch the drift here."""
    matches = [
        e for e in PHASE2_ALLOWLIST
        if e.plugin_id == "mcp-filesystem" and e.skill_id == "find_files"
    ]
    assert len(matches) == 1, (
        f"(mcp-filesystem, find_files) must be allowlisted exactly once; "
        f"found {len(matches)}"
    )


def test_find_files_is_read_only():
    """Phase 2 floor: the executor's read_only defense rejects
    non-read-only entries. The hero block surfaces find_files as
    read-only -- catalog must agree."""
    fs = next(
        e for e in PHASE2_ALLOWLIST
        if e.plugin_id == "mcp-filesystem" and e.skill_id == "find_files"
    )
    assert fs.read_only is True, (
        "find_files must be read_only=True (Sprint-6 PR-5 invariant)"
    )


# ──────────────────────────────────────────────────────────────────
# 2. Component file shape + safety
# ──────────────────────────────────────────────────────────────────


def test_block_hard_codes_filesystem_to_find_files():
    src = BLOCK.read_text(encoding="utf-8")
    assert "'mcp-filesystem'" in src or '"mcp-filesystem"' in src
    assert "'find_files'" in src or '"find_files"' in src


def test_block_uses_phase2_modal_for_actual_run():
    """The block must NOT bypass SkillExecuteModal -- that modal carries
    the no-writes/no-deletes/no-external confirmation that gives the
    operator informed consent."""
    src = BLOCK.read_text(encoding="utf-8")
    assert "import SkillExecuteModal" in src
    assert "<SkillExecuteModal" in src


def test_block_never_auto_fills_inputs():
    """The Sprint-7 brief: 'User chooses folder/path input.' The hero
    block must NOT prefill required_inputs with anything."""
    src = BLOCK.read_text(encoding="utf-8")
    forbidden = (
        # If a future regression tries to push a path into the modal:
        "process.cwd",
        "homedir",
        "os.tmpdir",
        # localStorage / sessionStorage as a sneaky prefill source:
        "localStorage.getItem(",
        "sessionStorage.getItem(",
        # A direct API call that fabricates a "default folder":
        "api.post(",
        "api.get(",
    )
    for needle in forbidden:
        assert needle not in src, (
            f"FirstSkillRunBlock.tsx leaks a prefill source: {needle!r}"
        )


def test_block_carries_test_ids():
    src = BLOCK.read_text(encoding="utf-8")
    assert 'data-testid="first-skill-run-block"' in src
    assert 'data-testid="first-skill-run-button"' in src
    # Locked variant for the not-callable path.
    assert 'data-testid="first-skill-run-block-locked"' in src


def test_block_handles_not_callable_path_honestly():
    """When plugin is recognized but not callable, the block shows a
    'almost there' hint instead of a fake Run button."""
    src = BLOCK.read_text(encoding="utf-8")
    # The 'almost there' copy or equivalent must exist in the locked branch.
    assert "almost there" in src.lower(), (
        "locked variant must surface that the plugin is not yet callable"
    )


# ──────────────────────────────────────────────────────────────────
# 3. PluginDetailDrawer renders the block
# ──────────────────────────────────────────────────────────────────


def test_drawer_renders_first_skill_run_block():
    src = DRAWER.read_text(encoding="utf-8")
    assert "import FirstSkillRunBlock" in src
    assert "<FirstSkillRunBlock" in src
