"""Stop-Slop: anti-AI-writing-pattern rules for all Daena-generated content.

Applies post-processing filters to strip filler phrases, formulaic structures,
and low-density patterns from LLM output. Scores content on five dimensions:
directness, rhythm, trust, authenticity, density.

Integration points:
- chat_orchestrator.py: post-LLM filter before streaming to user
- RuntimeAdapter: appended to system prompt for all runtimes
- Marketing/Sales departments: injected into department system prompts
"""

import re
from dataclasses import dataclass, field


# ── Banned Phrases (case-insensitive matching) ──

BANNED_PHRASES: list[str] = [
    "In today's fast-paced",
    "Let's dive in",
    "Let's unpack",
    "It's not just X, it's Y",
    "This is where X comes in",
    "In conclusion",
    "As we navigate",
    "At the end of the day",
    "Game-changer",
    "Groundbreaking",
    "Paradigm shift",
    "Transformative",
    "Cutting-edge",
    "Leverage",
    "Synergy",
    "Deep dive",
    "Circle back",
    "Move the needle",
    "Low-hanging fruit",
    "Think outside the box",
    "Take it to the next level",
    "Revolutionize",
    "Seamlessly",
    "Robust",
    "Comprehensive",
    "Innovative",
    "Excited to announce",
    "Thrilled to share",
    "Proud to announce",
    "Without further ado",
    "Buckle up",
    "Stay tuned",
    "Food for thought",
    "It goes without saying",
    "Needless to say",
    "The fact of the matter",
]

# Pre-compiled regex for fast matching
_BANNED_PATTERN = re.compile(
    "|".join(re.escape(phrase) for phrase in BANNED_PHRASES),
    re.IGNORECASE,
)

# ── Filler Adverbs ──

FILLER_ADVERBS: list[str] = [
    "really",
    "truly",
    "actually",
    "basically",
    "essentially",
    "literally",
    "honestly",
    "obviously",
    "clearly",
    "simply",
    "just",
    "very",
    "extremely",
    "absolutely",
    "definitely",
    "certainly",
]

# Word-boundary pattern so we don't match inside other words
_FILLER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in FILLER_ADVERBS) + r")\b",
    re.IGNORECASE,
)

# ── Structural Patterns ──

_RHETORICAL_QA = re.compile(
    r"(?:What if|Have you ever|Did you know|Ever wonder)[^?]*\?[^.]*(?:Well|The answer|Here's)",
    re.IGNORECASE,
)
_BINARY_CONTRAST = re.compile(
    r"It'?s not (?:just |really |only )?[\w\s]+,\s*it'?s",
    re.IGNORECASE,
)
_THROAT_CLEARING = re.compile(
    r"^(?:Here's the thing|Look,|Listen,|So,|Well,|Okay so)",
    re.IGNORECASE | re.MULTILINE,
)
_DRAMATIC_FRAGMENT = re.compile(
    r"(?:^|\. )(\w+)\. (\w+)\. (\w+)\.",
    re.MULTILINE,
)
_FALSE_BUILDUP = re.compile(
    r"(?:might surprise you|you won't believe|here's the kicker|wait for it)",
    re.IGNORECASE,
)


@dataclass
class SlopMatch:
    """A single detected slop pattern."""
    category: str
    matched_text: str
    position: int


@dataclass
class SlopScore:
    """Content quality score across five dimensions."""
    directness: int = 0     # 1-10: says the thing without setup
    rhythm: int = 0         # 1-10: sentence length/structure variety
    trust: int = 0          # 1-10: trusts reader, no over-explaining
    authenticity: int = 0   # 1-10: sounds human, not template
    density: int = 0        # 1-10: every sentence earns its place

    @property
    def total(self) -> int:
        return self.directness + self.rhythm + self.trust + self.authenticity + self.density

    @property
    def passes(self) -> bool:
        return self.total >= MINIMUM_SCORE

    def to_dict(self) -> dict:
        return {
            "directness": self.directness,
            "rhythm": self.rhythm,
            "trust": self.trust,
            "authenticity": self.authenticity,
            "density": self.density,
            "total": self.total,
            "passes": self.passes,
        }


