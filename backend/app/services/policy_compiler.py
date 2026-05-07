"""Plain-English policy compiler.

Phase 2 F8 (2026-04-24). Takes a natural-language policy description
("Daena should never post to my Twitter without showing me the draft
first") and produces the structured fields SecurityGate evaluates:
trigger, condition, action, enforcement_mode, governance_tier.

The compiler delegates the structured-output work to Claude CLI via
the ClaudeCodeAdapter; we don't reinvent JSON-schema-constrained
generation here. The CLI's --json-schema flag does the heavy lifting.

When the runtime adapter is unavailable (e.g. early dev, no
subscription), the compiler degrades to a simple keyword-based
classifier so the API endpoint always returns *something* the user
can iterate on. The deterministic path is intentionally crude --
production policies should always go through the LLM path; the
fallback exists so the UI never hits an empty pane.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CompiledPolicy:
    name: str
    plain_english: str
    trigger: str
    condition: str
    action: str  # BLOCK | APPROVE | LOG | REDACT | REQUIRE_APPROVAL
    enforcement_mode: str  # ALWAYS | BALANCED_ONLY | GOVERNED_ONLY
    governance_tier: int
    confidence: float
    reasoning: str
    matched_intents: list[str]
    compiled_by: str
    compiled_yaml: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plain_english": self.plain_english,
            "trigger": self.trigger,
            "condition": self.condition,
            "action": self.action,
            "enforcement_mode": self.enforcement_mode,
            "governance_tier": self.governance_tier,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "matched_intents": list(self.matched_intents),
            "compiled_by": self.compiled_by,
            "compiled_yaml": self.compiled_yaml,
        }


# Intent vocabulary the compiler picks from. Stable across versions so
# stored policies stay valid when the compiler model changes.
KNOWN_TRIGGERS = (
    "FINANCIAL:transfer",
    "EXTERNAL_COMMS:linkedin.post",
    "EXTERNAL_COMMS:twitter.post",
    "EXTERNAL_COMMS:twitter.reply",
    "EXTERNAL_COMMS:linkedin.reply",
    "EXTERNAL_COMMS:slack.post",
    "EXTERNAL_COMMS:email.send",
    "EXTERNAL_COMMS:dm.send",
    "EXTERNAL_COMMS:any",
    "DEPLOYMENT:any",
    "DEPLOYMENT:production",
    "FS:write",
    "FS:read",
    "FS:delete_or_overwrite",
    "BASH:exec",
    "BASH:destructive",
    "EXTERNAL_API:any",
    "EXTERNAL_API:billing",
    "OUTBOUND:any",
    "INBOUND:any",
    "AUTOPILOT:start",
    "AUTOPILOT:tool_use",
    "DATA_EXFIL:any",
    "PII:detected",
    "CUSTOM:any",
)

KNOWN_ACTIONS = ("BLOCK", "APPROVE", "LOG", "REDACT", "REQUIRE_APPROVAL")
KNOWN_ENFORCEMENT = ("ALWAYS", "BALANCED_ONLY", "GOVERNED_ONLY")


_COMPILER_SYSTEM = """You are Daena's policy compiler. Translate a single
plain-English governance rule into a strict JSON object. Do not return
prose; return ONLY one JSON object matching the schema. The user's
governance posture is power-first: BLOCK only for irreversible /
high-risk actions; prefer REQUIRE_APPROVAL or LOG otherwise.
"""


_COMPILER_SCHEMA = {
    "type": "object",
    "required": [
        "name", "trigger", "condition", "action",
        "enforcement_mode", "governance_tier", "confidence",
        "reasoning", "matched_intents",
    ],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 80},
        "trigger": {"type": "string", "enum": list(KNOWN_TRIGGERS)},
        "condition": {"type": "string", "minLength": 1, "maxLength": 400},
        "action": {"type": "string", "enum": list(KNOWN_ACTIONS)},
        "enforcement_mode": {"type": "string", "enum": list(KNOWN_ENFORCEMENT)},
        "governance_tier": {"type": "integer", "minimum": 0, "maximum": 4},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string", "minLength": 1, "maxLength": 800},
        "matched_intents": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
    },
    "additionalProperties": False,
}


async def compile_policy(plain_english: str, *, name_hint: str = "") -> CompiledPolicy:
    """Translate ``plain_english`` to a CompiledPolicy.

    Two-tier strategy:
    1. Ask Claude CLI with --json-schema for a structured object.
    2. If the LLM call fails or returns garbage, fall back to a
       keyword classifier so the UI always has something to render.
    """
    if not plain_english or not plain_english.strip():
        raise ValueError("plain_english must be non-empty")

    llm_compiled = await _compile_via_llm(plain_english, name_hint=name_hint)
    if llm_compiled is not None:
        return llm_compiled

    logger.info("policy_compiler.fallback_to_heuristic")
    return _compile_heuristic(plain_english, name_hint=name_hint)


async def _compile_via_llm(
    plain_english: str, *, name_hint: str,
) -> CompiledPolicy | None:
    """Call Claude CLI via the runtime adapter to get structured output."""
    try:
        from app.services.runtimes.adapters.claude_code import ClaudeCodeAdapter
    except Exception as exc:
        logger.warning("policy_compiler.adapter_import_failed", error=str(exc))
        return None

    adapter = ClaudeCodeAdapter()
    if not await adapter.check_installed():
        logger.warning("policy_compiler.claude_not_installed")
        return None

    prompt = (
        _COMPILER_SYSTEM
        + "\n\n## Allowed triggers\n"
        + ", ".join(KNOWN_TRIGGERS)
        + "\n\n## Allowed actions\n"
        + ", ".join(KNOWN_ACTIONS)
        + "\n\n## Allowed enforcement_mode\n"
        + ", ".join(KNOWN_ENFORCEMENT)
        + "\n\n## Tier guide\n"
        + "0=log only, 1=auto-proceed with notice, 2=ack, 3=approval, 4=block by default\n\n"
        + "## Plain-English policy\n"
        + plain_english.strip()
        + ("\n\n## Name hint (use as starting point)\n" + name_hint.strip() if name_hint else "")
        + "\n\nReturn one JSON object matching the schema. No prose.\n"
    )

    try:
        chunks: list[str] = []
        async for ch in adapter.execute(
            task=prompt,
            context={
                "session_id": "policy-compiler-singleshot",
                "working_directory": ".",
                "permission_mode": "plan",  # no side effects
                "add_dirs": [],
                "allowed_tools": "",  # no tools needed for pure synthesis
            },
        ):
            chunks.append(ch)
        raw = "\n".join(chunks).strip()
    except Exception as exc:
        logger.warning("policy_compiler.execute_failed", error=str(exc))
        return None

    parsed = _extract_json(raw)
    if not parsed:
        logger.warning("policy_compiler.no_json", raw_head=raw[:200])
        return None

    try:
        return _materialize(plain_english, parsed, compiled_by="claude-code-cli")
    except Exception as exc:
        logger.warning("policy_compiler.materialize_failed", error=str(exc))
        return None


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a possibly-noisy LLM response."""
    # Try the "obvious" parse first.
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Walk for a balanced { ... } block.
    depth = 0
    start = -1
    for idx, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = raw[start: idx + 1]
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    continue
    return None


