"""Draft Action Factory -- Sprint-13 PR-4 (2026-05-06).

Daena proposes; never auto-executes. For each opportunity type, the
factory returns a deterministic set of *suggested* action drafts the
operator can fill in locally. These are metadata only -- no
``send`` / ``submit`` / ``post`` / ``apply`` field is ever produced.

Wired into the opportunity workstream's ``initial_context`` so the
Workstreams console can show "what comes next" without any external
action.

Closed action-kind set
----------------------

::

    cold_email          local email draft (never sent)
    linkedin_msg        local LinkedIn DM draft (never sent)
    grant_application   local grant application draft
    hackathon_entry     local hackathon submission draft
    customer_proposal   local SOW / proposal draft
    bounty_report       local security report draft
    partnership_pitch   local partnership pitch draft
    rfp_response        local RFP response draft
    content_brief       local content brief / script draft
    program_application local accelerator / startup-program app draft

Each suggested draft carries:

::

    {
      "id":              <stable id, opportunity_type:action_kind>
      "kind":            ActionDraftKind
      "title":           short headline
      "rationale":       why this kind fits the opportunity_type
      "requires_approval": True   (always; locked)
      "delivery":        "manual_only"  (locked; no send/submit path)
      "payload_hash":    null         (filled by Phase 3 when wired)
    }

The shape is locked -- contract test in
``tests/test_draft_action_factory.py`` asserts no field whose name
contains send / submit / apply / post / publish / pay ever appears.
"""

from __future__ import annotations

from typing import Final, Literal


ActionDraftKind = Literal[
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
]


# Per-opportunity-type suggested action drafts. Order matters --
# the first entry is what the workstream's next_step_text would
# nudge toward when ``next_action`` is empty.
_OPPORTUNITY_TYPE_TO_ACTIONS: Final[dict[str, tuple[tuple[ActionDraftKind, str, str], ...]]] = {
    "grant": (
        ("grant_application", "Draft grant application",
         "Local-only application draft. Founder reviews + submits manually."),
        ("partnership_pitch", "Draft funder pitch follow-up",
         "Optional pitch deck for the program officer; manual send only."),
    ),
    "accelerator": (
        ("program_application", "Draft accelerator application",
         "Local-only application draft. Founder reviews + submits manually."),
        ("partnership_pitch", "Draft accelerator partner pitch",
         "Optional pitch deck for accelerator partners."),
    ),
    "hackathon": (
        ("hackathon_entry", "Draft hackathon submission",
         "Local-only entry draft (project description + demo notes)."),
        ("content_brief", "Draft launch content for the project",
         "Optional brief for X / LinkedIn launch posts; manual post only."),
    ),
    "freelance": (
        ("customer_proposal", "Draft customer proposal / SOW",
         "Local-only proposal draft. Founder reviews + sends manually."),
        ("cold_email", "Draft outreach email",
         "Local cold email draft; never auto-sent."),
    ),
    "customer": (
        ("cold_email", "Draft outreach email",
         "Local cold email draft; never auto-sent."),
        ("linkedin_msg", "Draft LinkedIn DM",
         "Local LinkedIn message draft; never auto-sent."),
        ("customer_proposal", "Draft customer proposal / SOW",
         "Local-only proposal draft."),
    ),
    "partnership": (
        ("partnership_pitch", "Draft partnership pitch",
         "Local pitch draft. Founder reviews + sends manually."),
        ("cold_email", "Draft partner outreach email",
         "Local cold email draft; never auto-sent."),
    ),
    "security_bounty": (
        ("bounty_report", "Draft security report",
         "Local security report draft. Founder reviews + submits manually "
         "via the program's official intake; never auto-submitted."),
    ),
    "rfp": (
        ("rfp_response", "Draft RFP response",
         "Local RFP response draft. Founder reviews + submits manually."),
    ),
    "content": (
        ("content_brief", "Draft content brief",
         "Local content brief / script. Goes to ContentOps approval queue."),
    ),
    "startup_program": (
        ("program_application", "Draft startup-program application",
         "Local-only application draft. Founder reviews + submits manually."),
    ),
}


# Locked action-draft shape keys. The contract test asserts these
# are the ONLY keys produced; no send/submit/apply field ever
# slips in.
_LOCKED_ACTION_KEYS: Final[frozenset[str]] = frozenset({
    "id",
    "kind",
    "title",
    "rationale",
    "requires_approval",
    "delivery",
    "payload_hash",
})


def suggested_action_drafts(opportunity_type: str) -> list[dict]:
    """Return the closed-set suggested action drafts for an opportunity type.

    Returns an empty list for unknown types -- never raises. Callers
    surface the empty case as "no actions suggested yet" rather than
    failing the workstream creation.
    """
    triples = _OPPORTUNITY_TYPE_TO_ACTIONS.get(opportunity_type, ())
    out: list[dict] = []
    for kind, title, rationale in triples:
        out.append({
            "id": f"{opportunity_type}:{kind}",
            "kind": kind,
            "title": title,
            "rationale": rationale,
            "requires_approval": True,    # locked
            "delivery": "manual_only",    # locked
            "payload_hash": None,         # filled by Phase 3 when wired
        })
    return out