MINIMUM_SCORE = 35  # out of 50


def scan_slop(text: str) -> list[SlopMatch]:
    """Scan text for slop patterns. Returns list of matches."""
    matches: list[SlopMatch] = []

    # Banned phrases
    for m in _BANNED_PATTERN.finditer(text):
        matches.append(SlopMatch(
            category="banned_phrase",
            matched_text=m.group(),
            position=m.start(),
        ))

    # Structural patterns
    for pattern, category in [
        (_RHETORICAL_QA, "rhetorical_question_then_answer"),
        (_BINARY_CONTRAST, "binary_contrast"),
        (_THROAT_CLEARING, "throat_clearing_opener"),
        (_DRAMATIC_FRAGMENT, "dramatic_fragmentation"),
        (_FALSE_BUILDUP, "false_buildup"),
    ]:
        for m in pattern.finditer(text):
            matches.append(SlopMatch(
                category=category,
                matched_text=m.group()[:80],
                position=m.start(),
            ))

    return matches


def strip_slop(text: str) -> str:
    """Remove banned phrases from text. Light cleanup only.

    Does NOT rewrite the text (that would require LLM re-generation).
    Strips obvious filler phrases and trims whitespace artifacts.
    """
    cleaned = _BANNED_PATTERN.sub("", text)
    # Collapse double spaces and leading/trailing whitespace per line
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r"^ +| +$", "", cleaned, flags=re.MULTILINE)
    # Remove empty lines left by stripping
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def score_content(text: str) -> SlopScore:
    """Score content quality across five dimensions.

    Heuristic scoring (no LLM call). Fast enough for every message.
    """
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    word_count = len(text.split())
    slop_matches = scan_slop(text)
    filler_count = len(_FILLER_PATTERN.findall(text))

    # Directness: penalize for setup patterns and throat-clearing
    setup_count = sum(1 for m in slop_matches if m.category in (
        "throat_clearing_opener", "rhetorical_question_then_answer", "false_buildup",
    ))
    directness = max(1, 10 - setup_count * 3 - len([
        m for m in slop_matches if m.category == "banned_phrase"
    ]))

    # Rhythm: measure sentence length variance
    if len(sentences) >= 3:
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        rhythm = min(10, max(1, int(variance ** 0.5)))
    else:
        rhythm = 5  # too short to judge

    # Trust: penalize over-explaining (filler adverbs, redundant phrases)
    filler_ratio = filler_count / max(1, word_count)
    trust = max(1, 10 - int(filler_ratio * 100))

    # Authenticity: penalize template patterns
    template_count = sum(1 for m in slop_matches if m.category in (
        "binary_contrast", "dramatic_fragmentation",
    ))
    banned_count = sum(1 for m in slop_matches if m.category == "banned_phrase")
    authenticity = max(1, 10 - template_count * 2 - banned_count)

    # Density: penalize low information density
    unique_words = len(set(text.lower().split()))
    density_ratio = unique_words / max(1, word_count)
    density = min(10, max(1, int(density_ratio * 15)))

    return SlopScore(
        directness=min(10, directness),
        rhythm=min(10, rhythm),
        trust=min(10, trust),
        authenticity=min(10, authenticity),
        density=min(10, density),
    )


# ── System Prompt Injection ──

STOP_SLOP_SYSTEM_INSTRUCTION = (
    "Writing rules: No filler phrases. No rhetorical setups. "
    "No binary contrasts ('It's not X, it's Y'). "
    "Vary sentence length. Trust the reader. Be direct. "
    "Every sentence must earn its place. "
    "Do not use: 'dive in', 'game-changer', 'groundbreaking', 'robust', "
    "'comprehensive', 'innovative', 'seamlessly', 'leverage', 'synergy', "
    "'paradigm shift', 'cutting-edge', 'transformative'. "
    "Do not use em dashes as separators."
)
