# Daena-v2 Phase 10b Deploy Plan

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Step C
**Status:** **PLAN ONLY — no deploy executed.**
**Target service:** `daena-v2` (project `daena-467315`, region `us-central1`)
**Source commits to ship:** `c696f6a` → `917b975` on
`rebuild-connections-mcp-runtime`

---

## 0. Headline

**daena-v2 should be updated, but only AFTER the founder reviews this
plan and explicitly approves the build.** The deploy is a
single-command Cloud Build → Cloud Run revision; estimated wall time
~15 minutes including readiness re-check.

The cloud service is healthy and on a clean baseline (`daena-v2-00003-7zx`,
17/17 PASS) but lags the local checkpoint by **5 code commits + 3
doc commits**. The doc commits don't need to ship; the code commits
do.

---

## 1. What this deploy includes

**Code commits to ship (in order):**

```
c696f6a  phase10: fix unsafe action gates (U1+U2+U3) at REST boundary
dc9d666  phase10: chat session audit emit + chat file-remove honest tooltip
ddb01cf  phase10b: close 5 OpenAPI ghost calls + add scan archive query
d55f3a9  phase10b: scan UX repairs (B1 re-run, B2 ready toast, B3 archive view)
```

(The 4th code commit `d55f3a9` includes the
`connections-rebuild-mcp-runtime` branch's pre-existing scan-page
refactor, which has never deployed before — see §3 for the risk.)

**Doc commits NOT shipping (already on the branch, no runtime impact):**

```
a6bf128  docs: phase 9 audit + 9E multi-model review + phase 10 verification
492aec8  docs: phase10b settings downstream-read audit
917b975  docs: phase10b verification report + post-fix OpenAPI spec
```

The image is built from the working tree, so the docs come along
silently — but they don't change runtime behavior.

---

## 2. What this deploy does NOT change

Per founder hard rules (carried over from prior plans):

| Item | Why locked |
|---|---|
| `USE_CONNECTION_REGISTRY_V2` | **Stays `false`.** V2 connections panel is a code-on-deck feature; production gate stays off until founder flip. |
| Vault state | **No `vault --apply`.** No secret rotation, no DEK changes. |
| `vault.py` / `oauth_credentials_store.py` | **Not touched.** Hands-off list per Phase 10 inbox. |
| Legacy `daena` service | **Untouched.** Kept for autopsy per `CLEAN_GCLOUD_REBUILD_PLAN.md`. |
| Cloud SQL instance (`daena-db`) | No schema migration in this set; Alembic head unchanged from existing image. Container's `start.sh` will run `alembic upgrade head` (no-op against current head). |
| Secret Manager bindings (8 secrets) | No re-bind needed; `deploy-cloud.sh` re-applies the same `--update-secrets` line (idempotent). |
| `CORS_ORIGINS` | Unchanged: `["https://daena.mas-ai.co","https://mas-ai.co","http://localhost:5173"]`. |
| Default service account split | `daena-build` (build SA) and `daena-run` (runtime SA) unchanged. |

---

## 3. Risk assessment + new surface in this build

### 3.1 New routes (4 of 5 ghost calls; G5 is frontend-only)

| Route | New behavior | Risk |
|---|---|---|
| `DELETE /api/v1/company-mode/seed-brief` | Soft-archives founder seed (rename to `*.archived-<UTC>.md`) | **LOW.** Founder-only; idempotent; no auth-bypass. |
| `GET /api/v1/projects/{id}/tasks` | Returns honest empty list with `meta.tracking_enabled: false` | **LOW.** Read-only; tenant-scoped via `_ensure_project`. |
| `GET /api/v1/projects/{id}/files` | Same as above | **LOW.** Same shape. |
| `GET /api/v1/runtimes/subscriptions` | Reads in-memory subscription cache; returns flat list | **LOW.** Read-only; no DB write. |
| `GET /api/v1/security/scans?archived=true` | New query param; loader points at `.archive/` | **LOW.** Read-only; default behavior unchanged. |

### 3.2 Hardened existing routes (Phase 10 P0 gates)

