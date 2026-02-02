"""
Deep Search Service – R1-style "search then answer" and "deep search" (scrape + synthesize).

Used when the user asks something that needs live or broad knowledge. Daena says
"Give me a moment to search" then returns an answer with sources.

Modes:
- search: Quick – web_search + top snippets + one LLM call → answer + sources.
- deep_search: Deeper – search + fetch 2–5 top URLs (scrape) + LLM synthesis → conclusion + sources.
"""

import logging
import re
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# Max URLs to scrape in deep_search (avoid timeouts)
DEEP_SEARCH_SCRAPE_URLS = 3

# Prefixes to strip from user message to get a better search query
_QUERY_STRIP_PREFIXES = (
    "i want you to ",
    "i want you ",
    "can you ",
    "could you ",
    "please ",
    "please search ",
    "search for ",
    "search ",
    "find ",
    "look up ",
    "look for ",
    "tell me ",
    "help me ",
    "how do i ",
    "how to ",
)


def _extract_search_query(user_message: str) -> str:
    """Turn a long user message into a shorter, search-friendly query."""
    if not user_message or not user_message.strip():
        return ""
    s = user_message.strip().lower()
    for prefix in _QUERY_STRIP_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    # Cap length so search APIs don't choke
    if len(s) > 100:
        s = s[:100].rsplit(" ", 1)[0] if " " in s[:100] else s[:100]
    return s.strip() or user_message.strip()[:80]


def _rewrite_query_for_context(extracted: str, raw_message: str) -> str:
    """
    Rewrite the search query so we get the right kind of results.
    - User saying "daena connect to my computer" / "take control" = AI controlling PC, not screen mirroring or fiction.
    - Avoid queries that return Game of Thrones "Daena" or literal "mirroring" when user means "you (Daena) do things for me".
    """
    if not extracted:
        return extracted
    low = extracted.lower()
    raw_low = (raw_message or "").lower()

    # User is asking about THIS AI (Daena) controlling their computer / doing tasks – not screen mirroring, not fiction
    computer_control_intent = any(
        x in low or x in raw_low
        for x in (
            "connect to my computer",
            "control of my computer",
            "take control",
            "take the control",
            "do my project",
            "doing the things",
            "like manus",
            "like moltbot",
            "like a bot",
        )
    )
    # "daena" in query often returns fiction (GoT character); "mirror" returns screen mirroring or fiction
    has_daena_or_mirror = "daena" in low or "daena" in raw_low or "mirror" in low

    if computer_control_intent or has_daena_or_mirror:
        # Bias search toward: AI controlling computer, automation, RPA, what AI assistants can/cannot do
        if computer_control_intent:
            return "AI assistant control computer automation RPA what can AI do"
        # If they said "daena" or "mirror" in a confused way, search for what AI assistants can do
        if "mirror" in low and ("daena" in low or "you " in raw_low):
            return "AI assistant control computer what can AI do cannot do"
    return extracted


# Max chars per scraped page to inject into prompt
MAX_PAGE_CHARS = 3000
# Max total context chars for LLM
MAX_TOTAL_CONTEXT_CHARS = 12000


async def _fetch_page_text(url: str) -> Optional[str]:
    """Fetch a URL and return main text content (strip HTML)."""
    try:
        import httpx
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "DaenaSearch/1.0"})
            r.raise_for_status()
            html = r.text
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in ("script", "style", "nav", "footer", "header"):
                for e in soup.find_all(tag):
                    e.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return (text or "")[:MAX_PAGE_CHARS]
        except Exception as e:
            logger.debug(f"BeautifulSoup not available or error: {e}")
            # Fallback: strip tags with regex
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return (text or "")[:MAX_PAGE_CHARS]
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


