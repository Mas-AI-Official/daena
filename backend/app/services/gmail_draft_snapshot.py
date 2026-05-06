"""Gmail Draft Snapshot Contract -- Sprint-16 PR-1 (2026-05-06).

Closes the draft-edit-after-approval gap.

The Sprint-15 send hash binds ``{draft_id, owner_email}`` only.
That blocks wrong-draft-id and wrong-account substitution but does
NOT block content mutation between approval and dispatch -- if
someone (or the operator) edits the draft in Gmail AFTER approval,
the original send hash still matches and the modified content
flies.

This module defines the snapshot contract:

  1. At send-approval CREATION time (server-side, NOT in the
     modal), capture a Gmail draft snapshot via Gmail's
     ``GET /drafts/{id}?format=metadata`` and store it on the
     GoaRequest's ``action_params['draft_snapshot']``.
  2. At send DISPATCH time, the handler re-fetches the draft, re-
     computes the snapshot, and refuses if any field drifted.

The canonical metadata hash is LOCKED. Sprint-15's
``compute_payload_hash`` proves the same payload was approved that
is being dispatched; Sprint-16's ``compute_draft_metadata_hash``
proves the same DRAFT was approved that is being SENT.

Snapshot fields
---------------

::

    draft_id              -> Gmail's draft id (the one approved)
    owner_email           -> normalized (strip + lower)
    message_id            -> Gmail's message id INSIDE the draft
                             (omitted when not yet assigned)
    thread_id             -> Gmail's thread id (omitted when missing)
    to                    -> normalized recipient
    from_value            -> normalized From: header (display + email)
    subject               -> exact subject (no normalization to
                             preserve operator-visible diffs)
    body_snippet          -> first 240 chars of plain text body, or
                             empty string when not retrievable
    captured_at           -> ISO-8601 UTC timestamp of the snapshot

The hash covers EVERYTHING above except ``captured_at`` (a
timestamp would always drift; the hash protects against content
drift, not time drift).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


# ── Snapshot dataclass ───────────────────────────────────────────────


@dataclass(frozen=True)
class GmailDraftSnapshot:
    """Captured at send-approval creation; verified at dispatch.

    All fields must be JSON-serializable so the snapshot can live
    inside ``GoaRequest.action_params``. The ``draft_metadata_hash``
    is computed from this dataclass and is the load-bearing
    invariant -- if any field drifts between approval and send,
    the hash differs and the dispatcher refuses.
    """

    draft_id: str
    owner_email: str
    to: str
    from_value: str
    subject: str
    body_snippet: str
    captured_at: str
    message_id: str | None = None
    thread_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in asdict(self).items()
            if v is not None or k in {"captured_at"}
        }


# ── Canonical metadata-hash format (LOCKED) ──────────────────────────


_HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset({"captured_at"})


def compute_draft_metadata_hash(snapshot: GmailDraftSnapshot | dict) -> str:
    """Locked canonical hash format.

    Steps:
      1. Coerce to dict.
      2. Drop the ``captured_at`` field (it's wall-clock time, would
         always drift).
      3. Lower-case + strip whitespace on the email-shaped fields
         (``owner_email``, ``to``, ``from_value``).
      4. Drop None / empty-string fields so missing-vs-explicit-empty
         don't produce different hashes for equivalent state.
      5. ``json.dumps(..., sort_keys=True, separators=(",", ":"),
         ensure_ascii=False)``.
      6. sha256 of UTF-8 bytes.

    The format is contract-pinned by
    ``TestCanonicalDraftHash::test_format_is_sha256_of_normalized_compact_json``.
    Any drift breaks the audit chain. Bump format only with a paired
    regression test.
    """
    if isinstance(snapshot, GmailDraftSnapshot):
        raw = snapshot.to_dict()
    else:
        raw = dict(snapshot)

    # Strip excluded fields.
    for k in _HASH_EXCLUDED_FIELDS:
        raw.pop(k, None)

    # Normalize email-shaped fields.
    for email_field in ("owner_email", "to", "from_value"):
        if email_field in raw and isinstance(raw[email_field], str):
            raw[email_field] = raw[email_field].strip().lower()

    # Drop None and empty-string values so absent and explicit-empty
    # produce the same hash.
    cleaned = {
        k: v
        for k, v in raw.items()
        if v is not None and v != ""
    }

    canonical = json.dumps(
        cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Snapshot extraction from Gmail's metadata payload ────────────────


def _extract_header(headers: list[dict], name: str) -> str:
    """Pull a header value by name (case-insensitive). Empty string
    when absent."""
    target = name.lower()
    for h in headers:
        if (h.get("name") or "").lower() == target:
            return (h.get("value") or "").strip()
    return ""


def build_snapshot_from_gmail_draft(
    *,
    draft_meta: dict,
    owner_email: str,
    body_snippet: str = "",
    captured_at: str | None = None,
) -> GmailDraftSnapshot:
    """Build a snapshot from a Gmail ``GET /drafts/{id}`` response.

    ``draft_meta`` is the full response body. ``body_snippet`` is
    optional (the snapshotter may compute a snippet from a separate
    ``format=full`` fetch; the contract supports omitting it for
    metadata-only paths).

    The snapshot is FROZEN once built -- any future drift becomes a
    refusal at dispatch.
    """
    captured = captured_at or datetime.now(UTC).isoformat()

    message = draft_meta.get("message", {}) or {}
    payload = message.get("payload", {}) or {}
    headers = payload.get("headers", []) or []

    return GmailDraftSnapshot(
        draft_id=str(draft_meta.get("id") or ""),
        owner_email=(owner_email or "").strip().lower(),
        message_id=str(message.get("id")) if message.get("id") else None,
        thread_id=str(message.get("threadId")) if message.get("threadId") else None,
        to=_extract_header(headers, "To"),
        from_value=_extract_header(headers, "From"),
        subject=_extract_header(headers, "Subject"),
        body_snippet=(body_snippet or "").strip()[:240],
        captured_at=captured,
    )


# ── Comparison helpers ───────────────────────────────────────────────


def first_drift_field(
    *, approved: GmailDraftSnapshot | dict, current: GmailDraftSnapshot | dict,
) -> str | None:
    """Return the FIRST drifted field name between approved and
    current snapshots, or None if hashes match.

    Order matters for refusal codes -- the handler maps each field
    name to a stable code (e.g. ``draft_recipient_mismatch``,
    ``draft_subject_mismatch``). The order below is the order the
    handler reports.
    """
    if compute_draft_metadata_hash(approved) == compute_draft_metadata_hash(current):
        return None

    a = approved.to_dict() if isinstance(approved, GmailDraftSnapshot) else dict(approved)
    c = current.to_dict() if isinstance(current, GmailDraftSnapshot) else dict(current)

    # Normalize for comparison.
    for fld in ("owner_email", "to", "from_value"):
        if fld in a and isinstance(a[fld], str):
            a[fld] = a[fld].strip().lower()
        if fld in c and isinstance(c[fld], str):
            c[fld] = c[fld].strip().lower()

    # Order is load-bearing for refusal-code mapping.
    for field_name in (
        "owner_email",
        "to",
        "subject",
        "from_value",
        "draft_id",
        "message_id",
        "thread_id",
        "body_snippet",
    ):
        if a.get(field_name) != c.get(field_name):
            return field_name
    # Hashes differed but no field above caught it -- shouldn't
    # happen with the current schema, but surface a generic mismatch.
    return "metadata_hash"
