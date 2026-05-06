# PR-3 — FormDraft Assistant

**Sprint:** DAENA-SUPERVISED-WORK-OPERATOR-SPRINT-11
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

The first **net-new** draft type in Sprint-11. Daena prepares form
answers locally for the operator to review and submit manually. Daena
never submits, never autofills sensitive fields, never drives a
browser at any external site.

## What changed

### 1. New models (`backend/app/models/form_draft.py`)

- `FormDraft`: tenant-scoped + user-scoped. Status is **DRAFT** or
  **ARCHIVED** only — no `sent`, `submitted`, `applied` states. There
  is no place in the schema where Daena can mark a draft "sent" because
  there is nowhere it can be sent from.
- `FormDraftField`: per-question row. Carries `field_type`,
  `value` (operator-editable), `suggested_value`, `confidence`,
  `needs_review`, `options`, `notes`. Cascades from FormDraft.
- Optional `research_draft_ref` on FormDraft so a CareerDraft (or
  ContentBrief) can link forward into a FormDraft. Stored as a string,
  not a FK, so a deleted research draft does not cascade-delete the
  in-progress form work.

### 2. Service (`backend/app/services/form_draft_service.py`)

#### `classify_field_type(label, name=None) -> str`

Returns one of: `text` | `textarea` | `email` | `url` | `phone` |
`select` | **`blocked_payment`** | **`blocked_sensitive`**.

Order of checks:
1. `blocked_payment` first — credit card / CVV / billing / payment-method.
2. `blocked_sensitive` next — passport / SSN / SIN / immigration /
   visa / driver's-license / bank-account / IBAN / SWIFT /
   mother's-maiden-name.
3. Then `email`, `url`, `phone`.
4. Default: `text` (or `textarea` for labels longer than 120 chars).

#### `_suggest_value_for(field_type, label) -> (value, confidence, notes)`

**Hard contract: blocked types ALWAYS return `(None, 0.0, "operator
must fill manually")`.** A test asserts this for every blocked type.

Non-blocked types currently return `(None, 0.0, "Awaiting LLM
enrichment + NBMF lookup")` — PR-3 ships **deterministic only**, same
honest-pending pattern as PR-2. LLM/NBMF wiring lands in a follow-up.

#### `parse_form_html(html) -> list[dict]`

Pure function using stdlib `html.parser`. Extracts `<input>`,
`<textarea>`, `<select>` with their resolved labels. Hidden / submit /
button input types are intentionally skipped. Malformed HTML returns
`[]` instead of crashing the request.

#### Three creation entry points

- `create_form_draft_from_questions(title, questions=[...])`
- `create_form_draft_from_html(title, html, source_url=...)`
- `(API only)` `from-url`: scrapes the URL via the existing
  `extract_from_url` worker and either picks lines ending in `?` or
  parses the result as HTML.

All three paths converge on the same persisted shape.

### 3. API (`backend/app/api/v1/form_drafts.py`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/form-drafts/from-questions` | FOUNDER, build from pasted questions |
| POST | `/form-drafts/from-html` | FOUNDER, build from pasted HTML |
| POST | `/form-drafts/from-url` | FOUNDER, scrape + build |
| GET | `/form-drafts` | List operator's drafts |
| GET | `/form-drafts/{id}` | Read one with fields |
| PATCH | `/form-drafts/{id}/fields/{field_id}` | Edit a value |
| POST | `/form-drafts/{id}/archive` | Soft-delete |
| DELETE | `/form-drafts/{id}` | Hard-delete only after ARCHIVED |

**No `/submit`. No `/send`. No `/apply`. No `/post`. No `/publish`.
No `/dispatch`.** A test asserts the OpenAPI spec contains none of
these paths under `/form-drafts/`.

### 4. Source-level hard rules

A static-analysis test reads the three new files and asserts:

- No `from playwright` / `from selenium` / `import playwright` /
  `import selenium` import lines.
- No `page.fill` / `page.click` / `page.goto` / `browser.new_page` /
  `webdriver.Chrome` API calls.
- No `@router.post("/submit"...)` / `@router.post("/send"...)` /
  similar route declarations.

This catches the "I added a private helper called
`_dispatch_through_browser`" failure mode at code review time.

### 5. Frontend lane integration

`WorkstreamsPage.tsx` `DraftsLane` now fetches `/form-drafts` in
parallel with research drafts. The Forms tab renders an honest list
(or a clear empty state pointing operators at the three input
endpoints). No "Submit" button. No "Send" button. The card surface
is read-only — the actual form-fill UX (clicking into a draft,
editing field values) is the next polish PR.

## Tests

`backend/tests/test_form_drafts.py` — **46 tests, all passing.**

| Group | Cases |
|---|---|
| `TestClassifier` | 8 (payment patterns, sensitive patterns, email, url, long-text, default, payment-beats-sensitive when both fire) |
| `TestSuggestedValueGate` | 3 (blocked types return None, text returns pending) |
| `TestHtmlParser` | 8 (visible-only, email override, url override, textarea, select with options, sensitive labels block, malformed HTML returns empty) |
| `TestCreateFromQuestions` | 3 (persists, empty raises, blank title raises) |
| `TestCreateFromHtml` | 1 (persists parsed shape) |
| `TestUpdateField` | 2 (filling clears needs_review, blocked type keeps field_type) |
| `TestArchive` | 1 (status flips to ARCHIVED) |
| `TestApiSurface` | 3 (no banned POST verbs return 200, OpenAPI shows expected routes, OpenAPI has no banned paths) |
| `TestSourceHardRules` | 3 (no browser imports, no banned route decorators, blocked-helper exported) |

Regression: PR-1 (16) + PR-2 (21) + research_flow (33) + integrations
(57) + form_drafts (46) = **155 passing, 0 failing**.

Frontend: `npx tsc --noEmit` exit 0.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets read/printed/committed | ✅ |
| No external messages | ✅ |
| No forms submitted | ✅ — no submit endpoint exists; OpenAPI test enforces |
| No social posts | ✅ |
| No payments | ✅ — `blocked_payment` field_type explicit |
| No browser automation on external sites | ✅ — static-analysis test enforces |
| No Phase 3 writes | ✅ |
| No duplicate command center page | ✅ — extends `WorkstreamsPage` |
| No duplicate Opportunity / ContentBrief models | ✅ |
| Sensitive auto-fill prevented | ✅ — `_suggest_value_for` hard-contract test |

## Files touched

```
new:        backend/app/models/form_draft.py
new:        backend/app/services/form_draft_service.py
new:        backend/app/api/v1/form_drafts.py
new:        backend/tests/test_form_drafts.py
modified:   backend/app/api/v1/__init__.py    (router include)
modified:   backend/app/models/__init__.py    (re-export + __all__)
modified:   frontend/src/pages/WorkstreamsPage.tsx  (Forms tab wiring)
new:        docs/Ultraview/PR_FORM_DRAFT_ASSISTANT_REPORT.md
```

## What this PR does *not* do (deferred)

- LLM-driven answer suggestion (PR-3.5 will run the question +
  research-context through llm_service to fill `suggested_value`).
- NBMF lookup for "answer this from my CV / past forms" — same
  follow-up.
- Per-field operator UI on the frontend (the lane currently shows a
  card list; clicking into a draft to edit fields is a polish PR).

## Next step

PR-4 — extend `ApprovalQueue` with draft kinds (`email_draft`,
`form_draft`, `application_draft`, `content_post_draft`,
`file_change_proposal`). Approving sets `approved_for_manual_action`;
test asserts no outbound dispatcher fires on approve.
