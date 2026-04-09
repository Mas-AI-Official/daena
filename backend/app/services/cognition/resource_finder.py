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

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


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
        """
        # Web search is available through DaenaBot's network tools
        # For now, return a placeholder indicating web search capability
        try:
            import httpx

            # Try DuckDuckGo instant answer API (no key needed)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": question, "format": "json", "no_html": "1"},
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
