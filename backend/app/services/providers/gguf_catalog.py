"""Catalog of GGUF models available to llama.cpp llama-server.

Static registry of the models Daena can route to on the local worker.
One model is loaded at a time; ``LlamaServerManager`` swaps when a
different one is requested. The tags feed into ``model_router`` so
task-class-based routing picks the right GGUF automatically
(code task -> coder, general -> qwen3-8b, cheap summarization -> gemma).

Models live under ``D:\\Ideas\\MODELS_ROOT\\gguf\\<model>\\*.gguf``.
This catalog is the single source of truth; adding a new GGUF means
adding an entry here plus dropping the file under MODELS_ROOT.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# MODELS_ROOT is on the Windows side; WSL backend accesses via
# /mnt/d/... transparently via the WSL drvfs bridge. Keep as raw
# Windows path for log readability -- resolve() converts when needed.
_MODELS_ROOT = Path(r"D:\Ideas\MODELS_ROOT\gguf")


@dataclass(frozen=True)
class GGUFModel:
    """A GGUF model entry.

    ``key`` is the internal identifier used in launcher flags (``-Model``
    in ``start-llama-server.ps1``) and in routing decisions.

    ``served_name`` is what llama-server advertises via
    ``GET /v1/models``. When we probe the running server we match on
    this value to decide "is the right model loaded?"

    ``tags`` feed the model router's priority-tag boost. Matching tags
    = the router picks this model for the task class.
    """

    key: str                    # "qwen3-8b" | "coder" | "gemma"
    display_name: str           # Human label for UI + logs
    file_path: Path             # Absolute path to .gguf file
    served_name: str            # What llama-server reports via /v1/models
    context_length: int         # Max ctx in tokens (-c flag)
    size_category: str          # "small" | "medium" | "large" -- VRAM hint
    tags: frozenset[str] = field(default_factory=frozenset)
    cost_per_1m_input_usd: float = 0.0    # Local = free
    cost_per_1m_output_usd: float = 0.0   # Local = free


# ---------------------------------------------------------------------------
# Catalog (all 3 models currently on disk)
# ---------------------------------------------------------------------------

CATALOG: dict[str, GGUFModel] = {
    "qwen3-8b": GGUFModel(
        key="qwen3-8b",
        display_name="Qwen3 8B (Q4_K_M)",
        file_path=_MODELS_ROOT / "qwen3-8b" / "Qwen3-8B-Q4_K_M.gguf",
        # llama-server derives served_name from the file basename;
        # we match the prefix so Q4_K_M vs Q5_K_M doesn't break lookup.
        served_name="qwen3-8b",
        context_length=16384,
        size_category="small",
        tags=frozenset({"general", "reasoning", "local", "fallback"}),
    ),
    "coder": GGUFModel(
        key="coder",
        display_name="Qwen3 Coder 30B-A3B (Q4_K_M)",
        file_path=_MODELS_ROOT
        / "qwen3-coder-30b-a3b"
        / "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
        served_name="qwen3-coder-30b-a3b",
        context_length=16384,
        size_category="large",
        tags=frozenset(
            {"coding", "refactor", "reasoning", "local", "fallback"}
        ),
    ),
    "gemma": GGUFModel(
        key="gemma",
        display_name="Gemma 4 E4B IT (Q4_K_M)",
        file_path=_MODELS_ROOT / "gemma-4-e4b" / "gemma-4-E4B-it-Q4_K_M.gguf",
        served_name="gemma-4-e4b",
        context_length=8192,
        size_category="small",
        tags=frozenset(
            {"general", "summarization", "lightweight", "local", "fallback"}
        ),
    ),
}


# Default model when no specific request is made. Matches the default
# in ``start-llama-server.ps1``.
DEFAULT_KEY: str = "qwen3-8b"


def get_model(key: str) -> GGUFModel | None:
    """Lookup by key. Returns None when the key is unknown."""
    return CATALOG.get(key.lower())


def find_by_served_name(served_name: str) -> GGUFModel | None:
    """Reverse lookup from llama-server's /v1/models advertised name.

    llama-server's model-id derivation varies between versions; we
    match by substring to tolerate ``Qwen3-8B-Q4_K_M``,
    ``qwen3-8b``, or ``Qwen3-8B-Instruct`` all resolving to the
    same catalog entry.
    """
    if not served_name:
        return None
    needle = served_name.lower()
    for entry in CATALOG.values():
        if entry.served_name.lower() in needle or needle in entry.served_name.lower():
            return entry
    return None


def pick_for_task(
    task_tags: frozenset[str] | set[str] | None = None,
) -> GGUFModel:
    """Pick the best GGUF for a task class.

    Matching rules (first hit wins):
        * task tags include "coding" or "refactor"   -> coder
        * task tags include "summarization"          -> gemma (cheap)
        * anything else                              -> qwen3-8b (default)

    Returns a catalog entry guaranteed to exist. The caller still has
    to ensure the model is actually loaded on llama-server via
    ``LlamaServerManager.ensure_loaded``.
    """
    if not task_tags:
        return CATALOG[DEFAULT_KEY]
    t = {str(x).lower() for x in task_tags}
    if t & {"coding", "refactor", "code", "diff", "bulk_refactor"}:
        return CATALOG["coder"]
    if t & {"summarization", "summarize", "compress"}:
        return CATALOG["gemma"]
    return CATALOG[DEFAULT_KEY]


def list_all() -> list[GGUFModel]:
    return list(CATALOG.values())
