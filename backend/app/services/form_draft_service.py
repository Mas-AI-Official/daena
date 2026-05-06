"""FormDraftService -- Sprint-11 PR-3.

Three input surfaces for building a FormDraft:

    1. ``create_from_questions(questions=[...])`` -- operator pastes
       a list of question strings.
    2. ``create_from_html(html=...)`` -- operator pastes the form's
       HTML; we parse <input>, <textarea>, <select>.
    3. ``create_from_url(url=...)`` -- we run the existing scrape
       worker, then run the same HTML / question extraction over the
       result.

All three converge on the same ``FormDraft + FormDraftField`` rows.

Hard rules enforced inside this module:

    * ``classify_field_type(label)`` MUST return ``blocked_payment``
      for credit-card / CVV / billing fields and ``blocked_sensitive``
      for passport / SSN / SIN / immigration / visa / driver's
      license / bank-account fields. The classifier is the only
      gate here; the data model defaults to ``needs_review=True`` so
      a missed classification still surfaces as operator-attention.
    * ``suggested_value`` is NEVER populated for blocked field types.
      Tests assert this for every blocked-pattern label.
    * No Playwright import. No browser automation. The only network
      call is the existing ``scrape_service.extract_from_url`` which
      itself enforces SSRF + audit + cap.
    * No submit / send / apply / post helper exists. Tests assert
      no public symbol in this module starts with those verbs.
"""

from __future__ import annotations

import re
import uuid
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.form_draft import FormDraft, FormDraftField

logger = get_logger(__name__)


# ── Field classification ──────────────────────────────────────────────


_PAYMENT_RE = re.compile(
    r"(credit\s*card|debit\s*card|card\s*number|card\s*holder|cvv|cvc|"
    r"exp(?:ir(?:y|ation))?\s*date|billing\s*(?:address|zip|postal)|"
    r"payment\s*(?:method|info)|paypal\s*id|bank\s*routing)",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"(passport(?:\s*number)?|\bssn\b|\bsin\b|social\s*(?:insurance|security)\s*number|"
    r"immigration|visa\s*(?:number|status)|driver'?s?\s*licen[cs]e|"
    r"bank\s*account\s*(?:number)?|iban|swift\s*code|mother'?s?\s*maiden\s*name)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b(email|e-?mail|inbox)\b", re.IGNORECASE)
_URL_RE = re.compile(r"\b(url|website|portfolio|linkedin|github|twitter)\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(phone|mobile|cell|tel(?:ephone)?)\b", re.IGNORECASE)


def classify_field_type(label: str, *, name: str | None = None) -> str:
    """Map a question label to a FormDraftField.field_type.

    Order matters: payment + sensitive checks fire first so a label
    like "Credit card number for billing" always lands in
    ``blocked_payment``, never in ``text``.
    """
    haystack = f"{label or ''} {name or ''}"
    if _PAYMENT_RE.search(haystack):
        return "blocked_payment"
    if _SENSITIVE_RE.search(haystack):
        return "blocked_sensitive"
    if _EMAIL_RE.search(haystack):
        return "email"
    if _URL_RE.search(haystack):
        return "url"
    if _PHONE_RE.search(haystack):
        return "phone"
    if len(label or "") > 120:
        return "textarea"
    return "text"


def is_blocked_type(field_type: str) -> bool:
    return field_type in ("blocked_payment", "blocked_sensitive")


# ── HTML parsing ──────────────────────────────────────────────────────


