from __future__ import annotations

from typing import Any, Dict

from backend.config.settings import settings


def _require_pyautogui():
    try:
        import pyautogui  # noqa: F401
    except Exception as e:
        raise RuntimeError(f"pyautogui not installed: {e}")


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: desktop_automation_pyautogui (optional dependency)

    Gated by AUTOMATION_ENABLE_DESKTOP=1.
    """
    if not getattr(settings, "automation_enable_desktop", False):
        raise RuntimeError("desktop automation disabled (AUTOMATION_ENABLE_DESKTOP=0)")
    _require_pyautogui()
    import pyautogui

    action = (args or {}).get("action")
    if action == "click":
        x = int((args or {}).get("x"))
        y = int((args or {}).get("y"))
        pyautogui.click(x=x, y=y)
        return {"clicked": True, "x": x, "y": y}
    if action == "type":
        text = str((args or {}).get("text", ""))
        pyautogui.typewrite(text)
        return {"typed": True}
    raise RuntimeError("unsupported desktop action (use click/type)")











