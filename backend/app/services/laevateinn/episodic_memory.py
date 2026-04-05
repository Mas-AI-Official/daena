"""Gap 3: Episodic Memory for Daena's NBMF.

Remembers not just facts but EXPERIENCES -- sessions, decisions, patterns,
failures, and preferences. Each episode is a structured record that can be
retrieved by similarity, topic, recency, and outcome.

Storage: self-contained SQLite via aiosqlite. No SQLAlchemy dependency.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import aiosqlite

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Episode:
    id: str
    session_id: str
    timestamp: float
    topic: str
    query: str
    answer: str
    outcome: str = ""
    decision_made: str = ""
    pattern_detected: str = ""
    failure_reason: str = ""
    preference_learned: str = ""
    tags: list[str] = field(default_factory=list)
    embedding: list[float] | None = None


@dataclass(slots=True)
class EpisodeSearchResult:
    episode: Episode
    relevance_score: float
    match_reason: str


# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    topic TEXT NOT NULL,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    outcome TEXT DEFAULT '',
    decision_made TEXT DEFAULT '',
    pattern_detected TEXT DEFAULT '',
    failure_reason TEXT DEFAULT '',
    preference_learned TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    embedding BLOB DEFAULT NULL
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_episodes_topic ON episodes(topic);",
    "CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp DESC);",
]

_INSERT_EPISODE = """\
INSERT INTO episodes (
    id, session_id, timestamp, topic, query, answer,
    outcome, decision_made, pattern_detected,
    failure_reason, preference_learned, tags, embedding
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_episode(row: aiosqlite.Row) -> Episode:
    """Convert a database row to an Episode dataclass."""
    return Episode(
        id=row[0],
        session_id=row[1],
        timestamp=row[2],
        topic=row[3],
        query=row[4],
        answer=row[5],
        outcome=row[6] or "",
        decision_made=row[7] or "",
        pattern_detected=row[8] or "",
        failure_reason=row[9] or "",
        preference_learned=row[10] or "",
        tags=json.loads(row[11]) if row[11] else [],
        embedding=None,  # not loaded on normal reads
    )


def _tokenize(text: str) -> set[str]:
    """Lowercase split into unique tokens, stripping common punctuation."""
    return {
        w
        for w in text.lower().replace(",", " ").replace(".", " ").replace("?", " ").split()
        if len(w) > 1
    }


# ---------------------------------------------------------------------------
# EpisodicMemory
# ---------------------------------------------------------------------------


class EpisodicMemory:
    """Stores and retrieves structured episodes for Daena's NBMF layer."""

    def __init__(self, db_path: str = "data/laevateinn_episodes.db") -> None:
        self._db_path = db_path
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create the database and tables if they do not already exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            for idx_sql in _CREATE_INDEXES:
                await db.execute(idx_sql)
            await db.commit()
        self._initialized = True
        logger.info("episodic_memory.initialized", db_path=self._db_path)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_episode(
        self,
        session_id: str,
        topic: str,
        query: str,
        answer: str,
        outcome: str,
        *,
        decision_made: str = "",
        pattern_detected: str = "",
        failure_reason: str = "",
        preference_learned: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Persist a new episode and return its unique ID."""
        episode_id = uuid.uuid4().hex
        ts = time.time()
        tags_json = json.dumps(tags or [])

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                _INSERT_EPISODE,
                (
                    episode_id,
                    session_id,
                    ts,
                    topic,
                    query,
                    answer,
                    outcome,
                    decision_made,
                    pattern_detected,
                    failure_reason,
                    preference_learned,
                    tags_json,
                    None,  # embedding — populated externally if needed
                ),
            )
            await db.commit()

        logger.info(
            "episodic_memory.recorded",
            episode_id=episode_id,
            topic=topic,
            outcome=outcome,
        )
        return episode_id

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def recall_relevant(
        self,
        query: str,
        *,
        limit: int = 5,
        min_relevance: float = 0.3,
    ) -> list[EpisodeSearchResult]:
        """Find past episodes relevant to *query* using keyword matching.

        Episodes are scored by keyword overlap across topic, query, answer,
        tags, and detected patterns.  Results are sorted by descending
        relevance then recency.
        """
        results: list[EpisodeSearchResult] = []

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes ORDER BY timestamp DESC"
            )
            rows = await cursor.fetchall()

        for row in rows:
            episode = _row_to_episode(row)
            score = self._keyword_relevance(query, episode)
            if score >= min_relevance:
                reason_parts: list[str] = []
                query_tokens = _tokenize(query)
                if query_tokens & _tokenize(episode.topic):
                    reason_parts.append("topic")
                if query_tokens & _tokenize(episode.query):
                    reason_parts.append("query")
                if query_tokens & _tokenize(episode.answer):
                    reason_parts.append("answer")
                if query_tokens & _tokenize(" ".join(episode.tags)):
                    reason_parts.append("tags")
                if query_tokens & _tokenize(episode.pattern_detected):
                    reason_parts.append("pattern")
                match_reason = "keyword overlap in: " + ", ".join(reason_parts) if reason_parts else "general overlap"
                results.append(EpisodeSearchResult(episode=episode, relevance_score=score, match_reason=match_reason))

        # Sort by relevance desc, then recency desc
        results.sort(key=lambda r: (r.relevance_score, r.episode.timestamp), reverse=True)
        return results[:limit]

    async def recall_by_topic(self, topic: str, *, limit: int = 10) -> list[Episode]:
        """Return episodes matching *topic* (case-insensitive substring)."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes WHERE LOWER(topic) LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (f"%{topic.lower()}%", limit),
            )
            rows = await cursor.fetchall()
        return [_row_to_episode(r) for r in rows]

    async def recall_failures(self, *, limit: int = 10) -> list[Episode]:
        """Return episodes where a failure reason was recorded."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes WHERE failure_reason != '' "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [_row_to_episode(r) for r in rows]

    async def recall_preferences(self) -> list[Episode]:
        """Return all episodes where a preference was learned."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes WHERE preference_learned != '' "
                "ORDER BY timestamp DESC"
            )
            rows = await cursor.fetchall()
        return [_row_to_episode(r) for r in rows]

    async def recall_patterns(self, *, limit: int = 10) -> list[Episode]:
        """Return episodes where a pattern was detected."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes WHERE pattern_detected != '' "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [_row_to_episode(r) for r in rows]

    async def get_session_episodes(self, session_id: str) -> list[Episode]:
        """Return every episode recorded during *session_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = None
            cursor = await db.execute(
                "SELECT id, session_id, timestamp, topic, query, answer, "
                "outcome, decision_made, pattern_detected, failure_reason, "
                "preference_learned, tags, embedding "
                "FROM episodes WHERE session_id = ? "
                "ORDER BY timestamp ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
        return [_row_to_episode(r) for r in rows]

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    async def enrich_query(self, query: str) -> str:
        """Prepend relevant episode context to *query* for richer answers.

        If no relevant episodes are found the original query is returned
        unchanged.
        """
        relevant = await self.recall_relevant(query, limit=3, min_relevance=0.3)
        if not relevant:
            return query

        context_lines: list[str] = ["[Episodic context from past sessions]"]
        for r in relevant:
            ep = r.episode
            line = f"- Topic={ep.topic} | Outcome={ep.outcome}"
            if ep.decision_made:
                line += f" | Decision={ep.decision_made}"
            if ep.pattern_detected:
                line += f" | Pattern={ep.pattern_detected}"
            if ep.failure_reason:
                line += f" | Failure={ep.failure_reason}"
            if ep.preference_learned:
                line += f" | Preference={ep.preference_learned}"
            context_lines.append(line)

        context_block = "\n".join(context_lines)
        return f"{context_block}\n\n{query}"

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _keyword_relevance(self, query: str, episode: Episode) -> float:
        """Compute a simple keyword-overlap relevance score in [0, 1].

        Tokens from *query* are compared against the episode's topic,
        query, answer, tags, and pattern_detected fields with per-field
        weighting.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return 0.0

        weighted_hits = 0.0
        field_weights: Sequence[tuple[str, float]] = [
            (episode.topic, 3.0),
            (episode.query, 2.0),
            (episode.answer, 1.0),
            (" ".join(episode.tags), 2.5),
            (episode.pattern_detected, 1.5),
            (episode.decision_made, 1.0),
            (episode.preference_learned, 1.5),
        ]
        total_weight = sum(w for _, w in field_weights)

        for text, weight in field_weights:
            field_tokens = _tokenize(text)
            if not field_tokens:
                continue
            overlap = len(query_tokens & field_tokens)
            field_score = overlap / len(query_tokens)
            weighted_hits += field_score * weight

        return min(weighted_hits / total_weight, 1.0)
