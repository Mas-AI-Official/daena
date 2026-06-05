"""Tamper-evident audit chain.

Sanitized public mirror of Daena's backend/app/services/audit.py
hash-chain algorithm. Each entry's hash links to the previous one::

    entry_hash = sha256(actor | action_type | result | prev_hash | timestamp)
    prev_hash  = entry_hash of the preceding entry (GENESIS for the first)

Mutating, reordering, or dropping any entry breaks the walk, which
``verify`` detects and localizes. The payload format is byte-compatible
with the production ledger, so a trail produced here verifies under the
same rules Daena uses in production.

This slice is dependency-free (stdlib only) on purpose: the public
hackathon repo must carry no commercial config or database coupling.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AuditEntry:
    """One immutable record in the hash-chained ledger."""

    index: int
    actor_type: str
    actor_id: str | None
    action_type: str
    result: str
    risk_level: str
    governance_tier: int
    timestamp: str
    prev_hash: str | None
    entry_hash: str


def compute_hash(
    *,
    actor_id: str | None,
    action_type: str,
    result: str,
    prev_hash: str | None,
    timestamp: str,
) -> str:
    """Compute the SHA-256 entry hash.

    Identical payload layout to ``AuditService._compute_hash`` in the
    backend: pipe-joined, ``SYSTEM`` for a null actor, ``GENESIS`` for a
    null predecessor.
    """
    payload = "|".join(
        [
            str(actor_id) if actor_id else "SYSTEM",
            action_type,
            result,
            prev_hash or "GENESIS",
            timestamp,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditChain:
    """Append-only, hash-chained, in-memory audit ledger."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def append(
        self,
        *,
        actor_type: str,
        action_type: str,
        result: str,
        risk_level: str,
        governance_tier: int,
        timestamp: str,
        actor_id: str | None = None,
    ) -> AuditEntry:
        """Append a new event, linking it to the chain tail."""
        prev_hash = self._entries[-1].entry_hash if self._entries else None
        entry_hash = compute_hash(
            actor_id=actor_id,
            action_type=action_type,
            result=result,
            prev_hash=prev_hash,
            timestamp=timestamp,
        )
        entry = AuditEntry(
            index=len(self._entries),
            actor_type=actor_type,
            actor_id=actor_id,
            action_type=action_type,
            result=result,
            risk_level=risk_level,
            governance_tier=governance_tier,
            timestamp=timestamp,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> dict:
        """Walk the chain and re-derive each hash.

        Returns ``{valid, total_entries, first_broken_index, reason}``.
        ``reason`` is ``broken_link`` when a ``prev_hash`` pointer does
        not match the actual predecessor, or ``content_tamper`` when an
        entry's stored hash does not match its recomputed payload hash.
        """
        prev: str | None = None
        for i, e in enumerate(self._entries):
            if e.prev_hash != prev:
                return {
                    "valid": False,
                    "total_entries": len(self._entries),
                    "first_broken_index": i,
                    "reason": "broken_link",
                }
            recomputed = compute_hash(
                actor_id=e.actor_id,
                action_type=e.action_type,
                result=e.result,
                prev_hash=e.prev_hash,
                timestamp=e.timestamp,
            )
            if recomputed != e.entry_hash:
                return {
                    "valid": False,
                    "total_entries": len(self._entries),
                    "first_broken_index": i,
                    "reason": "content_tamper",
                }
            prev = e.entry_hash
        return {
            "valid": True,
            "total_entries": len(self._entries),
            "first_broken_index": None,
            "reason": None,
        }

    def to_list(self) -> list[dict]:
        return [asdict(e) for e in self._entries]

    @classmethod
    def from_list(cls, rows: list[dict]) -> "AuditChain":
        chain = cls()
        chain._entries = [AuditEntry(**r) for r in rows]
        return chain
