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

## SELF_START_STATUS: BUILT + CORRECT, BUT NO CLI CAN SAFELY SELF-DRIVE ON THIS WINDOWS BOX (verified 2026-06-04)

Live verification (founder-authorized enable + run):
- codex: runs non-interactively, BUT its SAFE sandbox mode (`--sandbox workspace-write`) is INERT on this Windows
  machine -- "windows sandbox: setup refresh failed with status exit code: 1" makes shell + MCP + file tools all
  fail, so codex correctly refused to act ("can't safely inspect or edit ... right now"). Its only FUNCTIONAL mode
  is `--sandbox danger-full-access` (full filesystem + network + MCP) = UNSAFE for an unattended loop. So codex is
  either safe-but-useless or useful-but-unsafe here. Flag order matters: `--sandbox` MUST precede the prompt
  positional (verified -- SANDBOXCHECK reported workspace-write only with flags-first; placing it after the prompt
  silently leaves danger-full-access).
- claude -p: 401 Invalid authentication credentials (headless not logged in; needs re-auth + a verified
  non-interactive permission mode before tool use).
- gemini -p: timed out non-interactively (needs config/auth verification).

Conclusion: the runner is BUILT, correct, and bug-fixed (flag order + UTF-8 stream decode verified end-to-end via
a clean --once that reached DONE), but `agent_exec.enabled = false` because no CLI can safely AND functionally
self-drive here yet. Path to TRUE self-start: (a) fix codex's Windows sandbox so workspace-write works (codex
platform issue), or (b) re-auth claude + verify its headless permission mode, or (c) configure gemini
non-interactive. Until one passes, use a manual `/loop`. The runner does not fake automation.

## Classification key
- AVAILABLE: installed + usable as-is for the runner's purpose.
- FOUND_BUT_UNTESTED: installed, but its autonomous/non-interactive sprint-exec path is not verified here.
- NOT_FOUND: no CLI on PATH.
- NEEDS_USER_SETUP: requires a founder decision/verification (e.g. permission mode, auth) before safe autonomous use.
- HARD_GATED: would touch a hard gate; never auto-run.
