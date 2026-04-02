"""DaenaBot — computer-control agents for Daena's EXE mode.

Phase 1 agents:
    - FileAgent:           read, write, create, list, move, archive files
    - TerminalAgent:       sandboxed shell command execution
    - BrowserAgent:        Playwright-based web interaction (CSS selectors)
    - MCPAgent:            MCP tool calls through governance

Phase 2 agents (AI-powered):
    - VisionBrowserAgent:  AI-powered browser with visual understanding (browser-use)
    - WebCrawlerAgent:     Web crawling and data extraction (crawl4ai)
"""

from app.services.daenabot._base_agent import BaseAgent
from app.services.daenabot.browser_agent import BrowserAgent
from app.services.daenabot.file_agent import FileAgent
from app.services.daenabot.mcp_agent import MCPAgent
from app.services.daenabot.terminal_agent import TerminalAgent
from app.services.daenabot.vision_browser_agent import VisionBrowserAgent
from app.services.daenabot.web_crawler_agent import WebCrawlerAgent

__all__ = [
    "BaseAgent",
    "FileAgent",
    "TerminalAgent",
    "BrowserAgent",
    "MCPAgent",
    "VisionBrowserAgent",
    "WebCrawlerAgent",
]
