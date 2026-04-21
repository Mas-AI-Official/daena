"""Tests for LlamaServerManager lifecycle + GGUF catalog.

Focus areas:
    * Catalog: key lookup, served-name reverse, task-class dispatch
    * Manager mode parsing from env
    * PID-file coordination: RESPECT_EXTERNAL refuses to kill unknown
    * Mutex: two concurrent ensure_loaded calls resolve serialized
    * Cooldown: rapid re-swap within window is suppressed
    * Startup timeout raises cleanly
    * Matches via served_name prefix

All process spawning is mocked; nothing here actually launches
llama-server.exe.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.providers.gguf_catalog import (
    CATALOG,
    DEFAULT_KEY,
    find_by_served_name,
    get_model,
    pick_for_task,
)
from app.services.providers.llama_server_manager import (
    LlamaServerManager,
    ManagedMode,
    _read_mode,
    get_manager,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton + its lock between tests."""
    LlamaServerManager._instance = None  # noqa: SLF001
    yield
    LlamaServerManager._instance = None  # noqa: SLF001


# ----------------------------------------------------------------------
# GGUF catalog
# ----------------------------------------------------------------------


def test_catalog_has_three_models():
    assert set(CATALOG.keys()) == {"qwen3-8b", "coder", "gemma"}


def test_get_model_case_insensitive():
    assert get_model("CODER") is CATALOG["coder"]
    assert get_model("Qwen3-8B") is CATALOG["qwen3-8b"]


def test_get_model_unknown_returns_none():
    assert get_model("fake-model") is None


def test_find_by_served_name_prefix_match():
    # llama-server may report "Qwen3-8B-Q4_K_M" or "qwen3-8b" etc;
    # either should resolve to the same entry.
    assert find_by_served_name("Qwen3-8B-Q4_K_M") is CATALOG["qwen3-8b"]
    assert find_by_served_name("qwen3-8b-instruct") is CATALOG["qwen3-8b"]


def test_find_by_served_name_returns_none_for_empty():
    assert find_by_served_name("") is None


def test_pick_for_task_coding_routes_to_coder():
    assert pick_for_task({"coding"}).key == "coder"
    assert pick_for_task({"refactor"}).key == "coder"


def test_pick_for_task_summarization_routes_to_gemma():
    assert pick_for_task({"summarization"}).key == "gemma"
    assert pick_for_task({"summarize"}).key == "gemma"


def test_pick_for_task_default_is_qwen3():
    assert pick_for_task(None).key == DEFAULT_KEY
    assert pick_for_task(set()).key == DEFAULT_KEY
    assert pick_for_task({"general"}).key == DEFAULT_KEY


# ----------------------------------------------------------------------
# Mode parsing
# ----------------------------------------------------------------------


def test_mode_off_is_default():
    with patch.dict("os.environ", {"LLAMA_SERVER_MANAGED": "off"}, clear=False):
        assert _read_mode() == ManagedMode.OFF
    with patch.dict("os.environ", {"LLAMA_SERVER_MANAGED": ""}, clear=False):
        assert _read_mode() == ManagedMode.OFF


def test_mode_true_collapses_to_respect_external():
    """Safer default than force when user just flips to 'true'."""
    with patch.dict(
        "os.environ", {"LLAMA_SERVER_MANAGED": "true"}, clear=False,
    ):
        assert _read_mode() == ManagedMode.RESPECT_EXTERNAL


def test_mode_force_explicit():
    with patch.dict(
        "os.environ", {"LLAMA_SERVER_MANAGED": "force"}, clear=False,
    ):
        assert _read_mode() == ManagedMode.FORCE
    with patch.dict(
        "os.environ", {"LLAMA_SERVER_MANAGED": "takeover"}, clear=False,
    ):
        assert _read_mode() == ManagedMode.FORCE


def test_mode_unknown_falls_back_off():
    with patch.dict(
        "os.environ", {"LLAMA_SERVER_MANAGED": "asdf"}, clear=False,
    ):
        assert _read_mode() == ManagedMode.OFF


# ----------------------------------------------------------------------
# ensure_loaded contract
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_loaded_off_mode_is_noop():
    """OFF: return target, never touch the process."""
    with patch.dict(
        "os.environ", {"LLAMA_SERVER_MANAGED": "off"}, clear=False,
    ):
        mgr = LlamaServerManager()
        # Explicit override of parsed mode since __init__ reads env once.
        mgr._mode = ManagedMode.OFF  # noqa: SLF001
        result = await mgr.ensure_loaded("coder")
    assert result is CATALOG["coder"]


@pytest.mark.asyncio
async def test_ensure_loaded_unknown_model_raises():
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.OFF  # noqa: SLF001
    with pytest.raises(RuntimeError):
        await mgr.ensure_loaded("nonexistent")


