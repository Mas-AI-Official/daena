# AVAILABLE TOOLS (operator runner -- Phase 1 detection)

Detected 2026-06-04 on the founder machine (win32). Detection only -- nothing installed, nothing invoked.

| Tool | Status | Path | Non-interactive mode (KNOWN, UNVERIFIED here) |
|------|--------|------|-----------------------------------------------|
| claude | FOUND_BUT_UNTESTED | C:\Users\masou\.local\bin\claude.exe | `claude -p "<prompt>"` (headless print). Autonomous TOOL execution needs a permission mode (e.g. a non-interactive permission setting); NOT verified safe here -> NEEDS_USER_SETUP before enabling. |
| codex | FOUND_BUT_UNTESTED | C:\Users\masou\AppData\Roaming\npm\codex | `codex exec "<prompt>" --skip-git-repo-check` (per global rules). Not verified this loop. |
| gemini | FOUND_BUT_UNTESTED | C:\Users\masou\AppData\Roaming\npm\gemini | `gemini -p "<prompt>"` (Gemini CLI). Not verified this loop. |
| perplexity | NOT_FOUND | -- | No CLI; web/research via Claude/Codex MCP instead. |
| python | AVAILABLE | C:\Python311\python.exe | Python 3.11 -- runs the supervisor (daena_operator.py). |
| python3 | FOUND_BUT_UNTESTED | C:\Windows\System32\python3.bat | Windows Store alias shim; prefer `python`. |
| node | AVAILABLE | C:\Program Files\nodejs\node.exe | -- |
| npx | AVAILABLE | C:\Program Files\nodejs\npx | used by gitnexus etc. |
| git | AVAILABLE | C:\Program Files\Git\...\git.exe | Daena repo @ branch production-readiness-daena-vp, HEAD d963d67. |
| gh | AVAILABLE | C:\Program Files\GitHub CLI\gh.exe | GitHub CLI (read/PR only; no auto-push without gate). |
| rtk | AVAILABLE | C:\Users\masou\.cargo\bin\rtk.exe | output-token compressor for verbose commands. |
| ollama | AVAILABLE | C:\Users\masou\...\ollama.exe | local models (note: Daena backend uses llama-server, not ollama). |

## SELF_START_STATUS: PARTIAL

Three agent CLIs (claude, codex, gemini) exist with documented non-interactive flags, AND python is present to run
the supervisor. BUT none is verified for SAFE autonomous tool-executing sprint continuation in this loop (Phase 1
is detect-only). Therefore the runner ships with `agent_exec.enabled = false` and will NOT invoke an agent until
the founder verifies a chosen CLI and flips that flag. Until then the runner produces a plan + NEEDS_USER_LOOP.md
and requires a manual `/loop`. It does not fake automation.

## Classification key
- AVAILABLE: installed + usable as-is for the runner's purpose.
- FOUND_BUT_UNTESTED: installed, but its autonomous/non-interactive sprint-exec path is not verified here.
- NOT_FOUND: no CLI on PATH.
- NEEDS_USER_SETUP: requires a founder decision/verification (e.g. permission mode, auth) before safe autonomous use.
- HARD_GATED: would touch a hard gate; never auto-run.
