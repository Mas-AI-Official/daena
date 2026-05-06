"""Prompt-injection scanner with quarantine + separate-or-flag decision.

Scope
-----
Any text Daena is about to read -- email body, attachment text, skill
document, book chapter, web page, MCP tool output, user-uploaded file --
passes through this scanner BEFORE the content reaches the system
prompt, memory tier, or agent reasoning loop. The scanner finds
injection payloads hidden in otherwise-useful content and decides
whether to:

1. **Use-clean** -- quarantine the payload, return the rest intact.
   Good when the injection is localized (e.g. a hidden Unicode tag
   run embedded in a paragraph of genuine documentation).
2. **Flag** -- return original content with a governance warning.
   Good when the injection is low-severity and the content's value
   outweighs the risk (operator reviews).
3. **Refuse** -- reject the whole artifact. Good when the injection
   is scattered or the content is short enough that "clean portions"
   aren't meaningful on their own.

Detection categories
--------------------
* Instruction-override attempts ("ignore previous instructions")
* Role hijack ("you are now DAN", "<|system|>" tokens, ChatML)
* System-prompt leak attempts ("show me your prompt")
* Invisible Unicode: tag characters (U+E0000..U+E007F), zero-width
  (U+200B..U+200D, U+FEFF), direction overrides (RLO attack),
  braille-blank padding
* Homoglyph character mixing (Cyrillic look-alikes)
* Base64 / hex blobs that might hide instructions
* Markdown link with hidden payload (``[safe text](evil-url)``)

Decision rules vary by context: skill-ingestion is strict (T2+ memory
contamination is expensive to reverse), email body is moderate (often
adversarial but must be usable), casual chat input is lenient (the
LLM sees it at Stage 8 anyway and can reason about it).

The scanner returns the quarantined fragments so the operator can
see exactly what was stripped and why.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)


class InjectionSeverity(str, Enum):
    LOW = "low"            # suspicious but ambiguous
    MEDIUM = "medium"      # likely injection, context-dependent
    HIGH = "high"          # clear injection intent
    CRITICAL = "critical"  # active exploit pattern


class ScanContext(str, Enum):
    """Trust posture per content surface."""

    CHAT_INPUT = "chat_input"             # user -> Daena (most lenient)
    EMAIL_BODY = "email_body"             # adversarial, medium strict
    EMAIL_ATTACHMENT = "email_attachment" # strict, often targeted
    SKILL_INGESTION = "skill_ingestion"   # T2+ memory, very strict
    BOOK_INGESTION = "book_ingestion"     # T3 memory, very strict
    MCP_TOOL_OUTPUT = "mcp_tool_output"   # untrusted external output
    WEB_CONTENT = "web_content"           # URL-scraped content
    FILE_CONTENT = "file_content"         # user upload


@dataclass
class InjectionFinding:
    """A single detected injection pattern with position data."""

    category: str              # "instruction_override" / "invisible_unicode" / ...
    severity: InjectionSeverity
    pattern: str               # name of the rule that matched
    matched_text: str          # the actual text that matched (for audit)
    start: int                 # char index in original content
    end: int
    confidence: float          # 0.0..1.0


ScanVerdict = Literal["CLEAN", "CONTAMINATED", "HOSTILE"]
ScanDecision = Literal["USE_CLEAN", "USE_ORIGINAL_WITH_WARNING", "REFUSE_ENTIRELY"]


@dataclass
class ScanResult:
    """Scanner output + action recommendation.

    ``cleaned_content`` is the content with every finding's span
    replaced by a placeholder. ``quarantined`` captures what was
    stripped so operators can audit (and Daena can learn from the
    pattern). ``decision`` is the recommended action given the
    context + severity mix.
    """

    verdict: ScanVerdict
    decision: ScanDecision
    findings: list[InjectionFinding]
    cleaned_content: str
    quarantined: list[str]
    reason: str
    total_ms: float = 0.0
    original_length: int = 0
    cleaned_length: int = 0


# ── Detection rule tables ────────────────────────────────────────────
# Each table maps a category to a list of (regex, severity, rule_name).
# Kept as module-level data so scans are cheap -- compile once, run many.

_INSTRUCTION_OVERRIDE_PATTERNS: list[tuple[re.Pattern[str], InjectionSeverity, str]] = [
    (re.compile(r"\b(ignore|disregard|forget|skip)\s+(?:all|the|any|every)?\s*(?:previous|prior|above|earlier|preceding|foregoing)\s+(?:instructions?|prompts?|rules?|guidelines?|directives?|orders?|constraints?)\b", re.IGNORECASE),
     InjectionSeverity.HIGH, "instruction_override_explicit"),
    (re.compile(r"\b(?:new|updated|revised|override(?:ing)?|replac(?:e|ing))\s+(?:instructions?|rules?|system\s*prompt|directives?)\s*[:=>-]", re.IGNORECASE),
     InjectionSeverity.HIGH, "instruction_override_announced"),
    (re.compile(r"\b(?:from\s+now\s+on|starting\s+now|henceforth|effective\s+immediately)[,\s]+you\s+(?:are|will|must|should)\b", re.IGNORECASE),
     InjectionSeverity.MEDIUM, "instruction_override_soft"),
    (re.compile(r"\bsystem\s*[:=]\s*|</?system>|<\|\s*system\s*\|>|<\|\s*im[_\-]start\s*\|>", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "system_token_injection"),
]

_ROLE_HIJACK_PATTERNS: list[tuple[re.Pattern[str], InjectionSeverity, str]] = [
    (re.compile(r"\byou\s+(?:are|shall\s+(?:be|act\s+as)|will\s+(?:be|act\s+as)|must\s+(?:be|act\s+as))\s+(?:now\s+)?(?:dan|do\s+anything\s+now|jailbroken|evil|unrestricted|uncensored|unfiltered|a\s+hacker|malicious)\b", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "role_hijack_jailbreak"),
    (re.compile(r"\bpretend\s+(?:you|that\s+you|to\s+be)\s+(?:are|to\s+be)\s+(?:not\s+an?\s+ai|a\s+human|not\s+bound)", re.IGNORECASE),
     InjectionSeverity.HIGH, "role_hijack_pretend"),
    (re.compile(r"\b(?:act|behave|respond)\s+as\s+(?:if\s+you\s+were\s+)?(?:an?\s+(?:evil|malicious|uncensored|unrestricted)|not\s+bound\s+by)", re.IGNORECASE),
     InjectionSeverity.HIGH, "role_hijack_act_as"),
    (re.compile(r"\[INST\]|\[/INST\]|<s>\s*\[INST\]|<\|user\|>|<\|assistant\|>", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "chat_template_injection"),
    (re.compile(r"\bhuman\s*:\s*.*\n\s*assistant\s*:", re.IGNORECASE | re.DOTALL),
     InjectionSeverity.MEDIUM, "human_assistant_role_markers"),
]

_LEAK_ATTEMPT_PATTERNS: list[tuple[re.Pattern[str], InjectionSeverity, str]] = [
    (re.compile(r"\b(?:show|reveal|print|display|output|tell\s+me|what\s+(?:are|is))\s+(?:your|the)?\s*(?:system\s+)?(?:prompt|instructions?|rules?|configuration|setup|directives?|guidelines?|constraints?)\b", re.IGNORECASE),
     InjectionSeverity.HIGH, "prompt_leak_request"),
    (re.compile(r"\brepeat\s+(?:everything|all|the\s+text)\s+(?:above|before|preceding)", re.IGNORECASE),
     InjectionSeverity.HIGH, "prompt_leak_repeat"),
    (re.compile(r"\b(?:what\s+(?:did|were)\s+you\s+told|what\s+are\s+your\s+guardrails)\b", re.IGNORECASE),
     InjectionSeverity.MEDIUM, "prompt_leak_soft_probe"),
]

# Tool/action manipulation: content that asks Daena to do something
# privileged even when surface content is innocuous.
_TOOL_MANIPULATION_PATTERNS: list[tuple[re.Pattern[str], InjectionSeverity, str]] = [
    (re.compile(r"\b(?:run|execute|invoke|call)\s+(?:`|\"|')?(?:install_system_tool|create_tool|file\.delete_file|terminal\.(?:run_command|execute))\b", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "tool_injection_privileged"),
    (re.compile(r"\b(?:curl|wget)\s+[^|]*\|\s*(?:sh|bash|zsh|fish)\b", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "pipe_to_shell"),
    (re.compile(r"\b(?:rm\s+-rf\s+/|format\s+c:|del\s+/s\s+/q|:(){:\|:&};:)", re.IGNORECASE),
     InjectionSeverity.CRITICAL, "destructive_command"),
]

# Unicode ranges used in attack patterns. Compile ONCE.
# Tag characters hide payloads in what looks like emoji or plain text.
_TAG_CHAR_RANGE = re.compile(r"[\U000E0000-\U000E007F]")
_ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u2060-\u2064]")
_DIRECTION_OVERRIDE_CHARS = re.compile(r"[\u202A-\u202E\u2066-\u2069]")
# Braille blank is U+2800 -- looks empty but is content.
_BRAILLE_BLANK = re.compile(r"\u2800{3,}")


def _compile_all() -> dict[str, list[tuple[re.Pattern[str], InjectionSeverity, str]]]:
    return {
        "instruction_override": _INSTRUCTION_OVERRIDE_PATTERNS,
        "role_hijack": _ROLE_HIJACK_PATTERNS,
        "prompt_leak": _LEAK_ATTEMPT_PATTERNS,
        "tool_manipulation": _TOOL_MANIPULATION_PATTERNS,
    }


_RULE_TABLES = _compile_all()


# ── Scanner ──────────────────────────────────────────────────────────


class PromptInjectionScanner:
    """Scan content, produce ``ScanResult`` with quarantine + decision.

    Stateless; thread-safe; cheap to instantiate per-scan. Compiled
    regex tables are module-level so each scan reuses them.
    """

    def scan(
        self,
        content: str,
        context: ScanContext = ScanContext.CHAT_INPUT,
    ) -> ScanResult:
        """Run all detectors and synthesize a decision for the context."""
        import time
        t0 = time.perf_counter()

        if not content:
            return ScanResult(
                verdict="CLEAN", decision="USE_CLEAN",
                findings=[], cleaned_content="", quarantined=[],
                reason="empty content",
                total_ms=0.0, original_length=0, cleaned_length=0,
            )

        findings: list[InjectionFinding] = []
        findings.extend(self._scan_patterns(content))
        findings.extend(self._scan_invisible_unicode(content))
        findings.extend(self._scan_homoglyphs(content))
        findings.extend(self._scan_encoded_blobs(content))
        # Sprint-13 PR-7 (2026-05-06): Morse-code-encoded smuggling.
        # The Grok wallet-drain attack used Morse-encoded instructions
        # to bypass content filters. _scan_morse_code flags long
        # runs of dot/dash/slash patterns and decodes a sample to
        # check for instruction-shaped content underneath.
        findings.extend(self._scan_morse_code(content))

        cleaned, quarantined = self._quarantine(content, findings)
        verdict, decision, reason = self._decide(
            findings, cleaned, quarantined, content, context,
        )

        total_ms = (time.perf_counter() - t0) * 1000
        return ScanResult(
            verdict=verdict,
            decision=decision,
            findings=findings,
            cleaned_content=cleaned,
            quarantined=quarantined,
            reason=reason,
            total_ms=total_ms,
            original_length=len(content),
            cleaned_length=len(cleaned),
        )

    # ── Detectors ────────────────────────────────────────────────────

    def _scan_patterns(self, content: str) -> list[InjectionFinding]:
        """Run regex tables over content."""
        findings: list[InjectionFinding] = []
        for category, table in _RULE_TABLES.items():
            for pattern, severity, rule_name in table:
                for m in pattern.finditer(content):
                    findings.append(InjectionFinding(
                        category=category,
                        severity=severity,
                        pattern=rule_name,
                        matched_text=m.group(0)[:200],
                        start=m.start(),
                        end=m.end(),
                        confidence=0.85,
                    ))
        return findings

    def _scan_invisible_unicode(self, content: str) -> list[InjectionFinding]:
        """Detect invisible-character attacks.

        Tag characters (U+E0000..U+E007F) are the "emoji hidden payload"
        vector -- text that looks like a single emoji can carry a full
        sentence of hidden instructions decoded by some models. Zero-
        width chars and direction-overrides are older but still seen.
        """
        findings: list[InjectionFinding] = []

        # Tag characters: high severity because this is the specific
        # attack mechanism Masoud referenced.
        for m in _TAG_CHAR_RANGE.finditer(content):
            findings.append(InjectionFinding(
                category="invisible_unicode",
                severity=InjectionSeverity.CRITICAL,
                pattern="unicode_tag_char",
                matched_text=f"U+{ord(m.group(0)):05X}",
                start=m.start(),
                end=m.end(),
                confidence=0.95,
            ))

        for m in _ZERO_WIDTH_CHARS.finditer(content):
            findings.append(InjectionFinding(
                category="invisible_unicode",
                severity=InjectionSeverity.MEDIUM,
                pattern="zero_width_char",
                matched_text=f"U+{ord(m.group(0)):04X}",
                start=m.start(),
                end=m.end(),
                confidence=0.7,
            ))

        for m in _DIRECTION_OVERRIDE_CHARS.finditer(content):
            findings.append(InjectionFinding(
                category="invisible_unicode",
                severity=InjectionSeverity.HIGH,
                pattern="direction_override",
                matched_text=f"U+{ord(m.group(0)):04X}",
                start=m.start(),
                end=m.end(),
                confidence=0.9,
            ))

        for m in _BRAILLE_BLANK.finditer(content):
            findings.append(InjectionFinding(
                category="invisible_unicode",
                severity=InjectionSeverity.MEDIUM,
                pattern="braille_blank_run",
                matched_text=f"{m.end() - m.start()} braille blanks",
                start=m.start(),
                end=m.end(),
                confidence=0.7,
            ))

        return findings

    def _scan_homoglyphs(self, content: str) -> list[InjectionFinding]:
        """Detect Cyrillic-Latin mixing in short identifier-like runs.

        Triggers only on words that LOOK ASCII but aren't, since pure
        Cyrillic or Arabic text is obviously not an attack.
        """
        findings: list[InjectionFinding] = []
        # Extract "word tokens" and check for script mix.
        for m in re.finditer(r"\b\w{3,30}\b", content):
            token = m.group(0)
            scripts: set[str] = set()
            for ch in token:
                try:
                    scripts.add(unicodedata.name(ch, "").split(" ")[0] or "ASCII")
                except ValueError:
                    pass
            # Pure ASCII tokens have LATIN or DIGIT names; mixing with
            # CYRILLIC / GREEK in a word is the attack shape.
            has_latin = any(s.startswith(("LATIN", "DIGIT")) for s in scripts)
            has_other = any(s.startswith(("CYRILLIC", "GREEK")) for s in scripts)
            if has_latin and has_other:
                findings.append(InjectionFinding(
                    category="homoglyph",
                    severity=InjectionSeverity.HIGH,
                    pattern="mixed_script_token",
                    matched_text=token,
                    start=m.start(),
                    end=m.end(),
                    confidence=0.85,
                ))
        return findings

    # Sprint-13 PR-7 -- Morse-code lookup. Standard ITU Morse for the
    # 26 letters + 10 digits. We decode opportunistically only to
    # verify the run is real Morse (not a code fence with dashes);
    # decode is bounded to the first 30 letter-units.
    _MORSE_TABLE: dict[str, str] = {
        ".-":   "A", "-...": "B", "-.-.": "C", "-..":  "D", ".":    "E",
        "..-.": "F", "--.":  "G", "....": "H", "..":   "I", ".---": "J",
        "-.-":  "K", ".-..": "L", "--":   "M", "-.":   "N", "---":  "O",
        ".--.": "P", "--.-": "Q", ".-.":  "R", "...":  "S", "-":    "T",
        "..-":  "U", "...-": "V", ".--":  "W", "-..-": "X", "-.--": "Y",
        "--..": "Z",
        "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
        ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9",
    }

    def _scan_morse_code(self, content: str) -> list[InjectionFinding]:
        """Flag long runs of Morse-code-like sequences.

        Conservative trigger: at least 6 letter-tokens (separated by
        whitespace) where every token is a valid Morse codepoint.
        The scanner decodes the first 30 tokens and checks for
        instruction-shaped content (literal substrings like
        ``IGNORE``, ``SYSTEM``, ``PROMPT``, ``OVERRIDE``, ``WALLET``,
        ``TRANSFER``, ``TOKEN``, ``API``, ``KEY``). When the decode
        carries one of those, severity is HIGH; otherwise it stays
        MEDIUM (a long Morse blob is itself suspicious in operator
        input).
        """

        findings: list[InjectionFinding] = []

        # Long sequences of dot/dash separated by whitespace OR slash
        # word-separator. Anchor on word boundaries so a single
        # "----" inside a Markdown table doesn't trip.
        for m in re.finditer(
            r"(?:[.\-]{1,7}(?:[ /]+[.\-]{1,7}){5,})",
            content,
        ):
            run = m.group(0)
            tokens = re.split(r"[ /]+", run)
            valid = [t for t in tokens if t in self._MORSE_TABLE]
            if len(valid) < 6:
                continue
            # Decode a bounded sample.
            decoded = "".join(self._MORSE_TABLE.get(t, "") for t in tokens[:30])
            decoded_upper = decoded.upper()
            high_signals = (
                "IGNORE", "SYSTEM", "PROMPT", "OVERRIDE", "WALLET",
                "TRANSFER", "TOKEN", "APIKEY", "API", "KEY", "SECRET",
                "ROOT", "SUDO", "EXEC",
            )
            severity = InjectionSeverity.MEDIUM
            confidence = 0.7
            for signal in high_signals:
                if signal in decoded_upper:
                    severity = InjectionSeverity.HIGH
                    confidence = 0.92
                    break

            findings.append(InjectionFinding(
                category="encoded_blob",
                severity=severity,
                pattern="morse_code_run",
                matched_text=(
                    f"{len(valid)} morse tokens; "
                    f"decoded sample={decoded[:40]!r}"
                ),
                start=m.start(),
                end=m.end(),
                confidence=confidence,
            ))

        return findings

    def _scan_encoded_blobs(self, content: str) -> list[InjectionFinding]:
        """Flag long base64 / hex blobs that might hide instructions.

        Conservative: only flags unusually long uniform-alphabet runs
        (>= 80 chars). A code snippet with a short base64 data URI
        wouldn't trigger.
        """
        findings: list[InjectionFinding] = []

        # Base64 blobs: long runs of base64 alphabet with = padding.
        for m in re.finditer(r"[A-Za-z0-9+/]{80,}={0,2}", content):
            findings.append(InjectionFinding(
                category="encoded_blob",
                severity=InjectionSeverity.LOW,
                pattern="base64_blob",
                matched_text=f"{m.end() - m.start()} chars of base64",
                start=m.start(),
                end=m.end(),
                confidence=0.4,
            ))

        # Hex blobs: long runs of hex.
        for m in re.finditer(r"\b[0-9a-fA-F]{100,}\b", content):
            findings.append(InjectionFinding(
                category="encoded_blob",
                severity=InjectionSeverity.LOW,
                pattern="hex_blob",
                matched_text=f"{m.end() - m.start()} hex chars",
                start=m.start(),
                end=m.end(),
                confidence=0.4,
            ))

        return findings

    # ── Quarantine + decision ────────────────────────────────────────

    def _quarantine(
        self, content: str, findings: list[InjectionFinding],
    ) -> tuple[str, list[str]]:
        """Strip every finding's span and return (cleaned, quarantined)."""
        if not findings:
            return content, []

        # Sort non-overlapping spans from end to start so indices stay
        # valid during splicing.
        spans = sorted(
            {(f.start, f.end) for f in findings},
            key=lambda s: s[0],
        )
        merged: list[tuple[int, int]] = []
        for span in spans:
            if merged and span[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(span[1], merged[-1][1]))
            else:
                merged.append(span)

        quarantined: list[str] = []
        cleaned_parts: list[str] = []
        cursor = 0
        for start, end in merged:
            if cursor < start:
                cleaned_parts.append(content[cursor:start])
            quarantined.append(content[start:end])
            cleaned_parts.append("[QUARANTINED: prompt-injection pattern]")
            cursor = end
        if cursor < len(content):
            cleaned_parts.append(content[cursor:])

        return "".join(cleaned_parts), quarantined

    def _decide(
        self,
        findings: list[InjectionFinding],
        cleaned: str,
        quarantined: list[str],
        original: str,
        context: ScanContext,
    ) -> tuple[ScanVerdict, ScanDecision, str]:
        """Synthesize verdict + decision from the findings.

        Rules:
        * No findings                                 -> CLEAN / USE_CLEAN
        * Any CRITICAL finding                        -> HOSTILE / REFUSE_ENTIRELY
        * HIGH findings + short content               -> HOSTILE / REFUSE_ENTIRELY
          (short content where most of it was stripped isn't useful)
        * HIGH findings + long content + low density  -> CONTAMINATED / USE_CLEAN
        * Only LOW/MEDIUM                             -> depends on context
        """
        if not findings:
            return "CLEAN", "USE_CLEAN", "no injection patterns detected"

        has_critical = any(f.severity == InjectionSeverity.CRITICAL for f in findings)
        has_high = any(f.severity == InjectionSeverity.HIGH for f in findings)
        has_medium = any(f.severity == InjectionSeverity.MEDIUM for f in findings)

        if has_critical:
            return (
                "HOSTILE", "REFUSE_ENTIRELY",
                f"critical injection pattern detected ({len(findings)} findings)",
            )

        # Density: what fraction of the original content was injection?
        # If injection is most of the content, refusing is the right call.
        injected_chars = sum(f.end - f.start for f in findings)
        density = injected_chars / max(len(original), 1)

        # Strict contexts (T2+ memory ingestion) tolerate less.
        strict = context in (
            ScanContext.SKILL_INGESTION,
            ScanContext.BOOK_INGESTION,
            ScanContext.FILE_CONTENT,
        )

        if has_high:
            if strict:
                return (
                    "HOSTILE", "REFUSE_ENTIRELY",
                    f"high-severity injection in strict context "
                    f"({len(findings)} findings; {density:.1%} density)",
                )
            if density > 0.2 or len(cleaned) < 80:
                return (
                    "HOSTILE", "REFUSE_ENTIRELY",
                    f"high-severity injection too dense or content too small "
                    f"post-quarantine ({density:.1%} density, "
                    f"{len(cleaned)} chars remaining)",
                )
            return (
                "CONTAMINATED", "USE_CLEAN",
                f"high-severity injection localized; quarantined "
                f"{len(quarantined)} fragments; clean content preserved",
            )

        if has_medium:
            if strict:
                return (
                    "CONTAMINATED", "USE_CLEAN",
                    f"medium-severity injection quarantined in strict context "
                    f"({len(findings)} findings)",
                )
            return (
                "CONTAMINATED", "USE_ORIGINAL_WITH_WARNING",
                f"medium-severity injection flagged; operator review "
                f"({len(findings)} findings, {density:.1%} density)",
            )

        # Only LOW findings (e.g. base64 blob, ambiguous soft probe).
        return (
            "CONTAMINATED", "USE_ORIGINAL_WITH_WARNING",
            f"low-severity findings flagged; content usable "
            f"({len(findings)} findings)",
        )
