# Clean GCloud Rebuild — CORS Fix Cutover Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) at founder direction
**Predecessor:** `docs/Ultraview/CLEAN_GCLOUD_REBUILD_REPORT.md`
**Mode:** single-shot patch + single-shot deploy + verify; no further deploys triggered.

> **Status one-liner:** `daena-v2` is **up, serving 100% of traffic, and HEALTHY at the database and essentials layers**. The CORS_ORIGINS guardrail is satisfied. Readiness is **17 PASS / 0 FAIL / 0 WARN / 0 SKIP**. Legacy `daena` service is untouched. `USE_CONNECTION_REGISTRY_V2` remains `false`. The app is in seed-warming phase (`status: warming, seed_phase: runtime_registry`) — startup is progressing as expected and will move to `healthy` once seedings_complete becomes true.

---

## 1. Commit SHA

`ae9ba6d3da429b40922b2aecb1c05f172bc1c2e9`  ("production-hygiene: set production CORS origins for daena-v2")

| File              | Change |
| ----------------- | ------ |
| `cloudbuild.yaml` | Replaced `--update-env-vars` line: switched to gcloud's `^@^` alternative-delimiter form, added `CORS_ORIGINS=["https://daena.mas-ai.co","https://mas-ai.co","http://localhost:5173"]`. Added 8-line comment explaining the delimiter trick + the production guardrail it unblocks. |
| `deploy-cloud.sh` | Same env block transformation; collapsed the 5-line continuation into a single single-quoted argument so commas inside the JSON pass through verbatim. |

No secrets touched; no DB / vault / V2-flag changes; no other files modified.

## 2. Build ID

**None for this cutover.** The fix did not require a docker rebuild because the image already in Artifact Registry (`us-central1-docker.pkg.dev/daena-467315/daena-repo/daena@sha256:1b4e0e4e43bb724f3ed23c78157f7ff227cd7ae777be4340dc6bd2b477939fe2`, originally produced by commit `5646877` via build `8d232870-…` documented in the previous report) carries the schema-bootstrap fix and only needed an env-var update.

The deploy ran via `bash deploy-cloud.sh`, which calls `gcloud run services update daena-v2 …` (env + secrets + Cloud SQL) — this creates a new revision against the cached image, no new Cloud Build invocation. Single-shot, single attempt, exit 0.

## 3. Latest revision

`daena-v2-00003-7zx`

| Field          | Value |
| -------------- | ----- |
| Ready status   | `True` (type: `Ready`) |
| Image SHA      | `sha256:1b4e0e4e43bb724f3ed23c78157f7ff227cd7ae777be4340dc6bd2b477939fe2` |
| Traffic        | 100% |
| Service URL    | `https://daena-v2-mj6b2zy7xa-uc.a.run.app` |
| Predecessor    | `daena-v2-00002-vcp` (Failed; CORS guardrail) |

Earlier failed revisions remain in the service's revision list but receive 0% traffic.

## 4. App startup result

**Successful.** `gcloud run services update` output:

```
Creating Revision........................done
Routing traffic.....done
Done.
Service [daena-v2] revision [daena-v2-00003-7zx] has been deployed and is
serving 100 percent of traffic.
```

The startup guardrail at `backend/app/main.py:758` did not trigger; CORS_ORIGINS now contains 3 non-localhost-only entries, so `diagnostics["guardrail_issues"]` is empty and lifespan() proceeds. No `RuntimeError` in the revision logs.

## 5. Readiness result

`pwsh scripts/production_readiness_check.ps1 -Service daena-v2`:

```
PASS: 17   FAIL: 0   WARN: 0   SKIP: 0
```

Diff vs. the pre-fix baseline (`16 PASS / 0 FAIL / 1 WARN / 0 SKIP`):

| Check                       | Before   | After   |
| --------------------------- | -------- | ------- |
| `CORS-ORIGINS-RESTRICTED`   | WARN     | **PASS** ("CORS_ORIGINS is set to a non-wildcard list") |
| `ENV-INVENTORY`             | 12 entries (8 secret refs + 4 plaintext) | 13 entries (8 secret refs + 5 plaintext — added `CORS_ORIGINS`) |
| `V2-FLAG-NOT-FLIPPED`       | PASS     | PASS (still `false`) |

All other 15 checks unchanged at PASS.

## 6. Health endpoint result

```
GET https://daena-v2-mj6b2zy7xa-uc.a.run.app/api/v1/health
HTTP 200
{
  "status": "warming",
  "checks": {
    "redis": "unavailable",
    "database": "healthy",
    "essentials_ready": true,
    "seedings_complete": false,
    "seed_phase": "runtime_registry"
  },
  "version": "2.0.1"
}
```

Interpretation:

- `database: healthy` — Cloud SQL reachable, schema present, queries succeed. (Confirms the bootstrap stamp survived the redeploy.)
- `essentials_ready: true` — DAENA_KEK validated, JWT secret present, vault initialized, model registry loaded.
- `redis: unavailable` — expected; no Redis instance is provisioned for this Cloud Run service. The app degrades gracefully (per code path: in-memory rate limiting, no cross-instance cache).
- `seedings_complete: false`, `seed_phase: runtime_registry` — the post-essentials seeding pipeline is mid-flight (was at `connector_catalog` on the first probe, advanced to `runtime_registry` on the second, so it is progressing). `status` will flip from `warming` to `healthy` once seedings finish.

