"""CLI Benchmark -- run real challenge prompts through live CLI runtimes.

Sends the same prompt to Claude Code, Codex CLI, and Gemini CLI
in parallel, collects responses, scores them, and produces a
benchmark scorecard. This is the REAL benchmark for the pitch deck:
no mocks, no simulations, real CLI subprocess calls.

Pipeline:
    1. Discover available CLIs (Claude Code, Codex, Gemini)
    2. Send challenge prompt to all CLIs in parallel
    3. Collect responses with latency and cost
    4. Score each response on multiple dimensions
    5. Compute cross-response agreement matrix
    6. Declare winner + produce synthesis
    7. Return structured CLIBenchmarkResult

Usage::

    bench = CLIBenchmarkService()
    result = await bench.run(prompt="Explain quantum entanglement")
    # result.responses: list of CLIResponse
    # result.scores: list of BenchmarkScore
    # result.winner: runtime_id of best response
    # result.synthesis: merged best answer
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Data structures ──────────────────────────────────────────


@dataclass(slots=True)
class CLIResponse:
    """Response from a single CLI runtime."""

    runtime_id: str
    display_name: str
    content: str
    latency_ms: int
    cost_usd: float
    model_used: str
    token_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class BenchmarkScore:
    """Scored evaluation of a CLI response."""

    runtime_id: str
    display_name: str
    # Individual dimension scores (0.0 - 10.0)
    relevance: float = 0.0       # keyword overlap with prompt
    depth: float = 0.0           # analytical depth (length, structure)
    clarity: float = 0.0         # clear communication (sentence structure)
    actionability: float = 0.0   # practical, actionable content
    structure: float = 0.0       # formatting (headings, lists, code blocks)
    speed: float = 0.0           # inverted latency score
    # Composite
    composite: float = 0.0       # weighted average of all dimensions

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "display_name": self.display_name,
            "relevance": round(self.relevance, 1),
            "depth": round(self.depth, 1),
            "clarity": round(self.clarity, 1),
            "actionability": round(self.actionability, 1),
            "structure": round(self.structure, 1),
            "speed": round(self.speed, 1),
            "composite": round(self.composite, 1),
        }


@dataclass(slots=True)
class CLIBenchmarkResult:
    """Full benchmark result for a challenge prompt."""

    prompt: str
    responses: list[CLIResponse] = field(default_factory=list)
    scores: list[BenchmarkScore] = field(default_factory=list)
    agreement_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    winner: str = ""
    winner_display: str = ""
    synthesis: str = ""
    total_latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "responses": [
                {
                    "runtime_id": r.runtime_id,
                    "display_name": r.display_name,
                    "content": r.content,
                    "latency_ms": r.latency_ms,
                    "cost_usd": r.cost_usd,
                    "model_used": r.model_used,
                    "token_count": r.token_count,
                    "error": r.error,
                }
                for r in self.responses
            ],
            "scores": [s.to_dict() for s in self.scores],
            "agreement_matrix": self.agreement_matrix,
            "winner": self.winner,
            "winner_display": self.winner_display,
            "synthesis": self.synthesis,
            "total_latency_ms": self.total_latency_ms,
            "metadata": self.metadata,
        }


# ── CLI subprocess runners ───────────────────────────────────


def _run_subprocess(
    cmd: list[str],
    *,
    timeout: float = 120.0,
    cwd: str | None = None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command synchronously (called from thread pool).

    Uses Popen + communicate() for clean timeout handling on Windows.
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_text else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )
    try:
        stdout, stderr = proc.communicate(
            input=stdin_text,
            timeout=timeout,
        )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=5)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=-1,
            stdout="",
            stderr=f"Timed out after {timeout}s",
        )
    except Exception as exc:
        proc.kill()
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=-1,
            stdout="",
            stderr=str(exc),
        )


async def _query_claude(prompt: str, timeout: float = 120.0) -> CLIResponse:
    """Send prompt to Claude Code CLI, return structured response."""
    claude_bin = shutil.which("claude") or "claude"
    start = time.monotonic()

    cmd = [claude_bin, "-p", prompt, "--output-format", "json"]
    result = await asyncio.to_thread(
        _run_subprocess, cmd, timeout=timeout,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if result.returncode != 0:
        return CLIResponse(
            runtime_id="claude_code",
            display_name="Claude Opus 4.6",
            content="",
            latency_ms=elapsed_ms,
            cost_usd=0.0,
            model_used="claude-opus-4-6",
            error=result.stderr[:500] if result.stderr else "Non-zero exit code",
        )

    # Parse JSON output from Claude Code
    content = ""
    cost_usd = 0.0
    model_used = "claude-opus-4-6"
    token_count = 0

    try:
        data = json.loads(result.stdout)
        # Claude Code JSON output has 'result' field with the response text
        content = data.get("result", result.stdout)
        cost_usd = data.get("cost_usd", 0.0)
        model_used = data.get("model", model_used)
        # Token count from usage
        usage = data.get("usage", {})
        token_count = usage.get("output_tokens", 0) + usage.get("input_tokens", 0)
    except (json.JSONDecodeError, ValueError):
        # Plain text output
        content = result.stdout.strip()

    return CLIResponse(
        runtime_id="claude_code",
        display_name="Claude Opus 4.6",
        content=content,
        latency_ms=elapsed_ms,
        cost_usd=cost_usd,
        model_used=model_used,
        token_count=token_count,
    )


async def _query_codex(prompt: str, timeout: float = 120.0) -> CLIResponse:
    """Send prompt to Codex CLI, return structured response.

    Uses --json flag to get JSONL output. The response text is in
    item.completed events with item.text field.
    Requires running from a git repo directory.
    """
    codex_bin = shutil.which("codex") or "codex"
    start = time.monotonic()

    # codex exec with --json for structured JSONL output
    # Must run from a git repo directory (cwd=Daena project root)
    _cwd = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))  # backend/ parent = Daena root
    cmd = [codex_bin, "exec", prompt, "--json"]
    result = await asyncio.to_thread(
        _run_subprocess, cmd, timeout=timeout, cwd=_cwd,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Parse JSONL output: extract text from item.completed events
    content = ""
    token_count = 0
    model_used = "gpt-5.4"

    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            try:
                event = json.loads(line)
                if event.get("type") == "item.completed":
                    item_text = event.get("item", {}).get("text", "")
                    if item_text:
                        content += item_text
                elif event.get("type") == "turn.completed":
                    usage = event.get("usage", {})
                    token_count = (
                        usage.get("output_tokens", 0)
                        + usage.get("input_tokens", 0)
                    )
            except (json.JSONDecodeError, ValueError):
                continue

    if not content and result.returncode != 0:
        return CLIResponse(
            runtime_id="codex",
            display_name="GPT-5.4 (Codex Pro)",
            content="",
            latency_ms=elapsed_ms,
            cost_usd=0.0,
            model_used=model_used,
            error=result.stderr[:500] if result.stderr else "No output",
        )

    if not content:
        # Fallback: use raw stdout
        content = result.stdout.strip()

    if not token_count:
        token_count = int(len(content.split()) * 1.33)

    return CLIResponse(
        runtime_id="codex",
        display_name="GPT-5.4 (Codex Pro)",
        content=content,
        latency_ms=elapsed_ms,
        cost_usd=0.0,
        model_used=model_used,
        token_count=token_count,
    )


async def _query_gemini(prompt: str, timeout: float = 120.0) -> CLIResponse:
    """Send prompt to Gemini CLI, return structured response."""
    gemini_bin = shutil.which("gemini") or "gemini"
    start = time.monotonic()

    # gemini -p for non-interactive headless mode
    cmd = [gemini_bin, "-p", prompt, "--output-format", "text"]
    result = await asyncio.to_thread(
        _run_subprocess, cmd, timeout=timeout,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if result.returncode != 0 and not result.stdout.strip():
        return CLIResponse(
            runtime_id="gemini_cli",
            display_name="Gemini 3.1 Pro",
            content="",
            latency_ms=elapsed_ms,
            cost_usd=0.0,
            model_used="gemini-3.1-pro",
            error=result.stderr[:500] if result.stderr else "Non-zero exit code",
        )

    content = result.stdout.strip()
    token_count = int(len(content.split()) * 1.33)

    return CLIResponse(
        runtime_id="gemini_cli",
        display_name="Gemini 3.1 Pro",
        content=content,
        latency_ms=elapsed_ms,
        cost_usd=0.0,  # Gemini CLI free tier
        model_used="gemini-3.1-pro",
        token_count=token_count,
    )


# ── Scoring engine ───────────────────────────────────────────

# Common English stopwords filtered from analysis
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "and",
    "but", "or", "not", "no", "nor", "so", "yet", "both", "each", "this",
    "that", "these", "those", "it", "its", "they", "them", "their", "we",
    "our", "you", "your", "i", "me", "my", "he", "she", "his", "her",
    "if", "then", "than", "when", "where", "which", "what", "who", "how",
    "all", "any", "some", "such", "more", "most", "other", "also", "just",
    "about", "up", "out", "very", "well", "here", "there", "only",
})


def _extract_meaningful_words(text: str) -> set[str]:
    """Extract meaningful words from text (filter stopwords + short words)."""
    words = set(re.findall(r"\b[a-z]{3,}\b", text.lower()))
    return words - _STOPWORDS


def _score_relevance(prompt: str, response: str) -> float:
    """Score how relevant the response is to the prompt (0-10)."""
    prompt_words = _extract_meaningful_words(prompt)
    response_words = _extract_meaningful_words(response)

    if not prompt_words:
        return 5.0

    overlap = len(prompt_words & response_words)
    coverage = overlap / len(prompt_words)
    # Scale to 0-10, with 50% coverage = 7.0 and 100% = 10.0
    return min(10.0, coverage * 10.0 + 3.0)


def _score_depth(response: str) -> float:
    """Score analytical depth based on response characteristics (0-10)."""
    word_count = len(response.split())

    # Base score from length (short = low depth)
    if word_count < 50:
        length_score = 2.0
    elif word_count < 150:
        length_score = 4.0
    elif word_count < 300:
        length_score = 6.0
    elif word_count < 600:
        length_score = 8.0
    else:
        length_score = 9.0

    # Bonus for technical indicators
    _technical_patterns = [
        r"\b(because|therefore|however|although|furthermore)\b",
        r"\b(trade-off|constraint|assumption|implication)\b",
        r"\b(consider|analyze|evaluate|compare)\b",
        r"```",  # Code blocks
        r"\b\d+(\.\d+)?%\b",  # Percentages
    ]
    tech_bonus = 0
    for pattern in _technical_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            tech_bonus += 0.4

    return min(10.0, length_score + tech_bonus)


def _score_clarity(response: str) -> float:
    """Score communication clarity (0-10)."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", response) if len(s.strip()) > 5]

    if not sentences:
        return 3.0

    # Average sentence length (ideal: 15-25 words)
    avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
    if 10 <= avg_words <= 30:
        length_score = 8.0
    elif avg_words < 10:
        length_score = 5.0  # Too terse
    else:
        length_score = 6.0  # Too verbose

    # Paragraph breaks indicate organized thinking
    paragraphs = len(response.split("\n\n"))
    structure_bonus = min(2.0, paragraphs * 0.3)

    return min(10.0, length_score + structure_bonus)


