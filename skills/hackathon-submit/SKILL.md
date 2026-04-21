---
name: hackathon-submit
description: Given a hackathon + idea, generate the submission package (pitch deck, demo script, README, form draft). Human approval gate before any external action.
trigger: User picks a hackathon from the hunter pipeline and says "build the submission for [name]".
inputs: hackathon URL, project idea (1 sentence), any existing codebase reference
outputs: D:\Claude-Coworker\hackathons\submissions\<slug>\ (pitch.pptx, demo.md, README.md, form-draft.md)
requires: anthropic-skills:pptx, anthropic-skills:docx, web browsing (read-only on event page)
claude_only: false
---

# Hackathon Submit Builder

## Purpose

Produce a hackathon submission package quickly enough to make the deadline
but honestly enough to be competitive. No auto-submit to external forms —
Masoud always reviews the package and submits himself.

## Inputs required from Masoud

1. **Hackathon URL** (from the pipeline)
2. **Project idea** — 1 sentence. Example: "A Klyntar extension that
   audits the attack surface of any Devpost AI project in 60 seconds."
3. **Codebase hook** — which existing MAS-AI repo/component becomes the
   demo. Example: "Fork Klyntar scan-workflow + wrap it with a Devpost-
   specific adapter."

## Outputs (all generated in
`D:\Claude-Coworker\hackathons\submissions\<event-slug>\`)

1. **pitch.pptx** — 8-slide deck:
   - Problem (1 slide) · Solution (1) · Demo screenshot (1) · Architecture (1)
   - Market / who cares (1) · Traction / validation (1) · Team (1) · The ask (1)
   Use `anthropic-skills:pptx` skill + MAS-AI brand tokens (dark slate + gold + cyan).
2. **demo-script.md** — 60-second demo narration. Fits the most common
   hackathon video-submission requirement.
3. **README.md** — matches the event&apos;s README requirement (GitHub repo will
   need this).
4. **form-draft.md** — every text field from the event submission form,
   pre-filled. Masoud copy-pastes to actually submit.
5. **demo-video-prompts.md** — prompts for the `video-production` skill to
   generate a demo video (AI-generated B-roll + screen capture guidance).

## Process

1. Read the event's rules/judging criteria via WebFetch.
2. Align the project idea to the judging criteria (especially: innovation,
   feasibility, impact, use of sponsor tech if any).
3. Check the F6S tracker to avoid submitting the same idea to two
   conflicting programs that forbid dual-submission.
4. Generate the 5 artifacts above.
5. Run the `anthropic-skills:skill-creator` QA pattern: re-read the
   artifacts, score them against judging criteria, flag any weak section.
6. Write a final summary to the event folder: `SUBMISSION_CHECKLIST.md`
   with every action Masoud needs to take to submit.

## Safety + governance

- Never submit the form automatically.
- Never claim credentials we don&apos;t have (per the `happy-munching-storm`
  plan: 2 patents, Google for Startups, Anthropic Academy, Seneca AI,
  Klyntar + Daena shipped. Nothing else.)
- If the event requires a team: flag in the checklist. Solo submissions
  are preferred.
- If the event has exclusivity clauses (e.g., "submitted code may not be
  submitted elsewhere"), flag in the checklist loudly.

## Success metric

1 submission per week (Masoud's max review bandwidth). Prize accepted = $.
Prize not accepted = brand exposure + feedback loop into the next submission.
