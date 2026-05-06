"""DraftEnrichment -- Sprint-12 PR-1 + PR-2.

Reads :pyfunc:`app.services.runtime_readiness.get_runtime_readiness`,
picks the routed ``main_brain``, calls its provider via the existing
``ModelRegistry`` to fill ``_llm_pending`` fields on
:class:`ResearchDraft.structured_payload` (PR-1) and to suggest
local-only answers for :class:`FormDraftField` rows (PR-2).

Hard rules baked in (NEVER override):

* No hardcoded ``llama-server`` / Ollama / Anthropic / etc.. The
  routed runtime is whatever ``runtime_readiness.router_summary
  .main_brain_id`` resolves to right now.
* If ``main_brain_id is None``, the call refuses with
  :class:`NoReadyMainBrain` -- the operator gets the readiness
  ``next_action`` string back, no LLM call fires.
* Metered API providers are only used when the routed selection
  resolves to one AND ``allow_metered=True`` is passed in
  explicitly. Default policy is local-first; silent metered calls
  are forbidden by the readiness ladder anyway, but we double-gate
  here as defence in depth.
* Every enrichment call writes one
  ``draft.enrichment.<kind>`` audit row (ALLOWED on success,
  BLOCKED with safe reason on refusal). Result rows include the
  chosen ``runtime_id`` + ``cost_class`` for the audit trail.
* Output schema enforces ``confidence`` (0.0-1.0) and
  ``needs_review`` per filled field. The service never raises on
  bad LLM JSON -- low-confidence fall-through with
  ``needs_review=true`` is the failure mode.
* For form-drafts, blocked field types
  (``blocked_payment`` / ``blocked_sensitive``) ALWAYS skip
  enrichment, regardless of LLM output. The service refuses to
  write a ``suggested_value`` to those rows.

Hot-path side effects:

* DB writes the updated ``ResearchDraft.structured_payload`` JSONB
  or the ``FormDraftField.suggested_value`` cells.
* Audit ledger appended.

NEVER:

* sends, posts, emails, applies, submits, browses externally.
* edits an external system based on enrichment output.
* logs raw LLM output verbatim (only sanitised excerpts make it
  into structured logs).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field as _field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ModelProvider
from app.core.logging import get_logger
from app.models.form_draft import FormDraft, FormDraftField
from app.models.research import ResearchDraft
from app.services.audit import AuditService
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMMessage,
)
from app.services.runtime_readiness import get_runtime_readiness


logger = get_logger(__name__)


# Map readiness item ids to ModelProvider enum values used by the
# registry. CLI runtimes register under the matching API provider
# (cli_claude -> ANTHROPIC) when the API key is absent. The model
# registry returns whichever is actually instantiated.
RUNTIME_TO_PROVIDER: dict[str, ModelProvider] = {
    "vllm_configured":     ModelProvider.VLLM,
    "ollama_backend":      ModelProvider.OLLAMA,
    "ollama_windows":      ModelProvider.OLLAMA,
    "cli_ollama":          ModelProvider.OLLAMA,
    "cli_claude":          ModelProvider.ANTHROPIC,
    "cli_codex":           ModelProvider.OPENAI,
    "cli_gemini":          ModelProvider.GEMINI,
    "provider_anthropic":  ModelProvider.ANTHROPIC,
    "provider_openai":     ModelProvider.OPENAI,
    "provider_gemini":     ModelProvider.GEMINI,
    "provider_perplexity": ModelProvider.PERPLEXITY,
    "provider_groq":       ModelProvider.GROQ,
    "provider_openrouter": ModelProvider.OPENROUTER,
    "provider_together":   ModelProvider.TOGETHER,
}


# ── Errors ────────────────────────────────────────────────────────────


class EnrichmentRefused(Exception):
    """Stable refusal -- safe message for API + UI surfaces."""

    def __init__(self, code: str, next_action: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.next_action = next_action


class NoReadyMainBrain(EnrichmentRefused):
    def __init__(self, next_action: str) -> None:
        super().__init__(
            "no_ready_main_brain",
            next_action=next_action,
        )


class MeteredApiNotAllowed(EnrichmentRefused):
    def __init__(self, runtime_id: str) -> None:
        super().__init__(
            f"metered_api_not_allowed:{runtime_id}",
            next_action=(
                "Routed runtime is metered_api. Pass allow_metered=True "
                "on the call OR start a local model to take the slot."
            ),
        )


class ProviderNotInstantiated(EnrichmentRefused):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"provider_not_instantiated:{provider}",
            next_action=(
                "Routed runtime resolves to a ModelProvider that the "
                "registry has not initialised. Check provider startup."
            ),
        )


# ── Selection ────────────────────────────────────────────────────────


@dataclass(slots=True)
class RoutedSelection:
    """Concrete provider pick for one enrichment call."""
    runtime_id: str
    cost_class: str
    provider_enum: ModelProvider
    rationale: str


async def select_provider(
    *,
    allow_metered: bool = False,
    readiness: dict[str, Any] | None = None,
) -> RoutedSelection:
    """Resolve the routed main_brain to a concrete ModelProvider.

    Args:
        allow_metered: When False (default), refuse a metered_api
            selection. Local-first policy.
        readiness: Pre-fetched readiness payload (testing hook).
            When None, fetches via ``get_runtime_readiness``.

    Raises:
        NoReadyMainBrain: ``main_brain_id`` is None.
        MeteredApiNotAllowed: routed runtime is metered_api and
            allow_metered=False.
    """
    payload = readiness or await get_runtime_readiness()
    summary = payload["router_summary"]
    main_brain_id = summary.get("main_brain_id")
    if not main_brain_id:
        raise NoReadyMainBrain(summary.get("next_action") or "")

    cost_class = summary.get("main_brain_cost_class") or "unknown"
    if cost_class == "metered_api" and not allow_metered:
        raise MeteredApiNotAllowed(main_brain_id)

    provider_enum = RUNTIME_TO_PROVIDER.get(main_brain_id)
    if provider_enum is None:
        # Unknown id -- treat as not-instantiated so the audit row
        # captures the refusal. This shouldn't happen because the
        # readiness layer rejects unknowns first.
        raise ProviderNotInstantiated(main_brain_id)

    return RoutedSelection(
        runtime_id=main_brain_id,
        cost_class=cost_class,
        provider_enum=provider_enum,
        rationale=(
            f"runtime_readiness.router_summary picked "
            f"{main_brain_id} ({cost_class})."
        ),
    )


# ── LLM call helper ──────────────────────────────────────────────────


_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL,
)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Find the first JSON object in an LLM response.

    Order tried:

    1. Direct ``json.loads(text.strip())`` -- prompt asked for JSON
       only and the model complied.
    2. First ```json ... ``` fenced block.
    3. Greedy ``{...}`` slice between the first ``{`` and last ``}``.

    Returns None when nothing parses; the caller falls back to
    needs_review=true on every field.
    """
    if not text:
        return None
    s = text.strip()
    # Strip leading "json" line sometimes prepended by Ollama models.
    if s.lower().startswith("json"):
        s = s[4:].lstrip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    # Greedy brace match -- last-resort. Keeps us robust to a model
    # that prefixes a one-line preamble before the JSON.
    if "{" in text and "}" in text:
        chunk = text[text.index("{"): text.rindex("}") + 1]
        try:
            v = json.loads(chunk)
            return v if isinstance(v, dict) else None
        except Exception:
            return None
    return None


