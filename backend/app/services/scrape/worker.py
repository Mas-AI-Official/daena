"""ScrapeGraphAI worker -- runs in D:\\Ideas\\Daena\\venv_daena.

PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05).

Standalone script. Reads a JSON payload from stdin, performs ONE
scrapegraphai extraction, writes a JSON result to stdout, exits.

Hard rules:
  * No network egress beyond the URL the parent specified.
  * No login / form submission -- uses ``SmartScraperGraph`` only.
  * Output capped at the parent-supplied ``max_chars``.
  * Never echoes the LLM API key (or any env value) to stdout / stderr.
  * Returns a stable JSON shape so the parent can parse without
    string regex.

The parent (backend ``scrape.service``) enforces a 60-second timeout
on this process. The worker itself does not enforce its own deadline
-- the OS kills it.
"""

from __future__ import annotations

import json
import sys
import traceback


WORKER_VERSION = "1.0.0"


def _emit(payload: dict) -> None:
    """Write a JSON envelope to stdout in one go."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def _fail(reason: str, *, detail: str = "") -> None:
    _emit({
        "success": False,
        "result": "",
        "error": reason,
        "detail": detail,
        "truncated": False,
        "worker_version": WORKER_VERSION,
    })
    sys.exit(0)  # exit cleanly so the parent reads stdout


def _read_request() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        _fail("worker_input_empty")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"worker_input_invalid_json:{exc.msg}")
    return {}  # unreachable


def _build_scrapegraph_config(llm_block: dict) -> dict:
    """Translate the parent's llm spec into scrapegraphai config.

    The parent always picks Ollama by default -- no API key needed.
    We never log the env-resolved key value here; we read it lazily
    inside the dict scrapegraphai consumes.
    """
    provider = (llm_block.get("provider") or "ollama").lower()
    model = llm_block.get("model") or "ollama/llama3.1:latest"
    cfg: dict = {
        "llm": {
            "model": model,
            "temperature": float(llm_block.get("temperature") or 0),
        },
        # Hide the scrapegraphai banner + verbose prints. The library
        # would otherwise spam stdout with progress, breaking JSON
        # parsing on the parent.
        "verbose": False,
        "headless": True,
    }
    if provider == "openai":
        import os
        env_name = llm_block.get("api_key_env") or "OPENAI_API_KEY"
        api_key = os.environ.get(env_name) or ""
        if not api_key:
            _fail("worker_llm_key_missing", detail=f"env {env_name} empty")
        cfg["llm"]["api_key"] = api_key
    else:
        # Ollama -- pass base_url through so non-default ports work.
        base_url = llm_block.get("base_url") or "http://127.0.0.1:11434"
        cfg["llm"]["base_url"] = base_url
    return cfg


def main() -> None:
    req = _read_request()
    url = (req.get("url") or "").strip()
    goal = (req.get("goal") or "").strip()
    max_chars = int(req.get("max_chars") or 8000)
    llm_block = req.get("llm") or {}

    if not url or not goal:
        _fail("worker_input_required_fields_missing")

    try:
        # Late imports so failures here surface as a stable error code
        # instead of a Python ImportError at module load.
        from scrapegraphai.graphs import SmartScraperGraph
    except Exception as exc:
        _fail(
            "worker_import_failed",
            detail=f"{type(exc).__name__}: {str(exc)[:200]}",
        )
        return

    try:
        cfg = _build_scrapegraph_config(llm_block)
        graph = SmartScraperGraph(prompt=goal, source=url, config=cfg)
        result = graph.run()
    except Exception as exc:
        # Anything from network / parsing / LLM fails here.
        tb_head = "".join(
            traceback.format_exception_only(type(exc), exc)
        )[:200]
        _fail("worker_extract_failed", detail=tb_head)
        return

    # Normalize the result to a string. scrapegraphai may return a dict;
    # we serialize so the parent gets a stable shape.
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result)

    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    _emit({
        "success": True,
        "result": text,
        "error": None,
        "truncated": truncated,
        "worker_version": WORKER_VERSION,
    })


if __name__ == "__main__":
    main()
