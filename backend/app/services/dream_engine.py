"""
Dream Engine -- Autonomous Memory Consolidation for NBMF
MAS-AI Technologies Inc. | Patent Pending MAS-AI-2026-NBMF-PROV

Runs automatically on a schedule. Never needs manual invocation.
Operates only on agent experience metadata. Never touches user content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# -- Sensitivity patterns -------------------------------------------------------
SENSITIVE_PATTERNS: dict[str, list[str]] = {
    "pii": [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",   # email
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",                        # phone
        r"\b\d{3}-\d{2}-\d{4}\b",                                     # SSN
        r"\b\d{9}\b",                                                  # SIN
    ],
    "financial": [
        r"\$[\d,]+\.?\d*",                                             # dollar amounts
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",               # card numbers
        r"\bINVOICE[-\s]?\d+\b",                                       # invoice refs
    ],
    "legal": [
        r"\b(hereby|hereinafter|whereas|indemnif|liabilit|jurisdicti)\b",
        r"\b(plaintiff|defendant|arbitration|litigation|tort)\b",
    ],
    "medical": [
        r"\b(diagnosis|diagnosed|medication|prescribed|treatment|dosage)\b",
        r"\b(patient|symptoms|condition|disorder|syndrome)\b",
    ],
    "credentials": [
        r"\b(password|passwd|secret|api[_\s]?key|token|bearer)\s*[=:]\s*\S+",
        r"\bsk-[A-Za-z0-9]{20,}\b",                                   # OpenAI-style keys
    ],
}


def is_sensitive(text: str) -> tuple[bool, list[str]]:
    """Return (is_sensitive, [detected_categories])."""
    if not text:
        return False, []
    detected = []
    for category, patterns in SENSITIVE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(category)
                break
    return bool(detected), detected


# -- Similarity helpers ----------------------------------------------------------

def simple_token_similarity(a: str, b: str) -> float:
    """Fast token-overlap similarity (Jaccard). No ML dependency."""
    if not a or not b:
        return 0.0
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    union = len(ta | tb)
    return intersection / union if union else 0.0


# -- Core data structures -------------------------------------------------------

@dataclass
class DreamAction:
    action_type: str        # MERGE, PROMOTE, CONTRADICT, SYNTHESIZE, DECAY, SENSITIVE
    entry_ids: list[int]
    result_entry_id: int | None = None
    reason: str = ""
    trust_delta: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DreamReport:
    cycle_id: str
    started_at: datetime
    completed_at: datetime | None = None
    entries_scanned: int = 0
    merged: int = 0
    promoted_by_association: int = 0
    contradictions_flagged: int = 0
    patterns_synthesized: int = 0
    entries_decayed: int = 0
    sensitive_reencoded: int = 0
    lineage_entries_created: int = 0
    actions: list[DreamAction] = field(default_factory=list)
    error: str | None = None

    def summary(self) -> dict:
        duration_ms = 0
        if self.completed_at:
            duration_ms = int(
                (self.completed_at - self.started_at).total_seconds() * 1000
            )
        return {
            "cycle_id": self.cycle_id,
            "duration_ms": duration_ms,
            "entries_scanned": self.entries_scanned,
            "merged": self.merged,
            "promoted_by_association": self.promoted_by_association,
            "contradictions_flagged": self.contradictions_flagged,
            "patterns_synthesized": self.patterns_synthesized,
            "entries_decayed": self.entries_decayed,
            "sensitive_reencoded": self.sensitive_reencoded,
            "lineage_entries_created": self.lineage_entries_created,
            "error": self.error,
        }


# -- Dream Engine (async) -------------------------------------------------------

class DreamEngine:
    """
    Autonomous memory consolidation engine for NBMF.

    Runs on a background schedule. Consolidates, promotes, merges,
    synthesizes, decays, and sensitivity-scans agent memory.
    Never touches user content. All actions logged in LearningLog.

    Patent Pending: MAS-AI-2026-NBMF-PROV
    """

    SIMILARITY_THRESHOLD = 0.75
    ASSOCIATION_TRUST_MIN = 5
    MERGE_MIN_CLUSTER = 3
    MERGE_TRUST_BONUS = 0.1
    DECAY_30D_PENALTY = 0.05
    DECAY_90D_DEMOTE = True
    DECAY_180D_ARCHIVE = True

    def __init__(self) -> None:
        self.last_run: datetime | None = None
        self.total_cycles = 0
        self._running = False

    # -- Public interface --------------------------------------------------------

    async def run_cycle(self, db_session: Any, tenant_id: str = "system") -> DreamReport:
        """Run one full consolidation cycle. Called by scheduler or API."""
        from app.services.memory import MemoryService

        cycle_id = hashlib.sha256(
            f"{tenant_id}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        report = DreamReport(cycle_id=cycle_id, started_at=datetime.utcnow())
        self._running = True

        logger.info(f"[DreamEngine] Starting cycle {cycle_id}")

        try:
            svc = MemoryService(db_session)
            entries = await svc.get_all_entries(tenant_id=tenant_id)
            report.entries_scanned = len(entries)

            if not entries:
                logger.info("[DreamEngine] No entries to process.")
                report.completed_at = datetime.utcnow()
                self.last_run = report.completed_at
                self.total_cycles += 1
                self._running = False
                return report

            # Phase 1: Sensitivity scan (safety first)
            await self._phase_sensitivity_scan(svc, entries, report, tenant_id)

            # Phase 2: Cluster and merge
            clusters = self._build_clusters(entries)
            await self._phase_merge(svc, clusters, report, tenant_id)

            # Phase 3: Trust by association
            await self._phase_promote_by_association(svc, entries, report, tenant_id)

            # Phase 4: Contradiction detection
            await self._phase_contradict(svc, entries, report, tenant_id)

            # Phase 5: Pattern synthesis
            await self._phase_synthesize(svc, entries, report, tenant_id)

            # Phase 6: Decay stale entries
            await self._phase_decay(svc, entries, report, tenant_id)

            # Write dream report as memory entry
            await self._write_dream_report(svc, report, tenant_id)

            await db_session.commit()

        except Exception as e:
            report.error = str(e)
            logger.error(f"[DreamEngine] Cycle {cycle_id} failed: {e}", exc_info=True)
            await db_session.rollback()

        report.completed_at = datetime.utcnow()
        self.last_run = report.completed_at
        self.total_cycles += 1
        self._running = False

        logger.info(
            f"[DreamEngine] Cycle {cycle_id} complete: "
            f"merged={report.merged}, promoted={report.promoted_by_association}, "
            f"synthesized={report.patterns_synthesized}, "
            f"decayed={report.entries_decayed}, "
            f"sensitive={report.sensitive_reencoded}"
        )
        return report

    def should_run(self, idle_seconds: int = 300) -> bool:
        """Check if enough time has passed since last run."""
        if self.last_run is None:
            return True
        elapsed = (datetime.utcnow() - self.last_run).total_seconds()
        return elapsed >= idle_seconds

    @property
    def is_running(self) -> bool:
        return self._running

    # -- Phase 1: Sensitivity scan -----------------------------------------------

    async def _phase_sensitivity_scan(
        self, svc: Any, entries: list[dict], report: DreamReport, tenant_id: str
    ) -> None:
        for entry in entries:
            content = entry.get("content", "")
            metadata_str = json.dumps(entry.get("metadata", {}))
            combined = f"{content} {metadata_str}"

            sensitive, categories = is_sensitive(combined)
            if sensitive and not entry.get("is_sensitive"):
                try:
                    await svc.dream_mark_sensitive(
                        entry_id=entry["id"],
                        categories=categories,
                        tenant_id=tenant_id,
                    )
                    report.sensitive_reencoded += 1
                    report.lineage_entries_created += 1
                    report.actions.append(DreamAction(
                        action_type="SENSITIVE",
                        entry_ids=[entry["id"]],
                        reason=f"Detected: {', '.join(categories)}",
                        metadata={"categories": categories},
                    ))
                except Exception as e:
                    logger.warning(f"[DreamEngine] Sensitivity mark failed: {e}")

    # -- Phase 2: Cluster and merge ----------------------------------------------

    def _build_clusters(self, entries: list[dict]) -> list[list[dict]]:
        clusters: list[list[dict]] = []
        used: set[int] = set()

        for i, entry in enumerate(entries):
            if i in used:
                continue
            cluster = [entry]
            used.add(i)
            for j, other in enumerate(entries):
                if j in used or i == j:
                    continue
                sim = simple_token_similarity(
                    entry.get("content", ""),
                    other.get("content", ""),
                )
                if sim >= self.SIMILARITY_THRESHOLD:
                    cluster.append(other)
                    used.add(j)
            clusters.append(cluster)

        return clusters

    async def _phase_merge(
        self, svc: Any, clusters: list[list[dict]], report: DreamReport, tenant_id: str
    ) -> None:
        for cluster in clusters:
            if len(cluster) < self.MERGE_MIN_CLUSTER:
                continue
            successes = [e for e in cluster if e.get("success_flag") is True]
            if len(successes) < self.MERGE_MIN_CLUSTER:
                continue

            avg_trust = sum(e.get("trust_score", 0.5) for e in successes) / len(successes)
            merged_trust = min(1.0, avg_trust + self.MERGE_TRUST_BONUS)
            merged_content = self._synthesize_content(successes)

            try:
                new_id = await svc.dream_store_pattern(
                    content=merged_content,
                    trust_score=merged_trust,
                    tenant_id=tenant_id,
                    metadata={
                        "dream_merged_from": [e["id"] for e in successes],
                        "dream_cycle": True,
                        "source_count": len(successes),
                    },
                )
                for entry in successes:
                    await svc.dream_archive_entry(entry["id"], tenant_id)

                report.merged += 1
                report.lineage_entries_created += len(successes) + 1
                report.actions.append(DreamAction(
                    action_type="MERGE",
                    entry_ids=[e["id"] for e in successes],
                    result_entry_id=new_id,
                    reason=f"Merged {len(successes)} similar successful experiences",
                    trust_delta=merged_trust - avg_trust,
                ))
            except Exception as e:
                logger.warning(f"[DreamEngine] Merge failed: {e}")

    def _synthesize_content(self, entries: list[dict]) -> str:
        contents = [e.get("content", "") for e in entries if e.get("content")]
        if not contents:
            return "Synthesized pattern from dream consolidation"
        all_tokens: list[str] = []
        for c in contents:
            all_tokens.extend(c.split())
        from collections import Counter
        common = [w for w, _ in Counter(all_tokens).most_common(30)]
        return f"DREAM_SYNTHESIZED: {' '.join(common)}"

    # -- Phase 3: Trust by association -------------------------------------------

    async def _phase_promote_by_association(
        self, svc: Any, entries: list[dict], report: DreamReport, tenant_id: str
    ) -> None:
        trusted = [
            e for e in entries
            if not e.get("is_quarantined") and e.get("trust_score", 0) >= 0.7
        ]
        quarantined = [e for e in entries if e.get("is_quarantined")]

        for q_entry in quarantined:
            peer_count = 0
            for t_entry in trusted:
                sim = simple_token_similarity(
                    q_entry.get("content", ""),
                    t_entry.get("content", ""),
                )
                if sim >= self.SIMILARITY_THRESHOLD:
                    peer_count += 1
                if peer_count >= self.ASSOCIATION_TRUST_MIN:
                    break

            if peer_count >= self.ASSOCIATION_TRUST_MIN:
                try:
                    await svc.dream_promote_entry(
                        entry_id=q_entry["id"],
                        new_trust=0.72,
                        tenant_id=tenant_id,
                        reason="dream_association_promotion",
                    )
                    report.promoted_by_association += 1
                    report.lineage_entries_created += 1
                    report.actions.append(DreamAction(
                        action_type="PROMOTE",
                        entry_ids=[q_entry["id"]],
                        reason=f"Associated with {peer_count} trusted peers",
                        trust_delta=0.72 - q_entry.get("trust_score", 0),
                    ))
                except Exception as e:
                    logger.warning(f"[DreamEngine] Association promote failed: {e}")

    # -- Phase 4: Contradiction detection ----------------------------------------

    async def _phase_contradict(
        self, svc: Any, entries: list[dict], report: DreamReport, tenant_id: str
    ) -> None:
        by_intent: dict[str, list[dict]] = {}
        for entry in entries:
            intent = entry.get("metadata", {}).get("intent", "unknown")
            by_intent.setdefault(intent, []).append(entry)

        for intent, group in by_intent.items():
            if intent == "unknown" or len(group) < 2:
                continue
            successes = [e for e in group if e.get("success_flag") is True]
            failures = [e for e in group if e.get("success_flag") is False]
            if not successes or not failures:
                continue

            for fail_entry in failures:
                for succ_entry in successes:
                    sim = simple_token_similarity(
                        fail_entry.get("content", ""),
                        succ_entry.get("content", ""),
                    )
                    if sim >= self.SIMILARITY_THRESHOLD:
                        try:
                            await svc.dream_flag_contradiction(
                                entry_ids=[fail_entry["id"], succ_entry["id"]],
                                tenant_id=tenant_id,
                            )
                            report.contradictions_flagged += 1
                            report.lineage_entries_created += 1
                            report.actions.append(DreamAction(
                                action_type="CONTRADICT",
                                entry_ids=[fail_entry["id"], succ_entry["id"]],
                                reason=f"Opposing outcomes for intent: {intent}",
                                trust_delta=-0.15,
                            ))
                        except Exception as e:
                            logger.warning(f"[DreamEngine] Contradiction flag failed: {e}")
                        break

    # -- Phase 5: Pattern synthesis -----------------------------------------------

    async def _phase_synthesize(
        self, svc: Any, entries: list[dict], report: DreamReport, tenant_id: str
    ) -> None:
        model_by_intent: dict[str, dict[str, int]] = {}

        for entry in entries:
            if not entry.get("success_flag"):
                continue
            meta = entry.get("metadata", {})
            model = meta.get("model_used")
            intent = meta.get("intent", "unknown")

            if model and intent != "unknown":
                if intent not in model_by_intent:
                    model_by_intent[intent] = {}
                model_by_intent[intent][model] = model_by_intent[intent].get(model, 0) + 1

        for intent, model_counts in model_by_intent.items():
            if not model_counts:
                continue
            best_model = max(model_counts, key=model_counts.get)  # type: ignore[arg-type]
            count = model_counts[best_model]
            if count >= 3:
                pattern = (
                    f"DREAM_PATTERN: For intent '{intent}', "
                    f"model '{best_model}' succeeded {count} times. "
                    f"Prefer this model for similar tasks."
                )
                try:
                    await svc.dream_store_pattern(
                        content=pattern,
                        trust_score=0.75,
                        tenant_id=tenant_id,
                        metadata={
                            "dream_synthesized": True,
                            "intent": intent,
                            "recommended_model": best_model,
                            "evidence_count": count,
                        },
                    )
                    report.patterns_synthesized += 1
                    report.lineage_entries_created += 1
                    report.actions.append(DreamAction(
                        action_type="SYNTHESIZE",
                        entry_ids=[],
                        reason=pattern,
                        metadata={"intent": intent, "model": best_model},
                    ))
                except Exception as e:
                    logger.warning(f"[DreamEngine] Synthesis store failed: {e}")

    # -- Phase 6: Decay ----------------------------------------------------------

    async def _phase_decay(
        self, svc: Any, entries: list[dict], report: DreamReport, tenant_id: str
    ) -> None:
        now = datetime.utcnow()

        for entry in entries:
            last_accessed_str = entry.get("last_accessed") or entry.get("created_at")
            if not last_accessed_str:
                continue
            try:
                if isinstance(last_accessed_str, str):
                    last_accessed = datetime.fromisoformat(
                        last_accessed_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                else:
                    last_accessed = last_accessed_str

                days_idle = (now - last_accessed).days
                current_trust = entry.get("trust_score", 0.5)

                if days_idle >= 180 and self.DECAY_180D_ARCHIVE:
                    await svc.dream_archive_entry(entry["id"], tenant_id)
                    report.entries_decayed += 1
                elif days_idle >= 90 and self.DECAY_90D_DEMOTE:
                    await svc.dream_demote_tier(entry["id"], 0, tenant_id)
                    report.entries_decayed += 1
                elif days_idle >= 30:
                    new_trust = max(0.0, current_trust - self.DECAY_30D_PENALTY)
                    await svc.dream_update_trust(entry["id"], new_trust, tenant_id)
                    report.entries_decayed += 1
                    report.actions.append(DreamAction(
                        action_type="DECAY",
                        entry_ids=[entry["id"]],
                        reason=f"{days_idle} days idle",
                        trust_delta=new_trust - current_trust,
                    ))
            except Exception as e:
                logger.debug(f"[DreamEngine] Decay skip for {entry.get('id')}: {e}")

    # -- Dream report storage ----------------------------------------------------

    async def _write_dream_report(
        self, svc: Any, report: DreamReport, tenant_id: str
    ) -> None:
        try:
            summary = report.summary()
            await svc.dream_store_pattern(
                content=f"DREAM_REPORT: {json.dumps(summary)}",
                trust_score=1.0,
                tenant_id=tenant_id,
                metadata={"dream_report": True, "cycle_id": report.cycle_id},
            )
        except Exception as e:
            logger.warning(f"[DreamEngine] Could not write dream report: {e}")


# -- Singleton instance (stored on app.state) ------------------------------------

_dream_engine: DreamEngine | None = None


def get_dream_engine() -> DreamEngine:
    """Get or create the singleton DreamEngine instance."""
    global _dream_engine
    if _dream_engine is None:
        _dream_engine = DreamEngine()
    return _dream_engine
