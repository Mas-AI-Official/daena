---
name: coding-agent
description: "Delegate coding tasks to Claude Code, Codex, or Gemini CLI runtimes. Use when building features, reviewing PRs, refactoring code, or any task needing file exploration and code changes."
department: Engineering
cost_tier: high
requires:
  anyBins: ["claude", "codex", "gemini"]
---

# Coding Agent Skill

Delegate complex coding tasks to connected AI runtimes (Claude Code, Codex, Gemini CLI).

## When to Use

- Building new features or apps
- Reviewing pull requests
- Refactoring large codebases
- Iterative coding that needs file exploration
- Running tests and fixing failures

## NOT for

- Simple one-liner fixes (just edit directly)
- Reading code without changes (use file-ops skill)
- Questions about code (use CMD mode)

## Execution via Runtimes

### Claude Code (preferred for complex tasks)
```bash
claude --print --permission-mode bypassPermissions "Your task description here"
```

### Codex
```bash
codex exec "Your task description here"
```

### Gemini CLI
```bash
gemini "Your task description here"
```

## Best Practices

1. Provide clear, specific task descriptions
2. Include file paths when known
3. Specify test requirements ("run tests after changes")
4. For PRs: include the PR number and repo
5. Let the runtime handle file discovery -- don't over-specify
