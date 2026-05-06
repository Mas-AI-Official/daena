"""Sprint-16 PR-1 -- Gmail draft snapshot contract.

Pins:
  1. The canonical metadata-hash format (sha256 of normalized,
     sort_keys, separators=(",",":"), ensure_ascii=False JSON).
  2. captured_at is EXCLUDED from the hash so wall-clock drift
     doesn't break verification.
  3. Email-shaped fields are normalized (strip + lower) before
     hashing so "Founder@Example.com " hashes the same as
     "founder@example.com".
  4. None and empty-string fields are excluded so absence and
     explicit-empty produce identical hashes.
  5. Hash is stable across key-order permutations of the input dict.
  6. Snapshot extraction from Gmail metadata payload pulls the
     right headers (case-insensitive).
  7. first_drift_field returns the load-bearing-ordered field name
     so the handler can map to a stable refusal code.
"""

from __future__ import annotations

import json

import pytest


def _base_snapshot(**overrides):
    from app.services.gmail_draft_snapshot import GmailDraftSnapshot
    base = dict(
        draft_id="draft-abc",
        owner_email="founder@example.com",
        to="ops@example.com",
        from_value="Founder <founder@example.com>",
        subject="Q3 plan",
        body_snippet="Here's the Q3 plan we discussed.",
        captured_at="2026-05-06T12:00:00+00:00",
        message_id="msg-xyz",
        thread_id="thr-1",
    )
    base.update(overrides)
    return GmailDraftSnapshot(**base)