| Route | Change | Risk |
|---|---|---|
| `POST /api/v1/security/scans/start` | NOW requires authenticated user; NOW checks `target_matches_scope` and 403s on out-of-scope | **MEDIUM.** Behavior change visible to existing callers. **Any client that previously relied on the unauth path will break.** This is intentional — that path was the U2 vulnerability. |
| `POST /api/v1/engagements` | Same scope check at REST boundary | **MEDIUM.** Same shape. |
| `POST /api/v1/company-mode/activate` | Now refuses `auto_send=true` + `require_founder_approval=false` with 422 | **LOW.** New 422 surface; UI form already prevents the bad combo. |
| `PATCH /api/v1/chat/sessions/{id}` | Now appends `chat_session.{renamed,archived,unarchived,updated}` audit row | **LOW.** Best-effort emit; mutation always succeeds. |
| `DELETE /api/v1/chat/sessions/{id}` | Now appends `chat_session.deleted` audit row | **LOW.** Same shape. |

### 3.3 Frontend changes

| Surface | Change | Risk |
|---|---|---|
| `ScanPage.tsx` | Sweeps in pre-existing branch refactor: monolith → orchestrator + `frontend/src/pages/scan/` subdir (6 files) | **MEDIUM.** This refactor is large (~700 lines moved) and has never deployed. Visual regression risk on the Scan page; behavior should be identical. **Recommendation:** the smoke check post-deploy MUST include a visual eyes-on of `/scan`. |
| `ScanList.tsx` (within scan/ subdir) | Phase 10b additions: Re-run on active, "Report ready" Badge, Show-archived toggle | **LOW.** Pure additive; no removed handlers. |
| `CompanyModePage.tsx` | Auto-send Switch is `disabled` when approval is off; helper text added | **LOW.** Pure UX guard. |
| `ChatInput.tsx` | Tooltip + aria-label clarity on the X button (Phase 10) | **LOW.** Doc-string-grade change. |
| `SettingsDeveloper.tsx` | Trailing slash on `/settings/` request | **LOW.** Behavior identical (axios followed the 307 anyway); cleaner spec adherence. |

### 3.4 Database schema

**No schema migration.** Alembic head unchanged from the
`5646877`-built image's head (006/007). Container `start.sh` will run
`alembic upgrade head` and find nothing to do.

### 3.5 Image SHA churn risk

A new image build necessarily changes the image SHA. Cloud Run
revisions are immutable, so the deploy creates `daena-v2-00004-*`
serving 100% traffic; `daena-v2-00003-7zx` retains 0% traffic and
remains rollback-ready.

---

## 4. Deploy procedure (step by step)

**Estimated wall time:** ~15 min.
**Pre-flight:** founder approval of this plan; cloud auth current
(`gcloud auth list` shows the founder identity).

```bash
# 0. Confirm checkout matches the deploy plan.
cd /d/Ideas/Daena
git rev-parse HEAD          # expect 917b975
git status --short          # WIP is OK (will be excluded by .gcloudignore)
git log --oneline -5        # confirm last code commit is d55f3a9

# 1. Pre-flight readiness check (against current cloud state).
pwsh scripts/production_readiness_check.ps1 -Service daena-v2
# Expect: 17 PASS / 0 FAIL / 0 WARN / 0 SKIP (matches current baseline)

# 2. Build + deploy in one atomic Cloud Build run.
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=daena-467315 \
  .

# Cloud Build will:
#   - docker build -t .../daena:$BUILD_ID -t .../daena:latest .
#   - push both tags to Artifact Registry
#   - gcloud run deploy daena-v2 with the new image, re-applying
#     all 8 Secret Manager bindings + Cloud SQL link + the
#     production env block (CORS_ORIGINS unchanged,
#     USE_CONNECTION_REGISTRY_V2=false unchanged).
# Wall time: ~10-12 min including container build.

# 3. Capture the new revision id + image SHA.
gcloud run services describe daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --format='get(status.latestReadyRevisionName,status.latestCreatedRevisionName,status.url,spec.template.spec.containers[0].image)'

# 4. Health check (unauth allowed via --allow-unauthenticated).
curl -fsS https://daena-v2-mj6b2zy7xa-uc.a.run.app/api/v1/health | python -m json.tool
# Expect: {status: healthy, ...}; if status == warming, wait 30-60s.

# 5. Post-deploy readiness re-check.
pwsh scripts/production_readiness_check.ps1 -Service daena-v2
# Expect: 17 PASS / 0 FAIL / 0 WARN / 0 SKIP (no regression).

# 6. Phase 10b smoke spot-check (the new routes need to actually answer).
TOKEN=$(gcloud auth print-identity-token)  # service-to-service identity
SVC=https://daena-v2-mj6b2zy7xa-uc.a.run.app
# (these will all return 401 because the routes need a Daena JWT,
# not a GCP identity token — but a 401 proves the route exists.
# A 405/404 would prove the new code did not deploy.)
curl -sw "%{http_code}\n" -o /dev/null -X DELETE \
  -H "Authorization: Bearer ${TOKEN}" \
  "${SVC}/api/v1/company-mode/seed-brief"
# Expect: 401 (route present, JWT wrong). NOT 405.

curl -sw "%{http_code}\n" -o /dev/null \
  -H "Authorization: Bearer ${TOKEN}" \
  "${SVC}/api/v1/runtimes/subscriptions"
# Expect: 401. NOT a Runtime-not-found 200 (which would mean the
# old /{runtime_id} route caught it).

curl -sw "%{http_code}\n" -o /dev/null \
  -H "Authorization: Bearer ${TOKEN}" \
  "${SVC}/api/v1/security/scans?archived=true"
# Expect: 401 (route exists, accepts the new param).
```

