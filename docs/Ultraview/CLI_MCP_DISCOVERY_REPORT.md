# CLI / MCP Discovery Report

Date: 2026-04-30

## Verified Before Backend Went Down

- `/api/v1/mcp-sync/detected` returned 5 detected MCP definitions.
- `/api/v1/connections/mcp-registry` returned 4 registry rows.
- That proves the founder symptom was real: detection count and rendered/registered count were using different sources.
- `/api/v1/runtime/truth` was added as the replacement source and returned 22 runtime truth items during validation before the later WSL/backend restart blocker.
- Import persistence was tested with `cli_codex`: `POST /api/v1/runtime/import`, followed by `POST /api/v1/runtime/refresh`, preserved `persisted=true` and `imported_state=callable`.

## Current Discovery Model

`RuntimeTruthRegistry` now classifies:

- CLI tools: Claude, Codex, Gemini, Ollama, Node, npm, npx, Python, Docker.
- Local model endpoints: backend-local Ollama, Windows-host Ollama bridge, configured vLLM/OpenAI-compatible endpoint.
- API providers: Perplexity, Gemini, OpenAI, Anthropic.
- MCP definitions imported from CLI config via `CLIMCPDetector`.
- Daena MCP package at `packages/daena-mcp`.

## Important Truth Corrections

- Existence in a config file is `detected`, not `imported`.
- API key presence is `configured`, not `authenticated`.
- Windows-local Ollama and backend-local Ollama are separate. `localhost` inside backend is not automatically Windows localhost.
- Daena MCP package existing on disk is not persistence. It must be imported and health checked.
- Provider rows with no safe zero-cost check now use `configured_untested`, not `failed`.

## Known Runtime Findings

- Ollama Windows host bridge responded through `http://host.docker.internal:11434` and exposed `qwen2.5-coder:1.5b`.
- Backend-local Ollama at `http://localhost:11434` failed from backend context.
- Configured vLLM endpoint at `http://127.0.0.1:8080` failed connection attempts.
- Perplexity and Gemini API keys were configured from `.env`, but authentication was not verified by a zero-cost provider call.
- `gitnexus` and `local-llm` MCP definitions were detected but not callable from backend path evidence.

## Current Blocker

Live backend revalidation is blocked:

- `http://127.0.0.1:8000/health` is currently `ECONNREFUSED`.
- `wsl.exe` can list `kali-linux` but cannot execute commands (`Wsl/Service/0x8007072c`).
- Windows Python cannot import `asyncio` because `_overlapped` raises `WinError 10106`.

## Next Fix

Repair WSL/Windows runtime execution, start backend, then rerun:

1. `GET /api/v1/runtime/truth`
2. `POST /api/v1/runtime/refresh`
3. `POST /api/v1/runtime/import` for one MCP
4. Backend restart
5. Confirm persisted state survives restart
