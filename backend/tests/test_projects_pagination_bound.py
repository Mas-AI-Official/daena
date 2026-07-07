"""Guard test for the projects list pagination bound (DEFECT-1 hardening).

``GET /api/v1/projects`` previously declared ``limit: int = 50`` with no
upper bound, so a caller could request an arbitrarily large page
(``?limit=999999999``) and force the service to materialize + ``to_dict``
every owned row. Every sibling list endpoint in the v1 surface bounds its
limit via ``Query(default, ge=..., le=...)`` (house convention, e.g.
``pipeline.py``/``research.py``). This test pins that the projects
endpoint now matches the convention.

Pure introspection -- no DB, auth, or network -- so it runs under the
deterministic Rule-10 oracle. It discriminates the fix: before the fix the
default was a bare ``int`` (50) with no constraint metadata, so the
``isinstance(..., params.Query)`` assertion fails RED.
"""

from __future__ import annotations

import inspect

from fastapi import params

from app.api.v1.projects import list_projects


def _limit_default():
    return inspect.signature(list_projects).parameters["limit"].default


def _constraint(metadata, name):
    """Return the numeric value of the first annotated_types constraint of
    ``name`` (e.g. 'Ge'/'Le') found in a FieldInfo metadata list, else None.
    """
    for m in metadata:
        if type(m).__name__ == name:
            # annotated_types.Ge stores .ge, Le stores .le
            return getattr(m, name.lower(), None)
    return None


def test_list_projects_limit_uses_query():
    """The limit param must be a FastAPI Query (not a bare int) so FastAPI
    enforces validation before the handler runs."""
    default = _limit_default()
    assert isinstance(default, params.Query), (
        "projects list `limit` must be declared as Query(...) so the bound "
        "is enforced; got a bare default instead"
    )


def test_list_projects_limit_is_bounded():
    """The limit must declare both a lower (ge=1) and upper (le=200) bound,
    matching the house pagination convention."""
    default = _limit_default()
    metadata = getattr(default, "metadata", [])
    ge = _constraint(metadata, "Ge")
    le = _constraint(metadata, "Le")
    assert ge == 1, f"projects list `limit` lower bound must be ge=1, got {ge!r}"
    assert le == 200, f"projects list `limit` upper bound must be le=200, got {le!r}"
