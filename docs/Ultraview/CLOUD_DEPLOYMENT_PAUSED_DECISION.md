# Cloud Deployment Paused — Decision Record

**Date:** 2026-05-01
**Status:** PAUSED (no deploy, no automatic resume)
**Decision authority:** Founder
**Branch at decision:** `rebuild-connections-mcp-runtime`
**Last cloud-touching commit:** `f7f79dd` (production-hygiene wiring; not deployed)

---

## 1. The decision

Cloud Run production deployment is **paused indefinitely**. Daena
operates **local-first** on the founder's workstation as primary mode.
See `LOCAL_FIRST_DAENA_ARCHITECTURE.md` for the local architecture
that is now active.

This is a **strategic pivot**, not a temporary defer:

- Cloud Run was being treated as the production target. It is no
  longer the production target.
- The "production target" is now `localhost` on the founder's PC.
- Cloud Run is preserved as an **optional** future surface for
  demos / client-managed instances.

## 2. What's preserved (do NOT tear down)

The following GCP resources remain provisioned because tearing them
down and re-provisioning later is wasteful:

| Resource                   | Project          | State        | Cost notice |
|----------------------------|------------------|--------------|-------------|
| Cloud Run service `daena`  | daena-467315     | Last revision: 2026-03-21, scale-to-0 | Negligible while idle |
| Cloud SQL `daena-db`       | daena-467315     | RUNNABLE, POSTGRES_15 | ~$10-50/month while RUNNABLE — see §6 cost note |
| Secret Manager (7 secrets) | daena-467315     | Versions populated 2026-05-01 | Free under 1k versions |
| Artifact Registry          | daena-467315     | Image tags from 2026-03-21 | Negligible |
| IAM bindings               | daena-467315     | `daena-run` SA → secretAccessor on 7 | Free |

Founder may choose to **stop** Cloud SQL (preserves data, suspends
billing) — see §6 cost-control options.

## 3. What's paused (do NOT execute)

Following items are explicitly paused. Claude Code / Codex CLI must
NOT execute any of them without an explicit founder go-ahead in a
new session:

| # | Action                                                              | Why paused |
|---|---------------------------------------------------------------------|-----------|
| 1 | `gcloud builds submit --config=cloudbuild.yaml ...`                 | Triggers production deploy |
| 2 | `gcloud run services update daena --update-secrets ...`             | Triggers production env change |
| 3 | `gcloud run services update daena --update-env-vars USE_CONNECTION_REGISTRY_V2=true` | Premature V2 flip in cloud |
| 4 | Any `vault --apply` against the cloud DB                            | One-way operation; would consume DEK budget |
| 5 | `rm` / delete `vault.py` or `oauth_credentials_store.py`            | Legacy fallback still in active use |
| 6 | Provider-side rotation of `GROQ_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_SECRET` | Founder action only — not autonomous |
| 7 | `gcloud sql instances delete daena-db`                              | Loses provisioned state; founder may stop instead |
| 8 | `gcloud secrets delete daena-...`                                   | Loses Secret Manager refs already created |

## 4. What's safe (still allowed)

- Reading current Cloud Run env var **names** (not values) for
  audit purposes
- Listing Secret Manager secret **names** (not versions / values)
- Reading Cloud SQL instance state (`RUNNABLE` / `STOPPED`)
- Running `pwsh scripts/production_readiness_check.ps1` (read-only)
- Running `python scripts/setup_production_secrets.py --dry-run`
  (no mutations)
- Editing local code in `backend/`, `frontend/`, `scripts/`, `docs/`
- Editing `cloudbuild.yaml`, `deploy-cloud.sh`, `Dockerfile`,
  `start.sh` so they remain READY for a future resume

## 5. What still needs founder action (carries forward)

The following items are NOT paused — they are out-of-band actions
the founder still owns regardless of cloud deployment status:

1. **Provider-side rotation** of the 4 leaked secrets at issuer
   surfaces (Groq, Gemini, Google OAuth, GitHub OAuth). The values
   currently in Secret Manager are the SAME values that were leaked
   — moving them did not rotate them. Until rotated at the issuer,
   anyone with the leaked terminal output can still authenticate.
2. **JWT_SECRET_KEY** and **DAENA_KEK** in Secret Manager: these
   are fresh-generated (no prior version compromise) but if the
   founder later deploys to cloud, rotation cadence should be
   established (e.g., quarterly).
3. **`VAULT_ENCRYPTION_KEY`** remains plaintext in Cloud Run env
   per the original "keep legacy fallback for now" instruction.
   Still applies — do not migrate without explicit approval.

