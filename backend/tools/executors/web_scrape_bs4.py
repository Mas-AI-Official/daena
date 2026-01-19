from __future__ import annotations

from typing import Any, Dict, Literal, Optional

import httpx

from backend.config.settings import settings
from backend.tools.policies import check_allowed_url


async def run(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: web_scrape_bs4
    Args:
      - url (required)
      - selector (optional)
      - mode: text|links|tables (optional, default=text)
    """
    url = (args or {}).get("url")
    selector = (args or {}).get("selector")
    mode: Literal["text", "links", "tables"] = (args or {}).get("mode") or "text"

    check_allowed_url(url)

    timeout = float(getattr(settings, "automation_request_timeout_sec", 15.0))
    headers = {"User-Agent": "DaenaToolRunner/1.0"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception as e:
        raise RuntimeError(f"beautifulsoup4 not installed: {e}")

    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(selector) if selector else soup
    if not root:
        return {"url": url, "selector": selector, "mode": mode, "result": None}

    if mode == "links":
        links = []
        for a in root.select("a[href]"):
            links.append({"text": (a.get_text(" ", strip=True) or ""), "href": a.get("href")})
        return {"url": url, "selector": selector, "mode": mode, "result": links}

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
        return {"url": url, "selector": selector, "mode": mode, "result": tables}

    text = root.get_text("\n", strip=True)
    return {"url": url, "selector": selector, "mode": "text", "result": text}