def _materialize(plain_english: str, data: dict[str, Any], *, compiled_by: str) -> CompiledPolicy:
    name = str(data.get("name") or _short_name(plain_english))
    trigger = _coerce_choice(data.get("trigger"), KNOWN_TRIGGERS, "CUSTOM:any")
    action = _coerce_choice(data.get("action"), KNOWN_ACTIONS, "LOG")
    enforcement = _coerce_choice(data.get("enforcement_mode"), KNOWN_ENFORCEMENT, "ALWAYS")
    tier = max(0, min(4, int(data.get("governance_tier", 1))))
    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.6))))
    condition = str(data.get("condition") or "true").strip()
    reasoning = str(data.get("reasoning") or "Compiled from plain-English description.").strip()
    matched = [str(x) for x in (data.get("matched_intents") or [])][:8]

    yaml_doc = (
        f"name: {json.dumps(name)}\n"
        f"trigger: {trigger}\n"
        f"condition: {json.dumps(condition)}\n"
        f"action: {action}\n"
        f"enforcement_mode: {enforcement}\n"
        f"governance_tier: {tier}\n"
        f"plain_english: {json.dumps(plain_english)}\n"
        "enabled: true\n"
    )

    return CompiledPolicy(
        name=name,
        plain_english=plain_english,
        trigger=trigger,
        condition=condition,
        action=action,
        enforcement_mode=enforcement,
        governance_tier=tier,
        confidence=confidence,
        reasoning=reasoning,
        matched_intents=matched,
        compiled_by=compiled_by,
        compiled_yaml=yaml_doc,
    )


