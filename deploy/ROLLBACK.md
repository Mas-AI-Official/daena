# Daena production rollback runbook (service daena-v2, project daena-467315)

Region: us-central1. Last known-good baseline revision before the soul deploy: `daena-v2-00003-7zx`.

## Instant rollback (shift 100% traffic to the previous good revision)
```
gcloud run services update-traffic daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --to-revisions=daena-v2-00003-7zx=100
```

## List revisions (pick a good target)
```
gcloud run revisions list --service=daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --format="table(metadata.name, status.conditions[0].status, metadata.creationTimestamp)"
```

## Inspect current traffic split
```
gcloud run services describe daena-v2 \
  --project=daena-467315 --region=us-central1 \
  --format="json(status.traffic)"
```

## Notes
- The cloudbuild safety gate (cloudbuild.yaml) now lands new revisions with
  `--no-traffic` + a `candidate` tag and migrates traffic only after `/health`
  returns 200, so a broken image cannot take production. This runbook covers the
  case where a revision passed `/health` but misbehaves under real traffic.
- Cloud Run retains old revisions, so traffic can always be pinned back.
- After any rollback, record WHY in D:\Claude-Coworker\inbox.md.
