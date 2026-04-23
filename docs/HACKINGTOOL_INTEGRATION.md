# HackingTool Integration — Audit + Plan

**Upstream:** https://github.com/Z4nzu/hackingtool
**Audit date:** 2026-04-23
**Decision:** **INTEGRATE FILTERED SUBSET** (default-deny with pinned allowlist + hard RED denylist)

## Why we went through an audit before writing code

The repo is an aggregator that bundles ~185 pen-test tools across 20 categories. Roughly a third of those are explicit attack weapons (credential-stealing phishing kits, DDoS flooders, RATs, rootkits, silent keyloggers, wifi jammers). Adding it blindly to Daena's tool catalog would:

- expose MAS-AI to accessorial-liability risk if a user weaponized one
- violate Daena's governance-first product identity
- embed a `curl | sudo bash` supply-chain pattern into the platform

So we ran a read-only audit (the agent report is at `C:\Users\masou\AppData\Local\Temp\hackingtool_audit.md`) before touching `tool_catalog.py`.

## Findings (short form)

- The **repo itself is clean**: MIT-licensed, actively maintained (60k stars, last push 2026-03-15), no prompt-injection, no zero-width Unicode, no RTL override characters, no base64 blobs, no hidden HTML comments, no LLM-directed meta-instructions. Text is written for human pentesters, not for agents.
- **200 external URLs sampled**: all HTTPS, 193 on `github.com`, zero shortened URLs, one non-GitHub installer (`sliver.sh/install` piped to `sudo bash`) — which we never execute.
- **~55 of the 185 tools are RED** for Daena by policy: the entire Phishing (17), DDoS (5), and Payload Creation (8) categories, plus the RAT (Pyshell), rootkit (Vegile), silent keylogger (Hera), rogue-AP (Fluxion/Wifiphisher/WiFi-Pumpkin/EvilTwin/Airgeddon), wifi-deauth (WifiJammer-NG/KawaiiDeauther), social-media bruteforcer (Facebook attack), IDN homograph (EvilURL), Android abuse (Keydroid/MySMS/Lockphish/EvilApp/WishFish), payload injector (Debinject/Pixload), doxxing (I-See-You), and silent-webcam (SayCheese) tools.
- **~45 tools are GREEN** (safe to offer broadly): forensics (Volatility, Binwalk, Autopsy, Wireshark, pspy), offline reverse engineering (Ghidra, JadX, Radare2), passive OSINT (Sherlock, dnstwist), offline wordlist (Cupp, haiti), own-endpoint testing (testssl, mitmproxy).
- **~85 tools are YELLOW** (dual-use, founder/security-lead-gated): nmap, sqlmap, nikto, ZAP, nuclei, BloodHound, Impacket, NetExec, Certipy, Pacu, Sliver/Havoc/Mythic (C2), pwncat-cs, PEASS-ng, Hashcat, John, Responder-passive, etc. These we will eventually surface behind a Shield `authorized_scope` + approval-queue + rate-limit gate (TICKET-HACKINGTOOL-YELLOW-RUNTIME).

## What this commit ships

1. **`SecurityTier` enum** (`GREEN / YELLOW / RED`) on `SecurityTool`. Existing hand-curated tools default to `GREEN`.
2. **Pinned JSON catalog** at `backend/app/data/hackingtool_catalog.json`:
   - `_pinned_commit`: `v2.0.0-2026-03-15`
   - `allowlist`: 12 GREEN tools (forensics + reverse-engineering + passive OSINT subset)
   - `red_denylist`: 55+ tool names (case + dash/underscore normalized)
   - `red_denylist_reasons`: structured rationale per category
3. **Loader** in `tool_catalog.py`:
   - Reads JSON at import time. No runtime network call to `github.com/Z4nzu/hackingtool`.
   - Rejects entries with tier `RED`, unknown tier, or any name on the denylist (defense in depth).
   - Skips collisions with the hand-curated static `_CATALOG` (the curated install recipe wins).
   - Fail-safe: malformed JSON logs an error but doesn't crash import.
