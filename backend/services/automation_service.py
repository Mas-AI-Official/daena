"""
Operator / Automation service (safe-by-default).

Provides:
- HTTP scraping (httpx + BeautifulSoup)
- Optional session-based browser control (Playwright, gated + optional dependency)
- Optional desktop actions (pyautogui, gated + optional dependency)
- Process model for Manus-style step timelines
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)


def _trace_id() -> str:
    return uuid.uuid4().hex


def _redact(obj: Any) -> Any:
    """Redact common secret fields from logs/results."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in ["password", "passwd", "secret", "token", "api_key", "apikey", "authorization"]):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = _redact(v)
        return redacted
    return str(obj)


class AllowlistError(ValueError):
    pass


class DomainAllowlist:
    def __init__(self, allowed_domains: List[str]):
        self.allowed = {d.strip().lower() for d in (allowed_domains or []) if str(d).strip()}

    def check_url(self, url: str) -> None:
        if not url:
            raise AllowlistError("url is required")
        try:
            parsed = urlparse(url)
        except Exception:
            raise AllowlistError("invalid url")
        if parsed.scheme not in ("http", "https"):
            raise AllowlistError("only http/https urls are allowed")
        host = (parsed.hostname or "").lower()
        if not host:
            raise AllowlistError("url hostname missing")
        if settings.automation_safe_mode and self.allowed and host not in self.allowed:
            raise AllowlistError(f"domain not allowed: {host}")


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().isoformat()


@dataclass
class ProcessStep:
    step_id: str
    name: str
    input: Dict[str, Any]
    status: str = "pending"  # pending|running|completed|failed|cancelled
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AutomationProcess:
    process_id: str
    created_at: str
    status: str = "pending"
    title: str = "Operator Process"
    steps: List[ProcessStep] = None
    trace_id: str = ""
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "process_id": self.process_id,
            "created_at": self.created_at,
            "status": self.status,
            "title": self.title,
            "trace_id": self.trace_id,
            "cancelled": self.cancelled,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "input": _redact(s.input),
                    "status": s.status,
                    "started_at": s.started_at,
                    "finished_at": s.finished_at,
                    "output": _redact(s.output),
                    "error": s.error,
                }
                for s in (self.steps or [])
            ],
        }


