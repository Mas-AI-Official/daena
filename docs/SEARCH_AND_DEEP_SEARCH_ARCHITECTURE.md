# Search & Deep Search Architecture – Decision and Design

## Why Daena Can’t “Process” Some Answers

- **R1-style reasoning**: When a question needs **live or broad knowledge** (e.g. “what’s the latest on X?”, “how does Y work in 2025?”), the local model (R1/14B or similar) may not have the data or may be outdated.
- **Desired behavior**: Daena says *“Give me a moment to search”*, runs **web search** (and optionally **deep search** with scraping), then returns a **conclusion with sources** – similar to ChatGPT/Gemini search-augmented answers.
- **Goal**: Make the most advanced **data mining and scraper** available inside Daena’s “brain” and share that capability with all LLMs and agents (via API or shared service).

---

## Option A: Build in `Ideas/MODELS_ROOT`

| Pros | Cons |
|------|------|
| Other Ideas apps can import or call the same logic | `MODELS_ROOT` is today for **model weights** (ltx, ollama, whisper, xtts) – putting a scraper there is naming-confusing |
| Single source of truth for “search + scrape” | New package: path/sys.path or install, versioning, dependency management |
| Reusable without going through Daena | Slower to ship (new repo/folder, wiring from Daena) |

**Reuse**: Other apps under Ideas could add the path and `import search_core` or call an HTTP service if we expose one. We could add e.g. `Ideas/MODELS_ROOT/search_pack/` (Python package) and have Daena depend on it.

---

## Option B: Build Inside `Daena_old_upgrade_20251213`

| Pros | Cons |
|------|------|
| One place: all chat flow, tools, and UI already in Daena | Other apps reuse only by **calling Daena’s API** (e.g. POST with `mode=deep_search`) unless we extract later |
| Reuses existing `web_search`, browser/scraper tools | — |
| Fast to ship: no new repo or package wiring | — |
| Clear ownership: “Daena’s search brain” | — |

**Reuse**: Other apps (Mas-AI, contentops, VibeAgent, etc.) can call `POST /api/v1/daena/chat/stream` with `mode: "search"` or `mode: "deep_search"` and get the same behavior. Later we can extract the core into e.g. `Ideas/search_core` and have Daena depend on it.

---

## Decision: **Build Inside Daena First**

1. **Ship faster**: Implement search + deep search as backend services and chat modes inside `Daena_old_upgrade_20251213`. No new folder or package to maintain initially.
2. **Keep MODELS_ROOT for models only**: `Ideas/MODELS_ROOT` stays for model files (ltx, ollama, whisper, xtts). If we later add a shared “search pack”, we can use a different name (e.g. `Ideas/search_core`) to avoid overloading MODELS_ROOT.
3. **Reuse via API**: Any app can use Daena’s search/deep-search by calling the chat stream API with `mode: "search"` or `mode: "deep_search"`.
4. **Future extraction**: When we want other apps to use the same logic **without** calling Daena, we can extract the core (search + scrape + synthesize) into a small package (e.g. `Ideas/search_core`) and have Daena import it; Daena remains the main consumer and exposes it via API.

---

## Design Inside Daena

### Two Modes in Chat

| Mode | Behavior |
|------|----------|
| **Search** | Quick: run `web_search` (Brave/Serper/Tavily/DuckDuckGo), take top snippets, inject into prompt, one LLM call → answer + sources. User sees “Give me a moment to search…” then the answer. |
| **Deep search** | Deeper: run search (optionally 2–3 query variants), fetch 2–5 top URLs (scrape with existing `web_scrape_bs4` or httpx+bs4), build context, one LLM synthesis → conclusion with sources. User sees “Searching and reading sources…” then the answer. |

### Components

- **`backend/services/deep_search_service.py`**
  - `search_then_answer(query, mode="search" | "deep_search")`:
    - Uses existing `web_search` (and optionally `web_scrape_bs4` for deep_search).
    - Builds a context string (snippets + optional page excerpts).
    - Calls local LLM (`generate`) with a system + user prompt to “answer using these sources” or “synthesize and conclude”.
  - Returns `{ "answer": str, "sources": list, "mode": str }`.

- **Chat API**
  - Request body extended with `mode: "search" | "deep_search" | null`.
  - When `mode` is set, stream_chat runs the deep_search_service pipeline, then streams the resulting answer (e.g. token-by-token for UX).

- **Frontend (Daena Office)**
  - Two actions: **Search** and **Deep search** (buttons or dropdown next to Send).
  - When user picks one and sends, the request includes `mode`; UI shows “Searching…” / “Reading sources…” then the streamed answer.

### Sharing With Other LLMs and Agents

- **All agents/LLMs**: They get search-augmented answers by calling Daena’s API with `mode=search` or `mode=deep_search`. No need to duplicate scraper logic in each agent.
- **Other apps under Ideas**: Same: call `POST /api/v1/daena/chat/stream` with `message` and `mode`. Optionally later, use a shared `Ideas/search_core` package if we extract the logic.

---

## Automatic search (like ChatGPT)

- **Auto-trigger**: When the user does *not* click Search/Deep search but the message looks like a question (e.g. contains "?", "what is", "how to", "want you to", "connect to", "find", "latest"), the backend **automatically** runs **Search**. Daena says "Give me a moment to search…" and returns a search-based answer.
- **Fallback when LLM says "I don't know"**: For legacy (non-streaming) chat, if the LLM response is short and contains "don't know", "can't find", "I'm not sure", the backend runs search and returns "I didn't have that in my training data, so I searched the web: …" with the search answer.
- **Query extraction**: Long messages are turned into a shorter search query (e.g. strip "i want you to"); if the first search returns nothing, a shortened query (first 6–8 words) is tried. DuckDuckGo HTML parsing has fallback patterns for different DDG layouts.

---

## Summary

| Question | Answer |
|----------|--------|
| Why can’t Daena process some answers? | Local model lacks live/broad data; we add search + deep search so she can “search then answer.” |
| MODELS_ROOT vs Daena? | **Build inside Daena** first; keep MODELS_ROOT for model files only. |
| Can other apps use it? | Yes – via Daena’s API (`mode=search` / `mode=deep_search`). Later we can extract a shared package if needed. |
| Two modes? | **Search** (quick, snippets + LLM) and **Deep search** (scrape pages + synthesize + conclude). |
| Auto-search? | Question-like messages trigger Search automatically; legacy chat falls back to search when LLM says "I don't know". |
| UI/UX / backend sync? | Backend accepts `mode`; frontend has Search / Deep search buttons; auto-search runs when no mode set but message needs search. |
