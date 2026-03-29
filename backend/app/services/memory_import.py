"""Memory import wizard -- import memories from ChatGPT, Gemini, Claude.

Flow:
1. User clicks "Import from [provider]"
2. Daena shows a prompt to paste into the other AI
3. User copies the response and pastes into Daena
4. Daena parses JSON and creates NBMF memory entries
5. Each entry gets an appropriate tier based on content type
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Tier mapping: content type -> NBMF tier
TIER_MAP = {
    "name": 3,        # T3: core identity
    "profession": 3,  # T3: core identity
    "projects": 2,    # T2: verified project knowledge
    "preferences": 2, # T2: verified preferences
    "facts": 1,       # T1: working memory (needs verification)
    "decisions": 2,   # T2: verified decisions
}


# Prompts for each provider
IMPORT_PROMPTS = {
    "chatgpt": (
        "Please export a structured summary of everything you know about me. Include:\n"
        "- My name and how you address me\n"
        "- My work/profession\n"
        "- My projects and their status\n"
        "- My preferences (communication style, tools, interests)\n"
        "- Key facts you remember\n"
        "- Important decisions we've discussed\n"
        "Format as JSON with keys: name, profession, projects, preferences, facts, decisions"
    ),
    "gemini": (
        "Export everything you remember about me in structured JSON format.\n"
        "Use these keys:\n"
        "- name: my name\n"
        "- profession: what I do for work\n"
        "- projects: list of my projects with status\n"
        "- preferences: my communication and tool preferences\n"
        "- facts: key facts about me\n"
        "- decisions: important decisions we've discussed\n"
        "Output only valid JSON, no markdown."
    ),
    "claude": (
        "Please share everything you know about me in a structured JSON format.\n"
        "Keys: name, profession, projects (list with name and status), "
        "preferences (list), facts (list), decisions (list).\n"
        "Output only the JSON object."
    ),
}


def get_import_prompt(provider: str) -> str:
    """Get the prompt to paste into the source AI provider."""
    return IMPORT_PROMPTS.get(provider.lower(), IMPORT_PROMPTS["chatgpt"])


def parse_import_response(raw_text: str) -> dict[str, Any]:
    """Parse the JSON response from the source AI provider.

    Handles common edge cases:
    - JSON wrapped in markdown code blocks
    - Extra text before/after JSON
    - Slightly malformed JSON
    """
    text = raw_text.strip()

    # Strip markdown code blocks
    if "```json" in text:
        text = text.split("```json", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]

    text = text.strip()

    # Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"error": "Expected a JSON object, got " + type(data).__name__}
        return data
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse JSON: {exc}"}


def convert_to_memories(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert parsed import data to NBMF memory entries.

    Returns a list of memory entries ready to be inserted into
    the memory store, each with: content, tier, category, source.
    """
    if "error" in parsed:
        return []

    memories: list[dict[str, Any]] = []

    # Name
    name = parsed.get("name")
    if name and isinstance(name, str):
        memories.append({
            "content": f"User's name: {name}",
            "tier": TIER_MAP["name"],
            "category": "identity",
            "source": "import",
        })

    # Profession
    profession = parsed.get("profession")
    if profession and isinstance(profession, str):
        memories.append({
            "content": f"Profession: {profession}",
            "tier": TIER_MAP["profession"],
            "category": "identity",
            "source": "import",
        })

    # Projects
    projects = parsed.get("projects", [])
    if isinstance(projects, list):
        for proj in projects:
            if isinstance(proj, dict):
                content = f"Project: {proj.get('name', 'Unknown')} - Status: {proj.get('status', 'Unknown')}"
            elif isinstance(proj, str):
                content = f"Project: {proj}"
            else:
                continue
            memories.append({
                "content": content,
                "tier": TIER_MAP["projects"],
                "category": "project",
                "source": "import",
            })

    # Preferences
    prefs = parsed.get("preferences", [])
    if isinstance(prefs, list):
        for pref in prefs:
            if isinstance(pref, str):
                memories.append({
                    "content": f"Preference: {pref}",
                    "tier": TIER_MAP["preferences"],
                    "category": "preference",
                    "source": "import",
                })

    # Facts
    facts = parsed.get("facts", [])
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, str):
                memories.append({
                    "content": fact,
                    "tier": TIER_MAP["facts"],
                    "category": "fact",
                    "source": "import",
                })

    # Decisions
    decisions = parsed.get("decisions", [])
    if isinstance(decisions, list):
        for dec in decisions:
            if isinstance(dec, str):
                memories.append({
                    "content": f"Decision: {dec}",
                    "tier": TIER_MAP["decisions"],
                    "category": "decision",
                    "source": "import",
                })

    logger.info("memory_import.converted", count=len(memories), tiers={m["tier"] for m in memories})
    return memories
