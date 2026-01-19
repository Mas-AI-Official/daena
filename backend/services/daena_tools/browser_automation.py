"""
Browser Automation Tool for Daena AI VP

Provides Manus-style browser control capabilities:
- Navigate to URLs
- Login to pages
- Click elements
- Fill forms
- Take screenshots
- Extract content

Uses Playwright for reliable browser automation.
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import os
import json
import base64

logger = logging.getLogger(__name__)

# Browser session state
_browser = None
_page = None
_context = None


async def get_browser():
    """Get or create browser instance."""
    global _browser, _context, _page
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "Playwright not installed. Run: pip install playwright && playwright install chromium"
    
    if _browser is None:
        playwright = await async_playwright().start()
        _browser = await playwright.chromium.launch(
            headless=False,  # Show browser for Manus-style interaction
            args=['--start-maximized']
        )
        _context = await _browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        _page = await _context.new_page()
    
    return _page, None


async def navigate(url: str) -> Dict[str, Any]:
    """
    Navigate to a URL.
    
    Returns:
        {success, url, title, error}
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        return {
            "success": True,
            "url": page.url,
            "title": await page.title()
        }
    except Exception as e:
        logger.error(f"Navigate failed: {e}")
        return {"success": False, "error": str(e)}


async def click(selector: str) -> Dict[str, Any]:
    """
    Click an element.
    
    Args:
        selector: CSS selector or text to find
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        # Try direct selector first
        try:
            await page.click(selector, timeout=5000)
            return {"success": True, "clicked": selector}
        except:
            pass
        
        # Try by text content
        try:
            await page.click(f"text={selector}", timeout=5000)
            return {"success": True, "clicked": f"text={selector}"}
        except:
            pass
        
        # Try by button text
        try:
            await page.click(f"button:has-text('{selector}')", timeout=5000)
            return {"success": True, "clicked": f"button with text '{selector}'"}
        except:
            pass
        
        # Try by link text
        try:
            await page.click(f"a:has-text('{selector}')", timeout=5000)
            return {"success": True, "clicked": f"link with text '{selector}'"}
        except:
            pass
        
        return {"success": False, "error": f"Element not found: {selector}"}
        
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return {"success": False, "error": str(e)}


async def fill(selector: str, value: str) -> Dict[str, Any]:
    """
    Fill a form field.
    
    Args:
        selector: CSS selector, name, or label
        value: Value to enter
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        # Try direct selector
        try:
            await page.fill(selector, value, timeout=5000)
            return {"success": True, "filled": selector, "value": value[:20] + "..." if len(value) > 20 else value}
        except:
            pass
        
        # Try by name attribute
        try:
            await page.fill(f"[name='{selector}']", value, timeout=5000)
            return {"success": True, "filled": f"[name='{selector}']", "value": value[:20]}
        except:
            pass
        
        # Try by placeholder
        try:
            await page.fill(f"[placeholder*='{selector}' i]", value, timeout=5000)
            return {"success": True, "filled": f"placeholder containing '{selector}'", "value": value[:20]}
        except:
            pass
        
        # Try by label
        try:
            await page.fill(f"input:near(:text('{selector}'))", value, timeout=5000)
            return {"success": True, "filled": f"input near '{selector}'", "value": value[:20]}
        except:
            pass
        
        return {"success": False, "error": f"Input not found: {selector}"}
        
    except Exception as e:
        logger.error(f"Fill failed: {e}")
        return {"success": False, "error": str(e)}


async def screenshot(name: str = "screenshot") -> Dict[str, Any]:
    """
    Take a screenshot of the current page.
    
    Returns:
        {success, path, base64}
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        # Save to screenshots directory
        screenshots_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(screenshots_dir, filename)
        
        screenshot_bytes = await page.screenshot(full_page=False)
        
        with open(path, 'wb') as f:
            f.write(screenshot_bytes)
        
        return {
            "success": True,
            "path": path,
            "filename": filename,
            "url": page.url
        }
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return {"success": False, "error": str(e)}


async def get_page_content() -> Dict[str, Any]:
    """
    Get the current page content.
    
    Returns:
        {success, title, url, text, links}
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        # Get page info
        title = await page.title()
        url = page.url
        
        # Get visible text (limited)
        text = await page.evaluate('''() => {
            return document.body.innerText.substring(0, 5000);
        }''')
        
        # Get links
        links = await page.evaluate('''() => {
            return [...document.querySelectorAll('a[href]')]
                .slice(0, 20)
                .map(a => ({text: a.innerText.trim(), href: a.href}))
                .filter(l => l.text && l.text.length < 100);
        }''')
        
        # Get form fields
        forms = await page.evaluate('''() => {
            return [...document.querySelectorAll('input, textarea, select')]
                .slice(0, 20)
                .map(el => ({
                    type: el.tagName.toLowerCase(),
                    name: el.name,
                    placeholder: el.placeholder,
                    id: el.id
                }))
                .filter(f => f.name || f.placeholder || f.id);
        }''')
        
        return {
            "success": True,
            "title": title,
            "url": url,
            "text": text[:2000] + "..." if len(text) > 2000 else text,
            "links": links,
            "forms": forms
        }
    except Exception as e:
        logger.error(f"Get content failed: {e}")
        return {"success": False, "error": str(e)}