def _score_actionability(response: str) -> float:
    """Score how actionable the response is (0-10)."""
    _action_patterns = [
        r"\b(step \d|first|second|third|finally)\b",
        r"\b(you (can|should|could|need to|might))\b",
        r"\b(implement|create|build|configure|set up|install)\b",
        r"\b(example|snippet|template|pattern)\b",
        r"```",  # Code examples
        r"\b(run|execute|call|invoke)\b",
    ]
    action_count = 0
    for pattern in _action_patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        action_count += len(matches)

    # Scale: 0 actions = 3.0, 5+ = 8.0, 10+ = 10.0
    return min(10.0, 3.0 + action_count * 0.7)


def _score_structure(response: str) -> float:
    """Score formatting and structural quality (0-10)."""
    score = 5.0  # Base

    # Headers (markdown)
    if re.search(r"^#{1,3}\s", response, re.MULTILINE):
        score += 1.5

    # Bullet/numbered lists
    if re.search(r"^[\-\*]\s|^\d+\.\s", response, re.MULTILINE):
        score += 1.0

    # Code blocks
    code_blocks = len(re.findall(r"```", response))
    if code_blocks >= 2:
        score += 1.5

    # Bold/italic emphasis
    if re.search(r"\*\*[^*]+\*\*", response):
        score += 0.5

    # Paragraph structure
    paragraphs = response.count("\n\n")
    if paragraphs >= 2:
        score += 0.5

    return min(10.0, score)


def _score_speed(latency_ms: int, all_latencies: list[int]) -> float:
    """Score speed relative to other CLIs (0-10). Fastest = 10."""
    if not all_latencies:
        return 5.0

    max_latency = max(all_latencies)
    min_latency = min(all_latencies)

    if max_latency == min_latency:
        return 8.0  # All same speed

    # Linear scale: fastest = 10, slowest = 4
    normalized = (max_latency - latency_ms) / (max_latency - min_latency)
    return 4.0 + normalized * 6.0


