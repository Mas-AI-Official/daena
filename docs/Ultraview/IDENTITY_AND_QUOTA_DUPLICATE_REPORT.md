# Identity / Quota Duplicate Report

Date: 2026-04-30

## Verified Evidence

Before backend outage:

- `/api/v1/settings/user` returned a founder user with Masoud identity and settings.
- Founder screenshot/logs showed duplicate Masoud Masoori identity/plan surfaces.

## Likely Causes To Validate

- Duplicate user rows.
- Duplicate tenant/company rows.
- Duplicate quota profile rows.
- Seed scripts re-running without idempotent unique constraints.
- UI merging founder user, tenant owner, and billing profile as separate people.
- LocalStorage/session fallback user displayed alongside backend user.
- Billing page showing plan source and quota source as if they are separate subscriptions.

## Current Classification

Unresolved. Backend/database validation is blocked because:

- backend is currently `ECONNREFUSED`;
- WSL command execution fails with `Wsl/Service/0x8007072c`;
- Windows Python cannot import `asyncio`, so direct SQLAlchemy inspection cannot run.

## Required Fix

After backend or DB access is restored:

1. Query users by founder email.
2. Query tenants where founder is owner/admin.
3. Query quota profiles and billing plans for that tenant.
4. Confirm only one active founder user, one active tenant/company, and one active quota profile.
5. If multiple rows are legitimate historical rows, hide inactive ones from production UI.

## UI Rule

Until validated, Billing & Usage must not show multiple FREE/FOUNDER labels for the same founder. Show one canonical plan or hide billing as `Not production-ready`.
