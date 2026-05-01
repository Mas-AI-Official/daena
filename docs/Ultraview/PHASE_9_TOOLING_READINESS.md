# Phase 9A — Tooling Readiness Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction interaction-audit task
**Scope:** Yes/no with evidence on every probe required to execute Phases 9B–10
**Mode:** read-only audit; no installs performed in this phase
**Status one-liner:** Three of five probes are green out-of-the-box; OpenAPI exposure is green statically (live fetch deferred — backend not running locally); Schemathesis is the only missing tool. The hand-written axios client should be kept; layered-typed-types is the right next step, not full client regeneration.

---

## 1. Playwright MCP available?

**Yes.** Plugin namespace `mcp__plugin_playwright_playwright__browser_*` is enumerated in this session's deferred-tools manifest (32 tools: navigate, click, fill, snapshot, screenshot, network requests, console messages, evaluate, etc.). The Microsoft `@playwright/mcp` plugin is wired at the Claude Code level — no per-project install needed.

**Action:** none. Phase 9C can drive flows directly via MCP without `claude mcp add`.

> Note: `mcp__chrome-devtools__*` is also available (40+ tools). For Daena flows, Playwright MCP is preferred — it has `browser_snapshot` (DOM-aware action targeting) which is more deterministic for SPA testing than Chrome DevTools' coordinate-based `click`.

## 2. Playwright E2E (project) available?

**Yes.**
- `frontend/package.json:32` — `"@playwright/test": "^1.58.2"` in devDependencies.
- `frontend/playwright.config.ts:1-19` — config exists.
- `frontend/package.json:11-12` — scripts exposed: `npm run test:e2e` and `test:e2e:headed`.
- Existing specs:
  - `frontend/e2e/daena-flow.spec.ts` — 6-step user journey (register → login → chat → departments → settings toggle → dashboard).
  - `frontend/e2e/screenshot-all.spec.ts` — navigates 19 protected routes, captures screenshots and console errors.

**Action:** none for tooling. Spec coverage is thin (only 8 unique flows total) — Phase 9C will add focused traces and Phase 10 will add regression coverage for fixes.

## 3. Trace recording works?

**Yes (configured).**
- `frontend/playwright.config.ts:13` — `screenshot: 'only-on-failure'`.
- `frontend/playwright.config.ts:14` — `trace: 'retain-on-failure'`.
- `frontend/playwright.config.ts:5` — 60 s test timeout, 10 s expect timeout.

Trace artifacts will be written to `frontend/test-results/<spec>/trace.zip` on failure. Viewer: `npx playwright show-trace test-results/.../trace.zip`. Phase 9C runs will use `--trace on` to force traces on every flow, not just failures, so we capture the network/console even for "passing" flows that may be silently broken at the UI layer.

**Caveat:** trace recording requires the dev server (`vite` on `:5173`) and backend (`uvicorn` on `:8000`) to be running. As of this report, neither is up locally — see §4.

## 4. OpenAPI schema available?

**Yes (statically), unverified live.**

Static evidence:
- `backend/app/main.py:978-985`:
  ```python
  app = FastAPI(
      ...
      docs_url="/docs" if settings.debug else None,
      redoc_url="/redoc" if settings.debug else None,
  )
  ```
  `openapi_url` is **not** overridden, so it defaults to `/openapi.json` regardless of `debug`. The schema endpoint is ALWAYS exposed; only the human Swagger/ReDoc UI is gated on debug.
- `backend/app/api/v1/__init__.py:11-65` — 51 router modules registered under `/api/v1` prefix. This is the surface Phase 9D will diff against the UI's actual call sites.

Live probe:
```
$ curl -fsS -m 3 http://localhost:8000/openapi.json
curl: (7) Failed to connect to localhost port 8000
```
The backend is not running locally right now. Once started, `/openapi.json` will return the live spec.

**Action for Phase 9D:** start backend (`backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`) and dump the schema:
```
curl -fsS http://localhost:8000/openapi.json -o /tmp/daena-openapi.json
```
Then run the contract-diff script (to be written in 9D) against the 51-router static map.

## 5. Schemathesis runnable?

**No (not installed).**
- `backend/pyproject.toml:55-63` — dev deps include `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `ruff`, `mypy`. **No `schemathesis`.**
- No `requirements*.txt` files found at repo root.

**Recommendation:** install in dev-only mode for Phase 9D:
```
backend/.venv/Scripts/python.exe -m pip install schemathesis
```
Run scope must stay strictly local: `schemathesis run http://localhost:8000/openapi.json --base-url http://localhost:8000` against a dev backend with `APP_ENV=development` and a disposable SQLite DB. **Do not point Schemathesis at the cloud `daena-v2` deployment** — fuzz tests would create real audit rows, real approval-queue items, and could trip rate limits or governance gates.

Schemathesis adds value *only* if Phase 9D finds shape mismatches between OpenAPI and route handlers. If the diff is clean (likely, given FastAPI generates the spec from the same Pydantic models the routes use), Schemathesis is overhead. **Defer install pending Phase 9D findings.**

## 6. Current frontend API client generation status

**Hand-written, not generated.** 243 lines at `frontend/src/lib/api.ts`.

