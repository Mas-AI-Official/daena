---
name: github
description: "GitHub operations via gh CLI: issues, PRs, CI runs, code review. Use when user asks about PRs, issues, CI status, or repo management."
department: Engineering
cost_tier: low
requires:
  bins: ["gh"]
---

# GitHub Skill

Use the `gh` CLI to interact with GitHub repositories, issues, PRs, and CI.

## When to Use

- Checking PR status, reviews, or merge readiness
- Viewing CI/workflow run status and logs
- Creating, closing, or commenting on issues
- Creating or merging pull requests
- Querying GitHub API for repository data

## Common Commands

### Pull Requests
```bash
gh pr list --repo owner/repo
gh pr view 55 --repo owner/repo
gh pr checks 55 --repo owner/repo
gh pr create --title "Title" --body "Description" --repo owner/repo
gh pr merge 55 --squash --repo owner/repo
```

### Issues
```bash
gh issue list --repo owner/repo --state open
gh issue create --title "Bug" --body "Details" --repo owner/repo
gh issue close 42 --repo owner/repo
```

### CI / Actions
```bash
gh run list --repo owner/repo --limit 5
gh run view 12345 --repo owner/repo
gh run view 12345 --log --repo owner/repo
```

### API Queries
```bash
gh api repos/owner/repo/contributors --jq '.[].login'
gh api repos/owner/repo --jq '.stargazers_count'
```
