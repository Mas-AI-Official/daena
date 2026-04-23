"""Auto-Mind router (Step 2 of intelligence-layer consolidation).

When a session has no department pinned (e.g. the generic /chat page),
the orchestrator previously shipped a generic core-soul prompt with zero
Mind personality. That's the gap that made /chat feel flat: engineering
questions got generic Daena instead of Aria, marketing questions got
generic Daena instead of Zephyr.

This router classifies the user message with a zero-LLM keyword heuristic
(<5 ms) and returns a Mind slug the SoulEngine can load. The selection is
conservative: if no strong match, return None and let the generic soul
ship so we never put the wrong voice on a message.

Order of precedence when multiple Minds match: the highest keyword-score
wins; ties are broken by the order in _MIND_KEYWORDS (which mirrors the
soul vault spiral ordering -- engineering first, security last).

Design notes
------------
* Zero dependencies on the LLM, the DB, or the soul files. Pure string.
* Not a replacement for explicit department chat -- when the session
  IS pinned to a department, that overrides this router. This only
  activates when dept_name is None (generic /chat).
* The router is additive: if it picks a Mind, governance + skills +
  memory + council still run as usual. It only affects which persona
  gets prepended to the system prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MindMatch:
    """Result of the Mind router."""

    slug: str | None
    score: int
    matched_keywords: tuple[str, ...]


# Keyword buckets per Mind. Lowercase; word-boundary matched. The lists
# are intentionally small and distinctive -- not every word the domain
# owns, just the ones that reliably signal "this is a question for
# <that Mind>". Vague words (e.g. "team", "people") are excluded to
# avoid pulling every message into the router.
_MIND_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "engineering",  # Aria
        (
            "code", "codebase", "refactor", "bug", "debug", "test",
            "pytest", "typescript", "python", "javascript", "api",
            "endpoint", "pull request", "commit", "deploy", "git",
            "merge conflict", "unit test", "regression", "architecture",
            "function", "class", "module", "import", "lint",
            "compile", "build", "ci", "cd", "pipeline",
            "stack trace", "error message",
        ),
    ),
    (
        "sales",  # Orion
        (
            "prospect", "lead", "outreach", "cold email", "deal",
            "pipeline", "quota", "qualify", "discovery call",
            "closed won", "closed lost", "icp", "crm", "salesforce",
            "hubspot", "sdr", "bdr", "account executive",
        ),
    ),
    (
        "marketing",  # Zephyr
        (
            "campaign", "copy", "brand", "messaging", "positioning",
            "landing page", "ad", "seo", "keyword", "blog post",
            "newsletter", "social media", "linkedin post", "twitter post",
            "content", "audience", "funnel", "conversion", "ctr", "cpc",
            "attribution",
        ),
    ),
    (
        "product",  # Nova
        (
            "roadmap", "feature", "prd", "spec", "user story",
            "sprint", "backlog", "prioritize", "persona", "jtbd",
            "mvp", "launch", "retrospective", "a/b test", "analytics",
            "user research", "wireframe", "ux",
        ),
    ),
    (
        "finance",  # Sterling
        (
            "budget", "runway", "burn", "cash flow", "p&l",
            "invoice", "expense", "accounting", "tax", "revenue",
            "mrr", "arr", "gross margin", "unit economics", "cohort",
            "financial model",
        ),
    ),
    (
        "research",  # Iris
        (
            "paper", "literature", "study", "dataset", "benchmark",
            "prior art", "state of the art", "survey", "experiment",
            "hypothesis", "citation", "arxiv", "publish",
            "competitive analysis", "landscape", "trend report",
        ),
    ),
    (
        "legal_compliance",  # Themis
        (
            "contract", "nda", "agreement", "terms", "privacy policy",
            "gdpr", "ccpa", "hipaa", "soc2", "compliance", "clause",
            "indemnify", "liability", "intellectual property", "patent",
            "trademark", "copyright", "eula", "mutual nda",
        ),
    ),
    (
        "operations",  # Atlas
        (
            "process", "workflow", "sop", "runbook", "on-call",
            "incident", "status report", "okr", "okrs", "kpi", "kpis",
            "resource plan", "vendor", "procurement", "logistics",
            "capacity",
        ),
    ),
    (
        "skill_governance",  # Kira
        (
            "skill", "prompt", "template", "playbook", "skill refinery",
            "knowledge base", "training", "onboarding doc", "wiki",
            "guidelines", "style guide", "curriculum",
        ),
    ),
    (
        "security_operations",  # Rourke
        (
            "vulnerability", "cve", "exploit", "pentest", "malware",
            "ransomware", "phishing", "breach", "iam", "mfa", "rbac",
            "threat model", "attack surface", "waf", "siem", "soc",
            "zero trust", "incident response", "forensics",
        ),
    ),
)


# Compiled once at import. Each Mind gets a regex that matches any of
# its keywords with word boundaries -- avoids false matches like
# "codependent" triggering engineering's "code".
_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (
        slug,
        re.compile(
            r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b",
            re.IGNORECASE,
        ),
    )
    for slug, keywords in _MIND_KEYWORDS
)


# Minimum score to actually pick a Mind. 1 match = likely coincidence,
# 2+ = real topical match. Raise this if we get false picks in practice.
_MIN_SCORE = 2


def pick_mind(query: str) -> MindMatch:
    """Return the best-matching Mind slug for a free-text query.

    Zero-LLM, pure regex. Typical latency <5 ms for a 1-paragraph query.
    Returns ``MindMatch(slug=None, ...)`` when no Mind matches strongly
    enough -- in that case the orchestrator falls back to the generic
    core soul.
    """
    if not query or not query.strip():
        return MindMatch(slug=None, score=0, matched_keywords=())

    best_slug: str | None = None
    best_score = 0
    best_keywords: tuple[str, ...] = ()
    for slug, pattern in _COMPILED:
        matches = pattern.findall(query)
        if not matches:
            continue
        # Count UNIQUE keywords matched -- repeating the same word in a
        # long message should not double-count.
        unique = tuple(sorted({m.lower() for m in matches}))
        score = len(unique)
        if score > best_score:
            best_score = score
            best_slug = slug
            best_keywords = unique

    if best_score < _MIN_SCORE:
        return MindMatch(slug=None, score=best_score, matched_keywords=best_keywords)

    return MindMatch(slug=best_slug, score=best_score, matched_keywords=best_keywords)