Key bespoke behaviors (any client-regen approach must preserve all of these):
- **Silent-prefix list** (`api.ts:61-71`): 21 endpoint prefixes default to silent (no toast) so polling failures don't spam the user. Per-call override via `config.silent: false`.
- **Error-store integration** (`api.ts:213-221`): every error is recorded to `useErrorStore` regardless of toast policy. The navbar `ConnectionStatusIndicator` reads from this store. (ADR-001 honesty rule: no silent suppression.)
- **JWT refresh-queue** (`api.ts:153-184`): single in-flight refresh; concurrent failed requests queue and retry with the new token. Without this, a token-expiry blip would N×fail across simultaneous polling components.
- **Endpoint-prefix categorization** (`api.ts:191`): every request is bucketed via `extractEndpointPrefix` for the error store's per-family degradation tracking.
- **Cancellation pass-through** (`api.ts:146-148`): axios `CanceledError` skipped — intentional aborts on route change/refresh don't pollute the error store.

There is no codegen pipeline (no `orval.config.*`, no `openapi-typescript-codegen` invocation, no `openapi-fetch` import, no `paths` type imports anywhere in `frontend/src`). All call sites use untyped `api.get('/some/path')` and inline-type the response.

## 7. Recommendation: keep current client / generate typed client / hybrid

**Hybrid — keep the runtime, add types only.**

Concrete plan:

| Layer | Today | Recommended | Why |
|---|---|---|---|
| Axios runtime + interceptors | hand-written, 243 lines | **keep** | Five bespoke behaviors above are load-bearing; any full client regen would either delete them or require manual re-patching every regen. Cost > benefit. |
| Request/response types | inline `as Type` casts at call sites, no validation | **`openapi-typescript` for compile-time `paths` types** | One-line regen; types-only output (no runtime JS); `paths['/api/v1/skills']['get']['responses']['200']['content']['application/json']` becomes typed at the call site. |
| Runtime validation | none | **defer** | Adding zod/valibot at the boundary is a separate decision; do it only after Phase 9D finds shape mismatches that compile-time types alone can't catch. |
| Client SDK regen (Orval, openapi-fetch, openapi-typescript-codegen) | none | **reject** | Would force a full call-site rewrite (currently ~180+ `api.get/post/put/delete/patch` sites) and break the silent-prefix integration. ROI negative. |

Implementation sketch (Phase 10, *after* matrix and backlog are reviewed):
1. `cd frontend && npm i -D openapi-typescript`
2. `npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api-schema.d.ts`
3. Add `npm run gen:api` script: `openapi-typescript backend-openapi.json -o src/types/api-schema.d.ts`
4. Wrap one call site as a proof-of-concept: convert `useRuntimeRegistry.ts` from `as Runtime[]` casts to `paths['/api/v1/runtimes']['get']['responses']['200']['content']['application/json']`.
5. Migrate call sites incrementally (no big-bang rewrite).

Optional Phase 11+ enhancement: thin typed-fetch wrapper for *new* code while existing call sites keep using raw `api.get`. Lower migration cost; same end state.

`★ Insight ─────────────────────────────────────`
- The "keep runtime, regen types only" pattern is underrated. Most teams hit this fork and either (a) commit to a full SDK (which breaks bespoke interceptors) or (b) keep doing untyped axios forever (which silently rots). The middle path costs one config line + one CI step and pays back on the first response-shape change a backend team forgets to coordinate.
- Schemathesis is great when you have *no* type contract. Daena already has one (FastAPI's auto-generated OpenAPI spec). The marginal value of property-based fuzz testing against your own spec is low unless you find handler/spec drift. That's why §5 says "defer install pending 9D findings" — don't add a tool in search of a problem.
`─────────────────────────────────────────────────`

---

## Summary Table

| Probe | Status | Evidence | Action needed |
|---|---|---|---|
| Playwright MCP available | **YES** | deferred-tools manifest | none |
| Playwright E2E in project | **YES** | `frontend/package.json:32`, `playwright.config.ts:1-19`, `e2e/*.spec.ts` (2 specs) | add coverage in 9C/10 |
| Trace recording works | **YES** (configured) | `playwright.config.ts:13-14` | use `--trace on` in 9C |
| OpenAPI schema available | **YES (static)**, live unverified | `main.py:978-985` (default openapi_url), `api/v1/__init__.py` (51 routers) | start backend; fetch & save in 9D |
| Schemathesis runnable | **NO** | `pyproject.toml:55-63` (not in dev deps) | defer install pending 9D findings |
| Frontend API client | hand-written axios, 243 lines | `frontend/src/lib/api.ts` | keep runtime; add openapi-typescript in Phase 10 |
| Generated typed client | none | no orval/openapi-typescript-codegen config | hybrid (types only), not full SDK |

## Boundaries respected (per founder rules)

- No production deploy. No image rebuild. No GCP touch.
- No `USE_CONNECTION_REGISTRY_V2` flip.
- No `vault --apply`. No vault file deletion.
- No secrets read or printed.
- No external scans run.
- No package installed in this phase. Schemathesis recommendation deferred to 9D.
- No file deletions or rewrites — only this report and the matrix follow.
