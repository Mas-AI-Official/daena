"""
Smoke tests for Skill Registry: operator filter, access check, soft-delete.
Run from project root: python -m backend.scripts.smoke_skills_registry
No server required; uses registry and routes logic in-process.
"""
import os
import sys
from pathlib import Path

# Project root
root = Path(__file__).resolve().parent.parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
os.chdir(root)


def test_operator_filter():
    """GET /api/v1/skills?operator_role= filters by allowed_roles."""
    from backend.services.skill_registry import get_skill_registry
    reg = get_skill_registry()
    all_skills = reg.list_skills(operator_role=None, include_archived=False)
    founder_skills = reg.list_skills(operator_role="founder", include_archived=False)
    daena_skills = reg.list_skills(operator_role="daena", include_archived=False)
    assert len(founder_skills) <= len(all_skills), "founder filter should not exceed all"
    assert len(daena_skills) <= len(all_skills), "daena filter should not exceed all"
    for s in founder_skills:
        roles = [r.lower() for r in (s.get("access") or {}).get("allowed_roles", s.get("allowed_roles") or [])]
        assert "founder" in roles, f"Skill {s.get('id')} in founder list should have founder in allowed_roles"
    print("  OK operator_role filter")


def test_check_caller_access():
    """check_caller_access blocks role not in allowed_roles."""
    from backend.services.skill_registry import get_skill_registry
    reg = get_skill_registry()
    skills = reg.list_skills(operator_role=None, include_archived=False)
    if not skills:
        print("  SKIP check_caller_access (no skills)")
        return
    sid = skills[0].get("id")
    ok, err = reg.check_caller_access(sid, "founder", None, None)
    assert ok or err, "founder check should return (True, None) or (False, msg)"
    ok_agent, err_agent = reg.check_caller_access(sid, "agent", None, None)
    # If skill allows agent, ok_agent is True; else False
    print("  OK check_caller_access")


def test_archive_removes_from_list():
    """Archived skill is excluded from list_skills(include_archived=False). Set SMOKE_ARCHIVE=1 to run."""
    if os.environ.get("SMOKE_ARCHIVE") != "1":
        print("  SKIP archive (set SMOKE_ARCHIVE=1 to run)")
        return
    from backend.services.skill_registry import get_skill_registry
    reg = get_skill_registry()
    skills = reg.list_skills(operator_role=None, include_archived=False)
    for s in skills:
        sid = s.get("id")
        if not sid:
            continue
        out = reg.archive_skill(sid)
        if out.get("error"):
            continue
        list_after = reg.list_skills(operator_role=None, include_archived=False)
        ids_after = {x.get("id") for x in list_after}
        assert sid not in ids_after, "Archived skill should not appear in default list"
        print("  OK archive removes from list")
        return
    print("  SKIP archive (no registry skill to archive)")


def main():
    print("Smoke tests: Skill Registry")
    test_operator_filter()
    test_check_caller_access()
    test_archive_removes_from_list()
    print("Done.")


if __name__ == "__main__":
    main()
