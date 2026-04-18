---
name: code-review
description: "Review code changes for bugs, security issues, performance problems, and style. Use when user asks to review a PR, diff, or code changes."
department: Engineering
cost_tier: medium
requires:
  bins: ["git"]
---

# Code Review Skill

Analyze code changes for correctness, security, performance, and maintainability.

## When to Use

- User asks to review a PR or set of changes
- User wants feedback on code they wrote
- Pre-commit review of staged changes

## Review Process

1. **Get the diff**
```bash
git diff                    # unstaged changes
git diff --staged           # staged changes
git diff main...HEAD        # branch changes vs main
gh pr diff 55 --repo owner/repo  # PR diff
```

2. **Analyze for issues**
- Correctness: logic errors, edge cases, null handling
- Security: injection, auth bypass, data exposure
- Performance: N+1 queries, unnecessary allocations, missing indexes
- Style: naming conventions, dead code, missing types

3. **Report findings** with severity:
- CRITICAL: Security vulnerability or data loss risk
- HIGH: Bug that will cause failures in production
- MEDIUM: Performance issue or code smell
- LOW: Style suggestion or minor improvement

## Output Format

For each finding:
- File and line number
- Severity level
- Description of the issue
- Suggested fix (code snippet if applicable)