async def _call_main_brain(
    *,
    selection: RoutedSelection,
    system: str,
    user: str,
    max_tokens: int = 1024,
    registry: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Call the routed provider once and return (text, metadata).

    Uses the in-process ModelRegistry. Tests inject a fake registry
    via the ``registry`` kwarg.
    """
    if registry is None:
        # ModelRegistry is held on FastAPI app.state -- no module
        # singleton exists. The API layer passes it explicitly. We
        # only reach this branch from tests that forgot to inject one.
        raise ProviderNotInstantiated(
            "registry_not_provided -- pass registry= from app.state",
        )

    provider: BaseProvider | None = registry.get_provider(selection.provider_enum)
    if provider is None:
        raise ProviderNotInstantiated(selection.provider_enum.value)

    req = GenerateRequest(
        messages=[
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ],
        model_id=None,  # let the provider pick its default
        temperature=0.2,
        max_tokens=max_tokens,
        system_prompt=system,
        stream=False,
        metadata={
            "purpose": "draft_enrichment",
            "runtime_id": selection.runtime_id,
        },
    )
    resp = await provider.generate(req)
    return resp.content, {
        "model_id": resp.model_id,
        "latency_ms": resp.latency_ms,
        "token_count_input": resp.token_count_input,
        "token_count_output": resp.token_count_output,
        "cost_usd": resp.cost_usd,
    }


# ── ResearchDraft enrichment (PR-1) ──────────────────────────────────


_CAREER_FIELDS = (
    "company", "role", "team", "location", "compensation",
    "responsibilities", "fit_score", "fit_rationale",
    "missing_skills", "suggested_answers", "outreach_draft_local",
    "next_tasks",
)
_CONTENT_FIELDS = (
    "audience", "key_points", "angle", "outline",
    "captions", "hooks", "risks_to_verify", "claims_to_verify",
)


def _career_prompt(payload: dict[str, Any], goal: str) -> tuple[str, str]:
    system = (
        "You are Daena's research-draft enricher. The operator pasted a "
        "job posting; deterministic regex already extracted bullets and "
        "URLs into a structured payload. Your job is to fill the "
        "remaining fields HONESTLY. Never invent a fit_score above the "
        "evidence supports. Output STRICT JSON only -- no prose, no "
        "markdown fences. Use null for fields you cannot confidently "
        "fill from the input text."
    )
    schema_keys = ", ".join(_CAREER_FIELDS)
    user = (
        f"Operator goal: {goal!r}\n\n"
        f"Existing structured payload (deterministic-only):\n"
        f"{json.dumps({k: payload.get(k) for k in _CAREER_FIELDS}, ensure_ascii=False)}\n\n"
        f"Source URL: {payload.get('sources', [None])[0]}\n"
        f"Bulleted requirements already extracted:\n"
        f"{json.dumps(payload.get('requirements', []), ensure_ascii=False)}\n\n"
        f"Return JSON with these top-level keys: {schema_keys}, "
        f"plus a `field_confidence` map of {{key: float in [0,1]}} and "
        f"a `needs_review` array listing keys that should be flagged for "
        f"the operator. fit_score is an int 0-100; missing_skills + "
        f"next_tasks are short string lists; suggested_answers is a list "
        f"of {{question, answer, confidence}} objects; outreach_draft_local "
        f"is a short LOCAL ONLY message text the operator may copy. "
        f"NEVER include a 'send' or 'submit' field."
    )
    return system, user


def _content_prompt(payload: dict[str, Any], goal: str) -> tuple[str, str]:
    system = (
        "You are Daena's content-brief enricher. The operator pasted a "
        "URL; deterministic regex already extracted bullets and URLs. "
        "Your job is to draft the audience / angle / outline fields the "
        "regex cannot infer. Output STRICT JSON only. Never invent a "
        "claim that is not supported by the extract; flag everything "
        "uncertain in `claims_to_verify`."
    )
    schema_keys = ", ".join(_CONTENT_FIELDS)
    user = (
        f"Operator goal: {goal!r}\n\n"
        f"Existing structured payload (deterministic-only):\n"
        f"{json.dumps({k: payload.get(k) for k in _CONTENT_FIELDS}, ensure_ascii=False)}\n\n"
        f"Source URL: {payload.get('sources', [None])[0]}\n"
        f"Bulleted outline already extracted:\n"
        f"{json.dumps(payload.get('outline', []), ensure_ascii=False)}\n\n"
        f"Return JSON with these keys: {schema_keys}, plus a "
        f"`field_confidence` map and a `needs_review` array. captions "
        f"and hooks are short string lists (3-5 each). claims_to_verify "
        f"and risks_to_verify are string lists of cautions. "
        f"NEVER include a 'post' or 'publish' field."
    )
    return system, user


def _coerce_str_list(v: Any, *, limit: int = 16) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip()[:600])
        if len(out) >= limit:
            break
    return out


def _coerce_int_0_100(v: Any) -> int | None:
    try:
        n = int(v)
        if 0 <= n <= 100:
            return n
        return max(0, min(100, n))
    except Exception:
        return None


def _coerce_str(v: Any, *, limit: int = 4000) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()[:limit]
    return None


def _merge_career_payload(
    existing: dict[str, Any],
    llm: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply LLM output on top of the deterministic payload.

    LLM-only fills NEVER overwrite a non-None deterministic value
    -- the regex already had high signal there. confidence + needs_review
    are computed from LLM's self-report.
    """
    out = dict(existing)
    confidences: dict[str, float] = {}
    needs_review: list[str] = []

    # When LLM call fails, fall-through with _llm_pending=False but
    # mark every field as needs_review so the operator sees the gap.
    if not llm:
        out["_llm_pending"] = False
        out["_llm_failed"] = True
        out["_llm_field_confidence"] = {k: 0.0 for k in _CAREER_FIELDS}
        out["_llm_needs_review"] = list(_CAREER_FIELDS)
        return out

    raw_conf = llm.get("field_confidence") or {}
    raw_needs = llm.get("needs_review") or []
    if not isinstance(raw_conf, dict):
        raw_conf = {}
    if not isinstance(raw_needs, list):
        raw_needs = []
    raw_needs_set = {str(k) for k in raw_needs if isinstance(k, str)}

    def _conf(key: str, default: float = 0.5) -> float:
        try:
            v = float(raw_conf.get(key, default))
        except Exception:
            return default
        return max(0.0, min(1.0, v))

    # Per-field merge with type coercion. Deterministic values win
    # when they're already filled.
    if not out.get("company"):
        out["company"] = _coerce_str(llm.get("company"), limit=200)
    if not out.get("role"):
        out["role"] = _coerce_str(llm.get("role"), limit=200)
    if not out.get("team"):
        out["team"] = _coerce_str(llm.get("team"), limit=200)
    if not out.get("location"):
        out["location"] = _coerce_str(llm.get("location"), limit=200)
    if not out.get("compensation"):
        out["compensation"] = _coerce_str(llm.get("compensation"), limit=200)
    if not out.get("responsibilities"):
        out["responsibilities"] = _coerce_str_list(llm.get("responsibilities"))
    if out.get("fit_score") is None:
        out["fit_score"] = _coerce_int_0_100(llm.get("fit_score"))
    if not out.get("fit_rationale"):
        out["fit_rationale"] = _coerce_str(llm.get("fit_rationale"))
    if not out.get("missing_skills"):
        out["missing_skills"] = _coerce_str_list(llm.get("missing_skills"))
    if not out.get("outreach_draft_local"):
        out["outreach_draft_local"] = _coerce_str(
            llm.get("outreach_draft_local"), limit=2000,
        )
    if not out.get("next_tasks"):
        out["next_tasks"] = _coerce_str_list(llm.get("next_tasks"))

    # suggested_answers: list of {question, answer, confidence}
    raw_sa = llm.get("suggested_answers")
    if isinstance(raw_sa, list) and not out.get("suggested_answers"):
        cleaned: list[dict[str, Any]] = []
        for entry in raw_sa:
            if not isinstance(entry, dict):
                continue
            q = _coerce_str(entry.get("question"), limit=400)
            a = _coerce_str(entry.get("answer"), limit=2000)
            c = entry.get("confidence")
            try:
                cf = max(0.0, min(1.0, float(c)))
            except Exception:
                cf = 0.5
            if q and a:
                cleaned.append({
                    "question": q, "answer": a, "confidence": cf,
                })
        out["suggested_answers"] = cleaned[:10]

    for key in _CAREER_FIELDS:
        confidences[key] = _conf(key)
        if key in raw_needs_set or confidences[key] < 0.6:
            needs_review.append(key)

    out["_llm_pending"] = False
    out["_llm_failed"] = False
    out["_llm_field_confidence"] = confidences
    out["_llm_needs_review"] = needs_review
    return out


def _merge_content_payload(
    existing: dict[str, Any],
    llm: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(existing)
    if not llm:
        out["_llm_pending"] = False
        out["_llm_failed"] = True
        out["_llm_field_confidence"] = {k: 0.0 for k in _CONTENT_FIELDS}
        out["_llm_needs_review"] = list(_CONTENT_FIELDS)
        return out

    raw_conf = llm.get("field_confidence") or {}
    raw_needs = llm.get("needs_review") or []
    if not isinstance(raw_conf, dict):
        raw_conf = {}
    if not isinstance(raw_needs, list):
        raw_needs = []
    raw_needs_set = {str(k) for k in raw_needs if isinstance(k, str)}

    def _conf(key: str, default: float = 0.5) -> float:
        try:
            v = float(raw_conf.get(key, default))
        except Exception:
            return default
        return max(0.0, min(1.0, v))

    if not out.get("audience"):
        out["audience"] = _coerce_str(llm.get("audience"), limit=400)
    if not out.get("angle"):
        out["angle"] = _coerce_str(llm.get("angle"), limit=600)
    if not out.get("key_points"):
        out["key_points"] = _coerce_str_list(llm.get("key_points"), limit=10)
    if not out.get("outline"):
        out["outline"] = _coerce_str_list(llm.get("outline"))
    if not out.get("captions"):
        out["captions"] = _coerce_str_list(llm.get("captions"), limit=8)
    if not out.get("hooks"):
        out["hooks"] = _coerce_str_list(llm.get("hooks"), limit=8)
    if not out.get("risks_to_verify"):
        out["risks_to_verify"] = _coerce_str_list(llm.get("risks_to_verify"))
    if not out.get("claims_to_verify"):
        out["claims_to_verify"] = _coerce_str_list(llm.get("claims_to_verify"))

    confidences: dict[str, float] = {}
    needs_review: list[str] = []
    for key in _CONTENT_FIELDS:
        confidences[key] = _conf(key)
        if key in raw_needs_set or confidences[key] < 0.6:
            needs_review.append(key)

    out["_llm_pending"] = False
    out["_llm_failed"] = False
    out["_llm_field_confidence"] = confidences
    out["_llm_needs_review"] = needs_review
    return out


@dataclass(slots=True)
class EnrichmentResult:
    """What the API returns to the operator + audit row."""
    draft_id: str
    runtime_id: str
    cost_class: str
    fields_filled: int
    needs_review: list[str]
    llm_failed: bool = False
    metadata: dict[str, Any] = _field(default_factory=dict)


async def enrich_research_draft(
    db: AsyncSession,
    draft: ResearchDraft,
    *,
    allow_metered: bool = False,
    readiness: dict[str, Any] | None = None,
    registry: Any = None,
    actor_id: uuid.UUID | None = None,
) -> EnrichmentResult:
    """Fill ``_llm_pending`` fields on a ResearchDraft.

    Refuses honestly when no main_brain is ready. Persists the
    updated payload + writes an audit row in either case.
    """
    payload = dict(draft.structured_payload or {})
    kind = (draft.kind or "").lower()
    audit = AuditService(db)

    try:
        selection = await select_provider(
            allow_metered=allow_metered, readiness=readiness,
        )
    except EnrichmentRefused as exc:
        await audit.log_decision(
            tenant_id=draft.tenant_id,
            actor_id=actor_id,
            actor_type="SYSTEM",
            action_type=f"draft.enrichment.{kind or 'unknown'}",
            action_params={
                "draft_id": str(draft.id),
                "refusal_code": exc.code,
                "next_action": exc.next_action[:500],
            },
            result="BLOCKED",
            risk_level="LOW",
            governance_tier=1,
        )
        raise

    if kind == "career":
        sys_p, usr_p = _career_prompt(payload, draft.goal or "")
        merger = _merge_career_payload
    elif kind == "content":
        sys_p, usr_p = _content_prompt(payload, draft.goal or "")
        merger = _merge_content_payload
    else:
        raise EnrichmentRefused(f"unknown_kind:{kind}")

    try:
        text, meta = await _call_main_brain(
            selection=selection, system=sys_p, user=usr_p,
            registry=registry,
        )
        parsed = _extract_json(text)
    except EnrichmentRefused:
        raise
    except Exception:
        logger.exception(
            "draft_enrichment.llm_call_failed",
            draft_id=str(draft.id),
            runtime_id=selection.runtime_id,
        )
        text, meta, parsed = "", {}, None

    new_payload = merger(payload, parsed)
    draft.structured_payload = new_payload
    db.add(draft)
    await db.flush()

    needs_review = list(new_payload.get("_llm_needs_review") or [])
    fields_filled = sum(
        1 for k in (
            _CAREER_FIELDS if kind == "career" else _CONTENT_FIELDS
        )
        if new_payload.get(k) not in (None, [], "")
    )

    await audit.log_decision(
        tenant_id=draft.tenant_id,
        actor_id=actor_id,
        actor_type="SYSTEM",
        action_type=f"draft.enrichment.{kind}",
        action_params={
            "draft_id": str(draft.id),
            "runtime_id": selection.runtime_id,
            "cost_class": selection.cost_class,
            "fields_filled": fields_filled,
            "needs_review_count": len(needs_review),
            "llm_failed": bool(new_payload.get("_llm_failed")),
            "model_id": meta.get("model_id"),
        },
        result="ALLOWED",
        risk_level="LOW",
        governance_tier=1,
    )

    return EnrichmentResult(
        draft_id=str(draft.id),
        runtime_id=selection.runtime_id,
        cost_class=selection.cost_class,
        fields_filled=fields_filled,
        needs_review=needs_review,
        llm_failed=bool(new_payload.get("_llm_failed")),
        metadata=meta,
    )


# ── FormDraft enrichment (PR-2) ──────────────────────────────────────


# Field types enrichment is allowed to write a suggested_value for.
# The blocked types are intentionally absent.
_ENRICHABLE_FIELD_TYPES = {"text", "textarea", "email", "url", "phone"}


def _form_prompt(
    *,
    title: str,
    goal: str,
    questions: list[dict[str, Any]],
    research_context: dict[str, Any] | None,
) -> tuple[str, str]:
    system = (
        "You are Daena's form-draft answer suggester. The operator "
        "is filling out a form locally; you produce SUGGESTED answers "
        "they will review and edit. NEVER write any value for fields "
        "marked blocked_payment or blocked_sensitive (those will be "
        "filtered out by the caller -- assume you do not see them). "
        "Output STRICT JSON only. Use empty string for fields you "
        "cannot confidently answer; the caller maps that to "
        "needs_review=true. NEVER include a 'submit' / 'send' / "
        "'apply' field."
    )
    qs = [
        {
            "field_id": q["id"],
            "label": q["label"],
            "field_type": q["field_type"],
            "options": q.get("options") or None,
        }
        for q in questions
    ]
    ctx_part = ""
    if research_context:
        # Pass only the fields that aren't sensitive. ResearchDraft is
        # already operator-supplied; no PII filter needed here.
        whitelist = (
            "company", "role", "fit_rationale", "missing_skills",
            "outreach_draft_local", "next_tasks",
        )
        rc = {k: research_context.get(k) for k in whitelist}
        ctx_part = (
            f"\n\nResearch context (use to ground the answers):\n"
            f"{json.dumps(rc, ensure_ascii=False)}"
        )
    user = (
        f"Form title: {title!r}\n"
        f"Operator goal: {goal!r}\n"
        f"Questions:\n{json.dumps(qs, ensure_ascii=False)}\n"
        f"{ctx_part}\n\n"
        f"Return JSON with one top-level key `answers`, an array of "
        f"{{field_id, suggested_value, confidence (0-1), notes}} objects. "
        f"Provide one entry per question. Use confidence < 0.6 when the "
        f"answer is a guess; the UI will flag those for operator review."
    )
    return system, user


async def enrich_form_draft(
    db: AsyncSession,
    draft: FormDraft,
    *,
    research_context: dict[str, Any] | None = None,
    allow_metered: bool = False,
    readiness: dict[str, Any] | None = None,
    registry: Any = None,
    actor_id: uuid.UUID | None = None,
) -> EnrichmentResult:
    """Suggest local-only answers for unblocked FormDraftField rows.

    Blocked fields (payment, sensitive) are skipped unconditionally.
    Daena NEVER writes ``suggested_value`` for them, regardless of
    LLM output.
    """
    audit = AuditService(db)

    # Refresh fields so we never enrich a stale local copy.
    rows = (
        await db.execute(
            select(FormDraftField)
            .where(FormDraftField.draft_id == draft.id)
            .order_by(FormDraftField.order),
        )
    ).scalars().all()

    eligible = [
        r for r in rows if r.field_type in _ENRICHABLE_FIELD_TYPES
    ]
    skipped = len(rows) - len(eligible)

    try:
        selection = await select_provider(
            allow_metered=allow_metered, readiness=readiness,
        )
    except EnrichmentRefused as exc:
        await audit.log_decision(
            tenant_id=draft.tenant_id,
            actor_id=actor_id,
            actor_type="SYSTEM",
            action_type="draft.enrichment.form",
            action_params={
                "draft_id": str(draft.id),
                "refusal_code": exc.code,
                "next_action": exc.next_action[:500],
            },
            result="BLOCKED",
            risk_level="LOW",
            governance_tier=1,
        )
        raise

    if not eligible:
        await audit.log_decision(
            tenant_id=draft.tenant_id,
            actor_id=actor_id,
            actor_type="SYSTEM",
            action_type="draft.enrichment.form",
            action_params={
                "draft_id": str(draft.id),
                "runtime_id": selection.runtime_id,
                "cost_class": selection.cost_class,
                "skipped_blocked_or_other": skipped,
                "fields_filled": 0,
                "note": "no_eligible_fields",
            },
            result="ALLOWED",
            risk_level="LOW",
            governance_tier=1,
        )
        return EnrichmentResult(
            draft_id=str(draft.id),
            runtime_id=selection.runtime_id,
            cost_class=selection.cost_class,
            fields_filled=0,
            needs_review=[],
            llm_failed=False,
            metadata={},
        )

    questions = [
        {
            "id": str(r.id),
            "label": r.label,
            "field_type": r.field_type,
            "options": r.options,
        }
        for r in eligible
    ]
    sys_p, usr_p = _form_prompt(
        title=draft.title,
        goal=draft.goal or "",
        questions=questions,
        research_context=research_context,
    )

    try:
        text, meta = await _call_main_brain(
            selection=selection, system=sys_p, user=usr_p,
            max_tokens=2048, registry=registry,
        )
        parsed = _extract_json(text)
    except EnrichmentRefused:
        raise
    except Exception:
        logger.exception(
            "form_draft_enrichment.llm_call_failed",
            draft_id=str(draft.id),
            runtime_id=selection.runtime_id,
        )
        text, meta, parsed = "", {}, None

    answers_by_id: dict[str, dict[str, Any]] = {}
    if parsed:
        raw = parsed.get("answers") or []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                fid = str(entry.get("field_id") or "")
                if not fid:
                    continue
                answers_by_id[fid] = entry

    fields_filled = 0
    needs_review_ids: list[str] = []
    for r in eligible:
        # Defence-in-depth: re-check field type. The classifier might
        # have been bypassed, e.g. by an admin import. We refuse to
        # write to anything outside the enrichable set.
        if r.field_type not in _ENRICHABLE_FIELD_TYPES:
            continue
        a = answers_by_id.get(str(r.id))
        if not a:
            r.needs_review = True
            r.notes = (r.notes or "") + " enrichment.no_answer_returned"
            db.add(r)
            needs_review_ids.append(str(r.id))
            continue
        sv = _coerce_str(a.get("suggested_value"), limit=4000)
        try:
            cf = float(a.get("confidence", 0.5))
        except Exception:
            cf = 0.5
        cf = max(0.0, min(1.0, cf))
        notes = _coerce_str(a.get("notes"), limit=400)

        # Keep operator-typed `value` untouched; only fill suggested_value.
        if sv:
            r.suggested_value = sv
            fields_filled += 1
        r.confidence = cf
        r.needs_review = bool(cf < 0.6 or not sv)
        if r.needs_review:
            needs_review_ids.append(str(r.id))
        if notes:
            r.notes = notes
        db.add(r)

    await db.flush()

    await audit.log_decision(
        tenant_id=draft.tenant_id,
        actor_id=actor_id,
        actor_type="SYSTEM",
        action_type="draft.enrichment.form",
        action_params={
            "draft_id": str(draft.id),
            "runtime_id": selection.runtime_id,
            "cost_class": selection.cost_class,
            "fields_filled": fields_filled,
            "needs_review_count": len(needs_review_ids),
            "skipped_blocked_or_other": skipped,
            "llm_failed": parsed is None,
            "model_id": meta.get("model_id"),
        },
        result="ALLOWED",
        risk_level="LOW",
        governance_tier=1,
    )

    return EnrichmentResult(
        draft_id=str(draft.id),
        runtime_id=selection.runtime_id,
        cost_class=selection.cost_class,
        fields_filled=fields_filled,
        needs_review=needs_review_ids,
        llm_failed=parsed is None,
        metadata=meta,
    )
