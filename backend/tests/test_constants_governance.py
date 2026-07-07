"""Unit coverage for the pure RBAC + governance helpers in app.core.constants.

These four contracts live in the live governance/authorization decision path
(``resolve_governance_tier`` is called from governance.py and
query_understanding.py; ``UserRole.has_access`` is the RBAC primitive) yet had
NO direct test:

  * ``UserRole.has_access`` / ``UserRole.level`` -- the privilege-ordering
    comparison. grep over tests/ found zero references.
  * ``GovernanceSlider.to_governance_mode`` -- the deprecated-slider ->
    canonical-mode mapping. Only a *comment* mentions it
    (test_settings_governance_guard.py:70); the mapping itself is unasserted.
  * ``resolve_governance_tier``'s ``legacy_slider`` conversion branch -- the
    function-specific logic that sits ON TOP of GOVERNANCE_TIER_MAP. The MAP's
    values are already pinned by test_control_combinations.py and the
    UNLEASHED+CRITICAL regression by test_permission_resolver.py, so this file
    deliberately does NOT re-assert them -- only the wrapper branches the MAP
    tests cannot reach.

Each assertion fails for a concrete, named regression (see per-test comments),
so none is a tautology / change-detector on an arbitrary constant.
"""

from __future__ import annotations

import pytest

from app.core.constants import (
    GovernanceMode,
    GovernanceSlider,
    RiskLevel,
    UserRole,
    resolve_governance_tier,
)


# -- UserRole RBAC ordering -------------------------------------------


class TestUserRoleAccess:
    """``has_access`` is ``self.level >= required.level``. The ordering of
    the six roles encodes the privilege hierarchy: a wrong order or a wrong
    comparison operator is a real authorization defect."""

    def test_higher_role_meets_lower_requirement(self):
        # ADMIN (5) clears an OPERATOR (3) gate.
        assert UserRole.ADMIN.has_access(UserRole.OPERATOR) is True

    def test_lower_role_fails_higher_requirement(self):
        # VIEWER (2) must NOT clear an ADMIN (5) gate. RED if the level map
        # is reordered so a read-only role outranks a privileged one.
        assert UserRole.VIEWER.has_access(UserRole.ADMIN) is False

    def test_equal_role_meets_requirement(self):
        # The >= boundary: a role exactly meeting its own requirement passes.
        # RED if ``>=`` is ever weakened to ``>`` -- which would lock every
        # role out of resources gated at its own level.
        assert UserRole.OPERATOR.has_access(UserRole.OPERATOR) is True

    def test_levels_are_strictly_monotonic(self):
        # The documented hierarchy AUDITOR < VIEWER < OPERATOR < MANAGER <
        # ADMIN < FOUNDER must be strictly increasing. Asserting the
        # invariant (sorted + all-distinct) rather than the literal ints
        # 1..6 keeps this from being a brittle change-detector while still
        # going RED if any two roles are reordered or collide on a level.
        levels = [
            UserRole.AUDITOR.level,
            UserRole.VIEWER.level,
            UserRole.OPERATOR.level,
            UserRole.MANAGER.level,
            UserRole.ADMIN.level,
            UserRole.FOUNDER.level,
        ]
        assert levels == sorted(levels)
        assert len(set(levels)) == len(levels)


# -- GovernanceSlider backward-compat mapping -------------------------


class TestSliderToGovernanceMode:
    """The deprecated 5-level slider must collapse to the right 3-mode
    value. A wrong mapping is a silent governance MISCLASSIFICATION -- e.g.
    a stored PARANOID session resolving to UNLEASHED would downgrade a
    user who explicitly chose the strictest setting."""

    @pytest.mark.parametrize(
        "slider, expected",
        [
            (GovernanceSlider.YOLO, GovernanceMode.UNLEASHED),
            (GovernanceSlider.LIGHT, GovernanceMode.BALANCED),
            (GovernanceSlider.STANDARD, GovernanceMode.BALANCED),
            (GovernanceSlider.STRICT, GovernanceMode.GOVERNED),
            (GovernanceSlider.PARANOID, GovernanceMode.GOVERNED),
            # Forward-compat identity: resolve_governance_tier's skip-guard
            # relies on the canonical names round-tripping to themselves.
            (GovernanceSlider.UNLEASHED, GovernanceMode.UNLEASHED),
        ],
    )
    def test_legacy_slider_maps_to_mode(self, slider, expected):
        assert slider.to_governance_mode() is expected

    def test_strict_sliders_never_downgrade_to_unleashed(self):
        # The security-ordering invariant the mapping exists to protect:
        # the two strictest legacy values must land on the most restrictive
        # mode, never the permissive one. RED if either is remapped down.
        assert GovernanceSlider.STRICT.to_governance_mode() is GovernanceMode.GOVERNED
        assert GovernanceSlider.PARANOID.to_governance_mode() is GovernanceMode.GOVERNED


# -- resolve_governance_tier wrapper branches -------------------------


class TestResolveGovernanceTierLegacySlider:
    """Branch coverage for the parts of ``resolve_governance_tier`` that sit
    on top of GOVERNANCE_TIER_MAP. The MAP cell values are already pinned
    elsewhere; these tests exercise the legacy_slider seam exclusively."""

    def test_plain_lookup_delegates_to_map(self):
        # No legacy_slider: the function is a thin pass-through to the MAP.
        # GOVERNED x MEDIUM is 2 (see constants.py). RED if the delegation
        # or the final ``tier_map.get(risk, 0)`` lookup breaks.
        assert resolve_governance_tier(GovernanceMode.GOVERNED, RiskLevel.MEDIUM) == 2

    def test_legacy_slider_overrides_passed_mode(self):
        # YOLO is a legacy slider (not a canonical name), so it converts to
        # UNLEASHED and OVERRIDES the GOVERNED arg. UNLEASHED x HIGH is 0,
        # whereas GOVERNED x HIGH is 3 -- so a result of 0 proves the
        # conversion branch actually fired. RED if the conversion branch is
        # dropped (would return 3, the un-converted GOVERNED tier).
        tier = resolve_governance_tier(
            GovernanceMode.GOVERNED, RiskLevel.HIGH, legacy_slider="YOLO"
        )
        assert tier == 0

    def test_unknown_slider_is_swallowed_and_passed_mode_wins(self):
        # An unrecognized slider string makes ``GovernanceSlider(...)`` raise
        # ValueError; the ``except ValueError: pass`` must swallow it and fall
        # back to the explicitly-passed governance_mode. GOVERNED x HIGH = 3.
        # RED if the try/except is removed (the call would raise) or if a bad
        # slider silently degraded the mode.
        tier = resolve_governance_tier(
            GovernanceMode.GOVERNED, RiskLevel.HIGH, legacy_slider="NOT_A_REAL_SLIDER"
        )
        assert tier == 3
