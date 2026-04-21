"""ResourceFinder -- Einstein's Razor.

"I don't need to know everything. I just need to know where to find it."
-- Albert Einstein

When Daena doesn't know something, she doesn't give up. She:
    1. Searches her own knowledge base (NBMF memory)
    2. Searches the workspace/project files
    3. Searches the web
    4. Scrapes and learns from relevant sources
    5. Saves the knowledge for future use (Buffett: compounding knowledge)

This is the "search > memorize" philosophy. Instead of having a massive
static knowledge base, Daena has the TALENT to find any answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

# Web-search query hygiene: DuckDuckGo's instant-answer API rejects long
# queries with a 302 redirect and no result. A multi-paragraph system
# prompt is never a sensible search query anyway. We distill the
# question down to a short phrase before hitting the network.
_MAX_WEB_QUERY_CHARS = 200
# Cap on the total outgoing URL length so we never produce 5KB request
# lines. 1500 is generous for params + scheme + host.
_MAX_WEB_URL_CHARS = 1500
# Words too common to carry search signal. Short list so we stay fast.
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have i in is it its of on or "
    "that the to was were will with you your we our this these those "
    "been being do does did so can could should would may might must not "
    "if then else when where why how".split()
)


def _distill_web_query(raw: str) -> str | None:
    """Extract a short, searchable phrase from an arbitrary input.

    Strategy (cheapest first):
        1. If already short and single-line, return as-is.
        2. If the text contains a literal question ending in '?', use
           the last such sentence (it's almost always the real ask).
        3. Otherwise take the leading non-boilerplate line, cap at
           ``_MAX_WEB_QUERY_CHARS``, strip stopwords only if still
           too long.

    Returns ``None`` if no usable query can be distilled (e.g. the
    input is entirely whitespace or code).
    """
    if not raw:
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # Fast path: already short & single-line.
    if len(cleaned) <= _MAX_WEB_QUERY_CHARS and "\n" not in cleaned:
        return cleaned

    # Find the last question in the text; that's usually the operative ask.
    question_matches = re.findall(r"[^.!?\n]{5,200}\?", cleaned)
    if question_matches:
        return question_matches[-1].strip()

    # Take the first non-empty, non-heading line.
    for line in cleaned.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        # Skip markdown headings, separators, bullet boilerplate.
        if candidate.startswith(("#", "=", "-", "*", "```", ">")):
            continue
        if len(candidate) <= _MAX_WEB_QUERY_CHARS:
            return candidate
        break

    # Fallback: compress to keywords.
    tokens = re.findall(r"[A-Za-z0-9][\w.\-]*", cleaned.lower())
    keywords = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
    if not keywords:
        return None
    # Take enough keywords to fit the budget.
    phrase = " ".join(keywords[:12])
    return phrase[:_MAX_WEB_QUERY_CHARS]


@dataclass
class Knowledge:
    """A piece of knowledge found or retrieved."""
    question: str
    answer: str = ""
    source: str = ""  # "memory", "workspace", "web", "user"
    confidence: float = 0.0  # 0.0 to 1.0
    references: list[str] = field(default_factory=list)
    should_persist: bool = False  # Whether to save to NBMF


class ResourceFinder:
    """Find knowledge that Daena doesn't have.

    Einstein: don't memorize everything. Know WHERE to find it.
    Buffett: knowledge compounds. Save what you learn.
    """

    def __init__(
        self,
        db: Any = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id

    async def find(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        workspace_root: str | None = None,
    ) -> Knowledge:
        """Search for an answer through multiple sources.

        Search cascade (most specific to most general):
            1. NBMF memory (instant, most reliable)
            2. Workspace files (local, contextual)
            3. Web search (broad, needs validation)
            4. Ask user (last resort, 30-second rule)
        """
        # Level 1: Search NBMF memory
        memory_result = await self._search_memory(question)
        if memory_result and memory_result.confidence > 0.7:
            logger.info("resource_finder.found_in_memory", question=question[:100])
            return memory_result

        # Level 2: Search workspace files
        if workspace_root:
            workspace_result = await self._search_workspace(question, workspace_root)
            if workspace_result and workspace_result.confidence > 0.6:
                logger.info("resource_finder.found_in_workspace", question=question[:100])
                return workspace_result

        # Level 3: Web search
        web_result = await self._search_web(question)
        if web_result and web_result.confidence > 0.5:
            # Save for future use (Buffett: compounding knowledge)
            web_result.should_persist = True
            logger.info("resource_finder.found_on_web", question=question[:100])
            return web_result

        # Level 4: No answer found
        logger.info("resource_finder.not_found", question=question[:100])
        return Knowledge(
            question=question,
            source="needs_human",
            confidence=0.0,
            answer="",
        )

    async def deep_research(self, topic: str) -> dict[str, Any]:
        """Deep research on a topic -- search, scrape, synthesize.

        Used by SelfUpgrader to learn about new frameworks, tools, etc.
        """
        results = []

        # Search web for the topic
        web_result = await self._search_web(topic)
        if web_result and web_result.answer:
            results.append({
                "source": "web",
                "content": web_result.answer,
                "references": web_result.references,
            })

        return {
            "topic": topic,
            "findings": results,
            "source_count": len(results),
        }

    # ------------------------------------------------------------------
    # Internal search methods
    # ------------------------------------------------------------------

    async def _search_memory(self, question: str) -> Knowledge | None:
        """Search NBMF memory for relevant knowledge."""
        if not self.db or not self.user_id:
            return None

        try:
            from app.services.memory import MemoryService
            memory_svc = MemoryService(self.db, self.user_id, self.tenant_id)
            memories = await memory_svc.recall(question, limit=3)
            if memories:
                # Combine top memories into an answer
                answer = "\n".join(m.content[:500] for m in memories)
                return Knowledge(
                    question=question,
                    answer=answer,
                    source="memory",
                    confidence=0.8,
                    references=[f"NBMF T{m.tier}" for m in memories],
                )
        except Exception as exc:
            logger.debug("resource_finder.memory_search_failed", error=str(exc))

        return None

    async def _search_workspace(self, question: str, workspace_root: str) -> Knowledge | None:
        """Search workspace files for relevant information."""
        # Search for relevant files by name
        import os

        relevant_files = []
        keywords = question.lower().split()[:5]  # Top 5 words as search terms

        try:
            for root, dirs, files in os.walk(workspace_root):
                # Skip hidden dirs and common non-content dirs
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv")
                ]
                for f in files:
                    f_lower = f.lower()
                    if any(kw in f_lower for kw in keywords):
                        relevant_files.append(os.path.join(root, f))
                    if len(relevant_files) >= 5:
                        break
                if len(relevant_files) >= 5:
                    break
        except Exception as exc:
            logger.debug("resource_finder.workspace_walk_failed", error=str(exc))
            return None

        if relevant_files:
            # Read first relevant file
            try:
                with open(relevant_files[0], "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read(2000)
                return Knowledge(
                    question=question,
                    answer=f"Found in {relevant_files[0]}:\n{content}",
                    source="workspace",
                    confidence=0.6,
                    references=relevant_files[:3],
                )
            except Exception:
                pass

        return None

    async def _search_web(self, question: str) -> Knowledge | None:
        """Search the web for information.

        Uses available web search capabilities (MCP tools, HTTP, etc.)

        Hardened (2026-04-18): DuckDuckGo rejects long queries with a
        302 redirect, so a multi-paragraph system prompt used to burn
        a full round trip before resource_finder gave up. We now
        distill the raw input into a short query FIRST, and bail out
        without making any HTTP call if:

            * distillation returned nothing usable (prompt had no
              natural question or keyword content), OR
            * the distilled query is still so long that the outgoing
              URL would exceed ``_MAX_WEB_URL_CHARS``.
        """
        query = _distill_web_query(question)
        if not query:
            logger.debug(
                "resource_finder.web_search_skipped",
                reason="no_distillable_query",
                input_len=len(question),
            )
            return None

        # Build the full URL defensively before we fire. httpx will
        # accept any length, but DDG won't — and a 5KB request line is
        # the symptom we're here to stop.
        import urllib.parse as _urlparse

        base = "https://api.duckduckgo.com/"
        encoded_params = _urlparse.urlencode(
            {"q": query, "format": "json", "no_html": "1"}
        )
        total_url_len = len(base) + 1 + len(encoded_params)
        if total_url_len > _MAX_WEB_URL_CHARS:
            logger.debug(
                "resource_finder.web_search_skipped",
                reason="url_too_long",
                url_len=total_url_len,
                query_preview=query[:120],
            )
            return None

        if query != question:
            logger.debug(
                "resource_finder.web_query_distilled",
                original_len=len(question),
                distilled=query[:120],
            )

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    base,
                    params={"q": query, "format": "json", "no_html": "1"},
                    follow_redirects=False,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        return Knowledge(
                            question=question,
                            answer=abstract,
                            source="web",
                            confidence=0.6,
                            references=[data.get("AbstractURL", "")],
                            should_persist=True,
                        )
                else:
                    # 302 from DDG means "query was rejected" — treat
                    # as a non-fatal miss, don't spam error logs.
                    logger.debug(
                        "resource_finder.web_search_miss",
                        status=resp.status_code,
                        query_preview=query[:120],
                    )
        except Exception as exc:
            logger.debug("resource_finder.web_search_failed", error=str(exc))

        return None

    async def persist_knowledge(self, knowledge: Knowledge) -> None:
        """Save discovered knowledge to NBMF memory.

        Buffett: Knowledge compounds like interest. Every piece of knowledge
        saved makes future searches faster and more accurate.
        """
        if not knowledge.should_persist or not self.db or not self.user_id:
            return

        try:
            from app.services.memory import MemoryService
            memory_svc = MemoryService(self.db, self.user_id, self.tenant_id)
            await memory_svc.store(
                content=f"Q: {knowledge.question}\nA: {knowledge.answer}",
                tier=1,  # T1 Working (7 day)
                metadata={"source": knowledge.source, "references": knowledge.references},
            )
            logger.info(
                "resource_finder.knowledge_persisted",
                question=knowledge.question[:100],
                source=knowledge.source,
            )
        except Exception as exc:
            logger.debug("resource_finder.persist_failed", error=str(exc))
