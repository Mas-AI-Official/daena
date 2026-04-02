"""WebCrawlerAgent -- AI-powered web crawling and data extraction.

Uses crawl4ai to turn websites into clean, LLM-ready markdown.
Supports single-page extraction, multi-page deep crawling,
and structured data extraction with AI.

This agent gives Daena the ability to:
- Research companies, products, and competitors
- Extract structured data from web pages
- Crawl entire sites and produce knowledge summaries
- Feed web data into department workflows (Marketing, Sales, Research)

Governance tiers:
    - Single page read: T0-T1 (READ)
    - Multi-page crawl: T2 (EXECUTE, resource-intensive)
    - Structured extraction: T1 (READ)
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)

_CRAWL_TIMEOUT = 60  # seconds per page
_MAX_PAGES = 20  # Max pages in a deep crawl


class WebCrawlerAgent(BaseAgent):
    """Web crawling agent that extracts clean content from websites.

    Uses crawl4ai for async crawling with anti-bot detection,
    JavaScript rendering, and markdown conversion.

    Operations:
        extract_page: Extract content from a single URL as markdown
        deep_crawl: Crawl multiple pages from a site
        extract_structured: Extract specific data fields from a page
        research_topic: Search and extract information about a topic
    """

    agent_name = "web_crawler"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "extract_page": "READ",
        "deep_crawl": "EXECUTE",
        "extract_structured": "READ",
        "research_topic": "READ",
    }

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        ops = {
            "extract_page": self.extract_page,
            "deep_crawl": self.deep_crawl,
            "extract_structured": self.extract_structured,
            "research_topic": self.research_topic,
        }
        fn = ops.get(operation)
        if fn is None:
            raise ValueError(
                f"WebCrawlerAgent: unknown operation '{operation}'. "
                f"Supported: {list(ops)}"
            )
        return await fn(**params)

    # -- Operations --------------------------------------------------------

    async def extract_page(
        self,
        url: str,
        include_links: bool = False,
        include_images: bool = False,
    ) -> dict[str, Any]:
        """Extract content from a single URL as clean markdown.

        Args:
            url: URL to extract content from.
            include_links: Whether to preserve links in markdown.
            include_images: Whether to include image descriptions.
        """
        self._validate_url(url)
        logger.info("web_crawler.extract_page", url=url)

        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

            config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=not include_links,
                exclude_external_images=not include_images,
            )

            async with AsyncWebCrawler() as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=_CRAWL_TIMEOUT,
                )

            if result.success:
                return self._result("extract_page", {
                    "url": url,
                    "title": result.metadata.get("title", "") if result.metadata else "",
                    "markdown": result.markdown[:10000] if result.markdown else "",
                    "word_count": len((result.markdown or "").split()),
                    "links_count": len(result.links.get("internal", [])) if result.links else 0,
                    "success": True,
                })
            else:
                return self._error(
                    "extract_page",
                    f"Failed to crawl {url}: {result.error_message}",
                )

        except asyncio.TimeoutError:
            return self._error("extract_page", f"Crawl timed out after {_CRAWL_TIMEOUT}s")
        except ImportError:
            return await self._fallback_extract(url)
        except Exception as exc:
            logger.warning("web_crawler.extract_page.error", error=str(exc))
            return self._error("extract_page", str(exc))

    async def deep_crawl(
        self,
        url: str,
        max_pages: int = 5,
        same_domain_only: bool = True,
    ) -> dict[str, Any]:
        """Crawl multiple pages from a site.

        Args:
            url: Starting URL.
            max_pages: Maximum pages to crawl.
            same_domain_only: Only follow links on the same domain.
        """
        self._validate_url(url)
        max_pages = min(max_pages, _MAX_PAGES)
        logger.info("web_crawler.deep_crawl", url=url, max_pages=max_pages)

        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
            from urllib.parse import urlparse

            domain = urlparse(url).netloc
            visited: set[str] = set()
            to_visit: list[str] = [url]
            pages: list[dict[str, Any]] = []

            config = CrawlerRunConfig(
                word_count_threshold=10,
            )

            async with AsyncWebCrawler() as crawler:
                while to_visit and len(pages) < max_pages:
                    current_url = to_visit.pop(0)
                    if current_url in visited:
                        continue
                    visited.add(current_url)

                    try:
                        result = await asyncio.wait_for(
                            crawler.arun(url=current_url, config=config),
                            timeout=_CRAWL_TIMEOUT,
                        )

                        if result.success:
                            page_data = {
                                "url": current_url,
                                "title": result.metadata.get("title", "") if result.metadata else "",
                                "markdown_preview": (result.markdown or "")[:2000],
                                "word_count": len((result.markdown or "").split()),
                            }
                            pages.append(page_data)

                            # Collect internal links for further crawling
                            if result.links and same_domain_only:
                                internal = result.links.get("internal", [])
                                for link in internal:
                                    href = link.get("href", "") if isinstance(link, dict) else str(link)
                                    if href and urlparse(href).netloc == domain:
                                        if href not in visited:
                                            to_visit.append(href)
                    except (asyncio.TimeoutError, Exception) as exc:
                        logger.warning(
                            "web_crawler.deep_crawl.page_error",
                            url=current_url, error=str(exc),
                        )
                        continue

            return self._result("deep_crawl", {
                "starting_url": url,
                "pages_crawled": len(pages),
                "pages": pages,
                "urls_discovered": len(visited),
            })

        except ImportError:
            return self._error(
                "deep_crawl",
                "crawl4ai not available. Install with: pip install crawl4ai",
            )
        except Exception as exc:
            return self._error("deep_crawl", str(exc))

    async def extract_structured(
        self,
        url: str,
        fields: list[str] | None = None,
        schema_description: str = "",
    ) -> dict[str, Any]:
        """Extract specific structured data from a page.

        Args:
            url: URL to extract from.
            fields: List of field names to extract (e.g., ["price", "title", "description"]).
            schema_description: Natural language description of what to extract.
        """
        self._validate_url(url)
        logger.info("web_crawler.extract_structured", url=url, fields=fields)

        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

            config = CrawlerRunConfig(
                word_count_threshold=5,
            )

            async with AsyncWebCrawler() as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=_CRAWL_TIMEOUT,
                )

            if not result.success:
                return self._error(
                    "extract_structured",
                    f"Failed to crawl {url}: {result.error_message}",
                )

            # Return raw markdown for LLM to structure
            # The orchestrator's LLM will parse this based on fields/schema
            return self._result("extract_structured", {
                "url": url,
                "raw_content": (result.markdown or "")[:8000],
                "requested_fields": fields or [],
                "schema_description": schema_description,
                "note": "Raw content extracted. LLM will structure based on requested fields.",
            })

        except ImportError:
            return await self._fallback_extract(url)
        except Exception as exc:
            return self._error("extract_structured", str(exc))

    async def research_topic(
        self,
        topic: str,
        urls: list[str] | None = None,
        max_sources: int = 3,
    ) -> dict[str, Any]:
        """Research a topic by crawling multiple sources.

        Args:
            topic: Topic to research.
            urls: Optional list of URLs to research. If None, uses provided URLs only.
            max_sources: Maximum sources to process.
        """
        logger.info("web_crawler.research_topic", topic=topic, urls=urls)

        if not urls:
            return self._error(
                "research_topic",
                "No URLs provided. Provide specific URLs to research.",
            )

        sources: list[dict[str, Any]] = []
        for url in urls[:max_sources]:
            try:
                result = await self.extract_page(url=url)
                if result.get("success"):
                    output = result.get("output", {})
                    sources.append({
                        "url": url,
                        "title": output.get("title", ""),
                        "content": output.get("markdown", "")[:3000],
                    })
            except Exception as exc:
                logger.warning(
                    "web_crawler.research_topic.source_error",
                    url=url, error=str(exc),
                )

        return self._result("research_topic", {
            "topic": topic,
            "sources_processed": len(sources),
            "sources": sources,
        })

    # -- Fallback ----------------------------------------------------------

    async def _fallback_extract(self, url: str) -> dict[str, Any]:
        """Fallback to httpx + basic HTML parsing when crawl4ai unavailable."""
        logger.warning("web_crawler.fallback_to_httpx")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            # Basic HTML to text
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts: list[str] = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "noscript"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "noscript"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip:
                        stripped = data.strip()
                        if stripped:
                            self.text_parts.append(stripped)

            parser = TextExtractor()
            parser.feed(resp.text)
            text = "\n".join(parser.text_parts)

            return self._result("extract_page", {
                "url": url,
                "fallback": True,
                "markdown": text[:5000],
                "word_count": len(text.split()),
                "note": "Used basic HTTP fallback. Install crawl4ai for better extraction.",
            })
        except Exception as exc:
            return self._error("extract_page", f"Fallback extraction failed: {exc}")

    # -- Validation --------------------------------------------------------

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject non-HTTP(S) URLs."""
        lower = url.lower().strip()
        if not any(lower.startswith(s) for s in ("http://", "https://")):
            raise ValueError(
                f"URL scheme not allowed: '{url}'. Only http:// and https:// permitted."
            )