class _FormFieldParser(HTMLParser):
    """Extracts <input>, <textarea>, <select> fields and their labels.

    Best-effort label resolution: a <label for="X"> matched to an
    input id="X" wins; falls back to the input's own ``placeholder``,
    ``aria-label``, or ``name``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.fields: list[dict[str, Any]] = []
        self._labels: dict[str, str] = {}  # for-attr -> label text
        self._current_label_for: str | None = None
        self._current_label_buf: list[str] = []
        self._select_options: list[str] | None = None
        self._select_meta: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "label":
            self._current_label_for = a.get("for")
            self._current_label_buf = []
            return
        if tag == "input":
            input_type = (a.get("type") or "text").lower()
            if input_type in ("hidden", "submit", "button", "reset", "image"):
                return
            self.fields.append({
                "tag": "input",
                "input_type": input_type,
                "name": a.get("name") or "",
                "id": a.get("id") or "",
                "placeholder": a.get("placeholder") or "",
                "aria_label": a.get("aria-label") or "",
                "required": "required" in a,
                "options": None,
            })
            return
        if tag == "textarea":
            self.fields.append({
                "tag": "textarea",
                "input_type": "textarea",
                "name": a.get("name") or "",
                "id": a.get("id") or "",
                "placeholder": a.get("placeholder") or "",
                "aria_label": a.get("aria-label") or "",
                "required": "required" in a,
                "options": None,
            })
            return
        if tag == "select":
            self._select_options = []
            self._select_meta = {
                "tag": "select",
                "input_type": "select",
                "name": a.get("name") or "",
                "id": a.get("id") or "",
                "placeholder": "",
                "aria_label": a.get("aria-label") or "",
                "required": "required" in a,
            }
            return
        if tag == "option" and self._select_options is not None:
            label = a.get("label") or a.get("value") or ""
            self._select_options.append(label.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._current_label_for:
            self._labels[self._current_label_for] = "".join(
                self._current_label_buf
            ).strip()
            self._current_label_for = None
            self._current_label_buf = []
        if tag == "select" and self._select_meta is not None:
            self._select_meta["options"] = self._select_options or []
            self.fields.append(self._select_meta)
            self._select_meta = None
            self._select_options = None

    def handle_data(self, data: str) -> None:
        if self._current_label_for is not None:
            self._current_label_buf.append(data)
        elif self._select_options is not None and self._select_options:
            # Append option text content if it landed between
            # <option>...</option>.
            self._select_options[-1] = (
                self._select_options[-1] + data
            ).strip() or self._select_options[-1]

    def resolve_label(self, field: dict[str, Any]) -> str:
        for_id = field.get("id")
        if for_id and for_id in self._labels and self._labels[for_id]:
            return self._labels[for_id]
        for key in ("placeholder", "aria_label", "name"):
            v = field.get(key) or ""
            if v.strip():
                return v.strip()
        return "(unlabeled field)"


def parse_form_html(html: str) -> list[dict[str, Any]]:
    """Return a list of {label, field_type, options, name} dicts.

    Pure function -- no DB writes, no network. Hardened against
    HTML-parser exceptions so a malformed paste does not crash the
    request.
    """
    parser = _FormFieldParser()
    try:
        parser.feed(html or "")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("form_html_parse_failed", error=str(exc)[:200])
        return []
    out: list[dict[str, Any]] = []
    for f in parser.fields:
        label = parser.resolve_label(f)
        ft = classify_field_type(label, name=f.get("name"))
        # Override classifier when the input type is explicitly email/url.
        if f.get("input_type") == "email" and not is_blocked_type(ft):
            ft = "email"
        elif f.get("input_type") == "url" and not is_blocked_type(ft):
            ft = "url"
        elif f.get("input_type") == "tel" and not is_blocked_type(ft):
            ft = "phone"
        elif f.get("input_type") == "textarea":
            ft = "textarea" if not is_blocked_type(ft) else ft
        elif f.get("input_type") == "select":
            ft = "select" if not is_blocked_type(ft) else ft
        out.append({
            "label": label,
            "field_type": ft,
            "options": f.get("options"),
            "name": f.get("name") or "",
            "required": bool(f.get("required")),
        })
    return out


# ── Suggested-value generator ─────────────────────────────────────────


def _suggest_value_for(field_type: str, label: str) -> tuple[str | None, float, str]:
    """Return (suggested_value, confidence, notes).

    Deterministic only -- this is the same tier-D approach as PR-2.
    LLM-driven enrichment lands in a follow-up PR. Confidence < 0.7
    forces ``needs_review=True``.

    Blocked field types ALWAYS return (None, 0.0, "operator must fill")
    -- no LLM, no heuristic, no auto-population. The test suite asserts
    this contract explicitly.
    """
    if is_blocked_type(field_type):
        return None, 0.0, (
            "Sensitive / payment field: Daena does not auto-populate. "
            "Operator must fill manually."
        )
    # Conservative default: the operator hasn't given Daena a knowledge
    # base to draw from in this PR. Future PR wires NBMF lookup +
    # CV-derived suggestions.
    return None, 0.0, "Awaiting LLM enrichment + NBMF lookup."


# ── Service entry points ──────────────────────────────────────────────


async def create_form_draft_from_questions(
    db: AsyncSession,
    *,
    title: str,
    questions: list[str],
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    goal: str = "",
    research_draft_ref: str | None = None,
) -> FormDraft:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title_required")
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions_required")

    draft = FormDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        title=title.strip()[:256],
        source_kind="questions",
        goal=goal,
        status="DRAFT",
        research_draft_ref=research_draft_ref,
    )
    db.add(draft)
    await db.flush()

    for i, q in enumerate(questions):
        label = (q or "").strip()
        if not label:
            continue
        ft = classify_field_type(label)
        suggested, confidence, notes = _suggest_value_for(ft, label)
        db.add(FormDraftField(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            draft_id=draft.id,
            order=i,
            label=label[:2000],
            field_type=ft,
            suggested_value=suggested,
            value=None,
            confidence=confidence,
            needs_review=confidence < 0.7,
            options=None,
            notes=notes,
        ))
    await db.flush()
    return draft


async def create_form_draft_from_html(
    db: AsyncSession,
    *,
    title: str,
    html: str,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    source_url: str | None = None,
    goal: str = "",
    research_draft_ref: str | None = None,
) -> FormDraft:
    parsed = parse_form_html(html)
    if not parsed:
        raise ValueError("no_fields_parsed")

    source_host = None
    if source_url:
        try:
            parts = urlsplit(source_url)
            host = parts.hostname or "?"
            port = f":{parts.port}" if parts.port else ""
            source_host = f"{(parts.scheme or 'http').lower()}://{host}{port}"
        except Exception:
            source_host = None

    draft = FormDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        title=(title or "Untitled form").strip()[:256],
        source_kind="html",
        source_url=source_url,
        source_host=source_host,
        goal=goal,
        status="DRAFT",
        research_draft_ref=research_draft_ref,
    )
    db.add(draft)
    await db.flush()

    for i, field in enumerate(parsed):
        label = field["label"]
        ft = field["field_type"]
        suggested, confidence, notes = _suggest_value_for(ft, label)
        db.add(FormDraftField(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            draft_id=draft.id,
            order=i,
            label=label[:2000],
            field_type=ft,
            suggested_value=suggested,
            value=None,
            confidence=confidence,
            needs_review=confidence < 0.7,
            options=field.get("options"),
            notes=notes,
        ))
    await db.flush()
    return draft


async def update_field_value(
    db: AsyncSession,
    *,
    field: FormDraftField,
    new_value: str | None,
) -> FormDraftField:
    """Operator-driven field edit. Once the operator has filled a
    value, ``needs_review`` flips to False.

    Blocked-type fields still accept a value (the operator fills them
    by hand) but the original field_type stays so the UI keeps the
    "sensitive" treatment.
    """
    field.value = new_value
    if new_value is not None and new_value.strip():
        field.needs_review = False
    await db.flush()
    return field


async def archive_draft(db: AsyncSession, *, draft: FormDraft) -> FormDraft:
    draft.status = "ARCHIVED"
    await db.flush()
    return draft
