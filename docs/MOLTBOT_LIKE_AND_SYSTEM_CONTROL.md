# Moltbot-like Files and Making Daena Control Your System

## 1. Is there Moltbot inside the repo?

**No.** There are no files named "moltbot" or "Moltbot" in the Daena codebase. Moltbot is a separate open-source project. Daena does have **Moltbot-like** capabilities: browser automation, desktop automation (click/type), and web scraping. These are gated by settings and can be enabled so Daena can act more like Moltbot (control browser, and with desktop automation enabled, control your system).

---

## 2. Where are the Moltbot-like (automation) files?

All under `Daena_old_upgrade_20251213`:

| What | Path | What it does |
|------|------|----------------|
| **Desktop automation** (click, type on your PC) | `backend/tools/executors/desktop_automation_pyautogui.py` | Uses `pyautogui` to click at (x,y) and type text. **Gated by `AUTOMATION_ENABLE_DESKTOP=1`.** |
| **Browser automation** (Selenium) | `backend/tools/executors/browser_automation_selenium.py` | Headless Chrome: navigate, click, type, screenshot. **Gated by `AUTOMATION_ENABLE_BROWSER=1`.** |
| **Browser automation** (chat-facing) | `backend/services/daena_tools/browser_automation.py` | Used when you say "open browser", "go to url", "click", "fill" in chat. Can be gated by same browser setting. |
| **Web scrape** | `backend/tools/executors/web_scrape_bs4.py` | Fetch a URL and extract text/links/tables. |
| **UI consult** (Playwright) | `backend/tools/executors/ui_consult_playwright.py` | Browser automation via Playwright. |
| **Tool runner** | `backend/services/cmp_service.py` | `run_cmp_tool_action(tool_name, args, ...)` runs the executors above. |
| **Tool registry** | `backend/tools/registry.py` | Registers `browser_automation_selenium`, `desktop_automation_pyautogui`, etc. |
| **Settings** | `backend/config/settings.py` | `automation_enable_browser`, `automation_enable_desktop` (default `False`), `automation_safe_mode`, allowed domains. |

So: **the “Moltbot-like” behavior is already in the repo** – it’s the executors + CMP + Daena chat tools. By default desktop and (in some code paths) browser automation are **off** for safety.

---

## 3. What to do so Daena can “do everything” and “take operation of your system”

### Step 1: Enable automation (env or `.env`)

```env
AUTOMATION_ENABLE_BROWSER=1
AUTOMATION_ENABLE_DESKTOP=1
```

- **Browser**: Daena can use Selenium/Playwright and the chat browser tool (navigate, click, fill, screenshot).
- **Desktop**: Daena (via CMP) can run `desktop_automation_pyautogui` (click, type on the desktop). This is “take control” of your machine in the sense of sending mouse/keyboard.

### Step 2: Install optional dependencies

- **Desktop**: `pip install pyautogui`
- **Browser (Selenium)**: `pip install selenium` and Chrome/Chromium.
- **Browser (Playwright)**: `pip install playwright` and `playwright install` if you use the Playwright executor.

### Step 3: Wire Daena chat to desktop/browser actions

- **Browser**: Already wired. When you say “open browser”, “go to …”, “click …”, “fill …”, `backend/routes/daena.py` calls `daena_tools.browser_automation.daena_browser(message)`. With `AUTOMATION_ENABLE_BROWSER=1` and the right tool config, that can use the Selenium/Playwright executors.
- **Desktop**: **Wired from chat and Tool Console.** Say "click at 100 200" or "type on desktop hello" – Daena runs the desktop executor via CMP when `AUTOMATION_ENABLE_DESKTOP=1`. To have Daena “take control” of the system from chat you need to:
  - Either add **tool detection** in `daena.py`: when the user says things like “click at 100 200”, “type hello on the desktop”, call `run_cmp_tool_action("desktop_automation_pyautogui", { "action": "click", "x": 100, "y": 200 })`, etc.
  - Or add a **generic “run CMP tool”** step in the Daena flow: after LLM decides “user wants desktop action”, call `run_cmp_tool_action(...)` with the right tool and args.

So: **to make Daena like Moltbot and able to “take operation of your system” from chat:**

1. Set `AUTOMATION_ENABLE_DESKTOP=1` and `AUTOMATION_ENABLE_BROWSER=1`.
2. Install pyautogui (and browser drivers if needed).
3. Extend Daena’s tool detection (or CMP integration) so that desktop and browser actions requested in chat are translated into `run_cmp_tool_action(desktop_automation_pyautogui, ...)` and browser tool calls. Then she can “do everything” that these executors support (browser + desktop click/type) and you keep talking to her in chat.

---

## 4. Research / external links (like ChatGPT’s small links)

When Daena uses **Search** or **Deep search**, the backend sends **sources** (title + URL) in the stream. The Daena Office UI now shows these as **clickable links** below the message (e.g. “Sources: [1] Title… [2] Title…”). So you get the same kind of “small clickable links” to research/sources as in ChatGPT. If you don’t see them, ensure the response came from the search/deep_search path (e.g. use Search or Deep search, or ask a question that triggers auto-search).

---

## 5. Summary

| Question | Answer |
|----------|--------|
| Moltbot-related files in root? | No files named Moltbot. There are **Moltbot-like** files: `backend/tools/executors/desktop_automation_pyautogui.py`, `browser_automation_selenium.py`, `backend/services/daena_tools/browser_automation.py`, plus CMP and registry. |
| Where are the “Moltbot-like” parts? | Executors under `backend/tools/executors/`, Daena browser under `backend/services/daena_tools/browser_automation.py`, tool run via `backend/services/cmp_service.py`. |
| How to see sources as clickable links? | Use Search/Deep search (or ask a question that triggers auto-search); the Daena Office chat UI shows “Sources: [1] … [2] …” as clickable links below the message. |
| How to make Daena like Moltbot and control my system? | Set `AUTOMATION_ENABLE_DESKTOP=1` and `AUTOMATION_ENABLE_BROWSER=1`, install pyautogui (and browser stack), and extend Daena so chat requests for “click/type on desktop” and browser actions call the CMP desktop and browser executors. Then she can operate your system within those capabilities and you talk to her via chat. |
