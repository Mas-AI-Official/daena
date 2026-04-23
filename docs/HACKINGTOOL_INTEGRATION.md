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

## Applied decisions — 2026-04-23

All 7 audit open questions resolved with the default recommendations:

1. **YELLOW tier access** — Pro+ only (matches Burp Community/Pro industry split).
2. **AD tools** (BloodHound, Impacket, NetExec, Certipy, Kerbrute, Responder) — YELLOW + FOUNDER tier + per-project `authorized_scope` AD domain.
3. **C2 frameworks** (Sliver, Havoc, Mythic) — catalog-only; **not yet added to allowlist**. Daena never runs them. If we ever add them, they are FOUNDER-only + installed locally via pinned `go install` + `authorized_scope` enforced.
4. **Wireless tools** — only passive tools qualify for YELLOW (hcxtools). Rogue-AP / deauth / evil-twin remain **RED**.
5. **SocialMedia subcategory** — OSINT username-lookup (Sherlock, SocialScan, maigret, holehe) = **GREEN**. Bruteforcers (Facebook-attack, Instagram-bruteforce) = **RED**.
6. **Auto-install UX** — one-click confirm. User sees which binary is pulled before each install.
7. **Stale upstream flagging** — yes. Soft-deprecate + warn for tools whose upstream repo has no commit in > 540 days.

## Runtime gate — now live

The YELLOW runtime gate is shipped as `backend/app/services/security/yellow_runtime_gate.py`. It is **not yet wired into `scan_workflow` / `execution_service`** — that is the next ticket (TICKET-HACKINGTOOL-YELLOW-WIRING). The gate itself:

```python
from app.services.security.yellow_runtime_gate import check_yellow_runtime

decision = check_yellow_runtime(
    tool_name="nmap",
    target="example.com",
    user_role="FOUNDER",
    tenant_id=str(tenant_id),
    user_id=str(user_id),
    session_id=str(session_id),
    is_first_run_in_project=True,
)

if not decision.allow:
    raise PermissionError(decision.reason)

if decision.requires_approval:
    await approval_service.request(decision.audit_log, ...)

await audit_service.log(**decision.audit_log)
await rate_limit.check(decision.rate_limit_key, max_per_hour=10)
await actually_run_tool(...)
```

**Gate contract:**
- **RED names** block at runtime even if a future caller mutates the catalog. Defense-in-depth with the register-time RED gate.
- **Unknown tools** (not in catalog) deny by default.
- **GREEN tools** pass through — audit-logged but no role or scope check.
- **YELLOW tools** require:
  - role in `{FOUNDER, ADMIN, MANAGER}` for the general pool, or `FOUNDER`-only for the active-exploitation subset (sqlmap, commix, impacket, netexec, bloodhound, certipy, kerbrute, responder, evil-winrm, sliver, havoc, mythic, pwncat-cs)
  - non-empty `authorized_scope` for the tenant (deny-by-default if none declared)
  - target matches scope (exact domain, wildcard subdomain, IPv4 CIDR, or source path like `github.com/mas-ai/`)
- **First-run-in-project** flips `requires_approval=True` so the caller knows to create an approval record.

## Catalog state after this commit

| Tier | Count | Tools |
| ---:| ---:| --- |
| GREEN | 25 | Volatility, Binwalk, Ghidra, JadX, Radare2, mitmproxy, testssl, pspy, Sherlock, Cupp, haiti, dnstwist, maigret, holehe, socialscan, wafw00f, trufflehog, trivy, prowler, scoutsuite, mobsf, androguard, wireshark, autopsy, + existing hand-curated entries |
| YELLOW | 15 | nmap, sqlmap, nikto, owasp-zap, nuclei, ffuf, gobuster, feroxbuster, katana, hashcat, john-the-ripper, bloodhound, impacket, netexec, + the FOUNDER-only active-exploitation subset |
| RED | 55+ | Entire Phishing, DDoS, Payload Creation, RAT, rootkit, silent-keylogger, rogue-AP, wifi-deauth, social-bruteforce, Android-abuse, IDN-homograph, doxxing, silent-webcam categories. Hard-denied at register + runtime. |

## Tier-upgrade policy

When the pinned JSON classifies a tool with a **stricter** tier than the hand-curated static `_CATALOG` entry, the JSON tier wins. E.g. `nmap` was previously tier=GREEN (the dataclass default when the tier field was added); the JSON marks it YELLOW; the loader upgrades it to YELLOW in-place, logs `tool_catalog.hackingtool_tier_upgrade`, and preserves the curated `install_cmd` + `capabilities` + `description` from the static entry.

The policy is upgrade-only — a JSON entry can never DOWNGRADE a statically-declared tier. A tool that is already YELLOW cannot be silently GREEN-ified by editing the JSON.

## What this commit does NOT ship (tracked tickets)

### TICKET-HACKINGTOOL-YELLOW-WIRING
Wire `check_yellow_runtime()` into:
- `backend/app/services/security/scan_workflow.py` — before any tool dispatch
- `backend/app/services/execution_service.py` — before any security-tool subprocess spawn
- `backend/app/services/daenabot/router.py` — before dispatching security-shaped intents
Each call site surfaces `decision.reason` verbatim to the user on deny, creates an approval record when `requires_approval=True`, and feeds `decision.rate_limit_key` to a shared limiter (10/hour/user per YELLOW tool).

### TICKET-HACKINGTOOL-YELLOW-RUNTIME
Move `authorized_scope` from JSON file → `Tenant.settings` JSONB column. Pure plumbing change; `load_authorized_scope()` in the gate is the single call site to swap.

### TICKET-HACKINGTOOL-YELLOW-RUNTIME_OLD
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