@pytest.mark.asyncio
async def test_ensure_loaded_matching_current_is_noop():
    """RESPECT_EXTERNAL: server already serves target -> no swap."""
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.RESPECT_EXTERNAL  # noqa: SLF001

    # Probe returns the served_name for coder; match -> no swap.
    with patch.object(
        mgr, "_probe_running_model",
        AsyncMock(return_value="qwen3-coder-30b-a3b"),
    ), patch.object(mgr, "_start", AsyncMock()) as start_spy, \
         patch.object(mgr, "_stop_running", AsyncMock()) as stop_spy:
        result = await mgr.ensure_loaded("coder")

    assert result is CATALOG["coder"]
    start_spy.assert_not_called()
    stop_spy.assert_not_called()


@pytest.mark.asyncio
async def test_respect_external_refuses_to_kill_unknown_server():
    """When an external PID owns the server, do NOT swap."""
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.RESPECT_EXTERNAL  # noqa: SLF001
    mgr._managed_pid = None  # noqa: SLF001 - we did not start it

    with patch.object(
        mgr, "_probe_running_model",
        AsyncMock(return_value="qwen3-8b"),   # loaded != requested "coder"
    ), patch.object(
        mgr, "_read_pid_file", return_value=99999,  # external PID
    ), patch.object(
        mgr, "_is_process_alive", return_value=True,
    ), patch.object(mgr, "_start", AsyncMock()) as start_spy, \
         patch.object(mgr, "_stop_running", AsyncMock()) as stop_spy:
        result = await mgr.ensure_loaded("coder")

    # Caller gets the catalog entry, but no swap happened.
    assert result is CATALOG["coder"]
    start_spy.assert_not_called()
    stop_spy.assert_not_called()


@pytest.mark.asyncio
async def test_force_mode_always_swaps():
    """FORCE: kill external, start requested."""
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.FORCE  # noqa: SLF001

    with patch.object(
        mgr, "_probe_running_model",
        AsyncMock(return_value="qwen3-8b"),  # different from "coder"
    ), patch.object(
        mgr, "_stop_running", AsyncMock(),
    ) as stop_spy, patch.object(
        mgr, "_start", AsyncMock(),
    ) as start_spy:
        result = await mgr.ensure_loaded("coder")

    assert result is CATALOG["coder"]
    stop_spy.assert_called_once()
    start_spy.assert_called_once()


# ----------------------------------------------------------------------
# Cooldown
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cooldown_suppresses_rapid_reswap():
    """If we just swapped < 30s ago, prefer current model over thrash."""
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.FORCE  # noqa: SLF001
    mgr._last_swap_at = time.time()  # noqa: SLF001 - swap just happened

    # Running model is "qwen3-8b"; request "coder" but cooldown active.
    with patch.object(
        mgr, "_probe_running_model",
        AsyncMock(return_value="qwen3-8b"),
    ), patch.object(
        mgr, "_start", AsyncMock(),
    ) as start_spy, patch.object(
        mgr, "_stop_running", AsyncMock(),
    ) as stop_spy:
        result = await mgr.ensure_loaded("coder")

    # Caller still receives the catalog entry for their logical request;
    # the suppression is a hint to the provider layer.
    assert result is CATALOG["coder"]
    start_spy.assert_not_called()
    stop_spy.assert_not_called()


# ----------------------------------------------------------------------
# Mutex under concurrency
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_ensure_loaded_serializes():
    """Two concurrent callers must not race into two process spawns."""
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.FORCE  # noqa: SLF001
    spawn_calls = []

    async def fake_start(target):
        spawn_calls.append(target.key)
        await asyncio.sleep(0.05)
        mgr._current_model_key = target.key  # noqa: SLF001
        mgr._current_model_served = target.served_name  # noqa: SLF001

    # Running model is empty so both callers think they need to swap.
    with patch.object(
        mgr, "_probe_running_model", AsyncMock(return_value=None),
    ), patch.object(mgr, "_stop_running", AsyncMock()), \
         patch.object(mgr, "_start", side_effect=fake_start):
        results = await asyncio.gather(
            mgr.ensure_loaded("coder"),
            mgr.ensure_loaded("coder"),
        )

    assert all(r is CATALOG["coder"] for r in results)
    # Second call sees the first start's state and does not spawn again.
    assert spawn_calls.count("coder") == 1


# ----------------------------------------------------------------------
# Singleton identity
# ----------------------------------------------------------------------


def test_singleton_returns_same_instance():
    a = get_manager()
    b = get_manager()
    c = LlamaServerManager()
    assert a is b is c


def test_state_snapshot_fields():
    mgr = LlamaServerManager()
    mgr._mode = ManagedMode.RESPECT_EXTERNAL  # noqa: SLF001
    with patch.object(mgr, "_read_pid_file", return_value=None):
        state = mgr.state()
    assert state.mode == ManagedMode.RESPECT_EXTERNAL
    assert state.port == 8080
    assert state.managed_pid is None
    assert state.external_pid is None