**If step 6 returns 405 or `Runtime 'subscriptions' not found`:** the
build did not pick up the Phase 10b code. Investigate before
serving any demo traffic.

---

## 5. Rollback procedure

Cloud Run revisions are immutable; rollback is one command.

```bash
# 1. Find the previous good revision (the current baseline).
gcloud run services describe daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --format='value(status.traffic)'
# baseline before this deploy: daena-v2-00003-7zx at 100%

# 2. Move 100% traffic back to it.
gcloud run services update-traffic daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --to-revisions=daena-v2-00003-7zx=100

# 3. Verify.
curl -fsS ${SVC}/api/v1/health | python -m json.tool
# Expect: still healthy; image SHA matches the prior baseline.
```

Total rollback wall time: <1 min. The bad revision (`daena-v2-00004-*`)
remains in the revision list at 0% traffic for autopsy.

---

## 6. Verification + acceptance criteria

A successful deploy must satisfy ALL of the following:

| Criterion | How to check |
|---|---|
| `daena-v2-00004-*` revision exists | `gcloud run revisions list --service=daena-v2` |
| New revision serves 100% traffic | `gcloud run services describe daena-v2 --format='value(status.traffic)'` |
| Image SHA differs from the baseline `1b4e0e4e...39fe2` | `gcloud run revisions describe daena-v2-00004-* --format='value(spec.containers[0].image)'` |
| `/api/v1/health` returns `status: healthy` within 60 s of revision-ready | `curl ${SVC}/api/v1/health` |
| Readiness check: 17/17 PASS, no regression | `pwsh scripts/production_readiness_check.ps1 -Service daena-v2` |
| Phase 10b ghost-call routes registered (return 401, not 405/404) | three curl probes in §4 step 6 |
| `USE_CONNECTION_REGISTRY_V2=false` still set | confirmed by readiness check `V2-FLAG-NOT-FLIPPED` row |
| CORS_ORIGINS unchanged | confirmed by readiness check `CORS-ORIGINS-RESTRICTED` row |
| Cloud SQL connection still attached | confirmed by readiness check + health endpoint's `database: healthy` |
| 8 Secret Manager secrets still bound | confirmed by readiness check `SECRETS-BOUND` row + boot logs |

If any of these fail, execute §5 rollback and file a follow-up ticket
in `docs/Ultraview/`.

---

## 7. What to tell the founder before deploying

> "Cloud daena-v2 is currently on revision `daena-v2-00003-7zx` from
> commit `5646877` (pre-Phase-10). To match the local checkpoint, we
> need to ship 4 code commits — the Phase 10 P0 gates (which will
> 403 any unauthorized scan attempt that's currently 200-OK on cloud)
> and the Phase 10b ghost-call closures + scan UX. The Phase 10
> gates *are* a behavior change and any external client relying on
> the old unauth scan path will break — but breaking that path is
> the point. Image build + deploy is one `gcloud builds submit`
> command, ~12 minutes; rollback is one `gcloud run services
> update-traffic` line, <1 minute. No schema changes, no secret
> rotation, no V2 flag flip. Want me to run the deploy?"

---

## 8. The exact command for founder approval

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=daena-467315 \
  .
```

(Run from the repo root `/d/Ideas/Daena/` with HEAD at `917b975`.)

---

## 9. Boundaries respected

* This document is **PLAN ONLY**. No `gcloud` write was issued.
* No production deploy executed.
* No `USE_CONNECTION_REGISTRY_V2=true` flip — locked at `false` in
  this plan and the deploy command preserves it.
* No `vault --apply`.
* No `vault.py` / `oauth_credentials_store.py` touched.
* No secrets read or printed (`gcloud auth print-identity-token` is
  a verification probe, not stored or logged).
* No external scans.
* No external messages / emails sent.
* No Phase 11 work begun.

End of plan.
