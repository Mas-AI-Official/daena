"""Controlled execution handlers package.

Importing this package side-effect-registers every WRITE_TOOLS
handler in ``controlled_execution_dispatch._TOOL_HANDLERS``.

Sprint-14 ships:
  - gmail.create_draft                                   (PR-2)
  - calendar.create_tentative_event_without_invites      (PR-3)
  - local.file_change_proposal                           (PR-4)

Sprint-15 adds:
  - gmail.send_existing_draft                            (PR-2)

Adding a new handler module here is the SAME action as adding the
tool_id to ``controlled_execution_design.WRITE_TOOLS``. They must
move in lockstep; the dispatcher's ``register_tool_handler`` refuses
if you try to register a handler for a tool not in the allowlist.
"""

from __future__ import annotations

# Side-effect imports register handlers at load time.
from app.services.controlled_execution_handlers import (  # noqa: F401
    calendar_tentative_event,
    file_change_proposal,
    gmail_create_draft,
    gmail_send_existing_draft,
)