class TestCanonicalDraftHash:
    def test_format_is_sha256_of_normalized_compact_json(self):
        """Pin the format. Any drift here breaks the audit chain;
        bump format only with a paired regression test."""
        import hashlib

        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        snap = _base_snapshot()
        actual = compute_draft_metadata_hash(snap)

        # Recompute by hand to lock the format.
        expected_dict = {
            "body_snippet": "Here's the Q3 plan we discussed.",
            "draft_id": "draft-abc",
            "from_value": "founder <founder@example.com>",  # lowered
            "message_id": "msg-xyz",
            "owner_email": "founder@example.com",
            "subject": "Q3 plan",
            "thread_id": "thr-1",
            "to": "ops@example.com",
        }
        expected_json = json.dumps(
            expected_dict, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        )
        expected = hashlib.sha256(expected_json.encode("utf-8")).hexdigest()

        assert actual == expected
        assert len(actual) == 64

    def test_captured_at_excluded(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        a = _base_snapshot(captured_at="2026-05-06T12:00:00+00:00")
        b = _base_snapshot(captured_at="2027-01-01T03:14:15+00:00")
        assert compute_draft_metadata_hash(a) == compute_draft_metadata_hash(b)

    def test_email_normalization(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        a = _base_snapshot(owner_email="Founder@Example.com   ")
        b = _base_snapshot(owner_email="founder@example.com")
        assert compute_draft_metadata_hash(a) == compute_draft_metadata_hash(b)

    def test_none_and_empty_excluded(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        a = _base_snapshot(thread_id=None)
        b = _base_snapshot(thread_id="")
        assert compute_draft_metadata_hash(a) == compute_draft_metadata_hash(b)

    def test_dict_key_order_does_not_affect_hash(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        raw = _base_snapshot().to_dict()
        reversed_dict = dict(reversed(list(raw.items())))
        assert compute_draft_metadata_hash(raw) == compute_draft_metadata_hash(reversed_dict)

    def test_subject_change_changes_hash(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        a = _base_snapshot(subject="Q3 plan")
        b = _base_snapshot(subject="Wire $50K to attacker")
        assert compute_draft_metadata_hash(a) != compute_draft_metadata_hash(b)

    def test_to_change_changes_hash(self):
        from app.services.gmail_draft_snapshot import compute_draft_metadata_hash

        a = _base_snapshot(to="ops@example.com")
        b = _base_snapshot(to="attacker@evil.com")
        assert compute_draft_metadata_hash(a) != compute_draft_metadata_hash(b)


class TestSnapshotExtraction:
    def test_build_from_gmail_metadata(self):
        from app.services.gmail_draft_snapshot import (
            build_snapshot_from_gmail_draft,
        )

        gmail_payload = {
            "id": "draft-abc",
            "message": {
                "id": "msg-xyz",
                "threadId": "thr-1",
                "payload": {
                    "headers": [
                        {"name": "To", "value": "ops@example.com"},
                        {"name": "From", "value": "Founder <founder@example.com>"},
                        {"name": "Subject", "value": "Q3 plan"},
                    ],
                },
            },
        }
        snap = build_snapshot_from_gmail_draft(
            draft_meta=gmail_payload,
            owner_email="founder@example.com",
            body_snippet="Here's the plan",
            captured_at="2026-05-06T12:00:00+00:00",
        )
        assert snap.draft_id == "draft-abc"
        assert snap.message_id == "msg-xyz"
        assert snap.thread_id == "thr-1"
        assert snap.to == "ops@example.com"
        assert "founder@example.com" in snap.from_value.lower()
        assert snap.subject == "Q3 plan"
        assert snap.body_snippet == "Here's the plan"
        assert snap.captured_at == "2026-05-06T12:00:00+00:00"

    def test_headers_case_insensitive(self):
        from app.services.gmail_draft_snapshot import (
            build_snapshot_from_gmail_draft,
        )

        gmail_payload = {
            "id": "draft-abc",
            "message": {
                "payload": {
                    "headers": [
                        {"name": "to", "value": "ops@example.com"},
                        {"name": "FROM", "value": "f@x.co"},
                        {"name": "SUBJECT", "value": "S"},
                    ],
                },
            },
        }
        snap = build_snapshot_from_gmail_draft(
            draft_meta=gmail_payload, owner_email="f@x.co",
        )
        assert snap.to == "ops@example.com"
        assert snap.from_value == "f@x.co"
        assert snap.subject == "S"

    def test_missing_headers_become_empty_strings(self):
        from app.services.gmail_draft_snapshot import (
            build_snapshot_from_gmail_draft,
        )

        snap = build_snapshot_from_gmail_draft(
            draft_meta={"id": "draft-x", "message": {"payload": {"headers": []}}},
            owner_email="f@x.co",
        )
        assert snap.to == ""
        assert snap.subject == ""

    def test_body_snippet_truncated(self):
        from app.services.gmail_draft_snapshot import (
            build_snapshot_from_gmail_draft,
        )

        long_body = "x" * 1000
        snap = build_snapshot_from_gmail_draft(
            draft_meta={"id": "d"}, owner_email="f@x.co",
            body_snippet=long_body,
        )
        assert len(snap.body_snippet) == 240


class TestFirstDriftField:
    def test_no_drift_returns_none(self):
        from app.services.gmail_draft_snapshot import first_drift_field

        a = _base_snapshot()
        b = _base_snapshot()  # identical
        assert first_drift_field(approved=a, current=b) is None

    def test_only_captured_at_differs_returns_none(self):
        from app.services.gmail_draft_snapshot import first_drift_field

        a = _base_snapshot(captured_at="2026-05-06T12:00:00+00:00")
        b = _base_snapshot(captured_at="2027-01-01T00:00:00+00:00")
        assert first_drift_field(approved=a, current=b) is None

    def test_to_drift_reported_first(self):
        from app.services.gmail_draft_snapshot import first_drift_field

        a = _base_snapshot()
        b = _base_snapshot(to="attacker@evil.com")
        assert first_drift_field(approved=a, current=b) == "to"

    def test_subject_drift(self):
        from app.services.gmail_draft_snapshot import first_drift_field

        a = _base_snapshot()
        b = _base_snapshot(subject="WIRE $50K")
        assert first_drift_field(approved=a, current=b) == "subject"

    def test_owner_email_takes_priority(self):
        """Even if multiple fields drift, owner_email is reported
        first because it's the most security-relevant."""
        from app.services.gmail_draft_snapshot import first_drift_field

        a = _base_snapshot()
        b = _base_snapshot(
            owner_email="other@x.co",
            to="attacker@evil.com",
            subject="changed",
        )
        assert first_drift_field(approved=a, current=b) == "owner_email"


class TestSnapshotIsFrozen:
    def test_dataclass_frozen(self):
        from dataclasses import FrozenInstanceError

        snap = _base_snapshot()
        with pytest.raises(FrozenInstanceError):
            snap.subject = "tampered"  # type: ignore[misc]