async def login(url: str, username: str, password: str, 
                username_field: str = "username", 
                password_field: str = "password",
                submit_button: str = "submit") -> Dict[str, Any]:
    """
    Automated login to a page.
    
    Args:
        url: Login page URL
        username: Username to enter
        password: Password to enter
        username_field: Selector for username field
        password_field: Selector for password field
        submit_button: Selector for submit button
    """
    try:
        # Navigate to login page
        nav_result = await navigate(url)
        if not nav_result.get("success"):
            return nav_result
        
        # Wait for page to load
        page, _ = await get_browser()
        await asyncio.sleep(1)
        
        # Fill username
        fill_user = await fill(username_field, username)
        if not fill_user.get("success"):
            # Try common alternatives
            for alt in ["email", "user", "login", "Email", "Username", "input[type='email']"]:
                fill_user = await fill(alt, username)
                if fill_user.get("success"):
                    break
        
        # Fill password  
        fill_pass = await fill(password_field, password)
        if not fill_pass.get("success"):
            for alt in ["pass", "pwd", "Password", "input[type='password']"]:
                fill_pass = await fill(alt, password)
                if fill_pass.get("success"):
                    break
        
        # Click submit
        click_result = await click(submit_button)
        if not click_result.get("success"):
            for alt in ["Login", "Sign in", "Log in", "Submit", "button[type='submit']"]:
                click_result = await click(alt)
                if click_result.get("success"):
                    break
        
        # Wait for redirect
        await asyncio.sleep(2)
        
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "message": "Login attempted. Check current URL to verify success."
        }
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return {"success": False, "error": str(e)}


async def close_browser() -> Dict[str, Any]:
    """Close the browser session."""
    global _browser, _context, _page
    
    try:
        if _browser:
            await _browser.close()
            _browser = None
            _context = None
            _page = None
        return {"success": True, "message": "Browser closed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_script(script: str) -> Dict[str, Any]:
    """
    Execute JavaScript on the page.
    
    Args:
        script: JavaScript code to execute
    """
    page, error = await get_browser()
    if error:
        return {"success": False, "error": error}
    
    try:
        result = await page.evaluate(script)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Convenience function for Daena
async def daena_browser(command: str) -> Dict[str, Any]:
    """
    Parse browser automation commands.
    
    Examples:
        "go to https://google.com"
        "click Login"
        "fill email with test@test.com"
        "screenshot"
        "what's on this page"
    """
    command = command.strip()
    cmd_lower = command.lower()
    
    if cmd_lower.startswith(("go to ", "navigate to ", "open ")):
        url = command.split(" ", 2)[-1].strip()
        if not url.startswith("http"):
            url = "https://" + url
        return await navigate(url)
    
    elif cmd_lower.startswith("click "):
        selector = command[6:].strip().strip('"\'')
        return await click(selector)
    
    elif cmd_lower.startswith("fill "):
        # Parse "fill <field> with <value>"
        parts = command[5:].split(" with ", 1)
        if len(parts) == 2:
            field = parts[0].strip().strip('"\'')
            value = parts[1].strip().strip('"\'')
            return await fill(field, value)
        else:
            return {"success": False, "error": "Usage: fill <field> with <value>"}
    
    elif cmd_lower.startswith(("screenshot", "capture", "snap")):
        name = command.split()[-1] if len(command.split()) > 1 else "screenshot"
        return await screenshot(name)
    
    elif cmd_lower in ["content", "page", "what's on this page", "read page", "get content"]:
        return await get_page_content()
    
    elif cmd_lower.startswith("login"):
        # Simplified login - expects: login <url> <user> <pass>
        parts = command.split()
        if len(parts) >= 4:
            return await login(parts[1], parts[2], parts[3])
        else:
            return {"success": False, "error": "Usage: login <url> <username> <password>"}
    
    elif cmd_lower in ["close", "quit", "exit browser"]:
        return await close_browser()
    
    elif cmd_lower.startswith("run ") or cmd_lower.startswith("execute "):
        script = command.split(" ", 1)[1].strip()
        return await execute_script(script)
    
    else:
        return {
            "success": False, 
            "error": "Unknown command. Try: go to <url>, click <element>, fill <field> with <value>, screenshot, content, close"
        }


async def web_search(query: str) -> Dict[str, Any]:
    """
    Perform a web search using DuckDuckGo HTML (no API key needed).
    Falls back to browser-based search if httpx fails.
    
    Args:
        query: Search query string
    
    Returns:
        {success, query, results[{title, url, snippet}]}
    """
    import httpx
    from urllib.parse import quote_plus
    import re
    
    try:
        # Try fast API-based search first (DuckDuckGo HTML)
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
                # Find all result blocks
                result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'
                
                hrefs = re.findall(result_pattern, html)
                snippets = re.findall(snippet_pattern, html)
                
                for i, (url, title) in enumerate(hrefs[:8]):
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
                        "source": "duckduckgo"
                    }
        
        # Fallback: Try browser-based Google search
        logger.info("Falling back to browser-based search")
        
        # Navigate to Google
        nav_result = await navigate("https://www.google.com")
        if not nav_result.get("success"):
            return {"success": False, "error": f"Search failed: {nav_result.get('error')}", "query": query}
        
        page, _ = await get_browser()
        
        # Accept cookies if prompted
        try:
            await page.click("button:has-text('Accept all')", timeout=2000)
        except:
            pass  # Cookie dialog may not appear
        
        # Fill search box and submit
        await page.fill("input[name='q']", query)
        await page.press("input[name='q']", "Enter")
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Extract search results
        results = await page.evaluate('''() => {
            const items = document.querySelectorAll('div.g');
            return [...items].slice(0, 8).map(el => {
                const titleEl = el.querySelector('h3');
                const linkEl = el.querySelector('a');
                const snippetEl = el.querySelector('[data-sncf], .VwiC3b, span[style]');
                return {
                    title: titleEl?.innerText || '',
                    url: linkEl?.href || '',
                    snippet: snippetEl?.innerText?.substring(0, 200) || ''
                };
            }).filter(r => r.title && r.url);
        }''')
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "source": "google_browser"
        }
        
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {"success": False, "error": str(e), "query": query}
