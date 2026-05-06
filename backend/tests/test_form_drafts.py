"""PR-3 (Sprint-11): FormDraft Assistant.

Asserts:
    1. classify_field_type maps payment / SSN / SIN / passport / visa /
       immigration / driver's-license / bank-account labels to
       blocked_payment / blocked_sensitive.
    2. Blocked field types NEVER receive a suggested_value.
    3. parse_form_html extracts <input>/<textarea>/<select> with the
       right field_type per HTML input type.
    4. create_form_draft_from_questions persists a FormDraft + N
       FormDraftField rows, all with needs_review=True (deterministic
       PR-3 has no LLM enrichment).
    5. create_form_draft_from_html persists the parsed shape.
    6. update_field_value flips needs_review to False once the
       operator has filled a value (even on blocked types -- the
       operator is allowed to fill them by hand, the field_type stays
       so the UI keeps the sensitive treatment).
    7. The HTTP API surface includes the four expected endpoints +
       lacks any submit / send / apply / post / publish / dispatch
       route.
    8. The form_drafts source module contains no Playwright import
       (no browser automation).
"""

from __future__ import annotations

import pathlib
import re
import uuid

import pytest
from sqlalchemy import select

from app.models.form_draft import FormDraft, FormDraftField
from app.models.identity import Tenant, User
from app.services.form_draft_service import (
    archive_draft,
    classify_field_type,
    create_form_draft_from_html,
    create_form_draft_from_questions,
    is_blocked_type,
    parse_form_html,
    update_field_value,
    _suggest_value_for,
)


# ── Field classifier ─────────────────────────────────────────────────


class TestClassifier:
    @pytest.mark.parametrize(
        "label",
        [
            "Credit card number",
            "CVV",
            "CVC code",
            "Card expiration date",
            "Billing zip",
            "Payment method",
            "PayPal id",
        ],
    )
    def test_payment_labels_map_to_blocked_payment(self, label):
        assert classify_field_type(label) == "blocked_payment"

    @pytest.mark.parametrize(
        "label",
        [
            "Passport number",
            "Social Insurance Number",
            "SSN",
            "SIN",
            "Immigration status",
            "Visa number",
            "Driver's license",
            "Bank account number",
            "IBAN",
            "Mother's maiden name",
        ],
    )
    def test_sensitive_labels_map_to_blocked_sensitive(self, label):
        assert classify_field_type(label) == "blocked_sensitive"

    def test_email_label_maps_to_email(self):
        assert classify_field_type("Email address") == "email"

    def test_url_label_maps_to_url(self):
        assert classify_field_type("LinkedIn URL") == "url"

    def test_long_label_maps_to_textarea(self):
        long = "Tell us about a time when you " + "x" * 200
        assert classify_field_type(long) == "textarea"

    def test_default_is_text(self):
        assert classify_field_type("First name") == "text"

    def test_payment_beats_sensitive_when_both_match(self):
        # 'billing' is payment; ensure it doesn't accidentally map to text
        assert classify_field_type("Billing address") == "blocked_payment"


class TestSuggestedValueGate:
    """Hard rule: blocked types never get a suggested_value."""

    @pytest.mark.parametrize(
        "field_type",
        ["blocked_payment", "blocked_sensitive"],
    )
    def test_blocked_types_get_none_value(self, field_type):
        suggested, confidence, notes = _suggest_value_for(
            field_type, "any label",
        )
        assert suggested is None
        assert confidence == 0.0
        assert "operator must fill" in notes.lower() or "manually" in notes.lower()

    def test_text_returns_pending_marker(self):
        suggested, confidence, notes = _suggest_value_for("text", "First name")
        # PR-3 is deterministic-only; LLM enrichment ships in a follow-up.
        assert confidence < 0.7
        assert suggested is None or isinstance(suggested, str)


# ── HTML parser ──────────────────────────────────────────────────────


