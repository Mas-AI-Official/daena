"""Sprint-16 PR-4 -- Safe First Live Send Drill.

Operator-run end-to-end proof that the Gmail draft create -> fetch
-> send-existing-draft path actually works against Google's live
API with real OAuth credentials. The drill is GATED OFF by default
so CI / regression runs never trigger an external send.

To run:

  $env:DAENA_ENABLE_LIVE_SEND_SMOKE = "true"
  $env:DAENA_LIVE_SEND_ACCESS_TOKEN = "<OAuth access token>"
  $env:DAENA_LIVE_SEND_OWNER_EMAIL  = "masoud.masoori@mas-ai.co"
  $env:DAENA_LIVE_SEND_RECIPIENT    = "masoud.masoori@mas-ai.co"
  cd D:/Ideas/Daena/backend
  .venv/Scripts/python.exe -m pytest tests/test_live_send_drill.py -v -s

What this drill does:

  1. Refuses to run without the env flag (skip).
  2. Refuses if recipient is not in the allowlist
     (founder + agent emails only).
  3. Creates a Gmail draft addressed to the allowlisted recipient.
  4. Fetches the draft back with format=metadata.
  5. Builds a snapshot (the same one a send-approval would carry).
  6. Calls GmailClient.send_existing_draft(draft_id).
  7. Asserts a message_id comes back.
  8. Logs ONLY success boolean + message_id length -- no body, no
     recipient echo, no token.

Hard rules (locked into this test):

  * DAENA_ENABLE_LIVE_SEND_SMOKE must be exactly the string "true"
    (any other value, including "1", "yes", "TRUE", skips).
  * Recipient MUST be in ALLOWED_RECIPIENTS.
  * NO bulk loop. The drill sends EXACTLY ONE draft.
  * NO attachments.
  * NO arbitrary subject / body -- copy is fixed in this file.
  * NO retry on send failure -- one shot, log result, exit.
"""

from __future__ import annotations

import logging
import os

import pytest

logger = logging.getLogger(__name__)


# Allowlist: only these recipients are allowed for the live drill.
# Pinned per Sprint-16 brief and CLAUDE.md two-account contract.
ALLOWED_RECIPIENTS: frozenset[str] = frozenset({
    "masoud.masoori@mas-ai.co",
    "daena@mas-ai.co",
})


# Fixed copy. The drill is not a content test; the subject and body
# are deliberately uninteresting so any real-content tampering is
# the operator's responsibility to detect.
DRILL_SUBJECT = "[Daena Sprint-16 Live Send Drill]"
DRILL_BODY = (
    "This is an automated end-to-end test run by the Daena Sprint-16 "
    "live send drill. If you received this, Daena's controlled-"
    "execution send path is working against live Gmail OAuth. "
    "No follow-up needed."
)


def _drill_enabled() -> bool:
    """The drill ONLY runs when the env flag is the EXACT string
    'true'. Any other value (including '1', 'yes') skips."""
    return os.environ.get("DAENA_ENABLE_LIVE_SEND_SMOKE") == "true"


def _allowlisted_recipient() -> str | None:
    """Pull the recipient from env; return None if missing or not
    on the allowlist. The test gate refuses to send to anything off
    the list."""
    recipient = (os.environ.get("DAENA_LIVE_SEND_RECIPIENT") or "").strip().lower()
    if recipient and recipient in ALLOWED_RECIPIENTS:
        return recipient
    return None


@pytest.mark.skipif(
    not _drill_enabled(),
    reason=(
        "DAENA_ENABLE_LIVE_SEND_SMOKE is not 'true'. "
        "This is the operator-run live send drill; skipped by "
        "default to prevent accidental external sends."
    ),
)
@pytest.mark.asyncio
class TestLiveSendDrill:
    async def test_recipient_must_be_allowlisted(self):
        """Refuse to run if the env-supplied recipient is not on the
        founder / agent allowlist. This is the hard wall against
        accidentally drilling against a customer or third party."""
        recipient = _allowlisted_recipient()
        assert recipient is not None, (
            f"DAENA_LIVE_SEND_RECIPIENT must be one of "
            f"{sorted(ALLOWED_RECIPIENTS)}; got "
            f"{os.environ.get('DAENA_LIVE_SEND_RECIPIENT')!r}"
        )

    async def test_full_create_then_send_path(self):
        """End-to-end: create draft -> fetch -> snapshot -> send.

        Runs ONLY when:
          * DAENA_ENABLE_LIVE_SEND_SMOKE == "true"
          * DAENA_LIVE_SEND_ACCESS_TOKEN is set
          * DAENA_LIVE_SEND_OWNER_EMAIL is set
          * DAENA_LIVE_SEND_RECIPIENT is in the allowlist
        """
        from app.services.gmail_draft_snapshot import (
            build_snapshot_from_gmail_draft,
            compute_draft_metadata_hash,
            first_drift_field,
        )
        from app.services.integrations.gmail_client import GmailClient

        access_token = os.environ.get("DAENA_LIVE_SEND_ACCESS_TOKEN") or ""
        owner_email = (
            os.environ.get("DAENA_LIVE_SEND_OWNER_EMAIL") or ""
        ).strip().lower()
        recipient = _allowlisted_recipient()

        assert access_token, (
            "DAENA_LIVE_SEND_ACCESS_TOKEN env var is required for the "
            "live drill"
        )
        assert owner_email, (
            "DAENA_LIVE_SEND_OWNER_EMAIL env var is required for the "
            "live drill"
        )
        assert recipient is not None  # guarded by the previous test

        client = GmailClient({"access_token": access_token})

        # Step 1: create draft
        create_result = await client.create_draft(
            to=recipient,
            subject=DRILL_SUBJECT,
            body=DRILL_BODY,
        )
        draft_id = create_result.get("draft_id")
        assert draft_id, f"create_draft returned no draft_id: {list(create_result)}"

        # Step 2: fetch draft (verifies it's actually in Gmail)
        draft_meta = await client.get_draft(draft_id)
        assert draft_meta.get("id") == draft_id

        # Step 3: build the snapshot (what a send-approval would
        # carry), then re-build it to confirm hash stability.
        approved_snapshot = build_snapshot_from_gmail_draft(
            draft_meta=draft_meta, owner_email=owner_email,
        )
        # Re-fetch and re-build immediately; hashes must match.
        draft_meta_2 = await client.get_draft(draft_id)
        current_snapshot = build_snapshot_from_gmail_draft(
            draft_meta=draft_meta_2, owner_email=owner_email,
        )
        drift = first_drift_field(
            approved=approved_snapshot, current=current_snapshot,
        )
        assert drift is None, (
            f"snapshot drifted between two consecutive fetches "
            f"(field={drift!r}); approved_hash="
            f"{compute_draft_metadata_hash(approved_snapshot)[:16]}.. "
            f"current_hash="
            f"{compute_draft_metadata_hash(current_snapshot)[:16]}.."
        )

        # Step 4: send the draft
        send_result = await client.send_existing_draft(draft_id)
        message_id = send_result.get("message_id")
        assert message_id, f"send returned no message_id: {list(send_result)}"

        # Log ONLY a boolean + the message-id LENGTH (so no message
        # id leaks via test logs). The result dict itself is also
        # NOT echoed.
        logger.info(
            "live_send_drill.complete success=True "
            "message_id_length=%d",
            len(message_id),
        )