## 7. Is daena-v2 usable?

**Yes**, for code paths that do not depend on Redis or on seedings that are still in flight. Concretely:

- ✅ Public health endpoint is reachable and authentic-looking.
- ✅ Database read/write path is alive (essentials boot succeeded).
- ✅ Vault V2 is unlocked (KEK validated).
- ✅ Allow-unauthenticated is set, so the FE can reach `/api/v1/*` over HTTPS without an identity token. (The route-level auth middleware still enforces JWT for protected endpoints.)
- ⏳ Some endpoints that read from in-memory registries built during seeding (e.g., MCP server catalog, runtime catalog) may return empty/null until `seedings_complete: true`. This typically takes <60s on a cold start.
- ❌ Cross-instance state via Redis is unavailable. If this matters (e.g., distributed rate limiting), provision Redis or accept the in-memory fallback.

For founder/operator browser use against the run.app URL: usable now, will become "fully warm" within the next minute. For a public domain: pending DNS mapping at `daena.mas-ai.co`.

## 8. Is the old `daena` service untouched?

**Yes.**

```
NAME       URL                                              LATEST_READY_REVISION
daena      https://daena-mj6b2zy7xa-uc.a.run.app            daena-00038-msl
daena-v2   https://daena-v2-mj6b2zy7xa-uc.a.run.app         daena-v2-00003-7zx
```

Latest ready revision on `daena` is still `daena-00038-msl`, which predates this rebuild work. No deploy to `daena` was issued; no revision count change; no env mutation. The autopsy artifact is preserved as planned.

(Note: both services share the project-level Cloud Run hash `mj6b2zy7xa-uc` in their URLs — that's expected; the `<service>-` prefix differentiates them.)

## 9. Production V2 flag

**`USE_CONNECTION_REGISTRY_V2 = false`**, plaintext, locked.

- Source-of-truth: `cloudbuild.yaml:53` and `deploy-cloud.sh:53` (this commit's edited line).
- Verified: readiness check `V2-FLAG-NOT-FLIPPED` passed.
- Per ADR-002 D-003 + `PHASE_4B_DEV_ONLY_GUARDRAILS.md`, this flag must stay `false` in production until the explicit prod-soak gate clears. No code path was touched by this fix.

## 10. Remaining manual provider secret rotations

Unchanged from the prior report; not on the cutover critical path:

| Secret resource              | Action                                                    | Owner   |
| ---------------------------- | --------------------------------------------------------- | ------- |
| `daena-groq-api-key`         | Rotate at Groq console; `gcloud secrets versions add …`   | Founder |
| `daena-gemini-api-key`       | Rotate at Google AI Studio; `gcloud secrets versions add …` | Founder |
| `daena-google-client-secret` | Rotate at Google Cloud Console OAuth client; add new version | Founder |
| `daena-github-client-secret` | Rotate at GitHub OAuth App; add new version               | Founder |

After each rotation, no redeploy is required if the env binding uses `:latest` (it does); the next cold start picks up the new version. For an immediate refresh, restart the service: `gcloud run services update daena-v2 --update-secrets=…:latest …` (which is just a no-op env update that creates a new revision).

## 11. Next founder decision

In priority order:

1. **Map `daena.mas-ai.co` → `daena-v2`** in the GCP Cloud Console (Domain Mappings). Until then, the FE bundle that hard-codes that origin will work for CORS preflight (it's in the allowlist) but DNS will not resolve to the service. ~5 minutes of console work.
2. **Decide whether to add the run.app URL** (`https://daena-v2-mj6b2zy7xa-uc.a.run.app`) to `CORS_ORIGINS` for direct browser testing without DNS. Trade-off: it widens the allowlist by one well-known URL. If you want it added: I can produce a one-line patch to `cloudbuild.yaml` + `deploy-cloud.sh` and trigger a single env-only redeploy (same path as this cutover).
3. **Rotate the four provider secrets** (item 10) at your convenience. Not blocking.
4. **Verify warming completes**: hit `/api/v1/health` again in 60–120 seconds and confirm `status: healthy, seedings_complete: true`. If it stalls, pull the revision logs (`gcloud logging read … revision_name=daena-v2-00003-7zx`) to see what the seeder is waiting on.
5. **Plan first user-facing flow**: now that the cloud surface is usable, decide whether the next step is (a) a JWT-authenticated `/api/v1/chat/stream` smoke test from the prod FE, (b) provisioning Redis to remove the `redis: unavailable` line, or (c) staying local-first per `LOCAL_FIRST_DAENA_ARCHITECTURE.md` and treating `daena-v2` as a deployment-rehearsal sandbox.

---

## Boundary preserved (per founder rules)

- Database logic untouched. (Only env block changed.)
- Vault logic untouched. (`vault.py`, `oauth_credentials_store.py`, `vault_v2`, KEK rotation: none of these touched.)
- `USE_CONNECTION_REGISTRY_V2 = false`. Not flipped.
- No `vault --apply` run.
- No secret values printed. (Health JSON contains no credentials; logs not dumped.)
- Single deploy attempt; exit 0; no retry.
- Only `cloudbuild.yaml` + `deploy-cloud.sh` edited; this report file added; no other files changed.
