"""QA/QC verification capability for Daena (the ai-qa-loop adapter).

Public surface:
    run_qa_loop(base_url, ...)   -> QaResult        run the deterministic verification loop
    run_selftest()               -> QaResult        health-check the capability (zero tokens)
    engine_available()           -> bool            is the engine runnable on this host?
    build_qa_tool_definition()   -> ToolDefinition  the TLM catalog entry
    register_qa_tool(registry)   -> bool            idempotently register into a TLM registry
"""
from __future__ import annotations

from app.services.qa.qa_loop_adapter import (
    QA_TOOL_ID,
    QaResult,
    build_qa_tool_definition,
    engine_available,
    engine_dir,
    register_qa_tool,
    run_qa_loop,
    run_selftest,
)

__all__ = [
    "QA_TOOL_ID",
    "QaResult",
    "build_qa_tool_definition",
    "engine_available",
    "engine_dir",
    "register_qa_tool",
    "run_qa_loop",
    "run_selftest",
]
