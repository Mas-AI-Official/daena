"""Gap 5: Interaction Logger -- Records every I/O pair for future DPO fine-tuning.

Captures every query-response interaction with metadata (model, latency, tokens,
difficulty, confidence) and implicit feedback scoring. Exports top interactions
and DPO pairs for supervised fine-tuning.

Implicit feedback heuristic:
    - User rephrases the same question -> previous answer was bad (0.3)
    - User moves to a new topic -> previous answer was accepted (0.7)
    - User says "thanks" / "great" / positive -> previous answer was good (1.0)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import aiosqlite

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Interaction:
    """A single logged query-response pair with metadata."""

    id: str
    timestamp: float
    session_id: str
    query: str
    response: str
    model_id: str
    difficulty: str
    confidence: float
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    feedback_score: float
    feedback_type: str
    tags: list[str]


@dataclass(slots=True)
class InteractionStats:
    """Aggregate statistics over a time window."""

    total: int
    avg_confidence: float
    avg_latency_ms: float
    top_model: str
    feedback_distribution: dict[str, int]


# ---------------------------------------------------------------------------
# SQL schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    model_id TEXT DEFAULT '',
    difficulty TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    latency_ms INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    feedback_score REAL DEFAULT 0.5,
    feedback_type TEXT DEFAULT 'none',
    tags TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_feedback ON interactions(feedback_score DESC);
"""

# Positive sentiment markers for implicit feedback detection
_POSITIVE_MARKERS: tuple[str, ...] = (
    "thanks",
    "thank you",
    "great",
    "perfect",
    "awesome",
    "excellent",
    "nice",
    "good answer",
    "that helps",
    "got it",
    "makes sense",
)

# Similarity threshold -- above this, the user is rephrasing the same question
_REPHRASE_THRESHOLD: float = 0.55


# ---------------------------------------------------------------------------
# InteractionLogger
# ---------------------------------------------------------------------------


