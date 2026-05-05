"""ScrapeGraphAI service -- spawns the worker and parses its output.

PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05).

Boundary contract with the worker:
  Input (stdin): UTF-8 JSON with keys ``url`` (str), ``goal`` (str),
    ``max_chars`` (int), ``llm`` (dict) -- the whole config.
  Output (stdout): UTF-8 JSON with keys ``success`` (bool),
    ``result`` (str), ``error`` (str|None), ``truncated`` (bool),
    ``worker_version`` (str).
  Exit code: 0 on success, non-zero on failure.

The worker has zero credentials of its own. The parent reads
``OPENAI_API_KEY`` (or routes to Ollama) and passes only the LLM
config the worker needs. Any value with shape ``sk-*`` / ``Bearer *``
in the worker's stdout is rejected at parse time -- defense-in-depth.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.connection_v2.url_safety import is_public_url_safe

logger = get_logger(__name__)


# ── Boundaries ────────────────────────────────────────────────────


# Default character cap on the worker's output. The API layer can
# request a smaller value but never larger.
DEFAULT_MAX_CHARS: int = 8000

# Hard upper bound regardless of caller request. Keeps the audit row
# small and bounds memory.
ABSOLUTE_MAX_CHARS: int = 32000

# Hard timeout per scrape call. ScrapeGraphAI walks DOM + LLM extract
# which can be slow but anything beyond this is a stuck worker.
SCRAPE_TIMEOUT_SECONDS: float = 60.0


# Path to the canonical Daena venv that owns the scrapegraphai dep.
# Override via ``DAENA_SCRAPE_VENV_PYTHON`` for tests / non-Windows
# operators / CI.
DEFAULT_VENV_PYTHON = (
    Path("D:/Ideas/Daena/venv_daena/Scripts/python.exe")
    if os.name == "nt"
    else Path("D:/Ideas/Daena/venv_daena/bin/python")
)


# Path to the worker module (lives in this directory). The worker is
# imported by name (``-m``) so the venv resolves it through PYTHONPATH.
WORKER_MODULE_PATH = (
    Path(__file__).resolve().parent / "worker.py"
)


# ── Public types ──────────────────────────────────────────────────


class ScrapeError(Exception):
    """Operator-safe error -- the message is OK to surface in API
    responses. Never carries a token / secret. Specific failure modes
    are pinned with stable prefixes so the UI / audit row can match."""


@dataclass
class ExtractResult:
    """Outcome shape of a successful extract call.

    The ``result`` field carries the worker's extracted text up to
    ``max_chars``. ``truncated`` is True when the worker's output
    exceeded the cap.
    """
    success: bool
    result: str
    truncated: bool = False
    error: str | None = None
    worker_version: str = "?"
    meta: dict[str, Any] = field(default_factory=dict)


# ── Public API ────────────────────────────────────────────────────


async def extract_from_url(
    url: str,
    goal: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    venv_python: Path | None = None,
) -> ExtractResult:
    """Extract content from ``url`` matching ``goal`` via scrapegraphai.

    Arguments:
      url: target URL. Must pass ``is_public_url_safe`` first; we
        refuse loopback / private / link-local / reserved / internal-DNS
        + non-http(s) schemes.
      goal: natural-language extraction prompt fed to the LLM. The
        scrapegraphai library combines this with the rendered page.
      max_chars: cap on the returned text. Cannot exceed
        ``ABSOLUTE_MAX_CHARS``.
      venv_python: override the worker's Python interpreter (tests).

    Behaviour on the safety guard rejecting:
      raises ``ScrapeError("url_safety:<reason>")``.

    Behaviour on worker timeout / non-zero exit:
      returns ``ExtractResult(success=False, error="worker_timeout"/...)``
      so the caller can surface a structured failure without the
      stack trace.
    """
    if not isinstance(url, str) or not url.strip():
        raise ScrapeError("url_safety:url_invalid")
    if not isinstance(goal, str) or not goal.strip():
        raise ScrapeError("goal_required")
    ok, reason = is_public_url_safe(url)
    if not ok:
        raise ScrapeError(f"url_safety:{reason}")

    cap = max(1, min(int(max_chars or DEFAULT_MAX_CHARS), ABSOLUTE_MAX_CHARS))

    py_exe = venv_python or _resolve_venv_python()
    if not py_exe.is_file():
        raise ScrapeError(
            f"scrape_venv_missing: expected python at {py_exe}"
        )

    payload = {
        "url": url.strip(),
        "goal": goal.strip(),
        "max_chars": cap,
        "llm": _build_llm_config(),
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            str(py_exe),
            str(WORKER_MODULE_PATH),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Inherit env so OLLAMA_BASE_URL / OPENAI_API_KEY reach
            # the worker. We do NOT log env values here.
        )
    except OSError as exc:
        raise ScrapeError(f"scrape_spawn_failed: {exc}") from exc

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(json.dumps(payload).encode("utf-8")),
            timeout=SCRAPE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ExtractResult(
            success=False,
            result="",
            error="worker_timeout",
            meta={"timeout_seconds": SCRAPE_TIMEOUT_SECONDS},
        )

    return _parse_worker_output(
        proc.returncode or 0, stdout_bytes, stderr_bytes, cap=cap,
    )


# ── Internals ─────────────────────────────────────────────────────


def _resolve_venv_python() -> Path:
    override = os.environ.get("DAENA_SCRAPE_VENV_PYTHON")
    if override:
        return Path(override)
    return DEFAULT_VENV_PYTHON


def _build_llm_config() -> dict[str, Any]:
    """Build the LLM block scrapegraphai needs.

    Default route: Ollama (no key, local). Fallback to OpenAI if the
    operator has set ``OPENAI_API_KEY`` AND ``DAENA_SCRAPE_LLM`` to
    ``openai``. We default to Ollama because the brief explicitly
    forbids relying on paid APIs for the local beta.
    """
    selector = (os.environ.get("DAENA_SCRAPE_LLM") or "ollama").lower().strip()
    if selector == "openai" and os.environ.get("OPENAI_API_KEY"):
        return {
            "provider": "openai",
            "model": os.environ.get("DAENA_SCRAPE_OPENAI_MODEL")
                     or "openai/gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "temperature": 0,
        }
    # Default: Ollama local. The worker pulls ollama via langchain.
    return {
        "provider": "ollama",
        "model": os.environ.get("DAENA_SCRAPE_OLLAMA_MODEL")
                 or "ollama/llama3.1:latest",
        "base_url": os.environ.get("OLLAMA_BASE_URL")
                    or "http://127.0.0.1:11434",
        "temperature": 0,
    }


def _parse_worker_output(
    returncode: int,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    *,
    cap: int,
) -> ExtractResult:
    if returncode != 0:
        # Worker failed before producing valid JSON. We surface a
        # short generic message; the operator's audit row pins
        # returncode + a stderr prefix capped at 200 chars (the rest
        # stays inside the parent's logger).
        stderr_head = (stderr_bytes or b"").decode("utf-8", errors="replace")[:200]
        logger.warning(
            "scrape.worker_nonzero_exit",
            returncode=returncode,
            stderr_head=stderr_head[:120],
        )
        return ExtractResult(
            success=False,
            result="",
            error=f"worker_failed:exit{returncode}",
            meta={"stderr_head": stderr_head[:200]},
        )

    try:
        payload = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return ExtractResult(
            success=False,
            result="",
            error=f"worker_bad_output:{type(exc).__name__}",
        )

    if not isinstance(payload, dict):
        return ExtractResult(
            success=False, result="",
            error="worker_bad_output:not_dict",
        )

    raw = payload.get("result") or ""
    if not isinstance(raw, str):
        # Worker returned structured data; flatten to JSON string.
        raw = json.dumps(raw, ensure_ascii=False)

    # Defense-in-depth: refuse anything token-shaped.
    for forbidden in ("sk-", "Bearer ", "ya29.", "1//0e"):
        if forbidden in raw:
            return ExtractResult(
                success=False, result="",
                error="worker_bad_output:credential_shape",
            )

    truncated_by_parent = False
    if len(raw) > cap:
        raw = raw[:cap]
        truncated_by_parent = True

    return ExtractResult(
        success=bool(payload.get("success", True)),
        result=raw,
        truncated=bool(payload.get("truncated") or truncated_by_parent),
        error=(
            payload.get("error") if isinstance(payload.get("error"), str) else None
        ),
        worker_version=str(payload.get("worker_version") or "?"),
        meta={"returncode": returncode},
    )
