# PR-2: OpenAPI to Frontend Contract Diff — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE
**Doc:** [OPENAPI_FRONTEND_CONTRACT_DIFF.md](./OPENAPI_FRONTEND_CONTRACT_DIFF.md)

## What this PR does

Read-only audit. Generates the local OpenAPI spec from the live backend
(`a852c03`), greps the frontend for actual API calls, and classifies every
endpoint group into 5 buckets:

- **A** WIRED — frontend uses these
- **B** BACKEND-ONLY INTERNAL — intentionally not UI-bound
- **C** BACKEND EXISTS, UI SHOULD WIRE — Sprint-21 candidates
- **D** UI LABELS AHEAD OF BACKEND — must relabel or remove
- **E** DUPLICATES — flagged for later cleanup

## Counts

- **492** OpenAPI operations
- **76** tag groups
- **~75** distinct frontend-referenced path prefixes
- **4** Bucket-D contract gaps (Settings Developer / Notifications / Privacy + Skill Bundles)

## Hard rules respected

- [x] Read-only — no behavior change
- [x] No deploy
- [x] No secrets read or printed
- [x] No new architecture

## Next

PR-3: Reclassify Bucket-D coming-soon stubs.