class InteractionLogger:
    """Self-contained SQLite-backed logger for every query-response pair.

    Usage::

        logger = InteractionLogger("data/laevateinn_interactions.db")
        await logger.initialize()
        iid = await logger.log(session_id, query, response, model_id)
        await logger.record_feedback(iid, 0.9, "explicit")
        top = await logger.export_top_interactions(min_score=0.7)
    """

    def __init__(self, db_path: str = "data/laevateinn_interactions.db") -> None:
        self._db_path = db_path
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create the database and tables if they do not exist."""
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA_SQL)
            await db.commit()
        self._initialized = True
        logger.info("interaction_logger.initialized", db_path=self._db_path)

    async def _ensure_init(self) -> None:
        if not self._initialized:
            await self.initialize()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def log(
        self,
        session_id: str,
        query: str,
        response: str,
        model_id: str,
        *,
        difficulty: str = "",
        confidence: float = 0.0,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        tags: list[str] | None = None,
    ) -> str:
        """Log a query-response pair and return the interaction ID."""
        await self._ensure_init()
        interaction_id = uuid.uuid4().hex
        now = time.time()
        tags_json = json.dumps(tags or [])

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO interactions
                    (id, timestamp, session_id, query, response, model_id,
                     difficulty, confidence, latency_ms, input_tokens,
                     output_tokens, cost_usd, feedback_score, feedback_type, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.5, 'none', ?)
                """,
                (
                    interaction_id,
                    now,
                    session_id,
                    query,
                    response,
                    model_id,
                    difficulty,
                    confidence,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    cost_usd,
                    tags_json,
                ),
            )
            await db.commit()

        logger.debug(
            "interaction_logger.logged",
            interaction_id=interaction_id,
            session_id=session_id,
            model_id=model_id,
            latency_ms=latency_ms,
        )
        return interaction_id

    async def record_feedback(
        self,
        interaction_id: str,
        score: float,
        feedback_type: str = "implicit",
    ) -> None:
        """Update the feedback score and type for a logged interaction."""
        await self._ensure_init()
        clamped = max(0.0, min(1.0, score))
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE interactions SET feedback_score = ?, feedback_type = ? WHERE id = ?",
                (clamped, feedback_type, interaction_id),
            )
            await db.commit()

        logger.debug(
            "interaction_logger.feedback_recorded",
            interaction_id=interaction_id,
            score=clamped,
            feedback_type=feedback_type,
        )

    async def infer_implicit_feedback(
        self,
        session_id: str,
        query: str,
    ) -> float:
        """Score the *previous* interaction in this session based on the new query.

        Heuristic:
            - If the new query is a rephrase of the previous query -> 0.3 (bad)
            - If the new query contains a positive marker -> 1.0 (good)
            - Otherwise the user moved on -> 0.7 (accepted)

        Returns the inferred score. Also writes it to the previous interaction row.
        """
        await self._ensure_init()

        # Check for explicit positive sentiment first
        query_lower = query.lower().strip()
        for marker in _POSITIVE_MARKERS:
            if marker in query_lower:
                score = 1.0
                await self._apply_implicit_to_previous(session_id, score)
                return score

        # Fetch the most recent interaction in this session
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, query FROM interactions
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return 0.5  # no previous interaction to score

        prev_query: str = row["query"]
        similarity = SequenceMatcher(None, query_lower, prev_query.lower()).ratio()

        if similarity >= _REPHRASE_THRESHOLD:
            score = 0.3  # rephrase -- previous answer was unsatisfactory
        else:
            score = 0.7  # new topic -- previous answer was accepted

        await self.record_feedback(row["id"], score, "implicit")
        return score

    # ------------------------------------------------------------------
    # Export for fine-tuning
    # ------------------------------------------------------------------

    async def export_top_interactions(
        self,
        *,
        min_score: float = 0.7,
        limit: int = 1000,
    ) -> list[Interaction]:
        """Return high-quality interactions suitable for SFT training."""
        await self._ensure_init()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM interactions
                WHERE feedback_score >= ?
                ORDER BY feedback_score DESC, timestamp DESC
                LIMIT ?
                """,
                (min_score, limit),
            )
            rows = await cursor.fetchall()

        return [self._row_to_interaction(r) for r in rows]

    async def export_dpo_pairs(
        self,
        *,
        limit: int = 500,
    ) -> list[tuple[Interaction, Interaction]]:
        """Return (chosen, rejected) pairs for DPO training.

        For each query that has both a high-score and low-score response
        (e.g. the user rephrased and got a better answer), pair them together.
        The high-score response is "chosen", the low-score is "rejected".
        """
        await self._ensure_init()
        pairs: list[tuple[Interaction, Interaction]] = []

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            # Find sessions that have interactions with varied feedback scores
            cursor = await db.execute(
                """
                SELECT DISTINCT session_id FROM interactions
                WHERE feedback_type != 'none'
                GROUP BY session_id
                HAVING MAX(feedback_score) - MIN(feedback_score) >= 0.3
                LIMIT ?
                """,
                (limit * 2,),
            )
            session_ids = [row["session_id"] for row in await cursor.fetchall()]

        for sid in session_ids:
            if len(pairs) >= limit:
                break

            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT * FROM interactions
                    WHERE session_id = ? AND feedback_type != 'none'
                    ORDER BY timestamp ASC
                    """,
                    (sid,),
                )
                rows = await cursor.fetchall()

            interactions = [self._row_to_interaction(r) for r in rows]

            # Pair consecutive interactions where the second is a rephrase
            # with a better score (user got a better answer on retry)
            for i in range(len(interactions) - 1):
                if len(pairs) >= limit:
                    break
                prev = interactions[i]
                curr = interactions[i + 1]
                similarity = SequenceMatcher(
                    None,
                    prev.query.lower(),
                    curr.query.lower(),
                ).ratio()
                if similarity >= _REPHRASE_THRESHOLD:
                    # The one with higher feedback is "chosen"
                    if curr.feedback_score > prev.feedback_score:
                        pairs.append((curr, prev))
                    elif prev.feedback_score > curr.feedback_score:
                        pairs.append((prev, curr))
                    # If equal, skip -- no signal

        logger.info(
            "interaction_logger.dpo_pairs_exported",
            pair_count=len(pairs),
        )
        return pairs

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def get_stats(self, *, days: int = 7) -> InteractionStats:
        """Return aggregate statistics for the last N days."""
        await self._ensure_init()
        cutoff = time.time() - (days * 86400)

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            # Aggregates
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(AVG(confidence), 0.0) AS avg_confidence,
                    COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms
                FROM interactions
                WHERE timestamp >= ?
                """,
                (cutoff,),
            )
            agg = await cursor.fetchone()

            # Top model by count
            cursor = await db.execute(
                """
                SELECT model_id, COUNT(*) AS cnt
                FROM interactions
                WHERE timestamp >= ? AND model_id != ''
                GROUP BY model_id
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (cutoff,),
            )
            top_row = await cursor.fetchone()

            # Feedback distribution (bucketed)
            cursor = await db.execute(
                """
                SELECT
                    CASE
                        WHEN feedback_score >= 0.8 THEN 'good'
                        WHEN feedback_score >= 0.5 THEN 'neutral'
                        ELSE 'bad'
                    END AS bucket,
                    COUNT(*) AS cnt
                FROM interactions
                WHERE timestamp >= ?
                GROUP BY bucket
                """,
                (cutoff,),
            )
            dist_rows = await cursor.fetchall()

        feedback_dist = {row["bucket"]: row["cnt"] for row in dist_rows}

        return InteractionStats(
            total=agg["total"] if agg else 0,
            avg_confidence=round(float(agg["avg_confidence"]) if agg else 0.0, 4),
            avg_latency_ms=round(float(agg["avg_latency_ms"]) if agg else 0.0, 1),
            top_model=top_row["model_id"] if top_row else "",
            feedback_distribution=feedback_dist,
        )

    async def get_model_performance(self) -> dict[str, float]:
        """Return average feedback score per model.

        Returns a dict mapping model_id to its mean feedback score,
        considering only interactions that have received feedback.
        """
        await self._ensure_init()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT model_id, AVG(feedback_score) AS avg_score
                FROM interactions
                WHERE model_id != '' AND feedback_type != 'none'
                GROUP BY model_id
                ORDER BY avg_score DESC
                """
            )
            rows = await cursor.fetchall()

        return {row["model_id"]: round(float(row["avg_score"]), 4) for row in rows}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _apply_implicit_to_previous(
        self,
        session_id: str,
        score: float,
    ) -> None:
        """Apply an implicit feedback score to the most recent interaction."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT id FROM interactions
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (session_id,),
            )
            row = await cursor.fetchone()

        if row:
            await self.record_feedback(row[0], score, "implicit")

    @staticmethod
    def _row_to_interaction(row: aiosqlite.Row) -> Interaction:
        """Convert a database row to an Interaction dataclass."""
        tags_raw = row["tags"]
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags = []
        else:
            tags = tags_raw if tags_raw else []

        return Interaction(
            id=row["id"],
            timestamp=row["timestamp"],
            session_id=row["session_id"],
            query=row["query"],
            response=row["response"],
            model_id=row["model_id"],
            difficulty=row["difficulty"],
            confidence=row["confidence"],
            latency_ms=row["latency_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_usd=row["cost_usd"],
            feedback_score=row["feedback_score"],
            feedback_type=row["feedback_type"],
            tags=tags,
        )
