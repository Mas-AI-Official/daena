"""Sprint-13 PR-4 -- draft action factory contract.

Pins:
  1. ActionDraftKind set is closed (10 entries).
  2. suggested_action_drafts covers every opportunity_type in
     research_flow.ALLOWED_OPPORTUNITY_TYPES.
  3. Each suggested draft has EXACTLY the locked key set: no
     send/submit/apply/post/publish/pay field ever appears.
  4. Every draft is requires_approval=True and delivery="manual_only"
     -- the "Daena proposes; never auto-executes" rule.
  5. Unknown opportunity_type returns an empty list (no raise).
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


# Forbidden field-name patterns. Matched against the exact key
# (lowercased). "pay" alone is too greedy -- it matches "payload_hash"
# and other legitimate names; the action verbs we want to forbid are
# pay_, payment, _send, _submit, etc. -- never as a substring of an
# unrelated noun like "payload".
_FORBIDDEN_EXACT = {
    "send",
    "submit",
    "apply",
    "publish",
    "pay",
    "payment",
    "post",
}
_FORBIDDEN_PREFIXES = ("send_", "submit_", "apply_", "publish_", "pay_", "post_to_")
_FORBIDDEN_SUFFIXES = ("_send", "_submit", "_apply", "_publish", "_post")


class TestActionKindsClosed:
    async def test_kinds_locked(self):
        from app.services.draft_action_factory import _OPPORTUNITY_TYPE_TO_ACTIONS

        # Collect every action kind used.
        kinds: set[str] = set()
        for triples in _OPPORTUNITY_TYPE_TO_ACTIONS.values():
            for k, _, _ in triples:
                kinds.add(k)

        expected = {
            "cold_email",
            "linkedin_msg",
            "grant_application",
            "hackathon_entry",
            "customer_proposal",
            "bounty_report",
            "partnership_pitch",
            "rfp_response",
            "content_brief",
            "program_application",
        }
        # Some kinds may not be reachable from any opportunity_type
        # in the v1 map (e.g. linkedin_msg is reachable from customer
        # only). The test asserts the set we use is a SUBSET of the
        # locked vocabulary, not equality.
        unknown = kinds - expected
        assert not unknown, f"unexpected action kinds: {sorted(unknown)}"


class TestCoverage:
    async def test_every_opportunity_type_has_actions(self):
        from app.services.draft_action_factory import suggested_action_drafts
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        for opp_type in ALLOWED_OPPORTUNITY_TYPES:
            drafts = suggested_action_drafts(opp_type)
            assert drafts, (
                f"opportunity_type {opp_type!r} has no suggested actions"
            )

    async def test_unknown_opportunity_type_returns_empty(self):
        from app.services.draft_action_factory import suggested_action_drafts

        assert suggested_action_drafts("not_a_real_type") == []


class TestLockedShape:
    async def test_keys_locked(self):
        from app.services.draft_action_factory import (
            _LOCKED_ACTION_KEYS,
            suggested_action_drafts,
        )
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        for opp_type in ALLOWED_OPPORTUNITY_TYPES:
            for draft in suggested_action_drafts(opp_type):
                actual = set(draft.keys())
                assert actual == _LOCKED_ACTION_KEYS, (
                    f"draft for {opp_type!r} has wrong keys: "
                    f"got {sorted(actual)}, want {sorted(_LOCKED_ACTION_KEYS)}"
                )

    async def test_no_forbidden_field_names(self):
        from app.services.draft_action_factory import suggested_action_drafts
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        for opp_type in ALLOWED_OPPORTUNITY_TYPES:
            for draft in suggested_action_drafts(opp_type):
                for key in draft.keys():
                    lowered = key.lower()
                    bad = (
                        lowered in _FORBIDDEN_EXACT
                        or any(lowered.startswith(p) for p in _FORBIDDEN_PREFIXES)
                        or any(lowered.endswith(s) for s in _FORBIDDEN_SUFFIXES)
                    )
                    assert not bad, (
                        f"draft action factory leaked forbidden "
                        f"field name: {key} (opportunity_type={opp_type})"
                    )

    async def test_every_draft_requires_approval(self):
        from app.services.draft_action_factory import suggested_action_drafts
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        for opp_type in ALLOWED_OPPORTUNITY_TYPES:
            for draft in suggested_action_drafts(opp_type):
                assert draft["requires_approval"] is True, (
                    f"draft {draft['id']} not requires_approval; "
                    "the 'Daena proposes; never auto-executes' rule "
                    "is encoded as a locked field, not a default."
                )
                assert draft["delivery"] == "manual_only", (
                    f"draft {draft['id']} has delivery={draft['delivery']!r}; "
                    "every action draft must be manual_only -- there is "
                    "no automated send path here."
                )
                assert draft["payload_hash"] is None, (
                    f"draft {draft['id']} carries a payload_hash; that "
                    "field belongs to Phase 3 wiring, not the suggestion."
                )


class TestStableIds:
    async def test_id_is_opportunity_type_colon_kind(self):
        from app.services.draft_action_factory import suggested_action_drafts

        drafts = suggested_action_drafts("grant")
        for d in drafts:
            assert d["id"].startswith("grant:")
            kind_after_colon = d["id"].split(":", 1)[1]
            assert kind_after_colon == d["kind"]