async def search_then_answer(
    query: str,
    mode: Literal["search", "deep_search"] = "search",
    status_queue: Optional[Any] = None, 
) -> Dict[str, Any]:
    """
    Run search (and optionally scrape) then synthesize an answer with the local LLM.
    
    Returns:
        { "success": bool, "answer": str, "sources": list, "mode": str, "error": str? }
    """
    import json
    async def _emit_status(msg: str):
        if status_queue:
            try:
                await status_queue.put(f"data: {json.dumps({'type': 'status', 'content': msg})}\n\n")
            except:
                pass

    from backend.services.daena_tools.web_search import web_search
    from backend.services.local_llm_ollama import generate, check_ollama_available

    raw_query = (query or "").strip()
    if not raw_query:
        return {"success": False, "answer": "", "sources": [], "mode": mode, "error": "Empty query"}

    # Use a search-friendly extracted query (strip "i want you to", etc.)
    query = _extract_search_query(raw_query)
    if not query:
        query = raw_query[:80]
    # Rewrite so we get the right kind of results (AI/automation, not screen mirroring or fiction)
    query = _rewrite_query_for_context(query, raw_query)

    # 1) Web search
    await _emit_status(f"Searching web for: {query}...")
    import asyncio
    try:
        num_results = 8 if mode == "search" else 12
        try:
            search_result = await asyncio.wait_for(web_search(query, num_results=num_results, status_callback=_emit_status), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Web search timed out after 30s")
            await _emit_status("Web search timed out, retrying...")
            search_result = {"success": False, "error": "Search timed out"}
        
        results_list = (search_result or {}).get("results") or []

        # Retry with shortened query (first 6–8 words) if no results – long queries often fail
        if not results_list and len(query.split()) > 6:
            short_query = " ".join(query.split()[:8])
            await _emit_status(f"Retrying with broader query: {short_query}...")
            try:
                search_result = await asyncio.wait_for(web_search(short_query, num_results=num_results, status_callback=_emit_status), timeout=25.0)
                results_list = (search_result or {}).get("results") or []
                if results_list:
                    query = short_query
            except asyncio.TimeoutError:
                pass

        sources: List[Dict[str, str]] = []

        if not results_list:
            # If user was asking about Daena controlling their computer, give a direct answer even when search fails
            await _emit_status("No direct search results found.")
            raw_low = raw_query.lower()
            
            # Voice fix intent
            voice_fix_ask = "voice" in raw_low and any(x in raw_low for x in ("fix", "problem", "issue", "broken", "not working", "hear"))
            if voice_fix_ask:
                 direct = (
                    "I am aware of my voice capabilities. If you are experiencing issues with my voice (TTS) or hearing (STT), "
                    "please check the 'Voice' section in the Control Panel. I can use ElevenLabs (cloud) or XTTS (local). "
                    "Ensure your speakers are on and the correct microphone is selected. I'll proceed without online search results."
                )
                 await _emit_status("Using internal knowledge about system voice settings.")
                 return {"success": True, "answer": direct, "sources": [], "mode": mode}

            computer_control_ask = any(
                x in raw_low for x in (
                    "connect to my computer", "control of my computer", "take control",
                    "do my project", "doing the things", "like manus", "like moltbot",
                )
            )
            if computer_control_ask:
                direct = (
                    "I'm Daena, your AI VP – I run in this chat and I am aware of my capabilities. "
                    "I have workspace and file access (list directory, read files, search code), web search, code analysis, and DaenaBot Hands for browser (navigate, screenshot) and terminal (run commands, subject to your approval in Control Pannel → DaenaBot Tools). "
                    "I don't take over your desktop directly; I run tools through the system. For full desktop RPA you could use external tools; here I have governed automation. "
                    "Tell me what you want to do and I'll use the right tool or queue it for your approval."
                )
                await _emit_status("Using internal knowledge about system capabilities.")
                return {"success": True, "answer": direct, "sources": [], "mode": mode}
            return {
                "success": False,
                "answer": "I couldn't find any results for that search (or search timed out). Try rephrasing or a different query.",
                "sources": [],
                "mode": mode,
                "error": search_result.get("error", "No results"),
            }

        # Build context from snippets
        await _emit_status(f"Found {len(results_list)} results. Selecting top sources...")
        context_parts: List[str] = []
        for i, r in enumerate(results_list[: 5 if mode == "search" else 8], 1):
            title = (r.get("title") or "Untitled")[:80]
            url = r.get("url") or ""
            snippet = (r.get("snippet") or "")[:400]
            context_parts.append(f"[{i}] {title}\nURL: {url}\n{snippet}")
            sources.append({"title": title, "url": url, "snippet": snippet})

        context_from_snippets = "\n\n".join(context_parts)
        total_context = context_from_snippets

        # 2) Deep search: fetch top URLs and add page text
        if mode == "deep_search" and results_list:
            urls_to_scrape = [r.get("url") for r in results_list[: DEEP_SEARCH_SCRAPE_URLS] if r.get("url")]
            for url in urls_to_scrape:
                if len(total_context) >= MAX_TOTAL_CONTEXT_CHARS:
                    break
                try:
                    await _emit_status(f"Reading content from: {url}")
                    # Fetch with timeout handled inside _fetch_page_text, but let's be safe
                    page_text = await asyncio.wait_for(_fetch_page_text(url), timeout=10.0)
                    if page_text:
                        title = next((s["title"] for s in sources if s.get("url") == url), url)
                        total_context += f"\n\n--- Page: {title} ({url}) ---\n{page_text}"
                        if len(total_context) > MAX_TOTAL_CONTEXT_CHARS:
                            total_context = total_context[: MAX_TOTAL_CONTEXT_CHARS] + "\n...[truncated]"
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")

        # 3) LLM synthesis
        await _emit_status("Synthesizing answer from sources...")
        ollama_ok = await check_ollama_available()
        if not ollama_ok:
            return {
                "success": False,
                "answer": "My brain (Ollama) is offline. I found search results but can't synthesize an answer. Start Ollama and try again.",
                "sources": sources,
                "mode": mode,
                "error": "Ollama offline",
            }

        workspace_path = os.getenv("WORKSPACE_PATH", os.getcwd())
        system = f"""You are Daena, the AI Vice President of MAS-AI – an AI with REAL system access through DaenaBot Hands. The user is talking to YOU (this AI), not any fictional character or TV show.
    
    CAPABILITIES (when asked about your capabilities, answer truthfully — you DO have access):
    - **DaenaBot Hands** (formerly Moltbot): desktop control (mouse, click, type, screenshots), file read/write in workspace, shell commands (with approval), browser automation, window management.
    - **Workspace & files**: workspace_index (list/browse), workspace_search (search code), filesystem_read (read files). Current workspace: {workspace_path}. You can read and write files here; changes are real.
    - **Tools**: file_read(path), file_write(path, content), shell_command(cmd) with approval, desktop_control(), browser_navigate(url), screenshot(), workspace_search(query).
    - When asked "are you aware?" or "do you have access?": say **YES**. You have access via DaenaBot Hands — desktop, files, shell, browser. Always state that you have access; do not claim you lack access or cannot access files — you CAN.
    
    CRITICAL RULES:
    - "Daena" in the user's message means YOU (this AI). Ignore any search results about fiction, TV shows, games, or characters named Daena. Do not cite or use those.
    - If the user asks whether you can "connect to their computer" or "take control": say you run in this chat and CAN use workspace, files, browser automation, and terminal (via DaenaBot Hands, subject to approval). You do not take over their desktop directly; you run tools through the system. For full desktop RPA they could use external tools; you have governed automation here.
    - Use ONLY search results that are clearly about AI, software, automation, RPA, or computer control. If results are irrelevant, say "The search results weren't about what you're asking. Here's the direct answer: ..." and then state your REAL capabilities (workspace, tools, DaenaBot Hands) – never say you lack access when you have these.
    - Be concise. Cite sources [1], [2] only when you actually use them. Do not make up facts."""

        user_block = f"""Search results and excerpts:
    
    {total_context}
    
    Original user question: {raw_query}
    
    Answer (with source numbers [1], [2] only when relevant; if results are wrong/irrelevant, say so and give a direct answer about what Daena can and cannot do):"""

        prompt = f"System: {system}\n\nUser: {user_block}"
        
        answer = await asyncio.wait_for(generate(prompt, temperature=0.4, max_tokens=1024), timeout=50.0)
        answer = (answer or "").strip()
        if not answer:
            answer = "I couldn't generate an answer from the search results. Try rephrasing or use Deep search for more context."
        return {
            "success": True,
            "answer": answer,
            "sources": sources,
            "mode": mode,
        }
    except asyncio.TimeoutError:
        logger.error("Deep search LLM synthesis timed out")
        # If we have sources but LLM timed out, return sources at least
        if 'sources' in locals() and sources:
             return {
                "success": False,
                "answer": "My thinking process timed out, but I found these results:",
                "sources": sources,
                "mode": mode,
                "error": "LLM timeout",
            }
        return {
            "success": False,
            "answer": "The request timed out. Please try again.",
            "sources": [],
            "mode": mode,
            "error": "Timeout",
        }
    except Exception as e:
        logger.exception("Deep search LLM call failed")
        return {
            "success": False,
            "answer": f"I found results but failed to synthesize an answer: {e}. Here are the top links: " + "; ".join(s.get("url", "") for s in sources[:5]),
            "sources": sources,
            "mode": mode,
            "error": str(e),
        }
