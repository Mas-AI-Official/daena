---
name: career-ops
description: AI job search command center -- evaluate offers, generate CVs, scan portals, track applications
user_invocable: true
args: mode
argument-hint: "[scan | deep | pdf | oferta | ofertas | apply | batch | tracker | pipeline | training | project | interview-prep | patterns | followup]"
project_root: D:\Ideas\Career OPS
---

# career-ops -- Router

## Mode Routing

Determine the mode from `{{mode}}`:

| Input | Mode |
|-------|------|
| (empty / no args) | `discovery` -- Show command menu |
| JD text or URL (no sub-command) | **`auto-pipeline`** |
| `oferta` | `oferta` |
| `deep` | `deep` |
| `pdf` | `pdf` |
| `training` | `training` |
| `project` | `project` |
| `tracker` | `tracker` |
| `pipeline` | `pipeline` |
| `apply` | `apply` |
| `scan` | `scan` |
| `patterns` | `patterns` |
| `followup` | `followup` |

**Auto-pipeline detection:** If `{{mode}}` is not a known sub-command AND contains JD text (keywords: "responsibilities", "requirements", "qualifications", "about the role", "we're looking for") or a URL to a JD, execute `auto-pipeline`.

If `{{mode}}` is not a sub-command AND doesn't look like a JD, show discovery.

---

## Discovery Mode (no arguments)

Show this menu:

```
career-ops -- Command Center (Masoud Masoori)

Available commands:
  /career-ops {JD}      → AUTO-PIPELINE: evaluate + report + tracker (paste text or URL)
  /career-ops pipeline  → Process pending URLs from data/pipeline.md
  /career-ops oferta    → Evaluation only A-G (no auto PDF)
  /career-ops deep      → Deep research prompt about company
  /career-ops pdf       → PDF only, ATS-optimized CV
  /career-ops apply     → Live application assistant (reads form + generates answers)
  /career-ops scan      → Scan portals and discover new offers
  /career-ops tracker   → Application status overview
  /career-ops patterns  → Analyze rejection patterns and improve targeting
  /career-ops followup  → Follow-up cadence tracker: flag overdue, generate drafts
  /career-ops training  → Evaluate course/cert against target roles
  /career-ops project   → Evaluate portfolio project idea

Inbox: add URLs to D:\Ideas\Career OPS\data\pipeline.md → /career-ops pipeline
Or paste a JD directly to run the full pipeline.

Profile: D:\Ideas\Career OPS\config\profile.yml
CV:      D:\Ideas\Career OPS\cv.md
```

---

## Context Loading by Mode

After determining the mode, load files from `D:\Ideas\Career OPS\`:

### Modes requiring `modes/_shared.md` + mode file:
Read `modes/_shared.md` + `modes/{mode}.md`

Applies to: `auto-pipeline`, `oferta`, `pdf`, `apply`, `pipeline`, `scan`

### Standalone modes:
Read `modes/{mode}.md`

Applies to: `tracker`, `deep`, `training`, `project`, `patterns`, `followup`

Execute the instructions from the loaded mode file.
