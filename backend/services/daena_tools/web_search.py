"""
Web Search Service - Pluggable Search Providers

Provider priority:
1. Brave Search API (if BRAVE_API_KEY exists)
2. Serper (if SERPER_API_KEY exists)
3. Tavily (if TAVILY_API_KEY exists)
4. DuckDuckGo HTML scrape (always available fallback)
"""

import os
import logging
import httpx
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus
import re

logger = logging.getLogger(__name__)

# Search provider registry
PROVIDERS = []


async def search_brave(query: str, num_results: int = 8) -> Optional[Dict[str, Any]]:
    """Brave Search API."""
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": num_results},
                headers={"X-Subscription-Token": api_key}
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("web", {}).get("results", [])[:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "")[:200]
                    })
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "provider": "brave"
                }
    except Exception as e:
        logger.warning(f"Brave search failed: {e}")
    return None


async def search_serper(query: str, num_results: int = 8) -> Optional[Dict[str, Any]]:
    """Serper (Google Search API)."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": num_results},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("organic", [])[:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")[:200]
                    })
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "provider": "serper"
                }
    except Exception as e:
        logger.warning(f"Serper search failed: {e}")
    return None


async def search_tavily(query: str, num_results: int = 8) -> Optional[Dict[str, Any]]:
    """Tavily AI Search."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": num_results,
                    "include_answer": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("results", [])[:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:200]
                    })
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "provider": "tavily"
                }
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
    return None


async def search_duckduckgo(query: str, num_results: int = 8) -> Optional[Dict[str, Any]]:
    """DuckDuckGo HTML scrape fallback."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            
            if response.status_code == 200:
                html = response.text
                results = []
                
                # Parse DuckDuckGo HTML results
                result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'
                
                hrefs = re.findall(result_pattern, html)
                snippets = re.findall(snippet_pattern, html)
                
                for i, (url, title) in enumerate(hrefs[:num_results]):
                    snippet = snippets[i] if i < len(snippets) else ""
                    # Clean up snippet (remove HTML tags)
                    snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    
                    # Decode DuckDuckGo redirect URL
                    if "uddg=" in url:
                        import urllib.parse
                        url = urllib.parse.unquote(url.split("uddg=")[-1].split("&")[0])
                    
                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "snippet": snippet[:200]
                    })
                
                if results:
                    return {
                        "success": True,
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "provider": "duckduckgo"
                    }
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
    return None


async def web_search(query: str, num_results: int = 8) -> Dict[str, Any]:
    """
    Main search function with provider fallback chain.
    
    Priority:
    1. Brave (if API key)
    2. Serper (if API key)
    3. Tavily (if API key)
    4. DuckDuckGo HTML scrape (always)
    """
    if not query or not query.strip():
        return {"success": False, "error": "Empty query", "query": query}
    
    query = query.strip()
    
    # Try each provider in priority order
    providers = [
        ("brave", search_brave),
        ("serper", search_serper),
        ("tavily", search_tavily),
        ("duckduckgo", search_duckduckgo),
    ]
    
    for name, func in providers:
        try:
            result = await func(query, num_results)
            if result and result.get("success") and result.get("results"):
                logger.info(f"Search succeeded with provider: {name}")
                return result
        except Exception as e:
            logger.debug(f"Provider {name} failed: {e}")
            continue
    
    return {
        "success": False,
        "query": query,
        "results": [],
        "count": 0,
        "error": "All search providers failed",
        "provider": "none"
    }


def get_available_providers() -> List[str]:
    """Return list of configured search providers."""
    available = []
    if os.environ.get("BRAVE_API_KEY"):
        available.append("brave")
    if os.environ.get("SERPER_API_KEY"):
        available.append("serper")
    if os.environ.get("TAVILY_API_KEY"):
        available.append("tavily")
    available.append("duckduckgo")  # Always available
    return available