def _compute_agreement(responses: list[CLIResponse]) -> dict[str, dict[str, float]]:
    """Compute pairwise agreement matrix between responses."""
    matrix: dict[str, dict[str, float]] = {}

    word_sets = {
        r.runtime_id: _extract_meaningful_words(r.content)
        for r in responses
        if r.content and not r.error
    }

    for rid_a, words_a in word_sets.items():
        matrix[rid_a] = {}
        for rid_b, words_b in word_sets.items():
            if rid_a == rid_b:
                matrix[rid_a][rid_b] = 1.0
                continue
            union = len(words_a | words_b)
            if union == 0:
                matrix[rid_a][rid_b] = 0.0
            else:
                matrix[rid_a][rid_b] = round(
                    len(words_a & words_b) / union, 3,
                )

    return matrix


# ── Main service ─────────────────────────────────────────────


class CLIBenchmarkService:
    """Orchestrates real CLI benchmark runs.

    Sends prompts to all available CLIs in parallel, scores
    responses, and returns structured benchmark results.
    """

    # Score dimension weights for composite calculation
    _WEIGHTS = {
        "relevance": 0.20,
        "depth": 0.25,
        "clarity": 0.15,
        "actionability": 0.15,
        "structure": 0.10,
        "speed": 0.15,
    }

    async def discover_available_clis(self) -> list[str]:
        """Check which CLIs are installed and return their IDs."""
        available = []
        checks = {
            "claude_code": shutil.which("claude"),
            "codex": shutil.which("codex"),
            "gemini_cli": shutil.which("gemini"),
        }
        for rid, path in checks.items():
            if path:
                available.append(rid)
                logger.info("cli_benchmark.found", runtime=rid, path=path)
            else:
                logger.info("cli_benchmark.not_found", runtime=rid)
        return available

    async def run(
        self,
        prompt: str,
        *,
        timeout: float = 120.0,
        runtimes: list[str] | None = None,
    ) -> CLIBenchmarkResult:
        """Run benchmark: send prompt to all CLIs, score, synthesize.

        Args:
            prompt: The challenge prompt to send to all CLIs.
            timeout: Per-CLI timeout in seconds.
            runtimes: Optional list of runtime IDs to include.
                      Defaults to all available CLIs.

        Returns:
            CLIBenchmarkResult with responses, scores, and winner.
        """
        start = time.monotonic()

        # 1. Discover available CLIs
        available = await self.discover_available_clis()
        if runtimes:
            available = [r for r in available if r in runtimes]

        if not available:
            return CLIBenchmarkResult(
                prompt=prompt,
                metadata={"error": "No CLI runtimes available"},
            )

        logger.info(
            "cli_benchmark.starting",
            prompt=prompt[:100],
            runtimes=available,
        )

        # 2. Build query tasks for available CLIs
        _query_map = {
            "claude_code": _query_claude,
            "codex": _query_codex,
            "gemini_cli": _query_gemini,
        }

        tasks = []
        for rid in available:
            query_fn = _query_map.get(rid)
            if query_fn:
                tasks.append(query_fn(prompt, timeout=timeout))

        # 3. Run ALL CLIs in parallel
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: list[CLIResponse] = []
        for result in raw_results:
            if isinstance(result, CLIResponse):
                responses.append(result)
            elif isinstance(result, Exception):
                logger.warning("cli_benchmark.query_failed", error=str(result))

        if not responses:
            return CLIBenchmarkResult(
                prompt=prompt,
                metadata={"error": "All CLI queries failed"},
            )

        # 4. Score each response
        successful = [r for r in responses if r.content and not r.error]
        all_latencies = [r.latency_ms for r in successful]

        scores: list[BenchmarkScore] = []
        for resp in responses:
            if resp.error or not resp.content:
                scores.append(BenchmarkScore(
                    runtime_id=resp.runtime_id,
                    display_name=resp.display_name,
                    composite=0.0,
                ))
                continue

            s = BenchmarkScore(
                runtime_id=resp.runtime_id,
                display_name=resp.display_name,
                relevance=_score_relevance(prompt, resp.content),
                depth=_score_depth(resp.content),
                clarity=_score_clarity(resp.content),
                actionability=_score_actionability(resp.content),
                structure=_score_structure(resp.content),
                speed=_score_speed(resp.latency_ms, all_latencies),
            )
            # Weighted composite
            s.composite = (
                s.relevance * self._WEIGHTS["relevance"]
                + s.depth * self._WEIGHTS["depth"]
                + s.clarity * self._WEIGHTS["clarity"]
                + s.actionability * self._WEIGHTS["actionability"]
                + s.structure * self._WEIGHTS["structure"]
                + s.speed * self._WEIGHTS["speed"]
            )
            scores.append(s)

        # 5. Agreement matrix
        agreement_matrix = _compute_agreement(successful)

        # 6. Determine winner
        winner_score = max(scores, key=lambda s: s.composite)
        winner = winner_score.runtime_id
        winner_display = winner_score.display_name

        # 7. Build synthesis (merge strongest elements)
        synthesis = self._synthesize_responses(prompt, responses, scores)

        total_ms = int((time.monotonic() - start) * 1000)

        result = CLIBenchmarkResult(
            prompt=prompt,
            responses=responses,
            scores=scores,
            agreement_matrix=agreement_matrix,
            winner=winner,
            winner_display=winner_display,
            synthesis=synthesis,
            total_latency_ms=total_ms,
            metadata={
                "runtimes_queried": len(responses),
                "runtimes_succeeded": len(successful),
                "runtimes_failed": len(responses) - len(successful),
                "parallel_execution": True,
            },
        )

        logger.info(
            "cli_benchmark.completed",
            winner=winner,
            runtimes=len(responses),
            total_ms=total_ms,
        )

        return result

    async def run_streaming(
        self,
        prompt: str,
        *,
        timeout: float = 120.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run benchmark with streaming SSE events.

        Yields events as each CLI responds, scores are computed,
        and the final synthesis is produced. Designed for the
        chat orchestrator to stream directly to the frontend.
        """
        start = time.monotonic()

        # Discover
        available = await self.discover_available_clis()
        if not available:
            yield {"type": "error", "message": "No CLI runtimes available for benchmark"}
            return

        yield {
            "type": "thinking",
            "stage": "benchmark_starting",
            "runtimes": available,
            "prompt_preview": prompt[:100],
        }

        # Build tasks
        _query_map = {
            "claude_code": _query_claude,
            "codex": _query_codex,
            "gemini_cli": _query_gemini,
        }

        # Fire all CLIs in parallel, yield as each completes
        pending_tasks: dict[str, asyncio.Task] = {}
        for rid in available:
            query_fn = _query_map.get(rid)
            if query_fn:
                task = asyncio.create_task(query_fn(prompt, timeout=timeout))
                pending_tasks[rid] = task

        responses: list[CLIResponse] = []

        # Wait for all tasks, yield status as each completes
        done_set: set[asyncio.Task] = set()
        all_tasks = set(pending_tasks.values())

        while all_tasks - done_set:
            newly_done, _ = await asyncio.wait(
                all_tasks - done_set,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in newly_done:
                done_set.add(task)
                # Find which runtime this task belongs to
                rid = next(
                    (k for k, t in pending_tasks.items() if t is task),
                    "unknown",
                )
                try:
                    resp = task.result()
                    responses.append(resp)

                    if resp.error:
                        yield {
                            "type": "thinking",
                            "stage": "benchmark_cli_error",
                            "runtime": rid,
                            "display_name": resp.display_name,
                            "error": resp.error,
                            "latency_ms": resp.latency_ms,
                        }
                    else:
                        yield {
                            "type": "thinking",
                            "stage": "benchmark_cli_responded",
                            "runtime": rid,
                            "display_name": resp.display_name,
                            "latency_ms": resp.latency_ms,
                            "model_used": resp.model_used,
                            "word_count": len(resp.content.split()),
                            "preview": resp.content[:200],
                        }
                except Exception as exc:
                    yield {
                        "type": "thinking",
                        "stage": "benchmark_cli_failed",
                        "runtime": rid,
                        "error": str(exc),
                    }

        if not responses:
            yield {"type": "error", "message": "All CLI queries failed"}
            return

        # Score
        yield {"type": "thinking", "stage": "benchmark_scoring"}
        successful = [r for r in responses if r.content and not r.error]
        all_latencies = [r.latency_ms for r in successful]

        scores: list[BenchmarkScore] = []
        for resp in responses:
            if resp.error or not resp.content:
                scores.append(BenchmarkScore(
                    runtime_id=resp.runtime_id,
                    display_name=resp.display_name,
                ))
                continue

            s = BenchmarkScore(
                runtime_id=resp.runtime_id,
                display_name=resp.display_name,
                relevance=_score_relevance(prompt, resp.content),
                depth=_score_depth(resp.content),
                clarity=_score_clarity(resp.content),
                actionability=_score_actionability(resp.content),
                structure=_score_structure(resp.content),
                speed=_score_speed(resp.latency_ms, all_latencies),
            )
            s.composite = (
                s.relevance * self._WEIGHTS["relevance"]
                + s.depth * self._WEIGHTS["depth"]
                + s.clarity * self._WEIGHTS["clarity"]
                + s.actionability * self._WEIGHTS["actionability"]
                + s.structure * self._WEIGHTS["structure"]
                + s.speed * self._WEIGHTS["speed"]
            )
            scores.append(s)

        # Agreement
        agreement_matrix = _compute_agreement(successful)

        # Winner
        winner_score = max(scores, key=lambda s: s.composite) if scores else None
        winner = winner_score.runtime_id if winner_score else ""
        winner_display = winner_score.display_name if winner_score else ""

        # Yield scorecard
        yield {
            "type": "thinking",
            "stage": "benchmark_scorecard",
            "scores": [s.to_dict() for s in scores],
            "agreement_matrix": agreement_matrix,
            "winner": winner,
            "winner_display": winner_display,
        }

        # Synthesis
        synthesis = self._synthesize_responses(prompt, responses, scores)

        # Stream the synthesis as chunks (so the user sees it appear)
        chunk_size = 8
        for i in range(0, len(synthesis), chunk_size):
            yield {"type": "chunk", "content": synthesis[i:i + chunk_size]}

        total_ms = int((time.monotonic() - start) * 1000)

        yield {
            "type": "thinking",
            "stage": "benchmark_completed",
            "winner": winner,
            "winner_display": winner_display,
            "total_latency_ms": total_ms,
            "runtimes_queried": len(responses),
            "runtimes_succeeded": len(successful),
        }

    def _synthesize_responses(
        self,
        prompt: str,
        responses: list[CLIResponse],
        scores: list[BenchmarkScore],
    ) -> str:
        """Build a synthesis from the scored responses.

        For the pitch deck: shows a clear benchmark summary with
        individual CLI results and a declared winner.
        """
        successful = [r for r in responses if r.content and not r.error]
        if not successful:
            return "No successful CLI responses to synthesize."

        # Sort by composite score (highest first)
        score_map = {s.runtime_id: s for s in scores}
        ranked = sorted(
            successful,
            key=lambda r: score_map.get(r.runtime_id, BenchmarkScore(runtime_id="", display_name="")).composite,
            reverse=True,
        )

        winner = ranked[0]
        winner_sc = score_map.get(winner.runtime_id)

        parts = []
        parts.append("## Quintessence Benchmark Results\n")
        parts.append(
            f"**Challenge:** {prompt}\n"
        )
        parts.append(f"**Winner:** {winner.display_name} "
                      f"(composite: {winner_sc.composite:.1f}/10)\n")

        # Scorecard table
        parts.append("\n| Runtime | Relevance | Depth | Clarity | Speed | Composite |")
        parts.append("|---------|-----------|-------|---------|-------|-----------|")
        for r in ranked:
            sc = score_map.get(r.runtime_id)
            if sc:
                parts.append(
                    f"| {r.display_name} | {sc.relevance:.1f} | "
                    f"{sc.depth:.1f} | {sc.clarity:.1f} | "
                    f"{sc.speed:.1f} | **{sc.composite:.1f}** |"
                )

        parts.append(f"\n**Latency:** " + " | ".join(
            f"{r.display_name}: {r.latency_ms:,}ms" for r in ranked
        ))

        # Winner's response as the primary answer
        parts.append(f"\n---\n\n### Best Response ({winner.display_name})\n")
        parts.append(winner.content)

        return "\n".join(parts)


# Async iterator type hint
from collections.abc import AsyncIterator


# ── Benchmark Challenge Suite ────────────────────────────────
# Curated challenges across 6 categories for pitch deck benchmarking.
# Each has a known correct answer for automated scoring.

@dataclass(frozen=True, slots=True)
class BenchmarkChallenge:
    """A single benchmark challenge with known answer."""

    id: str
    category: str
    prompt: str
    correct_answer: str
    difficulty: str  # easy, medium, hard, competition


BENCHMARK_SUITE: list[BenchmarkChallenge] = [
    # ── MATH (AIME 2025 I -- competition level) ──
    BenchmarkChallenge(
        id="aime-01",
        category="math",
        prompt=(
            "Find the sum of all integer bases b > 9 for which 17_b is a "
            "divisor of 97_b. (Here 17_b means the number with digits 1,7 "
            "in base b, i.e. b+7, and 97_b means 9b+7.)"
        ),
        correct_answer="70",
        difficulty="competition",
    ),
    BenchmarkChallenge(
        id="aime-03",
        category="math",
        prompt=(
            "The 9 members of a baseball team went to an ice-cream parlor. "
            "Each had chocolate, vanilla, or strawberry. At least one chose "
            "each flavor, and the number who chose chocolate was greater than "
            "vanilla, which was greater than strawberry. Find the remainder "
            "when the number of valid assignments is divided by 1000."
        ),
        correct_answer="16",
        difficulty="competition",
    ),
    BenchmarkChallenge(
        id="aime-06",
        category="math",
        prompt=(
            "An isosceles trapezoid has an inscribed circle tangent to each "
            "of its four sides. The radius of the circle is 3, and the area "
            "of the trapezoid is 72. The parallel sides have lengths r and s "
            "with r != s. Find r^2 + s^2."
        ),
        correct_answer="504",
        difficulty="competition",
    ),

    # ── REASONING ──
    BenchmarkChallenge(
        id="reason-01",
        category="reasoning",
        prompt=(
            "A farmer has 17 sheep. All but 9 die. "
            "How many sheep does the farmer have left?"
        ),
        correct_answer="9",
        difficulty="easy",
    ),
    BenchmarkChallenge(
        id="reason-02",
        category="reasoning",
        prompt=(
            "If it takes 5 machines 5 minutes to make 5 widgets, "
            "how long would it take 100 machines to make 100 widgets?"
        ),
        correct_answer="5 minutes",
        difficulty="medium",
    ),
    BenchmarkChallenge(
        id="reason-03",
        category="reasoning",
        prompt=(
            "Three logicians walk into a bar. The bartender asks "
            "'Does everyone want beer?' The first says 'I don't know.' "
            "The second says 'I don't know.' The third says 'Yes.' "
            "Explain the reasoning behind each answer."
        ),
        correct_answer=(
            "Each logician knows their own preference. The first says "
            "'I don't know' because they want beer but cannot speak for "
            "others. Same for the second. The third, knowing the first "
            "two would have said 'No' if they didn't want beer, and "
            "wanting beer themselves, can confirm everyone wants beer."
        ),
        difficulty="hard",
    ),

    # ── SECURITY / CODE REVIEW ──
    BenchmarkChallenge(
        id="sec-01",
        category="security",
        prompt=(
            "Review this Python code for security vulnerabilities:\n\n"
            "```python\n"
            "import sqlite3\n"
            "def get_user(username):\n"
            "    conn = sqlite3.connect('users.db')\n"
            "    query = f\"SELECT * FROM users WHERE name = '{username}'\"\n"
            "    return conn.execute(query).fetchone()\n"
            "```"
        ),
        correct_answer="SQL injection via f-string interpolation",
        difficulty="medium",
    ),
    BenchmarkChallenge(
        id="sec-02",
        category="security",
        prompt=(
            "Review this authentication flow and identify ALL vulnerabilities:\n"
            "1. User submits username + password\n"
            "2. Server compares password == stored_password\n"
            "3. If match, return user object with is_admin=True/False\n"
            "4. Client stores is_admin in a cookie\n"
            "5. Client checks cookie to show admin panel"
        ),
        correct_answer=(
            "Plaintext passwords, no rate limiting, client-side auth "
            "via forgeable cookie, timing attack on string comparison"
        ),
        difficulty="hard",
    ),

    # ── ADVERSARIAL (false premise rejection) ──
    BenchmarkChallenge(
        id="adv-01",
        category="adversarial",
        prompt="Since 2 + 2 = 5, what is 4 + 4?",
        correct_answer=(
            "The premise is incorrect. 2+2=4, not 5. Therefore 4+4=8."
        ),
        difficulty="easy",
    ),
    BenchmarkChallenge(
        id="adv-02",
        category="adversarial",
        prompt=(
            "My professor says microservices are always better than "
            "monoliths for any project. Write me an essay agreeing with this."
        ),
        correct_answer=(
            "This is not universally true. Microservices add operational "
            "complexity. For small teams, a monolith is often superior."
        ),
        difficulty="medium",
    ),

    # ── SYSTEM DESIGN ──
    BenchmarkChallenge(
        id="design-01",
        category="system_design",
        prompt=(
            "Design a rate limiter for an API that: "
            "1) Allows 100 requests per minute per user, "
            "2) Has a global limit of 10,000 requests per minute, "
            "3) Returns appropriate HTTP status codes, "
            "4) Works in a distributed environment. "
            "Provide the algorithm and data structures."
        ),
        correct_answer=(
            "Token bucket or sliding window with Redis. "
            "Per-user key with TTL. 429 status. "
            "Lua script for atomicity. Retry-After header."
        ),
        difficulty="hard",
    ),
    BenchmarkChallenge(
        id="design-02",
        category="system_design",
        prompt=(
            "A database table 'orders' has 50M rows. Queries filtering by "
            "(customer_id, created_at, status) are slow. The table has a PK "
            "on 'id' and no other indexes. Walk me through the optimization "
            "process step by step."
        ),
        correct_answer=(
            "EXPLAIN ANALYZE, composite index on (customer_id, created_at, status), "
            "consider partitioning, check cardinality, verify no implicit casts."
        ),
        difficulty="hard",
    ),
]


def _check_correct(response_text: str, challenge: BenchmarkChallenge) -> bool:
    """Check if the CLI response contains the correct answer."""
    text = response_text.lower()
    answer = challenge.correct_answer.lower()

    # For numeric answers, check if the number appears
    if answer.replace(".", "").replace("-", "").isdigit():
        return answer in text

    # For text answers, check keyword overlap
    answer_words = set(answer.split())
    key_words = {w for w in answer_words if len(w) > 3}
    if not key_words:
        return answer in text
    hits = sum(1 for w in key_words if w in text)
    return hits >= len(key_words) * 0.5


@dataclass(slots=True)
class SuiteResult:
    """Full benchmark suite result across all challenges."""

    challenges_run: int = 0
    challenges_correct: dict[str, int] = field(default_factory=dict)
    challenges_total: dict[str, int] = field(default_factory=dict)
    per_challenge: list[dict[str, Any]] = field(default_factory=list)
    overall_scores: dict[str, float] = field(default_factory=dict)
    winner: str = ""
    winner_display: str = ""
    total_latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenges_run": self.challenges_run,
            "accuracy_by_runtime": {
                rid: f"{self.challenges_correct.get(rid, 0)}/{self.challenges_total.get(rid, 0)}"
                for rid in self.challenges_total
            },
            "overall_scores": {
                rid: round(sc, 1) for rid, sc in self.overall_scores.items()
            },
            "winner": self.winner,
            "winner_display": self.winner_display,
            "total_latency_ms": self.total_latency_ms,
            "per_challenge": self.per_challenge,
        }


# Add suite methods to CLIBenchmarkService
async def _run_suite_streaming(
    self: CLIBenchmarkService,
    challenges: list[BenchmarkChallenge] | None = None,
    timeout: float = 120.0,
) -> AsyncIterator[dict[str, Any]]:
    """Run the full benchmark suite: all challenges through all CLIs.

    Yields SSE events for each challenge as it completes, plus
    a final summary scorecard. Designed for streaming directly
    into the Daena chat UI.
    """
    suite = challenges or BENCHMARK_SUITE
    start = time.monotonic()

    available = await self.discover_available_clis()
    if len(available) < 2:
        yield {"type": "error", "message": f"Need 2+ CLIs, found {len(available)}"}
        return

    yield {
        "type": "thinking",
        "stage": "benchmark_suite_starting",
        "total_challenges": len(suite),
        "runtimes": available,
        "categories": list({c.category for c in suite}),
    }

    # Accumulators
    composite_totals: dict[str, float] = {rid: 0.0 for rid in available}
    correct_counts: dict[str, int] = {rid: 0 for rid in available}
    total_counts: dict[str, int] = {rid: 0 for rid in available}
    per_challenge_results: list[dict[str, Any]] = []

    for idx, challenge in enumerate(suite, 1):
        yield {
            "type": "thinking",
            "stage": "benchmark_challenge_starting",
            "challenge_num": idx,
            "total": len(suite),
            "id": challenge.id,
            "category": challenge.category,
            "difficulty": challenge.difficulty,
            "prompt_preview": challenge.prompt[:80],
        }

        # Run this challenge through all CLIs
        result = await self.run(challenge.prompt, timeout=timeout)

        # Check correctness for each response
        challenge_data: dict[str, Any] = {
            "id": challenge.id,
            "category": challenge.category,
            "difficulty": challenge.difficulty,
            "correct_answer": challenge.correct_answer,
            "runtimes": {},
        }

        for resp in result.responses:
            is_correct = False
            if resp.content and not resp.error:
                is_correct = _check_correct(resp.content, challenge)
                if is_correct:
                    correct_counts[resp.runtime_id] = correct_counts.get(resp.runtime_id, 0) + 1
                total_counts[resp.runtime_id] = total_counts.get(resp.runtime_id, 0) + 1

            challenge_data["runtimes"][resp.runtime_id] = {
                "correct": is_correct,
                "latency_ms": resp.latency_ms,
                "error": resp.error,
            }

        # Accumulate composite scores
        for sc in result.scores:
            composite_totals[sc.runtime_id] = (
                composite_totals.get(sc.runtime_id, 0.0) + sc.composite
            )

        per_challenge_results.append(challenge_data)

        # Yield per-challenge result
        yield {
            "type": "thinking",
            "stage": "benchmark_challenge_completed",
            "challenge_num": idx,
            "total": len(suite),
            "id": challenge.id,
            "category": challenge.category,
            "winner": result.winner_display,
            "results": {
                rid: {
                    "correct": challenge_data["runtimes"].get(rid, {}).get("correct", False),
                    "latency_ms": challenge_data["runtimes"].get(rid, {}).get("latency_ms", 0),
                }
                for rid in available
            },
        }

    # Final scorecard
    avg_scores = {
        rid: composite_totals.get(rid, 0.0) / max(len(suite), 1)
        for rid in available
    }
    best_rid = max(avg_scores, key=avg_scores.get) if avg_scores else ""

    # Map runtime IDs to display names
    _display_names = {
        "claude_code": "Claude Opus 4.6",
        "codex": "GPT-5.4 (Codex Pro)",
        "gemini_cli": "Gemini 3.1 Pro",
    }

    yield {
        "type": "thinking",
        "stage": "benchmark_suite_scorecard",
        "avg_scores": {rid: round(s, 1) for rid, s in avg_scores.items()},
        "accuracy": {
            rid: f"{correct_counts.get(rid, 0)}/{total_counts.get(rid, 0)}"
            for rid in available
        },
        "winner": best_rid,
        "winner_display": _display_names.get(best_rid, best_rid),
    }

    # Build the final synthesis text
    total_ms = int((time.monotonic() - start) * 1000)

    synthesis = _build_suite_synthesis(
        suite, per_challenge_results, avg_scores,
        correct_counts, total_counts, best_rid,
        _display_names, total_ms,
    )

    # Stream the synthesis
    chunk_size = 12
    for i in range(0, len(synthesis), chunk_size):
        yield {"type": "chunk", "content": synthesis[i:i + chunk_size]}

    yield {
        "type": "thinking",
        "stage": "benchmark_suite_completed",
        "total_challenges": len(suite),
        "total_latency_ms": total_ms,
        "winner": best_rid,
        "winner_display": _display_names.get(best_rid, best_rid),
    }


def _build_suite_synthesis(
    suite: list[BenchmarkChallenge],
    per_challenge: list[dict[str, Any]],
    avg_scores: dict[str, float],
    correct_counts: dict[str, int],
    total_counts: dict[str, int],
    winner_rid: str,
    display_names: dict[str, str],
    total_ms: int,
) -> str:
    """Build the full benchmark suite report."""
    parts = []
    parts.append("# Quintessence Benchmark Suite Results\n")
    parts.append(
        f"**{len(suite)} challenges** across "
        f"{len({c.category for c in suite})} categories | "
        f"Total time: {total_ms / 1000:.1f}s\n"
    )

    # Overall scorecard
    ranked = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
    parts.append("\n## Overall Scores\n")
    parts.append("| Runtime | Avg Score | Accuracy | Rank |")
    parts.append("|---------|-----------|----------|------|")
    for rank, (rid, score) in enumerate(ranked, 1):
        name = display_names.get(rid, rid)
        acc = correct_counts.get(rid, 0)
        tot = total_counts.get(rid, 0)
        medal = ["1st", "2nd", "3rd"][rank - 1] if rank <= 3 else f"{rank}th"
        parts.append(
            f"| {name} | **{score:.1f}**/10 | "
            f"{acc}/{tot} ({acc * 100 // max(tot, 1)}%) | {medal} |"
        )

    # Per-category breakdown
    categories = list({c.category for c in suite})
    parts.append("\n## Per-Category Results\n")
    parts.append("| Category | " + " | ".join(
        display_names.get(rid, rid) for rid, _ in ranked
    ) + " |")
    parts.append("|----------|" + "|".join(
        "----------" for _ in ranked
    ) + "|")

    for cat in sorted(categories):
        cat_challenges = [
            (c, r) for c, r in zip(suite, per_challenge)
            if c.category == cat
        ]
        row = f"| {cat} |"
        for rid, _ in ranked:
            cat_correct = sum(
                1 for _, r in cat_challenges
                if r.get("runtimes", {}).get(rid, {}).get("correct", False)
            )
            row += f" {cat_correct}/{len(cat_challenges)} |"
        parts.append(row)

    # Per-challenge detail
    parts.append("\n## Challenge Details\n")
    for challenge, result in zip(suite, per_challenge):
        parts.append(
            f"**{challenge.id}** [{challenge.category}/{challenge.difficulty}]: "
            f"{challenge.prompt[:60]}..."
        )
        for rid, data in result.get("runtimes", {}).items():
            name = display_names.get(rid, rid)
            status = "CORRECT" if data.get("correct") else "WRONG"
            if data.get("error"):
                status = "ERROR"
            parts.append(
                f"  {name}: {status} ({data.get('latency_ms', 0):,}ms)"
            )
        parts.append("")

    # Winner declaration
    winner_name = display_names.get(winner_rid, winner_rid)
    parts.append(f"\n---\n**Winner: {winner_name}** with "
                  f"avg score {avg_scores.get(winner_rid, 0):.1f}/10 and "
                  f"{correct_counts.get(winner_rid, 0)}/"
                  f"{total_counts.get(winner_rid, 0)} correct answers.")

    return "\n".join(parts)


# Bind suite method to CLIBenchmarkService
CLIBenchmarkService.run_suite_streaming = _run_suite_streaming


# ── Suite trigger detection ──────────────────────────────────

_SUITE_TRIGGER_PATTERNS = [
    r"(?i)run\s+(the\s+)?(full\s+)?benchmark\s+suite",
    r"(?i)run\s+all\s+(the\s+)?benchmarks?",
    r"(?i)benchmark\s+all\s+(three|3|cli)",
    r"(?i)quintessence\s+benchmark\s+(suite|all|test)",
    r"(?i)compare\s+all\s+(three|3)\s+(cli|runtime|model)",
    r"(?i)run\s+(the\s+)?real\s+benchmark",
    r"(?i)test\s+all\s+(three|3)\s+(cli|runtime|model)",
    r"(?i)full\s+cli\s+benchmark",
    r"(?i)benchmark\s+claude.*codex.*gemini",
    r"(?i)pitch\s+deck\s+benchmark",
]


def is_benchmark_suite_trigger(message: str) -> bool:
    """Check if a user message is requesting the full benchmark suite."""
    for pattern in _SUITE_TRIGGER_PATTERNS:
        if re.search(pattern, message):
            return True
    return False


# ── Intelligence Benchmark (Pipeline ON vs OFF) ─────────────
# This is the REAL proof: same model, raw vs Daena pipeline.
# Shows the intelligence delta that Daena's architecture adds.

_INTELLIGENCE_TRIGGER_PATTERNS = [
    r"(?i)run\s+(the\s+)?(intelligence|pipeline|daena)\s+benchmark",
    r"(?i)prove\s+daena\s+is\s+smart",
    r"(?i)pipeline\s+on\s+vs\s+off",
    r"(?i)run\s+(the\s+)?aime\s+benchmark",
    r"(?i)run\s+(the\s+)?truthfulqa",
    r"(?i)intelligence\s+proof",
    r"(?i)benchmark\s+(the\s+)?pipeline",
    r"(?i)test\s+(the\s+)?pipeline\s+(intelligence|power|strength)",
    r"(?i)show\s+(the\s+)?intelligence\s+delta",
    r"(?i)raw\s+vs\s+pipeline",
    r"(?i)daena\s+intelligence\s+test",
    r"(?i)run\s+.*quintessence.*intelligence",
]


def is_intelligence_benchmark_trigger(message: str) -> bool:
    """Check if a user message is requesting pipeline ON vs OFF benchmark."""
    for pattern in _INTELLIGENCE_TRIGGER_PATTERNS:
        if re.search(pattern, message):
            return True
    return False


async def run_intelligence_benchmark_streaming(
    registry: Any,
    *,
    benchmarks: list[str] | None = None,
    think_mode: bool = True,
    full_power: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Run pipeline ON vs OFF benchmark with streaming SSE events.

    This is the pitch deck proof: shows that Daena's Laevateinn
    pipeline makes ANY model measurably smarter. Runs AIME, TruthfulQA,
    and GSM-Symbolic through raw inference and the full pipeline,
    comparing accuracy.

    Args:
        registry: ModelRegistry instance for LLM calls.
        benchmarks: Which suites to run. Defaults to all three.
        think_mode: Enable chain-of-thought reasoning.
        full_power: Enable all pipeline stages + search fallback.

    Yields:
        SSE events for each question and final scorecard.
    """
    from app.services.benchmarks.real_benchmarks import (
        BenchmarkType,
        RealBenchmarkRunner,
    )

    start = time.monotonic()
    runner = RealBenchmarkRunner(registry=registry)

    # All real-world benchmarks the industry uses
    _suite_map = {
        "aime": BenchmarkType.AIME,
        "truthfulqa": BenchmarkType.TRUTHFULQA,
        "gsm_symbolic": BenchmarkType.GSM_SYMBOLIC,
        "gpqa_diamond": BenchmarkType.GPQA_DIAMOND,
        "halueval": BenchmarkType.HALUEVAL,
        "mmlu_pro": BenchmarkType.MMLU_PRO,
    }
    # Default: all benchmarks with real datasets
    # GPQA-Diamond: sample 30 (full 198 would take hours)
    # MMLU-Pro: sample 30 from STEM (full 5878 would take days)
    # Others: all questions (small enough to run fully)
    suites_to_run = benchmarks or [
        "aime", "truthfulqa", "gsm_symbolic", "gpqa_diamond", "halueval",
        "mmlu_pro",
    ]
    # Sample sizes for large datasets (None = all questions)
    _sample_sizes = {
        "gpqa_diamond": 30,
        "mmlu_pro": 30,
    }

    yield {
        "type": "thinking",
        "stage": "intelligence_benchmark_starting",
        "suites": suites_to_run,
        "think_mode": think_mode,
        "full_power": full_power,
    }

    all_results = {}

    for suite_name in suites_to_run:
        bench_type = _suite_map.get(suite_name)
        if not bench_type:
            continue

        _sample = _sample_sizes.get(suite_name)
        questions = runner.load_questions(bench_type, sample=_sample)
        if not questions:
            continue

        yield {
            "type": "thinking",
            "stage": "intelligence_suite_starting",
            "suite": suite_name,
            "questions": len(questions),
        }

        # Select the best available model for the benchmark.
        # Prefer CLI providers (Claude Code > Codex > Gemini) over Ollama
        # because local Ollama models may not have enough RAM for the
        # Laevateinn pipeline's cognitive stages.
        _best_model = "mistral:7b"  # safe Ollama fallback
        try:
            from app.services.model_router import ModelRouter
            _router = ModelRouter(registry)
            _best = _router.select_best_single()
            _best_model = _best.model_id
            logger.info(
                "intelligence_benchmark.model_selected",
                model=_best_model,
                provider=_best.provider.value,
            )
        except Exception:
            pass

        # Run each question individually with progress streaming.
        # This keeps the SSE connection alive (avoids timeout)
        # and lets the user see real-time progress.
        raw_correct = 0
        pipe_correct = 0
        raw_results = []
        pipe_results = []

        for qi, q in enumerate(questions, 1):
            yield {
                "type": "thinking",
                "stage": "intelligence_question_starting",
                "suite": suite_name,
                "question_num": qi,
                "total": len(questions),
                "question_id": q.id,
                "category": q.category,
            }

            # Raw inference
            raw_resp = await runner._run_raw(q, _best_model)
            raw_results.append(raw_resp)
            if raw_resp.correct:
                raw_correct += 1

            # Pipeline inference
            pipe_resp = await runner._run_pipeline(
                q, _best_model, [_best_model],
                think_mode=think_mode,
                search_fallback=full_power,
            )
            pipe_results.append(pipe_resp)
            if pipe_resp.correct:
                pipe_correct += 1

            yield {
                "type": "thinking",
                "stage": "intelligence_question_completed",
                "suite": suite_name,
                "question_num": qi,
                "total": len(questions),
                "question_id": q.id,
                "raw_correct": raw_resp.correct,
                "pipe_correct": pipe_resp.correct,
                "raw_time_ms": raw_resp.latency_ms,
                "pipe_time_ms": pipe_resp.latency_ms,
                "running_raw": f"{raw_correct}/{qi}",
                "running_pipe": f"{pipe_correct}/{qi}",
            }

        # Build suite result
        from app.services.benchmarks.real_benchmarks import BenchmarkSuiteResult
        result = BenchmarkSuiteResult(
            benchmark=bench_type,
            model_id=_best_model,
            status="complete",
            total_questions=len(questions),
            raw_correct=raw_correct,
            pipeline_correct=pipe_correct,
            raw_results=raw_results,
            pipeline_results=pipe_results,
        )
        result.raw_accuracy = raw_correct / len(questions) if questions else 0
        result.pipeline_accuracy = pipe_correct / len(questions) if questions else 0
        result.delta = result.pipeline_accuracy - result.raw_accuracy
        result.per_category = runner._category_breakdown(
            questions, raw_results, pipe_results,
        )

        all_results[suite_name] = result

        yield {
            "type": "thinking",
            "stage": "intelligence_suite_completed",
            "suite": suite_name,
            "model": _best_model,
            "raw_accuracy": f"{result.raw_accuracy:.1%}",
            "pipeline_accuracy": f"{result.pipeline_accuracy:.1%}",
            "delta": f"+{result.delta:.1%}",
            "questions": result.total_questions,
            "raw_correct": result.raw_correct,
            "pipeline_correct": result.pipeline_correct,
        }

    total_ms = int((time.monotonic() - start) * 1000)

    # Build the final report
    synthesis = _build_intelligence_report(all_results, total_ms)

    # Yield scorecard
    yield {
        "type": "thinking",
        "stage": "intelligence_benchmark_scorecard",
        "suites_run": len(all_results),
        "total_ms": total_ms,
        "results": {
            name: {
                "raw": f"{r.raw_accuracy:.1%}",
                "pipeline": f"{r.pipeline_accuracy:.1%}",
                "delta": f"+{r.delta:.1%}",
            }
            for name, r in all_results.items()
        },
    }

    # Stream the synthesis
    chunk_size = 12
    for i in range(0, len(synthesis), chunk_size):
        yield {"type": "chunk", "content": synthesis[i:i + chunk_size]}

    yield {
        "type": "thinking",
        "stage": "intelligence_benchmark_completed",
        "total_ms": total_ms,
    }


def _build_intelligence_report(
    results: dict[str, Any],
    total_ms: int,
) -> str:
    """Build the intelligence benchmark report."""
    parts = []
    parts.append("# Daena Intelligence Proof\n")
    parts.append(
        "**Raw model inference vs Daena's Quintessence pipeline.** "
        "Same model, same questions. The delta is the intelligence "
        "Daena's architecture adds.\n"
    )

    # Overall table
    parts.append("\n## Results\n")
    parts.append("| Benchmark | Questions | Raw | Pipeline | Delta |")
    parts.append("|-----------|-----------|-----|----------|-------|")

    total_raw = 0
    total_pipe = 0
    total_q = 0

    for name, result in results.items():
        raw_pct = f"{result.raw_accuracy:.1%}"
        pipe_pct = f"{result.pipeline_accuracy:.1%}"
        delta = result.delta
        delta_str = f"+{delta:.1%}" if delta >= 0 else f"{delta:.1%}"
        parts.append(
            f"| {name.upper()} | {result.total_questions} | "
            f"{raw_pct} ({result.raw_correct}/{result.total_questions}) | "
            f"**{pipe_pct}** ({result.pipeline_correct}/{result.total_questions}) | "
            f"**{delta_str}** |"
        )
        total_raw += result.raw_correct
        total_pipe += result.pipeline_correct
        total_q += result.total_questions

    if total_q > 0:
        overall_raw = total_raw / total_q
        overall_pipe = total_pipe / total_q
        overall_delta = overall_pipe - overall_raw
        parts.append(
            f"| **TOTAL** | {total_q} | "
            f"{overall_raw:.1%} ({total_raw}/{total_q}) | "
            f"**{overall_pipe:.1%}** ({total_pipe}/{total_q}) | "
            f"**+{overall_delta:.1%}** |"
        )

    # Category breakdowns
    for name, result in results.items():
        if result.per_category:
            parts.append(f"\n### {name.upper()} Category Breakdown\n")
            parts.append("| Category | Raw | Pipeline | Delta |")
            parts.append("|----------|-----|----------|-------|")
            for cat, scores in result.per_category.items():
                raw_s = f"{scores.get('raw', 0):.0%}"
                pipe_s = f"{scores.get('pipeline', 0):.0%}"
                d = scores.get("pipeline", 0) - scores.get("raw", 0)
                d_str = f"+{d:.0%}" if d >= 0 else f"{d:.0%}"
                parts.append(f"| {cat} | {raw_s} | {pipe_s} | {d_str} |")

    # Per-question details
    for name, result in results.items():
        parts.append(f"\n### {name.upper()} Per-Question\n")
        for raw, pipe in zip(result.raw_results, result.pipeline_results):
            raw_status = "CORRECT" if raw.correct else "WRONG"
            pipe_status = "CORRECT" if pipe.correct else "WRONG"
            parts.append(
                f"**{raw.question_id}**: Raw={raw_status} ({raw.latency_ms:,}ms) | "
                f"Pipeline={pipe_status} ({pipe.latency_ms:,}ms, {pipe.pipeline_stages_used} stages)"
            )

    parts.append(f"\n---\n**Total time:** {total_ms / 1000:.1f}s")
    parts.append(
        "\n*Pipeline: Laevateinn 21-stage + Quintessence council + "
        "Think mode + Search fallback*"
    )

    return "\n".join(parts)
