"""VisionBrowserAgent -- AI-powered browser automation with visual understanding.

Uses browser-use library to let LLMs see and interact with web pages
through screenshots rather than CSS selectors. This gives Daena the
ability to navigate unknown websites, fill forms, extract data, and
complete multi-step web tasks autonomously.

Governance tiers:
    - Research/read (browse, extract): T1-T2
    - Form interaction (fill, click): T2-T3
    - External submission: T3 (Hard Law #5)

BACKGROUND PATH ONLY for autonomous multi-step tasks.
Direct single-step operations can run in hot path.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)

# Max time for a single browser-use task
_TASK_TIMEOUT = 120  # seconds
_MAX_STEPS = 25  # Max autonomous steps per task


class VisionBrowserAgent(BaseAgent):
    """AI-powered browser agent that sees and understands web pages.

    Uses browser-use for visual navigation and interaction. Falls back
    to basic Playwright if browser-use is unavailable.

    Operations:
        browse_and_act: Execute a natural-language goal on a web page
        research_url: Navigate to URL and extract structured information
        screenshot_analyze: Take screenshot and describe what's visible
        fill_form_smart: Fill a form using visual understanding (no selectors needed)
        multi_step_task: Execute a complex multi-step web task
    """

    agent_name = "vision_browser"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "browse_and_act": "EXECUTE",
        "research_url": "READ",
        "screenshot_analyze": "READ",
        "fill_form_smart": "WRITE_FILE",
        "multi_step_task": "EXECUTE",
    }

    def __init__(self, llm_provider: str = "ollama") -> None:
        self._llm_provider = llm_provider
        self._browser = None
        self._agent = None

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        ops = {
            "browse_and_act": self.browse_and_act,
            "research_url": self.research_url,
            "screenshot_analyze": self.screenshot_analyze,
            "fill_form_smart": self.fill_form_smart,
            "multi_step_task": self.multi_step_task,
        }
        fn = ops.get(operation)
        if fn is None:
            raise ValueError(
                f"VisionBrowserAgent: unknown operation '{operation}'. "
                f"Supported: {list(ops)}"
            )
        return await fn(**params)

    # -- Core operations ---------------------------------------------------

    async def browse_and_act(
        self,
        goal: str,
        url: str | None = None,
        max_steps: int = 10,
    ) -> dict[str, Any]:
        """Execute a natural-language goal on a web page.

        Args:
            goal: What to accomplish (e.g., "Find the pricing page and extract all plan details")
            url: Starting URL. If None, agent starts from current page or searches.
            max_steps: Maximum autonomous steps before stopping.
        """
        max_steps = min(max_steps, _MAX_STEPS)
        logger.info("vision_browser.browse_and_act", goal=goal, url=url)

        try:
            agent = await self._get_agent()
            task = goal
            if url:
                task = f"Go to {url} and then: {goal}"

            result = await asyncio.wait_for(
                agent.run(task=task, max_steps=max_steps),
                timeout=_TASK_TIMEOUT,
            )

            # Extract result content
            output = self._extract_result(result)
            logger.info(
                "vision_browser.browse_and_act.done",
                steps=output.get("steps_taken", 0),
                success=output.get("success", False),
            )
            return self._result("browse_and_act", output)

        except asyncio.TimeoutError:
            return self._error("browse_and_act", f"Task timed out after {_TASK_TIMEOUT}s")
        except ImportError:
            return await self._fallback_browse(goal, url)
        except Exception as exc:
            logger.warning("vision_browser.browse_and_act.error", error=str(exc))
            return self._error("browse_and_act", str(exc))

    async def research_url(
        self,
        url: str,
        question: str = "",
        extract_links: bool = False,
    ) -> dict[str, Any]:
        """Navigate to URL and extract structured information.

        Args:
            url: URL to research.
            question: Specific question to answer from the page content.
            extract_links: Whether to also extract all links from the page.
        """
        self._validate_url(url)
        logger.info("vision_browser.research_url", url=url, question=question)

        try:
            agent = await self._get_agent()
            task = f"Go to {url}. "
            if question:
                task += f"Answer this question from the page: {question}"
            else:
                task += "Extract the main content, key information, and any important details."
            if extract_links:
                task += " Also list all important links on the page."

            result = await asyncio.wait_for(
                agent.run(task=task, max_steps=8),
                timeout=_TASK_TIMEOUT,
            )

            output = self._extract_result(result)
            output["url"] = url
            output["question"] = question
            return self._result("research_url", output)

        except asyncio.TimeoutError:
            return self._error("research_url", f"Research timed out after {_TASK_TIMEOUT}s")
        except ImportError:
            return await self._fallback_research(url, question)
        except Exception as exc:
            logger.warning("vision_browser.research_url.error", error=str(exc))
            return self._error("research_url", str(exc))

    async def screenshot_analyze(
        self,
        url: str,
        analysis_prompt: str = "Describe what you see on this page.",
    ) -> dict[str, Any]:
        """Take a screenshot of a URL and analyze it with vision LLM.

        Args:
            url: URL to screenshot.
            analysis_prompt: What to analyze in the screenshot.
        """
        self._validate_url(url)
        logger.info("vision_browser.screenshot_analyze", url=url)

        try:
            agent = await self._get_agent()
            task = (
                f"Go to {url}. Take a careful look at the page. "
                f"{analysis_prompt}"
            )
            result = await asyncio.wait_for(
                agent.run(task=task, max_steps=5),
                timeout=60,
            )
            output = self._extract_result(result)
            output["url"] = url
            return self._result("screenshot_analyze", output)

        except ImportError:
            return await self._fallback_research(url, analysis_prompt)
        except Exception as exc:
            return self._error("screenshot_analyze", str(exc))

    async def fill_form_smart(
        self,
        url: str,
        form_data: dict[str, str],
        submit: bool = False,
    ) -> dict[str, Any]:
        """Fill a form using visual understanding (no CSS selectors needed).

        Args:
            url: URL containing the form.
            form_data: Field label -> value mapping.
            submit: Whether to submit the form after filling.
        """
        self._validate_url(url)
        logger.info("vision_browser.fill_form_smart", url=url, fields=len(form_data))

        try:
            agent = await self._get_agent()
            fields_desc = "\n".join(
                f"- {label}: {value}" for label, value in form_data.items()
            )
            task = (
                f"Go to {url}. Fill in the form with the following information:\n"
                f"{fields_desc}\n"
            )
            if submit:
                task += "After filling all fields, submit the form."
            else:
                task += "Fill the fields but do NOT submit the form."

            result = await asyncio.wait_for(
                agent.run(task=task, max_steps=15),
                timeout=_TASK_TIMEOUT,
            )
            output = self._extract_result(result)
            output["fields_requested"] = len(form_data)
            output["submitted"] = submit
            return self._result("fill_form_smart", output)

        except ImportError:
            return self._error(
                "fill_form_smart",
                "browser-use not available. Use browser.fill_form with CSS selectors.",
            )
        except Exception as exc:
            return self._error("fill_form_smart", str(exc))

    async def multi_step_task(
        self,
        task_description: str,
        starting_url: str | None = None,
        max_steps: int = 20,
    ) -> dict[str, Any]:
        """Execute a complex multi-step web task.

        Args:
            task_description: Detailed description of the multi-step task.
            starting_url: Optional URL to start from.
            max_steps: Maximum number of steps.
        """
        max_steps = min(max_steps, _MAX_STEPS)
        logger.info("vision_browser.multi_step_task", task=task_description[:100])

        try:
            agent = await self._get_agent()
            task = task_description
            if starting_url:
                task = f"Start at {starting_url}. Then: {task_description}"

            result = await asyncio.wait_for(
                agent.run(task=task, max_steps=max_steps),
                timeout=_TASK_TIMEOUT * 2,  # Double timeout for complex tasks
            )
            output = self._extract_result(result)
            return self._result("multi_step_task", output)

        except asyncio.TimeoutError:
            return self._error(
                "multi_step_task",
                f"Complex task timed out after {_TASK_TIMEOUT * 2}s",
            )
        except ImportError:
            return self._error(
                "multi_step_task",
                "browser-use not available for multi-step tasks.",
            )
        except Exception as exc:
            return self._error("multi_step_task", str(exc))

    # -- Agent lifecycle ---------------------------------------------------

    async def _get_agent(self):
        """Get or create the browser-use Agent instance."""
        if self._agent is not None:
            return self._agent

        from browser_use import Agent
        from browser_use import Browser, BrowserConfig

        # Configure browser
        browser_config = BrowserConfig(
            headless=True,
            disable_security=False,
        )
        self._browser = Browser(config=browser_config)

        # Get LLM based on configured provider
        llm = self._create_llm()

        self._agent = Agent(
            task="placeholder",  # Will be overridden per operation
            llm=llm,
            browser=self._browser,
            max_failures=3,
        )
        return self._agent

    def _create_llm(self):
        """Create LLM instance for browser-use based on Daena's configured provider.

        browser-use supports langchain LLM interfaces. We create one based
        on the configured provider preference.
        """
        try:
            # Try Ollama first (local, free)
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model="llama3.1:8b",
                base_url="http://localhost:11434",
                temperature=0.1,
            )
        except ImportError:
            pass

        try:
            # Fall back to OpenAI-compatible (works with many providers)
            from langchain_openai import ChatOpenAI
            import os
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                return ChatOpenAI(
                    model="gpt-4o",
                    api_key=api_key,
                    temperature=0.1,
                )
        except ImportError:
            pass

        try:
            # Try Anthropic
            from langchain_anthropic import ChatAnthropic
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if api_key:
                return ChatAnthropic(
                    model="claude-sonnet-4-20250514",
                    api_key=api_key,
                    temperature=0.1,
                )
        except ImportError:
            pass

        raise ImportError(
            "No LLM provider available for VisionBrowserAgent. "
            "Install langchain-ollama, langchain-openai, or langchain-anthropic."
        )

    async def close(self) -> None:
        """Release browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        self._agent = None

    # -- Fallbacks ---------------------------------------------------------

    async def _fallback_browse(
        self, goal: str, url: str | None,
    ) -> dict[str, Any]:
        """Fallback to basic Playwright when browser-use is unavailable."""
        logger.warning("vision_browser.fallback_to_playwright")
        from app.services.daenabot.browser_agent import BrowserAgent

        basic = BrowserAgent(headless=True)
        try:
            if url:
                nav_result = await basic.navigate(url)
                text_result = await basic.extract_text()
                return self._result("browse_and_act", {
                    "fallback": True,
                    "url": url,
                    "title": nav_result.get("output", {}).get("title", ""),
                    "text_preview": str(
                        text_result.get("output", {}).get("text", "")
                    )[:2000],
                    "note": "Used basic Playwright fallback. Install browser-use for AI vision.",
                })
            return self._error("browse_and_act", "No URL provided and browser-use unavailable.")
        finally:
            await basic.close()

    async def _fallback_research(
        self, url: str, question: str,
    ) -> dict[str, Any]:
        """Fallback research using basic text extraction."""
        logger.warning("vision_browser.fallback_research")
        from app.services.daenabot.browser_agent import BrowserAgent

        basic = BrowserAgent(headless=True)
        try:
            await basic.navigate(url)
            text_result = await basic.extract_text()
            text = str(text_result.get("output", {}).get("text", ""))[:3000]
            return self._result("research_url", {
                "fallback": True,
                "url": url,
                "text": text,
                "question": question,
                "note": "Used basic text extraction. Install browser-use for AI-powered research.",
            })
        finally:
            await basic.close()

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _extract_result(agent_result) -> dict[str, Any]:
        """Extract structured output from browser-use Agent result."""
        if agent_result is None:
            return {"success": False, "content": "", "steps_taken": 0}

        # browser-use returns an AgentHistoryList
        content = ""
        steps_taken = 0

        if hasattr(agent_result, "final_result"):
            content = str(agent_result.final_result() or "")
        elif hasattr(agent_result, "last_result"):
            content = str(agent_result.last_result() or "")
        elif isinstance(agent_result, str):
            content = agent_result
        else:
            content = str(agent_result)

        if hasattr(agent_result, "history"):
            steps_taken = len(agent_result.history)
        elif hasattr(agent_result, "__len__"):
            steps_taken = len(agent_result)

        return {
            "success": bool(content),
            "content": content[:5000],  # Cap output size
            "steps_taken": steps_taken,
        }

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject non-HTTP(S) URLs."""
        lower = url.lower().strip()
        if not any(lower.startswith(s) for s in ("http://", "https://")):
            raise ValueError(
                f"URL scheme not allowed: '{url}'. Only http:// and https:// permitted."
            )
