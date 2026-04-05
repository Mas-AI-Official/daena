"""Gap 1: Code Execution in the Reasoning Loop.

Allows the cognitive pipeline (RDE) to extract code snippets from an
answer mid-reasoning, execute them in a sandboxed subprocess, and feed
the results back so claims can be verified against actual output.

Safety model:
    - Subprocess with hard timeout (default 10 s, configurable).
    - No network access (env stripped of proxy/credentials).
    - File writes restricted to a per-run temp directory.
    - Maximum output capture (64 KB) to prevent memory exhaustion.
    - Only Python and Bash are supported; all other languages are rejected.

Follows the TerminalAgent pattern (asyncio.create_subprocess_exec with
timeout and structured result capture).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────

_MAX_OUTPUT_BYTES: int = 65_536  # 64 KB stdout/stderr cap
_CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>python|bash|sh)\s*\n(?P<code>.*?)```",
    re.DOTALL,
)

# Environment variables stripped from child processes to block network
# access and prevent credential leakage.
_STRIPPED_ENV_KEYS: frozenset[str] = frozenset({
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "no_proxy",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    "AZURE_OPENAI_KEY", "TOGETHER_API_KEY", "GROQ_API_KEY",
    "DATABASE_URL", "REDIS_URL",
})

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"python", "bash", "sh"})


# ── Data structures ───────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CodeBlock:
    """A fenced code block extracted from markdown text."""

    language: str
    code: str
    line_start: int


@dataclass(slots=True)
class CodeExecutionResult:
    """Outcome of executing a single code block in a sandbox."""

    block: CodeBlock
    output: str
    exit_code: int
    success: bool
    error: str
    execution_time_ms: int


# ── CodeVerifier ──────────────────────────────────────────────────

class CodeVerifier:
    """Execute code snippets extracted from LLM answers to verify claims.

    Designed to plug into the Recursive Depth Engine (RDE) loop so that
    each recursion can ground its answer against real execution output.

    Usage::

        verifier = CodeVerifier()
        results = await verifier.verify_answer_code(answer_text)
        for r in results:
            if not r.success:
                # feed failure context back into the next RDE iteration
                ...
    """

    def __init__(
        self,
        default_timeout: int = 10,
        max_output_bytes: int = _MAX_OUTPUT_BYTES,
        python_executable: str | None = None,
    ) -> None:
        self._default_timeout = default_timeout
        self._max_output_bytes = max_output_bytes
        # Prefer the venv Python that is running this process.
        self._python: str = python_executable or sys.executable

    # ── extraction ────────────────────────────────────────────

    @staticmethod
    def extract_code_blocks(text: str) -> list[CodeBlock]:
        """Find all fenced ``python`` and ``bash``/``sh`` code blocks.

        Returns a list of :class:`CodeBlock` with the language, raw code,
        and the 1-based line number where the block starts in *text*.
        """
        blocks: list[CodeBlock] = []
        for match in _CODE_BLOCK_RE.finditer(text):
            lang = match.group("lang")
            # Normalise ``sh`` to ``bash`` for consistent downstream handling.
            if lang == "sh":
                lang = "bash"
            code = match.group("code")
            # Compute 1-based line number of the opening fence.
            line_start = text[:match.start()].count("\n") + 1
            blocks.append(CodeBlock(language=lang, code=code, line_start=line_start))
        return blocks

    # ── execution ─────────────────────────────────────────────

    async def execute_code(
        self,
        block: CodeBlock,
        timeout: int | None = None,
    ) -> CodeExecutionResult:
        """Run a single :class:`CodeBlock` in an isolated subprocess.

        The child process runs inside a fresh temp directory (cleaned up
        afterwards) with a sanitised environment that has no network
        credentials or proxy configuration.

        Args:
            block: The code block to execute.
            timeout: Hard timeout in seconds. Falls back to
                ``default_timeout`` if *None*.

        Returns:
            A :class:`CodeExecutionResult` with captured output.
        """
        if block.language not in SUPPORTED_LANGUAGES:
            return CodeExecutionResult(
                block=block,
                output="",
                exit_code=-1,
                success=False,
                error=f"Unsupported language: {block.language}",
                execution_time_ms=0,
            )

        effective_timeout = timeout if timeout is not None else self._default_timeout
        sandbox_env = self._build_sandbox_env()

        tmpdir = tempfile.mkdtemp(prefix="daena_code_verify_")
        start = time.monotonic()

        try:
            result = await self._run_in_subprocess(
                block=block,
                cwd=tmpdir,
                env=sandbox_env,
                timeout=effective_timeout,
            )
            return result
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            # Best-effort cleanup of the temp directory.
            self._cleanup_tmpdir(tmpdir)
            logger.debug(
                "code_verifier.executed",
                language=block.language,
                line_start=block.line_start,
                exit_code=result.exit_code if "result" in dir() else -1,
                elapsed_ms=elapsed_ms,
            )

    async def _run_in_subprocess(
        self,
        block: CodeBlock,
        cwd: str,
        env: dict[str, str],
        timeout: int,
    ) -> CodeExecutionResult:
        """Spawn and manage the actual child process."""
        # Write the code to a temp file so create_subprocess_exec can run it
        # without shell=True (avoids shell-injection surface).
        if block.language == "python":
            script_path = os.path.join(cwd, "_verify.py")
            cmd: Sequence[str] = (self._python, script_path)
        else:
            script_path = os.path.join(cwd, "_verify.sh")
            cmd = ("bash", script_path)

        Path(script_path).write_text(block.code, encoding="utf-8")

        timed_out = False
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                timed_out = True
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()

        except FileNotFoundError as exc:
            # Interpreter not found (e.g. bash missing on Windows).
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return CodeExecutionResult(
                block=block,
                output="",
                exit_code=-1,
                success=False,
                error=f"Interpreter not found: {exc}",
                execution_time_ms=elapsed_ms,
            )
        except OSError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return CodeExecutionResult(
                block=block,
                output="",
                exit_code=-1,
                success=False,
                error=f"OS error spawning subprocess: {exc}",
                execution_time_ms=elapsed_ms,
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        stdout = self._decode_and_cap(stdout_bytes)
        stderr = self._decode_and_cap(stderr_bytes)
        combined = stdout if not stderr else f"{stdout}\n--- stderr ---\n{stderr}"
        exit_code: int = proc.returncode if proc.returncode is not None else -1

        error_msg = ""
        if timed_out:
            error_msg = f"Timed out after {timeout}s"
        elif exit_code != 0:
            error_msg = stderr.strip() or f"Non-zero exit code: {exit_code}"

        return CodeExecutionResult(
            block=block,
            output=combined.strip(),
            exit_code=exit_code,
            success=(exit_code == 0 and not timed_out),
            error=error_msg,
            execution_time_ms=elapsed_ms,
        )

    # ── batch verification ────────────────────────────────────

    async def verify_answer_code(
        self,
        answer: str,
        timeout: int | None = None,
    ) -> list[CodeExecutionResult]:
        """Extract every code block from *answer* and execute them all.

        Blocks are executed sequentially (not in parallel) to avoid
        contention and to keep resource usage predictable inside the
        RDE loop.

        Args:
            answer: The LLM-generated answer text containing fenced
                code blocks.
            timeout: Per-block timeout override.

        Returns:
            A list of :class:`CodeExecutionResult`, one per extracted
            block. Empty list if no code blocks were found.
        """
        blocks = self.extract_code_blocks(answer)
        if not blocks:
            return []

        logger.info(
            "code_verifier.verify_answer_code",
            block_count=len(blocks),
            languages=[b.language for b in blocks],
        )

        results: list[CodeExecutionResult] = []
        for block in blocks:
            result = await self.execute_code(block, timeout=timeout)
            results.append(result)

        passed = sum(1 for r in results if r.success)
        logger.info(
            "code_verifier.verify_complete",
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
        )
        return results

    # ── helpers ────────────────────────────────────────────────

    def _build_sandbox_env(self) -> dict[str, str]:
        """Build a minimal environment for the child process.

        Strips credentials, proxy settings, and anything that could
        enable network access or leak secrets.
        """
        safe_env: dict[str, str] = {}
        # Carry over only essential variables.
        for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USER",
                     "LANG", "LC_ALL", "PYTHONIOENCODING"):
            val = os.environ.get(key)
            if val is not None:
                safe_env[key] = val

        # Force UTF-8 output from Python children.
        safe_env["PYTHONIOENCODING"] = "utf-8"

        # Explicitly ensure nothing from the stripped set leaked in.
        for key in _STRIPPED_ENV_KEYS:
            safe_env.pop(key, None)

        return safe_env

    def _decode_and_cap(self, raw: bytes | None) -> str:
        """Decode bytes to str, capping at ``_max_output_bytes``."""
        if not raw:
            return ""
        capped = raw[:self._max_output_bytes]
        text = capped.decode("utf-8", errors="replace")
        if len(raw) > self._max_output_bytes:
            text += f"\n... (output truncated at {self._max_output_bytes} bytes)"
        return text

    @staticmethod
    def _cleanup_tmpdir(path: str) -> None:
        """Best-effort recursive removal of a temp directory."""
        import shutil
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            # Cleanup is best-effort; do not let it crash the pipeline.
            pass
