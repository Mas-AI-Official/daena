---
name: debate
description: Multi-LLM council debate using Karpathy 3-stage proposer-fanout-then-chairman-synthesis pattern. Spawns parallel critiques across all available LLMs (Claude internal sub-agents + Codex CLI/GPT-5.5 + Gemini CLI + Perplexity API), forces big thinking through anti-incremental prompts, then synthesizes. Trigger when user says "debate", "council", "ask all LLMs", "force big thinking", or wants model-diverse stress-testing on high-stakes decisions. Do NOT use for routine code edits or simple lookups.
---

# debate — Multi-LLM Council Skill (Daena mirror)

> Canonical: `~/.claude/skills/debate/SKILL.md` (Claude Code primary)
> This file: Daena runtime mirror per SKILLS SYNC RULE

This is the Daena-runtime mirror of the canonical Claude Code skill at `C:\Users\masou\.claude\skills\debate\SKILL.md`. The Daena runtime (`backend/app/services/chat_orchestrator.py` Council/QE flow) implements the same Karpathy 3-stage architecture programmatically. See the canonical file for the full skill specification.

## Daena-specific integration notes

The Daena runtime already implements proposer fan-out + chairman synthesis as part of Council and Quintessence reasoning modes. The skill in this file is for parity with Claude Code, so that Daena and Claude Code share the same playbook when delegating to external CLIs (Codex, Gemini) or APIs (Perplexity).

When Daena's `chat_orchestrator.py` enters Council/QE mode and the operator has explicitly toggled multi-runtime mode (council_models >= 3), the runtime should:

1. Detect available council members the same way Claude Code does (`codex --version`, `gemini --version`, `$PERPLEXITY_API_KEY`).
2. Use the same force-big-think prompt template with explicit disagreement permission.
3. Synthesize via Daena's chairman model (the configured Primary Mind, e.g. Claude Code or local Ollama).
4. Save the transcript to `D:\Claude-Coworker\debates\<topic>-<date>.md` for shared replay.

See canonical skill for full details on:
- Trigger phrases
- Available council members + auth detection
- Force-big-think prompt template
- 6-step execution flow
- Path gotchas (Windows /tmp mismatch)
- Failure modes & recovery