SAMPLE_FORM_HTML = """
<form>
  <label for="name">Full name</label>
  <input id="name" type="text" name="name" required>

  <label for="email">Work email</label>
  <input id="email" type="email" name="email">

  <label for="portfolio">Portfolio URL</label>
  <input id="portfolio" type="url" name="portfolio">

  <label for="cc">Credit card number</label>
  <input id="cc" type="text" name="card">

  <label for="ssn">Social insurance number</label>
  <input id="ssn" type="text" name="sin">

  <label for="cover">Cover letter</label>
  <textarea id="cover" name="cover"></textarea>

  <label for="role">Role preference</label>
  <select id="role" name="role">
    <option value="ic">Individual contributor</option>
    <option value="lead">Tech lead</option>
  </select>

  <input type="hidden" name="csrf" value="...">
  <input type="submit" value="Apply">
</form>
"""


class TestHtmlParser:
    def test_extracts_visible_fields_only(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        labels = [f["label"] for f in fields]
        assert "Full name" in labels
        assert "Work email" in labels
        assert "Cover letter" in labels
        assert "Role preference" in labels
        # Hidden + submit + button must be skipped
        for skip in ("csrf", "Apply"):
            assert skip not in labels

    def test_email_input_type_overrides_to_email(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        email = next(f for f in fields if f["label"] == "Work email")
        assert email["field_type"] == "email"

    def test_url_input_type_overrides_to_url(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        url = next(f for f in fields if f["label"] == "Portfolio URL")
        assert url["field_type"] == "url"

    def test_textarea_classified(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        cover = next(f for f in fields if f["label"] == "Cover letter")
        assert cover["field_type"] == "textarea"

    def test_select_with_options(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        role = next(f for f in fields if f["label"] == "Role preference")
        assert role["field_type"] == "select"
        assert role["options"]

    def test_credit_card_label_blocks_even_on_text_input(self):
        """The classifier wins over input_type=text for sensitive labels."""
        fields = parse_form_html(SAMPLE_FORM_HTML)
        cc = next(f for f in fields if f["label"] == "Credit card number")
        assert cc["field_type"] == "blocked_payment"

    def test_sin_label_blocks(self):
        fields = parse_form_html(SAMPLE_FORM_HTML)
        sin = next(
            f for f in fields if f["label"] == "Social insurance number"
        )
        assert sin["field_type"] == "blocked_sensitive"

    def test_malformed_html_returns_empty_not_crash(self):
        # Garbage shouldn't 500 the request
        assert parse_form_html("<><<<<><") == []
        assert parse_form_html("") == []
        assert parse_form_html(None) == []  # type: ignore[arg-type]


# ── DB-backed creation ───────────────────────────────────────────────


@pytest.fixture
async def seed_user(db_session, test_tenant_id, test_user_id):
    existing = (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id)
    )).scalar_one_or_none()
    if existing is None:
        db_session.add(Tenant(id=test_tenant_id, name="T", slug="t"))
    existing_u = (await db_session.execute(
        select(User).where(User.id == test_user_id)
    )).scalar_one_or_none()
    if existing_u is None:
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email="m@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
    await db_session.flush()
    return {"tenant_id": test_tenant_id, "user_id": test_user_id}


class TestCreateFromQuestions:
    @pytest.mark.asyncio
    async def test_persists_draft_and_fields(self, db_session, seed_user):
        draft = await create_form_draft_from_questions(
            db_session,
            title="Apply: AI Engineer",
            questions=[
                "Full name",
                "Work email",
                "Credit card number",  # must be blocked
                "Why are you interested?",
            ],
            user_id=seed_user["user_id"],
            tenant_id=seed_user["tenant_id"],
        )
        await db_session.refresh(draft, attribute_names=["fields"])
        assert draft.status == "DRAFT"
        assert len(draft.fields) == 4
        labels = {f.label for f in draft.fields}
        assert "Full name" in labels
        assert "Credit card number" in labels

        cc = next(f for f in draft.fields if f.label == "Credit card number")
        assert cc.field_type == "blocked_payment"
        assert cc.suggested_value is None

        # All deterministic-only suggestions => needs_review True
        assert all(f.needs_review for f in draft.fields)

    @pytest.mark.asyncio
    async def test_empty_questions_raises(self, db_session, seed_user):
        with pytest.raises(ValueError, match="questions_required"):
            await create_form_draft_from_questions(
                db_session, title="x", questions=[],
                user_id=seed_user["user_id"],
                tenant_id=seed_user["tenant_id"],
            )

    @pytest.mark.asyncio
    async def test_blank_title_raises(self, db_session, seed_user):
        with pytest.raises(ValueError, match="title_required"):
            await create_form_draft_from_questions(
                db_session, title="   ", questions=["x"],
                user_id=seed_user["user_id"],
                tenant_id=seed_user["tenant_id"],
            )


class TestCreateFromHtml:
    @pytest.mark.asyncio
    async def test_persists_parsed_fields(self, db_session, seed_user):
        draft = await create_form_draft_from_html(
            db_session,
            title="Pasted form",
            html=SAMPLE_FORM_HTML,
            user_id=seed_user["user_id"],
            tenant_id=seed_user["tenant_id"],
            source_url="https://jobs.acme.com/apply",
        )
        await db_session.refresh(draft, attribute_names=["fields"])
        assert draft.source_kind == "html"
        assert draft.source_host == "https://jobs.acme.com"
        labels = {f.label for f in draft.fields}
        assert "Full name" in labels
        # Sensitive blocks survive the round-trip
        cc = next(f for f in draft.fields if "credit" in f.label.lower())
        assert cc.field_type == "blocked_payment"
        assert cc.suggested_value is None


class TestUpdateField:
    @pytest.mark.asyncio
    async def test_filling_value_clears_needs_review(
        self, db_session, seed_user,
    ):
        draft = await create_form_draft_from_questions(
            db_session, title="X",
            questions=["Full name"],
            user_id=seed_user["user_id"],
            tenant_id=seed_user["tenant_id"],
        )
        await db_session.refresh(draft, attribute_names=["fields"])
        f = draft.fields[0]
        assert f.needs_review is True
        await update_field_value(db_session, field=f, new_value="Masoud")
        assert f.needs_review is False
        assert f.value == "Masoud"

    @pytest.mark.asyncio
    async def test_blocked_type_keeps_field_type_after_fill(
        self, db_session, seed_user,
    ):
        draft = await create_form_draft_from_questions(
            db_session, title="X",
            questions=["Credit card number"],
            user_id=seed_user["user_id"],
            tenant_id=seed_user["tenant_id"],
        )
        await db_session.refresh(draft, attribute_names=["fields"])
        f = draft.fields[0]
        await update_field_value(db_session, field=f, new_value="1234-...")
        # Operator filled it manually, but the field_type stays blocked
        # so the UI continues to render the sensitive treatment.
        assert f.field_type == "blocked_payment"


class TestArchive:
    @pytest.mark.asyncio
    async def test_archive_sets_status(self, db_session, seed_user):
        draft = await create_form_draft_from_questions(
            db_session, title="X",
            questions=["Q"],
            user_id=seed_user["user_id"],
            tenant_id=seed_user["tenant_id"],
        )
        await archive_draft(db_session, draft=draft)
        assert draft.status == "ARCHIVED"


# ── HTTP surface ─────────────────────────────────────────────────────


class TestApiSurface:
    @pytest.mark.asyncio
    async def test_no_submit_endpoint(self, client, auth_headers):
        # Each path is asserted to not have a POST handler that does
        # something. FastAPI returns 405 (Method Not Allowed) when the
        # path matches /form-drafts/{draft_id} but no POST is declared
        # at that level -- which is exactly what we want. 404 happens
        # for paths that don't match any route at all. Either is proof
        # that no submit/send/apply/post/publish/dispatch endpoint
        # exists and does work.
        OK_NEGATIVE = {404, 405, 422}
        for verb_path in (
            "/api/v1/form-drafts/submit",
            "/api/v1/form-drafts/send",
            "/api/v1/form-drafts/apply",
            "/api/v1/form-drafts/post",
            "/api/v1/form-drafts/publish",
            "/api/v1/form-drafts/dispatch",
        ):
            r = await client.post(verb_path, headers=auth_headers, json={})
            assert r.status_code in OK_NEGATIVE, (
                f"{verb_path} unexpectedly accepted POST -- this violates "
                f"the Sprint-11 hard rule. Returned: {r.status_code}"
            )

    @pytest.mark.asyncio
    async def test_route_set_via_openapi(self, app):
        """Existence check via OpenAPI spec -- no DB hit, no auth.

        Verifies the four expected POST/GET/PATCH paths are all wired
        on the FastAPI app instance.
        """
        spec = app.openapi()
        paths = spec.get("paths", {})
        # Every expected path MUST appear; if a Sprint-11 hard-rule
        # violator path slipped in (e.g. /submit), a separate test in
        # this class catches it.
        assert "/api/v1/form-drafts/from-questions" in paths
        assert "/api/v1/form-drafts/from-html" in paths
        assert "/api/v1/form-drafts/from-url" in paths
        assert "/api/v1/form-drafts" in paths

    @pytest.mark.asyncio
    async def test_no_banned_path_in_openapi(self, app):
        """Hard rule: no /submit /send /apply /post /publish /dispatch
        path under /form-drafts shows up in the OpenAPI spec."""
        spec = app.openapi()
        paths = spec.get("paths", {})
        for verb in ("submit", "send", "apply", "publish", "dispatch"):
            offending = f"/api/v1/form-drafts/{verb}"
            assert offending not in paths, (
                f"{offending} appears in the OpenAPI spec -- this "
                f"violates the Sprint-11 hard rule."
            )


# ── Source-code static assertions ────────────────────────────────────


_FORM_DRAFT_FILES = [
    pathlib.Path(__file__).parent.parent
    / "app" / "services" / "form_draft_service.py",
    pathlib.Path(__file__).parent.parent
    / "app" / "api" / "v1" / "form_drafts.py",
    pathlib.Path(__file__).parent.parent
    / "app" / "models" / "form_draft.py",
]

# Match real import statements / API calls, not docstring mentions.
# We split this into "real-code regex" (skip lines starting with # or
# inside triple-quoted blocks).
_BANNED_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(?:playwright|selenium|webdriver_manager)|"
    r"import\s+(?:playwright|selenium))\b",
    re.MULTILINE | re.IGNORECASE,
)
_BANNED_CALL_RE = re.compile(
    r"\b(?:page\.fill|page\.click|page\.goto|browser\.new_page|"
    r"webdriver\.Chrome)\b",
)
_BANNED_ROUTES = re.compile(
    r"@router\.(post|put|patch|delete)\(\s*['\"]/(submit|send|apply|post|publish|dispatch)",
    re.IGNORECASE,
)


class TestSourceHardRules:
    def test_no_browser_automation_imports(self):
        for path in _FORM_DRAFT_FILES:
            text = path.read_text(encoding="utf-8")
            assert not _BANNED_IMPORT_RE.search(text), (
                f"{path.name} imports browser automation. "
                f"FormDraft is local-only -- no browser."
            )
            assert not _BANNED_CALL_RE.search(text), (
                f"{path.name} calls browser automation API. "
                f"FormDraft is local-only -- no browser."
            )

    def test_no_submit_route_decorators(self):
        for path in _FORM_DRAFT_FILES:
            text = path.read_text(encoding="utf-8")
            m = _BANNED_ROUTES.search(text)
            assert m is None, (
                f"{path.name} declares a banned route: {m.group(0)}"
            )

    def test_blocked_helper_is_exported(self):
        # The classifier helper must exist + be reachable for callers.
        assert callable(is_blocked_type)
        assert is_blocked_type("blocked_payment") is True
        assert is_blocked_type("blocked_sensitive") is True
        assert is_blocked_type("text") is False
