"""Contract tests for the backend launcher (run.py).

These lock in the launch-critical port/teardown logic the 2026-06-19 launch fix
relies on. Every test targets a real edge that goes RED if the logic regresses
(negative-control valid) -- not a tautology:
  - find_free_port must scan upward off a busy port and raise when the window is
    full, so a second backend never silently binds an occupied port.
  - _is_port_listening must distinguish a live listener from a dead port, since
    stale-port cleanup and frontend proxying both depend on it.
  - _remove_stale_port_file must delete ONLY a dead-port file and keep a live one,
    so an abrupt-termination leftover self-heals without nuking a running boot.
"""

from __future__ import annotations

import os
import socket

import pytest

import run


def _occupy(port: int = 0) -> tuple[socket.socket, int]:
    """Bind+listen on 0.0.0.0:<port> exactly as find_free_port probes (no
    SO_REUSEADDR), so a conflicting bind deterministically fails. 0 = ephemeral.
    Returns (socket, actual_port); caller owns close().
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    return s, s.getsockname()[1]


class TestIsPortListening:
    def test_true_when_listener_present(self):
        s, port = _occupy()
        try:
            assert run._is_port_listening(port) is True
        finally:
            s.close()

    def test_false_when_port_dead(self):
        s, port = _occupy()
        s.close()  # release -> nothing listening
        assert run._is_port_listening(port) is False


class TestFindFreePort:
    def test_returns_start_when_free(self):
        s, free = _occupy()
        s.close()  # free it
        assert run.find_free_port(free) == free

    def test_scans_upward_when_start_busy(self):
        occupied, busy = _occupy()
        try:
            got = run.find_free_port(busy, max_tries=20)
            assert got != busy
            # the returned port must be genuinely bindable, not just != busy
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind(("0.0.0.0", got))
            finally:
                probe.close()
        finally:
            occupied.close()

    def test_raises_when_window_full(self):
        held: list[socket.socket] = []
        try:
            base_sock, base = _occupy()
            held.append(base_sock)
            max_tries = 5
            for off in range(1, max_tries):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.bind(("0.0.0.0", base + off))
                    s.listen(1)
                    held.append(s)
                except OSError:
                    s.close()
                    pytest.skip("could not occupy a contiguous port block")
            with pytest.raises(RuntimeError):
                run.find_free_port(base, max_tries=max_tries)
        finally:
            for s in held:
                s.close()


class TestRemoveStalePortFile:
    def test_removes_file_for_dead_port(self, tmp_path):
        s, dead = _occupy()
        s.close()  # port now dead
        pf = tmp_path / ".daena-port"
        pf.write_text(str(dead), encoding="utf-8")
        run._remove_stale_port_file(pf)
        assert not pf.exists()

    def test_preserves_file_for_live_port(self, tmp_path):
        s, live = _occupy()
        try:
            pf = tmp_path / ".daena-port"
            pf.write_text(str(live), encoding="utf-8")
            run._remove_stale_port_file(pf)
            assert pf.exists()  # a running boot's port file must survive
        finally:
            s.close()

    def test_noop_when_file_missing(self, tmp_path):
        pf = tmp_path / ".daena-port"
        run._remove_stale_port_file(pf)  # must not raise
        assert not pf.exists()

    def test_noop_on_garbage_content(self, tmp_path):
        pf = tmp_path / ".daena-port"
        pf.write_text("not-a-port", encoding="utf-8")
        run._remove_stale_port_file(pf)
        assert pf.exists()  # unparseable -> left untouched, not deleted


class _FakeSettings:
    """Minimal settings stand-in so main() runs without real config/boot."""

    host = "127.0.0.1"
    port = 8999
    auto_port = False  # skip the upward scan; use port as-is
    log_level = "INFO"

    def __init__(self, debug: bool):
        self.debug = debug

    def runtime_diagnostics(self) -> dict:
        return {"env_precedence": "test", "env_file": "n/a", "env_file_present": False}


class TestReloadPolicy:
    """Locks the launch-fix reload policy: Windows defaults to NO reload (the
    reloader re-execs system Python and silently drops routes), POSIX keeps
    debug-driven reload, and DAENA_RELOAD overrides either way.

    We drive main() with the REAL os.name and never monkeypatch it: os.name is
    read by pathlib.Path at instantiation, so faking it globally makes Path try
    to build a PosixPath on Windows (NotImplementedError) and corrupts the run.
    Env-override and not-debug branches are os-independent and run everywhere;
    the two os-default branches are skipif-gated so each executes natively on
    its own OS instead of via an unsafe global mutation.
    """

    def _captured_reload(self, monkeypatch, *, env, debug) -> bool:
        captured: dict = {}
        monkeypatch.setattr(run.uvicorn, "run", lambda app, **kw: captured.update(kw))
        monkeypatch.setattr(run, "get_settings", lambda: _FakeSettings(debug))
        monkeypatch.setattr(run, "_remove_stale_port_file", lambda pf: None)  # no real .daena-port touch
        if env is None:
            monkeypatch.delenv("DAENA_RELOAD", raising=False)
        else:
            monkeypatch.setenv("DAENA_RELOAD", env)
        run.main()
        return captured["reload"]

    @pytest.mark.skipif(os.name != "nt", reason="exercises the Windows default branch natively")
    def test_windows_default_is_no_reload(self, monkeypatch):
        # THE launch fix: debug + Windows + no override -> reload OFF.
        assert self._captured_reload(monkeypatch, env=None, debug=True) is False

    @pytest.mark.skipif(os.name == "nt", reason="exercises the POSIX default branch natively")
    def test_posix_default_reloads_when_debug(self, monkeypatch):
        assert self._captured_reload(monkeypatch, env=None, debug=True) is True

    def test_no_reload_when_not_debug(self, monkeypatch):
        # debug False -> reload OFF on every platform (the os.name check never matters)
        assert self._captured_reload(monkeypatch, env=None, debug=False) is False

    def test_env_forces_reload(self, monkeypatch):
        # explicit override beats the os default, regardless of platform
        assert self._captured_reload(monkeypatch, env="1", debug=False) is True

    def test_env_disables_reload(self, monkeypatch):
        # explicit "0" override beats debug, regardless of platform
        assert self._captured_reload(monkeypatch, env="0", debug=True) is False

    def test_env_is_case_insensitive(self, monkeypatch):
        assert self._captured_reload(monkeypatch, env="ON", debug=False) is True

    def test_env_unrecognized_value_is_falsey(self, monkeypatch):
        # anything not in the truthy set -> reload OFF, even with debug on
        assert self._captured_reload(monkeypatch, env="maybe", debug=True) is False
