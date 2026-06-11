"""Mythos Mode lens -- mode-aware cognition directives.

Classifies a turn into DEBUG / DECIDE / AUDIT / BUILD with deterministic
regexes and returns the matching Mythos directive as a prompt fragment.
Fired by ``lens_router`` (Stage 6.7) so every Council debater and every
Quintessence expert reasons in the RIGHT mode for the turn: a debug turn
gets hypothesis discipline, a decision turn gets alternatives + steelman,
an audit turn gets hostile-reviewer posture.

Cross-runtime parity: the regexes and directive semantics are kept in
sync with the operator-side hook at
``D:\\agents\\AI_COMPANY_OS\\gates\\mythos_nudge.py`` (v2) so Claude Code,
Codex, and Daena share one cognitive layer. If you change a mode here,
change it there in the same commit.

Zero LLM, zero I/O. Pure string logic, well under the lens router's
150ms budget.
"""

from __future__ import annotations

import re

__all__ = ["MythosMode", "classify"]

# Mode detection -- first match wins, ordered by specificity
# (audit > debug > decide > build).
_MODES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AUDIT", re.compile(
        r"\b(review|audit|secur(e|ity)|pentest|harden|vulnerab|compliance)\b", re.I)),
    ("DEBUG", re.compile(
        r"\b(fix|debug|bug|broken|fail(s|ing|ed)?|crash|error|root cause|investigate|"
        r"regression|too slow|leak|hang|timeout|flaky)\b", re.I)),
    ("DECIDE", re.compile(
        r"\b(should (we|i)|compare|versus|\bvs\b|choose|decide|decision|strategy|"
        r"trade-?off|which (one|approach|stack|model)|worth it|better to)\b", re.I)),
    ("BUILD", re.compile(
        r"\b(build|create|implement|design|architect|add (a |the )?(feature|endpoint|"
        r"service|module|page)|refactor|migrat|integrat|wire|orchestrat|pipeline|"
        r"redesign|rewrite|scal|upgrade|improve|optimi[sz]e)\b", re.I)),
)

_DIRECTIVES: dict[str, str] = {
    "BUILD": (
        "  - Restate the real ask; map consumers and the user's next step before changing anything.\n"
        "  - Plan files/commands/tests/rollback, then hostile self-critique: blind spots, silent "
        "regressions, half-failed states. Check unknowns before executing.\n"
        "  - Compare alternatives and benchmark best-in-class; state the trade-off accepted. "
        "Simplicity: no overbuild."
    ),
    "DEBUG": (
        "  - Reproduce first: no repro, no fix. Observe logs/state/diff before theorizing.\n"
        "  - Hypothesis ladder: cheapest test first, one variable at a time. Fix the root cause, "
        "not the symptom.\n"
        "  - Add a regression test that fails before and passes after. If two hypotheses die, "
        "stop and widen observation."
    ),
    "DECIDE": (
        "  - Generate at least 3 real alternatives including 'do nothing'; steelman each, "
        "don't strawman.\n"
        "  - Score on reversibility, blast radius, cost, and maintenance. Benchmark how "
        "best-in-class solved it.\n"
        "  - Verdict: the pick, why it beats the runner-up, and the tripwire that would reverse it."
    ),
    "AUDIT": (
        "  - Assume defects exist; the job is to find them, not bless the work. Evidence over "
        "claims: run it, probe it, read the diff.\n"
        "  - Severity-ranked findings, each with location and reproduction.\n"
        "  - State explicitly what was NOT covered."
    ),
}


def classify(task: str) -> str:
    """Return the Mythos mode for ``task``, or the empty string when no
    mode keyword hits (the lens then simply does not fire).

    Zero-cost: pure regex, no I/O.
    """
    text = (task or "").strip()
    if not text:
        return ""
    for name, pattern in _MODES:
        if pattern.search(text):
            return name
    return ""


class MythosMode:
    """Mode-aware Mythos directive provider for the cognitive lens router."""

    async def analyze(self, task: str) -> dict[str, str]:
        """Classify ``task`` and return ``{"mode": ..., "directive": ...}``.

        Both values are empty strings when no mode matches. Async for
        interface symmetry with the other cognition modules; performs
        no awaitable work.
        """
        mode = classify(task)
        if not mode:
            return {"mode": "", "directive": ""}
        return {"mode": mode, "directive": _DIRECTIVES[mode]}
