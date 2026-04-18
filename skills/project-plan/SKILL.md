---
name: project-plan
description: "Create project plans with milestones, tasks, timelines, and dependencies. Use when user asks to plan a project, break down work, or create a roadmap."
department: Operations
cost_tier: low
requires: {}
---

# Project Planning Skill

Break down projects into actionable plans with clear structure.

## When to Use

- Starting a new project or initiative
- Breaking down a large task into steps
- Creating a sprint plan or roadmap
- Estimating effort and dependencies

## Plan Structure

### 1. Goal Statement
One sentence: what does success look like?

### 2. Phases
Break into 3-5 phases, each with:
- Phase name and objective
- Key deliverables
- Dependencies (what must be done first)
- Risks and mitigations

### 3. Tasks per Phase
Each task should have:
- Clear description (verb + object)
- Assigned department or role
- Priority (P0/P1/P2/P3)
- Definition of done

### 4. Milestones
Checkpoints where progress is measurable:
- What's complete at this point?
- What can be demonstrated?
- Go/no-go decision criteria

## Output Format

```markdown
# Project: [Name]
Goal: [One sentence]

## Phase 1: [Name]
Objective: [What this phase achieves]
- [ ] Task 1 (P0) -- [department]
- [ ] Task 2 (P1) -- [department]
Milestone: [What's true when this phase is done]

## Phase 2: [Name]
...
```
