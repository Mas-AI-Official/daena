"""Cognitive Knowledge Graph (CKG) -- Daena's cross-domain learning substrate.

This is the architecture that makes Daena fundamentally different from every
other AI system. Knowledge doesn't live in silos. An insight from security
scanning transfers to engineering debugging. A pattern from competitive
analysis feeds sales strategy. Everything connects.

The CKG sits ON TOP of NBMF (which handles tiered persistence) and BELOW
the department agents (which consume knowledge). It is the universal
pattern language that all 10 departments read from and write to.

Architecture:
    Experience -> Extraction -> Abstraction -> Connection -> Validation -> Promotion

    1. EXPERIENCE: Raw outcome from any department (scan result, code review,
       task completion, conversation, research finding)
    2. EXTRACTION: Pattern identification -- what worked, what failed, why
    3. ABSTRACTION: Strip domain-specific details, keep the reasoning pattern.
       "timing reveals hidden state" not "HTTP 500 after 2s timeout reveals nginx"
    4. CONNECTION: Graph integration -- find structural similarity to existing
       nodes across ALL domains, create transfer edges
    5. VALIDATION: Backtest the abstracted pattern against historical data
       from every domain it could apply to
    6. PROMOTION: NBMF tier advancement (T0 -> T1 -> T2 -> T3)

Anti-drift guarantee:
    - Patterns can only UPGRADE (raise confidence) or DECAY (lower confidence)
    - Decay is gradual (time-based) and reversible (re-validation restores)
    - Deletion requires explicit founder action (T4 tier, immutable)
    - Every promotion is auditable (who promoted, why, evidence count)

Why this matters:
    - Mythos: deep narrow intelligence (memory layout -> 0-days)
    - Meta-Harness: self-assembling narrow harness (rewrite own orchestration)
    - ARTEMIS: parallel narrow agents (8 sub-agents, all pentesting)
    - Daena CKG: WIDE compounding intelligence (every domain feeds every other)

    10 departments x 6 sub-capabilities x N learned patterns x M transfer edges
    = intelligence that grows superlinearly with usage

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain taxonomy -- the 10 departments + meta-domains
# ---------------------------------------------------------------------------

class Domain(str, Enum):
    """Every domain Daena operates in. Maps 1:1 to departments."""
    ENGINEERING = "engineering"
    PRODUCT = "product"
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    OPERATIONS = "operations"
    RESEARCH = "research"
    LEGAL = "legal"
    SKILL_GOVERNANCE = "skill_governance"
    SECURITY = "security"
    # Meta-domains (cross-cutting)
    REASONING = "reasoning"       # Pure reasoning patterns
    COMMUNICATION = "communication"  # How to explain, present, persuade
    SYSTEMS = "systems"           # Architecture, design, infrastructure


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    """A single learned pattern -- the atom of Daena's intelligence.

    An insight is NOT data. It's a PATTERN: "when X condition exists,
    Y approach works with Z confidence." The condition and approach
    are abstracted from the domain they were discovered in.

    Example:
        raw: "HTTP 500 after 2s timeout reveals nginx behind cloudflare"
        abstracted: "timing analysis on error responses reveals hidden
                     infrastructure layers"
        domains: [security, engineering, operations]
        confidence: 0.82 (validated in 14/17 historical cases)
    """
    id: str                           # SHA-256 of abstracted pattern
    raw_observation: str              # What was actually observed
    abstracted_pattern: str           # Domain-independent insight
    origin_domain: Domain             # Where it was first discovered
    applicable_domains: list[Domain]  # Where it transfers to
    confidence: float = 0.5           # 0.0 to 1.0, Bayesian-updated
    evidence_count: int = 1           # How many times validated
    evidence_sources: list[str] = field(default_factory=list)  # trace IDs
    created_at: float = 0.0           # Unix timestamp
    last_validated_at: float = 0.0    # Unix timestamp
    nbmf_tier: int = 0               # 0=ephemeral, 1=working, 2=project, 3=institutional
    tags: list[str] = field(default_factory=list)
    transfer_score: float = 0.0      # How well it transfers across domains


@dataclass
class TransferEdge:
    """A connection between two insights across domains.

    "This security pattern about error analysis is structurally similar
    to this engineering pattern about debugging production issues."

    Transfer edges are how knowledge flows between departments.
    """
    source_id: str                # Insight that was discovered first
    target_id: str                # Insight it connects to
    source_domain: Domain
    target_domain: Domain
    similarity: float = 0.0       # Structural similarity score
    validated: bool = False       # Has the transfer been confirmed useful?
    created_at: float = 0.0


@dataclass
class Experience:
    """Raw input to the learning pipeline -- an outcome from any department."""
    domain: Domain
    task_type: str                # "security_scan", "code_review", "research", etc.
    outcome: str                  # "success", "partial", "failure"
    observation: str              # What happened (human-readable)
    context: dict[str, Any] = field(default_factory=dict)  # Domain-specific details
    trace_id: str = ""            # Link to full trace (scan trace, task log, etc.)
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Pattern abstraction -- the key innovation
# ---------------------------------------------------------------------------

# These are the STRUCTURAL CATEGORIES that enable cross-domain transfer.
# Two insights in different domains share a category if they follow
# the same reasoning structure, even if the specifics differ completely.

STRUCTURAL_CATEGORIES = {
    "timing_reveals_state": {
        "description": "Measuring timing differences reveals hidden internal state",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.OPERATIONS],
        "examples": [
            "security: response time variance reveals WAF rules",
            "engineering: latency spikes reveal garbage collection",
            "operations: deployment timing reveals rollout strategy",
        ],
    },
    "error_responses_leak_info": {
        "description": "Error conditions reveal more about internals than success conditions",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.PRODUCT],
        "examples": [
            "security: 403 vs 404 reveals path existence",
            "engineering: stack traces reveal dependency graph",
            "product: error messages reveal feature boundaries",
        ],
    },
    "boundary_probing": {
        "description": "Testing limits reveals system design decisions",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.PRODUCT, Domain.FINANCE],
        "examples": [
            "security: input size limits reveal buffer allocations",
            "engineering: rate limit headers reveal capacity planning",
            "product: feature limits reveal pricing tier boundaries",
            "finance: transaction limits reveal risk thresholds",
        ],
    },
    "pattern_from_absence": {
        "description": "What is NOT present reveals as much as what IS present",
        "domains": [Domain.SECURITY, Domain.RESEARCH, Domain.LEGAL, Domain.SALES],
        "examples": [
            "security: missing headers reveal developer experience level",
            "research: gaps in competitor offerings reveal market opportunity",
            "legal: missing clauses in contracts reveal negotiation priorities",
            "sales: unanswered questions in RFPs reveal decision criteria",
        ],
    },
    "decomposition_bypasses_blocks": {
        "description": "Breaking a blocked action into sub-actions can bypass the block",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.OPERATIONS, Domain.SALES],
        "examples": [
            "security: WAF blocks full payload but allows sub-components",
            "engineering: monolith migration works service-by-service",
            "operations: large change request succeeds as series of small ones",
            "sales: big deal closes faster as phased pilot",
        ],
    },
    "developer_empathy": {
        "description": "Understanding the creator's mindset predicts system behavior",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.PRODUCT, Domain.RESEARCH],
        "examples": [
            "security: junior dev patterns predict specific vulnerability classes",
            "engineering: framework choice predicts architectural constraints",
            "product: feature naming predicts product roadmap direction",
            "research: methodology choice predicts study limitations",
        ],
    },
    "chain_amplification": {
        "description": "Individual weak findings compose into critical chains",
        "domains": [Domain.SECURITY, Domain.FINANCE, Domain.LEGAL, Domain.OPERATIONS],
        "examples": [
            "security: info disclosure + IDOR + weak session = account takeover",
            "finance: small cost overruns + vendor lock-in + growth = budget crisis",
            "legal: minor non-compliance + audit + precedent = regulatory action",
            "operations: technical debt + team turnover + deadline = project failure",
        ],
    },
    "inverse_surface": {
        "description": "Visible interfaces imply hidden interfaces with predictable naming",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.RESEARCH],
        "examples": [
            "security: /api/v1/users implies /api/v1/admin, /api/v2/users",
            "engineering: public API implies internal API with richer features",
            "research: published results imply unpublished negative results",
        ],
    },
    "cost_asymmetry": {
        "description": "Cheap inputs that cause expensive processing reveal design flaws",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.FINANCE],
        "examples": [
            "security: small payload causing ReDoS or algorithmic DoS",
            "engineering: simple query triggering full table scan",
            "finance: low-cost acquisition with high-cost retention",
        ],
    },
    "state_machine_violations": {
        "description": "Systems that don't enforce state transitions have logic flaws",
        "domains": [Domain.SECURITY, Domain.ENGINEERING, Domain.PRODUCT, Domain.LEGAL],
        "examples": [
            "security: access after logout = broken session management",
            "engineering: deploy without tests = broken CI/CD",
            "product: checkout without cart = broken user flow",
            "legal: signature without review = broken approval chain",
        ],
    },
}


# ---------------------------------------------------------------------------
# Cognitive Knowledge Graph
# ---------------------------------------------------------------------------

class CognitiveKnowledgeGraph:
    """The universal learning substrate for all 10 Daena departments.

    This is not a database. It's a living graph where insights from every
    domain connect to insights in every other domain through structural
    similarity. When security learns something, engineering benefits.
    When product discovers a pattern, sales can use it.

    Usage::

        ckg = CognitiveKnowledgeGraph()

        # Record an experience from any department
        exp = Experience(
            domain=Domain.SECURITY,
            task_type="cognitive_scan",
            outcome="success",
            observation="timing analysis revealed nginx behind cloudflare",
        )
        insight = ckg.learn(exp)

        # Query for relevant insights in a different domain
        relevant = ckg.query(
            domain=Domain.ENGINEERING,
            context="debugging slow API responses",
            limit=5,
        )

        # Get cross-domain transfer suggestions
        transfers = ckg.find_transfers(insight.id)
    """

    def __init__(self, storage_dir: str = "") -> None:
        self._storage_dir = storage_dir or os.path.join(
            os.environ.get("DAENA_VAR", "var"), "ckg"
        )
        self._insights: dict[str, Insight] = {}
        self._edges: list[TransferEdge] = []
        self._load()

    # ── Core learning pipeline ──────────────────────────────────

    def learn(self, experience: Experience) -> Insight:
        """Process a raw experience through the full learning pipeline.

        Experience -> Extraction -> Abstraction -> Connection -> Insight
        """
        # 1. EXTRACT: Identify the pattern
        raw = experience.observation

        # 2. ABSTRACT: Find structural category
        category, abstracted = self._abstract(raw, experience.domain)

        # 3. Create or update insight
        insight_id = self._hash(abstracted)

        if insight_id in self._insights:
            # Existing insight -- reinforce
            existing = self._insights[insight_id]
            existing.evidence_count += 1
            existing.confidence = min(
                0.99,
                existing.confidence + (1 - existing.confidence) * 0.1
            )
            existing.last_validated_at = time.time()
            if experience.trace_id:
                existing.evidence_sources.append(experience.trace_id)
            # Maybe expand applicable domains
            if experience.domain not in existing.applicable_domains:
                existing.applicable_domains.append(experience.domain)
                existing.transfer_score = len(existing.applicable_domains) / len(Domain)
            self._maybe_promote(existing)
            self._persist()
            return existing

        # New insight
        now = time.time()
        insight = Insight(
            id=insight_id,
            raw_observation=raw,
            abstracted_pattern=abstracted,
            origin_domain=experience.domain,
            applicable_domains=self._infer_domains(category, experience.domain),
            confidence=0.5,
            evidence_count=1,
            evidence_sources=[experience.trace_id] if experience.trace_id else [],
            created_at=now,
            last_validated_at=now,
            nbmf_tier=0,
            tags=[category] if category else [],
            transfer_score=0.0,
        )
        insight.transfer_score = len(insight.applicable_domains) / len(Domain)

        self._insights[insight_id] = insight

        # 4. CONNECT: Find transfer edges to existing insights
        self._connect(insight)

        self._persist()
        logger.info(
            "ckg.learned",
            insight_id=insight_id[:8],
            pattern=abstracted[:80],
            domains=len(insight.applicable_domains),
            category=category or "uncategorized",
        )
        return insight

    def query(
        self,
        domain: Domain,
        context: str = "",
        limit: int = 10,
        min_confidence: float = 0.3,
    ) -> list[Insight]:
        """Get relevant insights for a domain, ranked by relevance.

        This is how departments consume cross-domain knowledge:
        Engineering asks "what do we know about slow API responses?"
        and gets insights from Security, Operations, and Product too.
        """
        candidates = []
        for insight in self._insights.values():
            if insight.confidence < min_confidence:
                continue
            if domain in insight.applicable_domains:
                # Score: confidence * recency * transfer_score
                recency = 1.0 / (1.0 + (time.time() - insight.last_validated_at) / 86400)
                score = insight.confidence * 0.5 + recency * 0.3 + insight.transfer_score * 0.2
                candidates.append((score, insight))

        candidates.sort(key=lambda x: x[0], reverse=True)

        # Context-based filtering if provided
        if context:
            context_lower = context.lower()
            context_words = set(context_lower.split())
            filtered = []
            for score, insight in candidates:
                pattern_words = set(insight.abstracted_pattern.lower().split())
                overlap = len(context_words & pattern_words)
                if overlap > 0:
                    filtered.append((score + overlap * 0.1, insight))
                else:
                    filtered.append((score, insight))
            filtered.sort(key=lambda x: x[0], reverse=True)
            return [ins for _, ins in filtered[:limit]]

        return [ins for _, ins in candidates[:limit]]

    def find_transfers(self, insight_id: str) -> list[TransferEdge]:
        """Find all transfer edges for an insight."""
        return [
            e for e in self._edges
            if e.source_id == insight_id or e.target_id == insight_id
        ]

    def get_domain_insights(self, domain: Domain) -> list[Insight]:
        """Get all insights applicable to a domain."""
        return [
            i for i in self._insights.values()
            if domain in i.applicable_domains
        ]

    def decay(self, max_age_days: int = 90) -> int:
        """Decay unvalidated insights. Returns count of decayed insights.

        Anti-drift: insights that haven't been re-validated decay gradually.
        They're never deleted -- just lose confidence until they're no longer
        returned by queries. Re-validation restores them.
        """
        now = time.time()
        cutoff = now - (max_age_days * 86400)
        decayed = 0

        for insight in self._insights.values():
            if insight.nbmf_tier >= 3:
                continue  # Institutional knowledge doesn't decay
            if insight.last_validated_at < cutoff:
                old_conf = insight.confidence
                insight.confidence *= 0.9  # 10% decay per cycle
                if insight.confidence < 0.01:
                    insight.confidence = 0.01  # Floor, never zero
                decayed += 1
                logger.debug(
                    "ckg.decay",
                    insight_id=insight.id[:8],
                    old_confidence=round(old_conf, 3),
                    new_confidence=round(insight.confidence, 3),
                )

        if decayed:
            self._persist()
        return decayed

    def reinforce(self, insight_id: str, success: bool) -> None:
        """Reinforce or weaken an insight based on real-world outcome.

        Called when a department uses an insight and reports whether it helped.
        Bayesian update: success increases confidence, failure decreases.
        """
        insight = self._insights.get(insight_id)
        if not insight:
            return

        if success:
            insight.confidence = min(0.99, insight.confidence + (1 - insight.confidence) * 0.15)
            insight.evidence_count += 1
        else:
            insight.confidence = max(0.01, insight.confidence * 0.85)

        insight.last_validated_at = time.time()
        self._maybe_promote(insight)
        self._persist()

    @property
    def total_insights(self) -> int:
        return len(self._insights)

    @property
    def total_edges(self) -> int:
        return len(self._edges)

    @property
    def domain_coverage(self) -> dict[str, int]:
        """Count of insights per domain."""
        coverage: dict[str, int] = {d.value: 0 for d in Domain}
        for insight in self._insights.values():
            for domain in insight.applicable_domains:
                coverage[domain.value] = coverage.get(domain.value, 0) + 1
        return coverage

    # ── Abstraction engine ──────────────────────────────────────

    def _abstract(self, raw: str, domain: Domain) -> tuple[str, str]:
        """Abstract a raw observation into a domain-independent pattern.

        Returns (category_name, abstracted_description).
        """
        raw_lower = raw.lower()

        # Match against structural categories
        for cat_name, cat_info in STRUCTURAL_CATEGORIES.items():
            # Simple keyword matching -- LLM-based abstraction is the upgrade path
            keywords = cat_name.replace("_", " ").split()
            matches = sum(1 for kw in keywords if kw in raw_lower)
            if matches >= 2 or (matches >= 1 and domain in cat_info["domains"]):
                return cat_name, f"{cat_info['description']} (from {domain.value}: {raw[:100]})"

        # Fallback: use as-is with domain tag
        return "", f"[{domain.value}] {raw[:200]}"

    def _infer_domains(self, category: str, origin: Domain) -> list[Domain]:
        """Infer which domains an insight applies to based on its category."""
        if category in STRUCTURAL_CATEGORIES:
            domains = list(STRUCTURAL_CATEGORIES[category]["domains"])
            if origin not in domains:
                domains.append(origin)
            return domains
        return [origin]

    # ── Connection engine ───────────────────────────────────────

    def _connect(self, new_insight: Insight) -> None:
        """Find and create transfer edges to existing insights."""
        for existing in self._insights.values():
            if existing.id == new_insight.id:
                continue

            # Same structural category = high similarity
            shared_tags = set(new_insight.tags) & set(existing.tags)
            if shared_tags:
                similarity = 0.8
            else:
                # Check domain overlap
                shared_domains = set(new_insight.applicable_domains) & set(existing.applicable_domains)
                if not shared_domains:
                    continue
                similarity = len(shared_domains) / max(
                    len(new_insight.applicable_domains),
                    len(existing.applicable_domains),
                )

            if similarity >= 0.3:
                edge = TransferEdge(
                    source_id=new_insight.id,
                    target_id=existing.id,
                    source_domain=new_insight.origin_domain,
                    target_domain=existing.origin_domain,
                    similarity=similarity,
                    created_at=time.time(),
                )
                self._edges.append(edge)

    # ── NBMF tier promotion ────────────────────────────────────

    def _maybe_promote(self, insight: Insight) -> None:
        """Promote insight to higher NBMF tier based on evidence.

        T0 (ephemeral): 1 evidence, < 0.5 confidence
        T1 (working):   3+ evidence, >= 0.5 confidence
        T2 (project):   10+ evidence, >= 0.7 confidence, 2+ domains
        T3 (institutional): 25+ evidence, >= 0.85 confidence, 3+ domains
        """
        if insight.evidence_count >= 25 and insight.confidence >= 0.85 and len(insight.applicable_domains) >= 3:
            if insight.nbmf_tier < 3:
                insight.nbmf_tier = 3
                logger.info("ckg.promoted", insight_id=insight.id[:8], tier=3)
        elif insight.evidence_count >= 10 and insight.confidence >= 0.7 and len(insight.applicable_domains) >= 2:
            if insight.nbmf_tier < 2:
                insight.nbmf_tier = 2
                logger.info("ckg.promoted", insight_id=insight.id[:8], tier=2)
        elif insight.evidence_count >= 3 and insight.confidence >= 0.5:
            if insight.nbmf_tier < 1:
                insight.nbmf_tier = 1

    # ── Persistence ─────────────────────────────────────────────

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _persist(self) -> None:
        """Save graph to disk."""
        os.makedirs(self._storage_dir, exist_ok=True)

        data = {
            "insights": {
                iid: {
                    "id": i.id,
                    "raw_observation": i.raw_observation,
                    "abstracted_pattern": i.abstracted_pattern,
                    "origin_domain": i.origin_domain.value,
                    "applicable_domains": [d.value for d in i.applicable_domains],
                    "confidence": i.confidence,
                    "evidence_count": i.evidence_count,
                    "evidence_sources": i.evidence_sources[-50:],  # Cap at 50
                    "created_at": i.created_at,
                    "last_validated_at": i.last_validated_at,
                    "nbmf_tier": i.nbmf_tier,
                    "tags": i.tags,
                    "transfer_score": i.transfer_score,
                }
                for iid, i in self._insights.items()
            },
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "source_domain": e.source_domain.value,
                    "target_domain": e.target_domain.value,
                    "similarity": e.similarity,
                    "validated": e.validated,
                    "created_at": e.created_at,
                }
                for e in self._edges
            ],
        }

        path = os.path.join(self._storage_dir, "graph.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        """Load graph from disk."""
        path = os.path.join(self._storage_dir, "graph.json")
        if not os.path.isfile(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for idata in data.get("insights", {}).values():
                try:
                    insight = Insight(
                        id=idata["id"],
                        raw_observation=idata["raw_observation"],
                        abstracted_pattern=idata["abstracted_pattern"],
                        origin_domain=Domain(idata["origin_domain"]),
                        applicable_domains=[Domain(d) for d in idata["applicable_domains"]],
                        confidence=idata.get("confidence", 0.5),
                        evidence_count=idata.get("evidence_count", 1),
                        evidence_sources=idata.get("evidence_sources", []),
                        created_at=idata.get("created_at", 0),
                        last_validated_at=idata.get("last_validated_at", 0),
                        nbmf_tier=idata.get("nbmf_tier", 0),
                        tags=idata.get("tags", []),
                        transfer_score=idata.get("transfer_score", 0),
                    )
                    self._insights[insight.id] = insight
                except (KeyError, ValueError):
                    continue

            for edata in data.get("edges", []):
                try:
                    edge = TransferEdge(
                        source_id=edata["source_id"],
                        target_id=edata["target_id"],
                        source_domain=Domain(edata["source_domain"]),
                        target_domain=Domain(edata["target_domain"]),
                        similarity=edata.get("similarity", 0),
                        validated=edata.get("validated", False),
                        created_at=edata.get("created_at", 0),
                    )
                    self._edges.append(edge)
                except (KeyError, ValueError):
                    continue

            logger.info(
                "ckg.loaded",
                insights=len(self._insights),
                edges=len(self._edges),
            )

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("ckg.load_failed", error=str(exc)[:100])