## 6. Cost-control options

If keeping Cloud SQL `daena-db` running while Daena is local-first
feels wasteful (~$10-50/month for `db-g1-small`), the founder has
three options:

### Option A — Leave RUNNABLE (default)

Cost: ~$10-50/month
Pro: Resume cloud deploy is one-command
Con: Pays for an idle DB

### Option B — Stop the instance

```bash
gcloud sql instances patch daena-db --activation-policy=NEVER --project=daena-467315
```

Cost: Storage only (~$1-3/month for 10 GB)
Pro: 90%+ cost reduction
Con: Resume requires `--activation-policy=ALWAYS` first (~3-5 min cold start)
Data: Preserved on storage; backups continue

### Option C — Delete the instance

```bash
gcloud sql instances delete daena-db --project=daena-467315
```

Cost: $0
Pro: Zero ongoing cost
Con: Resume requires full re-provision per `DAENA_DATABASE_READINESS_PLAN.md`
Data: Lost (only the schema lives there today; no real prod data)

**Recommendation:** Option B (stop) — preserves the 5-minute resume
path while eliminating idle cost. Founder decides.

## 7. Resume criteria

Cloud Run deployment resumes only when **one** of these is true and
the founder explicitly issues the go-ahead in a new session:

1. **Live demo** — investor / client meeting where `daena.mas-ai.co`
   is preferable to a localhost screen-share.
2. **Managed-client engagement** — paid customer wants a hosted
   instance under MAS-AI Technologies operations.
3. **24/7 unattended operation** — heartbeat / autopilot tasks must
   keep running while the workstation is off / sleeping.
4. **Multi-device founder access** — founder needs Daena reachable
   from a phone / tablet / second workstation outside the LAN.

Until one of these is true, every cloud-side TODO stays parked.

## 8. Risk inventory (still-live concerns)

These risks are NOT resolved by the pause:

| Risk                                                                 | Mitigation status |
|---------------------------------------------------------------------|-------------------|
| Leaked secrets remain valid at provider until rotated by founder   | OPEN (founder action) |
| Cloud Run plaintext env still has secret values                    | OPEN (resolved on next deploy + revoke at issuer) |
| `VAULT_ENCRYPTION_KEY` is plaintext in Cloud Run env               | OPEN (held intentionally) |
| Cloud SQL has a working `daena` user with rotated password         | NEUTRAL (rotated 2026-05-01; idle pending deploy) |
| Cloud Run service still publicly reachable on `*.run.app`          | OPEN — founder may want to lock down with `--no-allow-unauthenticated` |
| Old image (2026-03-21) has unguarded `Base.metadata.create_all`    | NEUTRAL (only matters if deployed against new DATABASE_URL) |
| Cloud Build trigger may fire automatically                          | VERIFY — founder should confirm no automatic Cloud Build trigger is active on git push |

### Recommended quick lockdown (1 command)

If the founder wants to make absolutely sure Cloud Run isn't a
public surface during the pause:

```bash
gcloud run services update daena \
  --project=daena-467315 --region=us-central1 \
  --no-allow-unauthenticated
```

This requires every request to carry `Authorization: Bearer
$(gcloud auth print-identity-token)`. It does not change app code.

## 9. How to resume (when the time comes)

When founder issues the go-ahead:

1. Re-validate the readiness state:
   ```bash
   pwsh scripts/production_readiness_check.ps1
   ```
2. If Cloud SQL is stopped (Option B above), restart:
   ```bash
   gcloud sql instances patch daena-db --activation-policy=ALWAYS --project=daena-467315
   # Wait ~3-5 min for state=RUNNABLE
   ```
3. Re-run the secret setup (idempotent — skips existing):
   ```bash
   python scripts/setup_production_secrets.py
   ```
4. Trigger atomic build + deploy:
   ```bash
   gcloud builds submit --config=cloudbuild.yaml --project=daena-467315 .
   ```
5. Watch the new revision come up:
   ```bash
   gcloud run services logs read daena --project=daena-467315 --region=us-central1 --limit=200
   ```
6. Re-run the readiness check post-deploy.

The exact full sequence is in `PRODUCTION_HYGIENE_AUTOMATION_REPORT.md`
§5 "Recommended deploy sequence". That guidance is still valid;
nothing in the local-first pivot makes it stale.

---

**Last updated:** 2026-05-01
**Counterpart doc:** `LOCAL_FIRST_DAENA_ARCHITECTURE.md`
**Audit reference:** commit `f7f79dd` (production-hygiene wiring, NOT deployed)