class RateLimiter:
    """Very small in-memory rate limiter (per-process)."""

    def __init__(self, per_min: int):
        self.per_min = max(1, int(per_min))
        self._events: Dict[str, List[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        lst = self._events.get(key, [])
        lst = [t for t in lst if t >= window_start]
        if len(lst) >= self.per_min:
            self._events[key] = lst
            return False
        lst.append(now)
        self._events[key] = lst
        return True


class BrowserSessionManager:
    """Playwright session-based browser control (optional dependency)."""

    def __init__(self):
        self._sessions: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def _require_playwright(self):
        if not settings.automation_enable_browser:
            raise RuntimeError("browser automation disabled (AUTOMATION_ENABLE_BROWSER=0)")
        try:
            from playwright.async_api import async_playwright  # noqa: F401
        except Exception as e:
            raise RuntimeError(f"playwright not installed: {e}")

    async def create(self, trace_id: str) -> Dict[str, Any]:
        await self._require_playwright()
        from playwright.async_api import async_playwright

        session_id = uuid.uuid4().hex
        async with self._lock:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            self._sessions[session_id] = {"pw": pw, "browser": browser, "page": page, "created_at": time.time()}
        logger.info("automation.browser.session.create", extra={"trace_id": trace_id, "session_id": session_id})
        return {"session_id": session_id}

    async def get_page(self, session_id: str) -> Any:
        async with self._lock:
            s = self._sessions.get(session_id)
        if not s:
            raise RuntimeError("session not found")
        return s["page"]

    async def close(self, session_id: str, trace_id: str) -> Dict[str, Any]:
        async with self._lock:
            s = self._sessions.pop(session_id, None)
        if not s:
            return {"closed": False, "reason": "session not found"}
        try:
            await s["browser"].close()
            await s["pw"].stop()
        except Exception:
            pass
        logger.info("automation.browser.session.close", extra={"trace_id": trace_id, "session_id": session_id})
        return {"closed": True}


class AutomationService:
    def __init__(self):
        self.allowlist = DomainAllowlist(settings.automation_allowed_domains)
        self.rate_limiter = RateLimiter(settings.automation_rate_limit_per_min)
        self.browser = BrowserSessionManager()
        self._processes: Dict[str, AutomationProcess] = {}
        self._process_lock = asyncio.Lock()

    # ---------------------------
    # Scrape
    # ---------------------------
    async def scrape(
        self,
        url: str,
        selector: Optional[str] = None,
        mode: str = "text",
        timeout_sec: Optional[float] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tid = trace_id or _trace_id()
        self.allowlist.check_url(url)
        timeout = timeout_sec or settings.automation_request_timeout_sec

        headers = {"User-Agent": "DaenaOperator/1.0"}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text

        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception as e:
            raise RuntimeError(f"beautifulsoup4 missing: {e}")

        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(selector) if selector else soup

        if not root:
            return {"status": "ok", "data": {"mode": mode, "url": url, "selector": selector, "result": None}, "trace_id": tid}

        if mode == "links":
            links = []
            for a in root.select("a[href]"):
                links.append({"text": (a.get_text(" ", strip=True) or ""), "href": a.get("href")})
            return {"status": "ok", "data": {"mode": mode, "url": url, "selector": selector, "result": links}, "trace_id": tid}

        if mode == "tables":
            tables = []
            for t in root.select("table"):
                rows = []
                for tr in t.select("tr"):
                    cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
                    if cells:
                        rows.append(cells)
                if rows:
                    tables.append(rows)
            return {"status": "ok", "data": {"mode": mode, "url": url, "selector": selector, "result": tables}, "trace_id": tid}

        # Default: text
        text = root.get_text("\n", strip=True)
        return {"status": "ok", "data": {"mode": "text", "url": url, "selector": selector, "result": text}, "trace_id": tid}

    # ---------------------------
    # Browser actions (optional)
    # ---------------------------
    async def browser_navigate(self, session_id: str, url: str, trace_id: str) -> Dict[str, Any]:
        self.allowlist.check_url(url)
        page = await self.browser.get_page(session_id)
        await page.goto(url, timeout=int(settings.automation_action_timeout_sec * 1000))
        return {"status": "ok", "data": {"session_id": session_id, "url": url}, "trace_id": trace_id}

    async def browser_click(self, session_id: str, selector: str, trace_id: str) -> Dict[str, Any]:
        page = await self.browser.get_page(session_id)
        await page.click(selector, timeout=int(settings.automation_action_timeout_sec * 1000))
        return {"status": "ok", "data": {"session_id": session_id, "selector": selector}, "trace_id": trace_id}

    async def browser_type(self, session_id: str, selector: str, text: str, trace_id: str, submit: bool = False) -> Dict[str, Any]:
        page = await self.browser.get_page(session_id)
        await page.fill(selector, text, timeout=int(settings.automation_action_timeout_sec * 1000))
        if submit:
            await page.keyboard.press("Enter")
        return {"status": "ok", "data": {"session_id": session_id, "selector": selector, "submit": submit}, "trace_id": trace_id}

    async def browser_screenshot(self, session_id: str, trace_id: str) -> Dict[str, Any]:
        page = await self.browser.get_page(session_id)
        png = await page.screenshot(full_page=True)
        # Return as base64 to keep JSON-only
        import base64
        return {"status": "ok", "data": {"session_id": session_id, "png_base64": base64.b64encode(png).decode("ascii")}, "trace_id": trace_id}

    # ---------------------------
    # Desktop actions (optional + gated)
    # ---------------------------
    async def desktop_click(self, x: int, y: int, trace_id: str) -> Dict[str, Any]:
        if not settings.automation_enable_desktop:
            raise RuntimeError("desktop automation disabled (AUTOMATION_ENABLE_DESKTOP=0)")
        try:
            import pyautogui  # type: ignore
        except Exception as e:
            raise RuntimeError(f"pyautogui not installed: {e}")
        pyautogui.click(x=x, y=y)
        return {"status": "ok", "data": {"x": x, "y": y}, "trace_id": trace_id}

    async def desktop_type(self, text: str, trace_id: str) -> Dict[str, Any]:
        if not settings.automation_enable_desktop:
            raise RuntimeError("desktop automation disabled (AUTOMATION_ENABLE_DESKTOP=0)")
        try:
            import pyautogui  # type: ignore
        except Exception as e:
            raise RuntimeError(f"pyautogui not installed: {e}")
        pyautogui.typewrite(text)
        return {"status": "ok", "data": {"typed": True}, "trace_id": trace_id}

    # ---------------------------
    # Processes (Manus-style timelines)
    # ---------------------------
    async def create_process(self, title: str, steps: List[Tuple[str, Dict[str, Any]]], trace_id: Optional[str] = None) -> AutomationProcess:
        tid = trace_id or _trace_id()
        proc = AutomationProcess(
            process_id=uuid.uuid4().hex,
            created_at=_now_iso(),
            status="pending",
            title=title or "Operator Process",
            steps=[ProcessStep(step_id=uuid.uuid4().hex, name=name, input=inp) for name, inp in steps],
            trace_id=tid,
        )
        async with self._process_lock:
            # prune
            if len(self._processes) >= settings.automation_max_processes:
                oldest = sorted(self._processes.values(), key=lambda p: p.created_at)[:10]
                for p in oldest:
                    self._processes.pop(p.process_id, None)
            self._processes[proc.process_id] = proc
        return proc

    async def get_process(self, process_id: str) -> Optional[AutomationProcess]:
        async with self._process_lock:
            return self._processes.get(process_id)

    async def list_processes(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with self._process_lock:
            procs = list(self._processes.values())
        procs.sort(key=lambda p: p.created_at, reverse=True)
        return [p.to_dict() for p in procs[: max(1, min(200, limit))]]

    async def cancel_process(self, process_id: str) -> bool:
        async with self._process_lock:
            p = self._processes.get(process_id)
            if not p:
                return False
            p.cancelled = True
            if p.status in ("pending", "running"):
                p.status = "cancelled"
        return True

    async def run_process(self, proc: AutomationProcess, emit_cb=None) -> AutomationProcess:
        key = proc.process_id
        if not self.rate_limiter.allow(key):
            proc.status = "failed"
            if proc.steps:
                proc.steps[0].status = "failed"
                proc.steps[0].error = "rate_limited"
            return proc

        proc.status = "running"
        if emit_cb:
            emit_cb(proc)
        for step in proc.steps or []:
            if proc.cancelled:
                step.status = "cancelled"
                proc.status = "cancelled"
                if emit_cb:
                    emit_cb(proc)
                break
            step.status = "running"
            step.started_at = _now_iso()
            if emit_cb:
                emit_cb(proc)
            try:
                out = await self._execute_step(step.name, step.input, proc.trace_id)
                step.output = out
                step.status = "completed"
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                proc.status = "failed"
            step.finished_at = _now_iso()
            if emit_cb:
                emit_cb(proc)
            if proc.status == "failed":
                break
        if proc.status == "running":
            proc.status = "completed"
            if emit_cb:
                emit_cb(proc)
        return proc

    async def _execute_step(self, name: str, payload: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        name = (name or "").strip().lower()
        payload = payload or {}

        # Prefer canonical tool runner for scrape (prevents duplicate logic)
        if name in ("tool.scrape.extract", "scrape.extract", "automation.scrape", "web_scrape_bs4"):
            from backend.services.cmp_service import run_cmp_tool_action
            url = payload.get("url")
            selector = payload.get("selector")
            mode = payload.get("mode", "text")
            out = await run_cmp_tool_action(
                tool_name="web_scrape_bs4",
                args={"url": url, "selector": selector, "mode": mode},
                department=payload.get("department"),
                agent_id=payload.get("agent_id"),
                reason="automation.process.step",
                trace_id=trace_id,
            )
            if out.get("status") != "ok":
                raise RuntimeError(out.get("error") or "tool failed")
            return out.get("result") or {}

        if name in ("tool.browser.navigate", "browser.navigate"):
            return (await self.browser_navigate(payload["session_id"], payload["url"], trace_id))["data"]

        if name in ("tool.browser.click", "browser.click"):
            return (await self.browser_click(payload["session_id"], payload["selector"], trace_id))["data"]

        if name in ("tool.browser.type", "browser.type"):
            return (await self.browser_type(payload["session_id"], payload["selector"], payload.get("text", ""), trace_id, bool(payload.get("submit", False))))["data"]

        if name in ("tool.browser.screenshot", "browser.screenshot"):
            return (await self.browser_screenshot(payload["session_id"], trace_id))["data"]

        if name in ("tool.desktop.click", "desktop.click"):
            return (await self.desktop_click(int(payload["x"]), int(payload["y"]), trace_id))["data"]

        if name in ("tool.desktop.type", "desktop.type"):
            return (await self.desktop_type(str(payload.get("text", "")), trace_id))["data"]

        raise RuntimeError(f"unknown step/tool: {name}")


automation_service = AutomationService()


