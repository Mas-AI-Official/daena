# DeFi MVP Demo Script
## Daena DeFi Guardian - 2 Minute Hackathon Demo

---

## Pre-Demo Setup

1. **Sample Contract Ready**: `workspace/contracts/VulnerableDAO.sol`
2. **Slither Installed**: `pip install slither-analyzer`
3. **DeFi Tools Enabled**: Control Plane → DeFi tab → Enable Slither
4. **Browser Open**: `http://localhost:8000/ui/control-plane`

---

## Demo Script (120 seconds)

### 0:00 - 0:15 | Hook
> "Every week, another DeFi protocol loses millions to preventable vulnerabilities. 
> What if your AI VP could audit smart contracts, generate reports, and fix issues—
> all with governance guardrails?"

### 0:15 - 0:30 | Open Control Plane
- Navigate to Control Plane
- Click "Web3 / DeFi" tab
- Show the clean interface

> "This is Daena's DeFi Security module. It lives inside our unified Control Plane—
> no sprawling dashboards, just one place for everything."

### 0:30 - 0:50 | Run Quick Scan
- Select workspace: `contracts/`
- Enter contract: `VulnerableDAO.sol`
- Click "Quick Scan (Read-Only)"

> "Let's scan a DAO contract. Watch—Daena orchestrates Slither, our static analyzer, 
> in a sandboxed environment. No network access, strict timeouts, full audit logging."

[Wait for scan to complete]

### 0:50 - 1:10 | Show Findings
- Expand findings panel
- Highlight critical vulnerability (reentrancy)
- Click on evidence

> "Found it: a classic reentrancy bug on line 42. Daena shows severity, location, 
> tool evidence, and a plain-English recommendation. 
> This is what auditors spend hours finding manually."

### 1:10 - 1:30 | Generate Fix
- Click "Suggest Fixes"
- Show AI-generated patch diff

> "Now watch the magic. Daena generates a fix using the checks-effects-interactions pattern.
> This isn't a template—it's context-aware code generation."

### 1:30 - 1:50 | Approval Flow
- Click "Apply Fixes"
- Show approval modal popup
- Point to "Requires Founder Approval" badge

> "Here's where governance matters. High-risk changes require explicit approval.
> No rogue AI modifications. The founder sees the diff, approves, and only then 
> does Daena create the branch."

[Click Approve]

### 1:50 - 2:00 | Wrap Up
- Show "PR Created" confirmation
- Quick flash of audit log

> "In two minutes: scan, report, fix, governance. This is Daena DeFi Guardian—
> AI-powered security with human oversight. Thank you!"

---

## Backup Talking Points

**If scan is slow**:
> "We're running real analysis here—Slither inspects every code path. 
> In production, we queue scans and alert when done."

**If asked about other tools**:
> "We support Slither, Mythril, Foundry, and Echidna. Each tool is sandboxed, 
> has timeouts, and requires explicit enablement."

**If asked about false positives**:
> "Daena uses AI to triage findings—cross-referencing tool outputs, 
> filtering noise, and ranking by exploitability."

---

## Key Messages to Hit

1. **Multi-agent audit**: Daena orchestrates multiple tools
2. **Governance gates**: High-risk = approval required
3. **Not just detection**: Generates fixes, creates PRs
4. **Security-first**: Sandboxed, logged, no auto-execution
5. **Unified UX**: One Control Plane, not dashboard sprawl

---

*Demo Script - Daena DeFi Guardian - 2026-01-31*
