"""Global console-window silencer for ALL subprocess calls in ContentOps.

THE PROBLEM
===========
When a Python script launched via pythonw.exe (no console parent) spawns a
console-subsystem child like ffmpeg, git, edge-tts, npx, whisper, yt-dlp,
or even cmd.exe, Windows ALLOCATES A NEW CONSOLE for that child. The
console flashes briefly on screen even though the parent Python had none.

This happens because Windows sees:
  - Parent process has STARTUPINFO.dwFlags without USESHOWWINDOW set
  - Child is a CONSOLE subsystem binary
  - → OS creates a fresh console for it

The fix: pass `creationflags=subprocess.CREATE_NO_WINDOW` (0x08000000) to
every Popen call. That flag tells Windows "do NOT allocate a console for
this child." stdout/stderr still work — `subprocess.PIPE`, file redirects,
DEVNULL all behave normally. Only the window allocation is skipped.

THIS MODULE
===========
Installs a process-wide monkey-patch on `subprocess.Popen.__init__` that
OR's CREATE_NO_WINDOW into `creationflags` on Windows. Loaded automatically
from contentops/__init__.py so the entire package and anything it imports
runs silent.

Tested invariants:
  - Output capture via PIPE/DEVNULL/file redirect: unaffected.
  - shell=True calls: silenced (cmd.exe gets the flag too).
  - Cross-platform: noop on Linux/Mac (CREATE_NO_WINDOW is Windows-only).
  - Idempotent: safe to call install() multiple times.
  - Reversible via uninstall() for tests that need to verify the patch
    isn't masking output bugs.

WHAT THIS DOES NOT TOUCH
========================
  - Chrome relaunch by the watchdog — Chrome is GUI subsystem already,
    we WANT it visible.
  - Remotion Studio when manually started — visible by design (dev tool).
  - The dashboard's stdout when run interactively — terminal-mode output
    is preserved when run via python.exe with a console parent (the flag
    is a no-op when a console already exists).
"""
from __future__ import annotations

import subprocess
import sys

# Windows CREATE_NO_WINDOW: tells CreateProcess not to allocate a console
# for the child process. Equivalent on newer Python: subprocess.CREATE_NO_WINDOW
_CREATE_NO_WINDOW = 0x08000000

_orig_popen_init = None
_installed = False


def install() -> bool:
    """Install the global subprocess silencer. Returns True if applied."""
    global _orig_popen_init, _installed
    if sys.platform != "win32":
        return False
    if _installed:
        return True
    _orig_popen_init = subprocess.Popen.__init__

    def patched_init(self, *args, **kwargs):
        # OR in CREATE_NO_WINDOW; preserve any caller-provided creationflags.
        cf = kwargs.get("creationflags", 0)
        kwargs["creationflags"] = cf | _CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched_init  # type: ignore[method-assign]
    _installed = True
    return True


def uninstall() -> None:
    """Restore the original Popen.__init__. Mostly used in tests."""
    global _installed, _orig_popen_init
    if not _installed or _orig_popen_init is None:
        return
    subprocess.Popen.__init__ = _orig_popen_init  # type: ignore[method-assign]
    _installed = False
    _orig_popen_init = None


def is_installed() -> bool:
    return _installed