4. **`ToolCatalog.register_tool()`** — raises `ValueError` if a caller tries to register any RED-denylisted name, even if they construct a `SecurityTool` object directly and set `tier=GREEN` to spoof it. Defense-in-depth against runtime injections via future MCP-provided tools or ops scripts.
5. **`is_red_denylisted(name)` public helper** for other services (scan_workflow, execution_service, DaenaBot router) to call before any auto-install or runtime dispatch.
6. **Tests** at `backend/tests/test_hackingtool_integration.py` (46 cases, all pass):
   - RED denylist blocks known-bad names (case + punctuation insensitive)
   - RED denylist blocks register_tool() calls even with spoofed `tier=GREEN`
   - GREEN tools from the JSON land in the runtime catalog with correct tier
   - Known-safe names (nmap, sqlmap, etc.) are NOT denylisted
   - Enum values stable, frozen denylist, malformed JSON doesn't crash

## What this commit does NOT ship (tracked tickets)

### TICKET-HACKINGTOOL-YELLOW-RUNTIME
The full YELLOW runtime gate:

- `BehaviorGuard.check_security_tool(tool_id, target)` called before any YELLOW tool runs.
- `authorized_scope` enforcement: YELLOW tools may only run against targets that match the tenant's declared `authorized_scope` list (their own domains/IPs). Off-scope targets hard-block + security-event-log.
- Approval-queue entry per project, per YELLOW tool, on first-run.
- Per-user rate limit (default: 10 YELLOW invocations per hour).
- Council-mode + FOUNDER tier required for active-exploitation subset (sqlmap, commix, Impacket-active, Sliver/Havoc/Mythic, Evil-WinRM).

The `SecurityTool.tier` field this commit ships is the data-layer hook those gates will read.

### TICKET-HACKINGTOOL-EXPAND-GREEN
Expand the allowlist from 12 to the full ~45 audited GREEN tools. Pure JSON change once TICKET-HACKINGTOOL-YELLOW-RUNTIME lands.

### TICKET-HACKINGTOOL-YELLOW-EXPAND
Add the ~85 YELLOW tools to the JSON allowlist (with `"tier": "yellow"`). Only mergeable after the runtime gate is live.

### TICKET-HACKINGTOOL-CATALOG-REFRESH
Build a Python script (`backend/scripts/refresh_hackingtool_catalog.py`) that fetches `tool_*.py` files from `raw.githubusercontent.com` at the pinned commit SHA, extracts `TITLE / DESCRIPTION / PROJECT_URL`, and diffs against the current JSON. Any new entry lands in `PENDING_REVIEW` state — human review before it's classified GREEN / YELLOW / RED.

## Open questions — Masoud's call

These were surfaced by the audit (section 7 of the full report). Default recommendations applied unless you say otherwise:

| # | Question | Default |
| ---:| --- | --- |
| 1 | YELLOW tier — Pro/Enterprise only, or FREE with ack-dialog? | Pro+ (matches Burp Community/Pro split) |
| 2 | BloodHound/Impacket/Responder/NetExec/Certipy policy | YELLOW + FOUNDER tier + per-project `authorized_scope` AD domain |
| 3 | Sliver / Havoc / Mythic (C2 frameworks) | Catalog-only, never run from Daena; install pointers only |
| 4 | Wireless — hcxdumptool, Bettercap, pixiewps, bluepot | YELLOW (require physical radio), not RED |
| 5 | SocialMedia subcategory | Split: OSINT username-lookup (Sherlock/SocialScan) = GREEN; bruteforcers = RED |
| 6 | Auto-install UX for GREEN tools | One-click confirm (user sees which binary is pulled) |
| 7 | Stale upstream flagging | Yes — soft-deprecate + warn if upstream has no commit in >18 months |

Speak up on any of these and I'll adjust the JSON.

## Refresh policy

- Update `_pinned_commit` in the JSON only via a Masoud-signed PR. No automated sync.
- Diff the extracted catalog against the previous JSON on refresh. Any **new** upstream entry enters `PENDING_REVIEW` — not surfaced until manually classified.
- The RED denylist is append-only. A tool that was ever RED stays RED (paranoia default).

## References

- Full audit report: `C:\Users\masou\AppData\Local\Temp\hackingtool_audit.md` (not committed — founder local)
- CLAUDE.md rule 15 (founder IP / OSS leak prevention) — the JSON catalog here does not contain any founder IP, just public tool metadata, so it is safe to commit to both Daena and Daena OSS.
- v3.7.0-security-supercharge stack (see `D:\Claude-Coworker\inbox.md` HANDS OFF list) — this integration respects that list; no modifications to `real_scanner.py`, `scan_workflow.py`, `zero_fp_gate.py`, `source_correlator.py`, or the existing governance pipeline.
