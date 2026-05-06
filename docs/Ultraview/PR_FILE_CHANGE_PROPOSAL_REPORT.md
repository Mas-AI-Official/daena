# PR-4 -- File Change Proposal (Diff, Not Direct Write)

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 4 of 7
**Date:** 2026-05-06

## Goal

Daena PROPOSES a local file change as a unified diff persisted as
a JSON artifact. NEVER directly overwrites. NEVER deletes (in v1).
NEVER touches secret files. NEVER escapes the repo root.

## What ships

`backend/app/services/controlled_execution_handlers/file_change_proposal.py`
(new). Handler for `local.file_change_proposal`.

### Refusal codes

| Code | Trigger |
|---|---|
| `payload_field_missing:target_path/change_type/diff_text` | required field missing |
| `change_type_delete_not_allowed_in_proposal_v1` | delete is forbidden in v1 |
| `change_type_invalid` | not in {"create", "modify"} |
| `target_path_is_secret_file` | matches a secret-file pattern |
| `target_path_outside_repo` | resolves outside the repo root |

### Secret-file patterns (closed)

```
.env (and .env.production, .env.dev, etc.)
*.pem
*.key
*.p12
secrets/* (any path component)
credentials*.json
.daena_oauth_overrides.json
.autonomy_mode.json
.credentials
*_token.json / *_tokens.json
```

The regex match runs on the full path string. The contract test
hits each pattern with a representative path.

### Artifact shape

```ts
.file_change_proposals/<uuid>.json:

{
  proposal_id:                    uuid,
  tool_id:                        "local.file_change_proposal",
  tenant_id:                      uuid,
  user_id:                        uuid,
  owner_email:                    string | null,
  approval_id:                    string,
  consent_grant_id:               string,
  payload_hash:                   string,
  target_path:                    abs path,
  target_path_repo_relative:      relative path (forward slashes),
  change_type:                    "create" | "modify",
  diff_text:                      unified diff,
  status:                         "proposed",
  applied_at:                     null,
  rejected_at:                    null,
  created_at:                     ISO 8601 UTC
}
```

The artifact directory `.file_change_proposals/` is gitignored.

### Handler does NOT apply

The proposal lives as data only. A future apply tool (Sprint-15+)
will load the artifact, re-validate the diff against the current
file content, and apply it under its own controlled-execution
gate. PR-4 is the first half: capture the intent, surface for
approval, never modify the working tree.

## Tests

`backend/tests/test_file_change_proposal_handler.py` -- 18 tests
(parametrized over secret patterns + required fields):

```
TestRegistered::test_handler_in_registry_after_import
TestPayloadValidation::test_required_field_missing[target_path/change_type/diff_text]
TestChangeTypeRules::test_delete_refused
TestChangeTypeRules::test_invalid_change_type_refused
TestSecretFiles::test_secret_path_refused[10 patterns]
TestOutsideRepo::test_absolute_outside_path_refused
TestSuccessPath::test_proposal_artifact_written
```

Combined Sprint-14 fast subset: 50/50 pass.

## Hard rules audit

| Rule | Status |
|---|---|
| No direct overwrite | enforced -- artifact is data only, never touches the file |
| Shows diff | artifact carries `diff_text` verbatim |
| Requires separate approval before apply | enforced -- PR-4 has no apply path |
| No files outside repo | enforced + tested |
| No secret files | enforced + tested |
| No delete by default | enforced + tested |

## Files

```
new:        backend/app/services/controlled_execution_handlers/file_change_proposal.py  (200 lines)
modified:   backend/app/services/controlled_execution_handlers/__init__.py              (+1 line: import)
modified:   backend/.gitignore                                                          (+1 line: .file_change_proposals/)
new:        backend/tests/test_file_change_proposal_handler.py                          (220 lines, 18 tests)
new:        docs/Ultraview/PR_FILE_CHANGE_PROPOSAL_REPORT.md
```

## Next: PR-5 -- Trust Ladder Foundation
