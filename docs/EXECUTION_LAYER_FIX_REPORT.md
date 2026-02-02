# Execution Layer & MODELS_ROOT — Fix Report

## 1) SECURITY — Execution token

| Fix | File(s) |
|-----|--------|
| When `EXECUTION_TOKEN` env is set, require `X-Execution-Token` header on all `/api/v1/execution/*` endpoints. | `backend/config/settings.py` (added `execution_token`), `backend/routes/execution_layer.py` (added `verify_execution_token` dependency and `Depends(verify_execution_token)` on all execution routes) |
| Default: if token is unset, no auth (local dev). If set and header missing/invalid → 401. | `backend/routes/execution_layer.py` |
| Dashboard JS adds header from `sessionStorage.execution_token`; on 401 clears and throws. | `frontend/templates/dashboard.html` (`executionHeaders()`, `executionFetch()`, use in `loadExecutionLayer` and `toggleExecutionTool`) |

## 2) APPROVAL MODE — Enforced

| Fix | File(s) |
|-----|--------|
| When `approval_mode == "require_approval"` and tool `risk_level >= medium`, block unless valid `approval_id`. | `backend/routes/execution_layer.py` (in `execution_run`: read config, get risk, call `consume_approval`; 403 if required and missing) |
| `POST /api/v1/execution/approve?tool_name=...` creates short-lived approval (TTL 300s), returns `approval_id`. | `backend/routes/execution_layer.py` |
| Risk levels and approval store. | `backend/services/execution_layer_config.py` (`TOOL_RISK_LEVELS`, `create_approval`, `consume_approval`, `get_tool_risk_level`) |
| `RunRequest` includes optional `approval_id`. | `backend/routes/execution_layer.py` |

## 3) BUDGET GUARD — Enforced

| Fix | File(s) |
|-----|--------|
| Playbook execution capped by `max_steps_per_run` (break loop when step index >= max). | `backend/services/tool_playbooks.py` |
| Per-step retries capped by `max_retries_per_tool` (min(step.max_retries, config)). | `backend/services/tool_playbooks.py` |

## 4) TOOL SET — Missing tools added

| Tool | File(s) | Behavior |
|------|--------|----------|
| `filesystem_read` | `backend/tools/registry.py` | Workspace allowlist only; path resolved under `execution_workspace_root`; read text. |
| `filesystem_write` | `backend/tools/registry.py` | Workspace allowlist; text only (deny binary). |
| `git_diff` | `backend/tools/registry.py` | `git diff --no-color` in workspace. |
| `apply_patch` | `backend/tools/registry.py` | Unified diff via `git apply --check` then `git apply -`. |
| `shell_exec` | `backend/tools/registry.py` | Allowlist only (`settings.shell_allowlist`: e.g. `git `, `python -m `, `pip list`, etc.). |

Helpers: `_workspace_root()`, `_resolve_workspace_path()` in `backend/tools/registry.py`. Config: `config/execution_layer_config.json` and `_DEFAULT` in `backend/services/execution_layer_config.py` updated with new tools and risk levels.

## 5) MODELS_ROOT — Standardized

| Fix | File(s) |
|-----|--------|
| `ollama_models_path` and `xtts_model_path` derived from `models_root` when unset. | `backend/config/settings.py` (model validator) |
| TTS/XTTS: `tts/xtts.py` uses `settings.xtts_model_path` / `settings.models_root` (no hardcoded D:/Ideas/Daena). | `tts/xtts.py` |
| Voice: `backend/config/voice_config.py` adds `MODELS_ROOT/xtts/voices/daena_voice.wav`; `get_daena_voice_path()` prefers it. | `backend/config/voice_config.py` |
| Settings: `models_root`, `xtts_*`, `ollama_reasoning_model`, `ollama_reasoning_fallback`, `execution_workspace_root`, `shell_allowlist`. | `backend/config/settings.py` |
| BAT: `START_DAENA.bat` sets `MODELS_ROOT`, `OLLAMA_MODELS`, `TTS_HOME` and passes them to backend window. | `START_DAENA.bat` |
| New `start_xtts.bat` uses `MODELS_ROOT` (like contentops-core). | `start_xtts.bat` |

## 6) Requirements & environment

| Fix | File(s) |
|-----|--------|
| `soundfile>=0.12.1` and optional TTS note. | `requirements.txt` |
| `.env.example`: `MODELS_ROOT`, `EXECUTION_TOKEN`, XTTS, Ollama/reasoning models, execution workspace, shell allowlist. | `.env.example` (new) |

## 7) New smoke test

| Item | File |
|------|------|
| Validates: tools list (with token when required), POST approve, apply_patch dry_run, git_status. | `scripts/smoke_execution_layer_v2.py` |
| Usage: `python scripts/smoke_execution_layer_v2.py [--base URL] [--token TOKEN]`. Set `EXECUTION_TOKEN` to test token auth. | — |

---

## Quick “does it really work?” checks

1. **Token**: Set `EXECUTION_TOKEN=secret` and restart backend. Call `GET /api/v1/execution/tools` without header → 401. With `X-Execution-Token: secret` → 200.
2. **Approval**: Set config `approval_mode` to `require_approval`. Call `POST /api/v1/execution/run` with `tool_name=apply_patch` and no `approval_id` → 403. Call `POST /api/v1/execution/approve?tool_name=apply_patch`, then run with returned `approval_id` → allowed.
3. **Budget**: Run a playbook with more steps than `max_steps_per_run` → execution stops at cap.
4. **Tools**: Toggle a tool off in dashboard, then run it → “tool disabled”. Run `apply_patch` with `dry_run: true` → audit log entry, no file change.
5. **MODELS_ROOT**: Set `MODELS_ROOT` to a different path; start backend; confirm Ollama/XTTS paths use it (logs or `/api/v1/brain/status`).
