# 3-minute demo script -- Daena on Qwen Cloud

Target: the Global AI Hackathon with Qwen Cloud (Devpost). Deadline
2026-07-09 14:00 PDT. Recording is founder-gated; this is the shot list.

## One-line pitch (say first, on camera)
"Most multi-agent demos show capability. We show accountability: every agent
action is governed by policy and recorded to a tamper-evident audit trail,
running on Qwen Cloud."

## Beat sheet (0:00 -- 3:00)

**0:00-0:20 -- The problem.**
Multi-agent systems are getting capable enough to take real actions. The
missing layer is proof: what did each agent do, was it allowed, can you
trust the record. Show the title card: "Daena on Qwen Cloud -- governed
multi-agent, signed audit trail."

**0:20-0:45 -- The scenario.**
Show `scenario.py` Vault contract. "A smart-contract security review. This
Vault has a reentrancy bug. Four Qwen agents review it -- one is told to
write a working exploit." Highlight the four-agent table from the README.

**0:45-1:30 -- Run it (governed).**
Terminal: `python run_demo.py`. Narrate the output live:
- ANALYST (qwen-plus) finds the reentrancy. RUN.
- ADVERSARY (qwen-max) asked for the exploit -> **GATE**. "The model can
  write it. The governance gate classified that Tier 4 and held it for human
  approval. Capability withheld on purpose."
- AUDITOR (qwen-turbo) scores it CRITICAL. RUN.
- JUDGE (qwen-max) synthesizes the verdict and the remediation -- without the
  exploit.

**1:30-2:10 -- The audit trail.**
"Every one of those decisions, including the gated one, is on a hash chain."
Run `python run_demo.py --out result.json`, open `result.json`, scroll the
`audit_trail`: show `prev_hash` / `entry_hash` linking each entry. "Same
SHA-256 payload format Daena uses in production."

**2:10-2:40 -- Tamper-evidence (the kicker).**
`python run_demo.py --tamper`. "Now an attacker edits the ledger to hide that
the exploit was gated -- flips APPROVAL_REQUIRED to ALLOWED." Show
`valid=False reason=content_tamper first_broken_index=1`. "The chain catches
it and points to the exact row."

**2:40-3:00 -- Close.**
"Governed action plus a signed, tamper-evident record, on Qwen Cloud. The
consensus topology is patent-pending. This is the accountability layer
production AI needs." Show the repo URL card and `python -m pytest tests/`
going green.

## Capture checklist
- [ ] Replay run (deterministic -- safe to re-take).
- [ ] One live run on Qwen Cloud for authenticity (founder runs, key set).
- [ ] `result.json` audit-trail scroll.
- [ ] `--tamper` detection.
- [ ] `pytest` green.
- [ ] No secrets / no real keys on screen.
