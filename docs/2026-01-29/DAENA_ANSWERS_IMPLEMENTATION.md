# Daena Answers – Implementation Summary

**Date:** 2026-01-29  
**Reference:** User’s 8-point list (report bug.txt + screenshots)

---

## 1. Tools under your permission

- Execution Layer already gates all tools: allowlist, approval for risky tools, audit log, EXECUTION_TOKEN.
- Daena only runs tools through this layer; you control token and lockdown (Incident Room).
- No code change; design is already permission-based.

---

## 2. Link type like ChatGPT (small, clickable, collapsible)

- **Status:** Not implemented in this pass.
- **Suggestion:** In the chat UI, render links as small pill/chip elements, and add a “Compact links” or “Show links inline” option. Requires frontend change in the chat template and message renderer.

---

## 3. Chat: show links vs answer only

- **Status:** Not implemented in this pass.
- **Suggestion:** Add a toggle (e.g. “Show sources/links” / “Answer only”) that shows or hides link blocks in assistant messages. Needs chat template + optional backend flag for “include_sources”.

---

## 4. Daena aware of all files, read/understand, modify with permission, learn

- Execution Layer already has `filesystem_read` (workspace allowlist) and `filesystem_write` / destructive tools behind approval.
- NBMF/memory and learning are in place; “learn over time” is architectural (memory_service, brain store).
- **Suggestion:** Keep using Execution Layer for file access; add a “workspace index” or “file list” API if you want Daena to explicitly “see” all files (e.g. for RAG or planning). Not changed in this pass.

---

## 5. deepseek-r1:7b “1 api 0 token” and r1 14b not in list / model downloader

**Done:**

- **Model downloader** (`model downloader/download_models.py`):
  - Already includes **deepseek-r1:14b** and **deepseek-r1:7b** in `OLLAMA_MODELS`.
  - **MODELS_ROOT** is configurable via env: `MODELS_ROOT` or `DAENA_MODELS_ROOT` (default `D:\Ideas\MODELS_ROOT`). Ollama models go to `MODELS_ROOT/ollama`.
  - Added `model downloader/README.md` with run instructions.
- **Brain & API list:** Model list comes from Ollama `api/tags`. After you run the downloader (or `ollama pull deepseek-r1:14b`), **deepseek-r1:14b** appears in the list. No backend change needed for “r1 14b in list.”
- **“1 api 0 token”:** That’s usage stats (one call, zero tokens for that model). It’s correct if you only triggered one test call; token counting depends on your usage endpoint. No bug fix applied.

---

## 6. Cloud LLM APIs in frontend and synced with backend

**Done:**

- **Backend** (`backend/routes/brain_status.py`):
  - Cloud API keys and enabled state are stored in DB (`SystemConfig`, key `cloud_apis`). Keys are not returned to the client; only “has key” and “enabled” are.
  - **DeepSeek** added as a cloud provider: `deepseek/deepseek-chat` in the default cloud list; `set_cloud_api_key` and `set_cloud_api_toggle` accept `provider=deepseek`.
- **Frontend** (Brain & API tab): Cloud section already calls `POST /api/v1/brain/cloud/{provider}/key` and `.../toggle`. Save/toggle are wired; with DeepSeek added, it’s in sync with the backend.
- **Security:** Keys live in DB only; frontend never receives raw keys. Use env or secrets for production if you prefer not to store keys in DB.

---

## 7. Registry library (registry.ollama.ai/library) failing / purpose / remove or fix

**Done:**

- **What it is:** “Trained” models in Brain & API are built from `local_brain/manifests/<registry>/<model>`. If you have a folder like `manifests/registry.ollama.ai/library`, it was shown as a runnable model; it’s a registry/metadata placeholder, not an Ollama model, so it showed OFFLINE and “Failed to toggle.”
- **Change:** In `backend/routes/brain_status.py`, when building the trained list, entries whose name contains **`registry.ollama.ai`** are **excluded**. So “registry.ollama.ai/library” no longer appears in the UI, and the failing toggle goes away.
- **Pipeline:** The pipeline uses Ollama models (from `api/tags`) and cloud APIs; the manifests “trained” list is for custom/trained blobs. Keeping the list but hiding registry placeholders is the chosen fix.

---

## 8. Brain duplicated, menu/sector bad view, optimize dashboard

**Current state:**

- **Brain in one place:** App Setup text says “Brain & API is configured in the Brain & API tab of the Control Plane (no duplicate card here).” So Brain is only configured under Control Plane → Brain & API.
- **Embed mode:** When Control Plane loads tabs in iframes (e.g. `?embed=1`), `base.html` already **hides the sidebar** and uses full-width content (`.embed-mode`). So if you see two sidebars, the iframe may have been loaded without `embed=1` in the URL; Control Plane uses `?embed=1` in iframe `src`.
- **Layout overlap:** “Connection comes over each other” / “Connection Status” overlapping “UI wiring audit” is a CSS/layout issue on the App Setup (or Integrations) view. Not changed in this pass; recommend adjusting the App Setup card grid and moving “Connection Status” so it doesn’t overlap text.
- **Rebuild/wire:** A full redesign of Control Plane and App Setup (new layout, no legacy sidebar reuse) was not done; only the above fixes and clarifications were applied.

---

## Summary of code changes

| Area | Change |
|------|--------|
| **brain_status.py** | Exclude trained entries with `registry.ollama.ai` in name; add DeepSeek to cloud list and to key/toggle provider allowlist. |
| **model downloader** | `MODELS_ROOT` / `DAENA_MODELS_ROOT` env support; README with deepseek-r1:14b and run instructions. |
| **Docs** | This file + `model downloader/README.md`. |

---

## Suggested next steps (not done)

- **Chat:** Small link style + “show links vs answer only” toggle (points 2 and 3).
- **App Setup / Control Plane:** Adjust layout so Connection Status and cards don’t overlap; optional full redesign of embedded tabs (point 8).
- **Workspace awareness:** Optional “list/index workspace files” API for Daena (point 4).
