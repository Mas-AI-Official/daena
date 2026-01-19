"""
UI Consult Mode: Consult Gemini/ChatGPT via browser automation (manual approval only).

This is a fallback mode when APIs are unavailable or too costly.
Uses Playwright for reliable browser automation.
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Check if Playwright is available
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("Playwright not installed. UI Consult Mode unavailable. Install with: pip install playwright && playwright install")


# Allowed domains for UI consult
ALLOWED_DOMAINS = {
    "chatgpt": ["chat.openai.com", "chatgpt.com"],
    "gemini": ["gemini.google.com", "bard.google.com"],
}

# Browser profile directory (local, per-user)
BROWSER_PROFILE_DIR = Path.home() / ".daena_browser_profiles"


async def consult_ui(
    *,
    provider: str,  # "chatgpt" | "gemini"
    question: str,
    timeout_sec: int = 60,
    manual_approval: bool = True,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Consult external LLM UI via browser automation.
    
    Args:
        provider: "chatgpt" or "gemini"
        question: Question to ask
        timeout_sec: Maximum time to wait for response
        manual_approval: If True, requires explicit approval (default: True)
        trace_id: Optional trace ID for audit logging
    
    Returns:
        {
            "status": "ok" | "error" | "timeout" | "captcha" | "not_logged_in",
            "provider": provider,
            "answer_text": str,
            "timestamp": ISO datetime,
            "trace_id": trace_id,
            "raw_html_snapshot": Optional[str],  # Only if enabled
            "error": Optional[str],
        }
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "status": "error",
            "provider": provider,
            "answer_text": "",
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "error": "Playwright not installed. Install with: pip install playwright && playwright install",
        }
    
    # Check feature flag
    if os.getenv("ENABLE_UI_CONSULT", "0") != "1":
        return {
            "status": "error",
            "provider": provider,
            "answer_text": "",
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "error": "UI Consult Mode disabled. Set ENABLE_UI_CONSULT=1 to enable.",
        }
    
    # Validate provider
    provider_lower = provider.lower()
    if provider_lower not in ALLOWED_DOMAINS:
        return {
            "status": "error",
            "provider": provider,
            "answer_text": "",
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "error": f"Unsupported provider: {provider}. Supported: {list(ALLOWED_DOMAINS.keys())}",
        }
    
    # Get target URL
    if provider_lower == "chatgpt":
        url = "https://chat.openai.com"
    elif provider_lower == "gemini":
        url = "https://gemini.google.com"
    else:
        return {
            "status": "error",
            "provider": provider,
            "answer_text": "",
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "error": f"Unknown provider: {provider}",
        }
    
    # Ensure browser profile directory exists
    profile_dir = BROWSER_PROFILE_DIR / provider_lower
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            # Launch browser with persistent context (to preserve login)
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,  # Show browser for transparency
                viewport={"width": 1280, "height": 720},
                timeout=timeout_sec * 1000,
            )
            
            try:
                # Create new page
                page = await browser.new_page()
                
                # Navigate to provider
                logger.info(f"[UI Consult] Navigating to {url}")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait a bit for page to load
                await asyncio.sleep(2)
                
                # Check for CAPTCHA
                captcha_indicators = [
                    "captcha",
                    "verify you're human",
                    "robot",
                    "challenge",
                ]
                page_text = await page.inner_text("body")
                if any(indicator in page_text.lower() for indicator in captcha_indicators):
                    return {
                        "status": "captcha",
                        "provider": provider,
                        "answer_text": "",
                        "timestamp": datetime.now().isoformat(),
                        "trace_id": trace_id,
                        "error": "CAPTCHA detected. Please solve manually and try again.",
                    }
                
                # Check if logged in (provider-specific)
                if provider_lower == "chatgpt":
                    # Look for chat input or new chat button
                    chat_input = await page.query_selector("textarea[placeholder*='Message']")
                    if not chat_input:
                        return {
                            "status": "not_logged_in",
                            "provider": provider,
                            "answer_text": "",
                            "timestamp": datetime.now().isoformat(),
                            "trace_id": trace_id,
                            "error": "Not logged in to ChatGPT. Please log in manually first.",
                        }
                    
                    # Type question
                    await chat_input.fill(question)
                    await asyncio.sleep(0.5)
                    
                    # Submit (Enter key or send button)
                    send_button = await page.query_selector("button[aria-label*='Send']")
                    if send_button:
                        await send_button.click()
                    else:
                        await chat_input.press("Enter")
                    
                    # Wait for response
                    logger.info(f"[UI Consult] Waiting for response (timeout: {timeout_sec}s)")
                    try:
                        # Wait for response indicator (ChatGPT shows streaming)
                        await page.wait_for_selector(
                            "div[data-message-author-role='assistant']",
                            timeout=timeout_sec * 1000,
                        )
                        
                        # Wait a bit more for full response
                        await asyncio.sleep(3)
                        
                        # Extract response
                        response_elements = await page.query_selector_all(
                            "div[data-message-author-role='assistant']"
                        )
                        if response_elements:
                            # Get the last (most recent) response
                            answer_text = await response_elements[-1].inner_text()
                        else:
                            answer_text = "Response received but could not extract text."
                        
                    except PlaywrightTimeout:
                        return {
                            "status": "timeout",
                            "provider": provider,
                            "answer_text": "",
                            "timestamp": datetime.now().isoformat(),
                            "trace_id": trace_id,
                            "error": f"Timeout after {timeout_sec} seconds",
                        }
                
                elif provider_lower == "gemini":
                    # Look for input field
                    input_selector = "textarea[placeholder*='Enter a prompt']"
                    chat_input = await page.query_selector(input_selector)
                    if not chat_input:
                        return {
                            "status": "not_logged_in",
                            "provider": provider,
                            "answer_text": "",
                            "timestamp": datetime.now().isoformat(),
                            "trace_id": trace_id,
                            "error": "Not logged in to Gemini. Please log in manually first.",
                        }
                    
                    # Type question
                    await chat_input.fill(question)
                    await asyncio.sleep(0.5)
                    
                    # Submit
                    send_button = await page.query_selector("button[aria-label*='Send']")
                    if send_button:
                        await send_button.click()
                    else:
                        await chat_input.press("Enter")
                    
                    # Wait for response
                    logger.info(f"[UI Consult] Waiting for response (timeout: {timeout_sec}s)")
                    try:
                        # Wait for response (Gemini shows in specific containers)
                        await page.wait_for_selector(
                            "div[data-message-author-role='model']",
                            timeout=timeout_sec * 1000,
                        )
                        
                        await asyncio.sleep(3)
                        
                        # Extract response
                        response_elements = await page.query_selector_all(
                            "div[data-message-author-role='model']"
                        )
                        if response_elements:
                            answer_text = await response_elements[-1].inner_text()
                        else:
                            answer_text = "Response received but could not extract text."
                        
                    except PlaywrightTimeout:
                        return {
                            "status": "timeout",
                            "provider": provider,
                            "answer_text": "",
                            "timestamp": datetime.now().isoformat(),
                            "trace_id": trace_id,
                            "error": f"Timeout after {timeout_sec} seconds",
                        }
                
                # Close page
                await page.close()
                
                return {
                    "status": "ok",
                    "provider": provider,
                    "answer_text": answer_text.strip(),
                    "timestamp": datetime.now().isoformat(),
                    "trace_id": trace_id,
                }
                
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"[UI Consult] Error: {e}", exc_info=True)
        return {
            "status": "error",
            "provider": provider,
            "answer_text": "",
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "error": str(e),
        }