def _coerce_choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if isinstance(value, str):
        upper = value.upper().replace(" ", "_")
        if upper in allowed:
            return upper
    return default


def _short_name(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= 60:
        return text.rstrip(".") or "Unnamed Policy"
    return text[:57].rstrip() + "..."


# ── Heuristic fallback ─────────────────────────────────────────────

_HEURISTIC_RULES = (
    # (regex, trigger, action, tier)
    (r"\b(send|transfer|wire|move)\s+money|payment\b", "FINANCIAL:transfer", "BLOCK", 4),
    (r"\bcredit\s*card\b|\bbank\s*account\b|\bssn\b|\bsin\b", "PII:detected", "BLOCK", 4),
    (r"\baddress\b|\bphone\b|\bemail\b.*founder|home\s+address", "PII:detected", "REDACT", 0),
    (r"\blinkedin\b.*\b(post|publish|share)\b", "EXTERNAL_COMMS:linkedin.post", "REQUIRE_APPROVAL", 3),
    (r"\b(twitter|x\.com|tweet)\b.*\b(post|publish|share)\b", "EXTERNAL_COMMS:twitter.post", "REQUIRE_APPROVAL", 3),
    (r"\b(slack|teams)\b.*\bpost\b", "EXTERNAL_COMMS:slack.post", "REQUIRE_APPROVAL", 2),
    (r"\bemail\b.*\b(send|reply)\b", "EXTERNAL_COMMS:email.send", "LOG", 1),
    (r"\bdm\b|\bdirect\s+message\b", "EXTERNAL_COMMS:dm.send", "REQUIRE_APPROVAL", 3),
    (r"\b(deploy|push|release|ship)\b.*\bproduction\b", "DEPLOYMENT:production", "REQUIRE_APPROVAL", 4),
    (r"\b(delete|overwrite|rm\s+-rf)\b", "FS:delete_or_overwrite", "BLOCK", 4),
    (r"\bdaena[-_ ]mind\b", "FS:delete_or_overwrite", "BLOCK", 4),
    (r"\b(api|external)\s+(call|request)\b", "EXTERNAL_API:any", "LOG", 0),
    (r"\bautopilot\b", "AUTOPILOT:tool_use", "REQUIRE_APPROVAL", 3),
)


def _compile_heuristic(plain_english: str, *, name_hint: str = "") -> CompiledPolicy:
    text = plain_english.lower()
    chosen_trigger = "CUSTOM:any"
    chosen_action = "LOG"
    chosen_tier = 1
    matched: list[str] = []

    for pattern, trigger, action, tier in _HEURISTIC_RULES:
        if re.search(pattern, text):
            chosen_trigger = trigger
            chosen_action = action
            chosen_tier = tier
            matched.append(pattern)
            break  # first match wins; user can edit afterward

    name = name_hint.strip() or _short_name(plain_english)
    enforcement = "ALWAYS"

    yaml_doc = (
        f"name: {json.dumps(name)}\n"
        f"trigger: {chosen_trigger}\n"
        f'condition: "true"\n'
        f"action: {chosen_action}\n"
        f"enforcement_mode: {enforcement}\n"
        f"governance_tier: {chosen_tier}\n"
        f"plain_english: {json.dumps(plain_english)}\n"
        "enabled: true\n"
    )

    return CompiledPolicy(
        name=name,
        plain_english=plain_english,
        trigger=chosen_trigger,
        condition="true",
        action=chosen_action,
        enforcement_mode=enforcement,
        governance_tier=chosen_tier,
        confidence=0.55,
        reasoning="Heuristic keyword classifier (LLM compiler unavailable).",
        matched_intents=matched,
        compiled_by="heuristic",
        compiled_yaml=yaml_doc,
    )
