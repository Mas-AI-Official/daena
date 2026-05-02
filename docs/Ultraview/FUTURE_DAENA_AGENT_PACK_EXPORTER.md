# FUTURE: Daena Agent Pack Exporter

**Status:** Parked. Not in current canonicalization sprint.
**Trigger to start:** After Daena Execution Spine is live and stable.
**Owner:** TBD (assign when picked up).
**Priority:** P3 (post-canonicalization, post-Spine).

---

## 0. Hard Rules Locked At Park-Time (2026-05-02)

These rules apply whenever this work is eventually picked up. They
exist because the founder considered the alternatives and rejected
them. Re-litigating any of these requires explicit founder approval,
not just an "easier way" justification:

1. **Do NOT vendor any external agents repo into Daena.** This
   includes (but is not limited to) agency-agents and any equivalent
   collection. Daena is the source of truth, not a downstream
   consumer.
2. **Do NOT copy external agents into Daena's runtime.** Daena does
   not load Claude Code agents, OpenCode agents, Gemini CLI agents,
   Cursor rules, OpenClaw workspaces, or MCP manifests written by
   third parties to drive its own departments.
3. **Do NOT add new runtime dependencies** on any of those tools'
   client libraries or SDKs. The exporter writes plain text files in
   well-documented formats; Daena does not import their packages.
4. **Do NOT interrupt the current canonicalization sprint.** Park the
   idea here, do not start.
5. **One-way only.** Daena -> external formats. No 2-way sync, no
   "import a Cursor rule and become a department". Daena is upstream.
6. **No scope sprawl in any future PR that picks this up.** The
   exporter is one feature with six output targets; it is not a
   replatforming, not a marketplace, not a hosted service. If
   marketplace/hosting comes later, it is a separate effort that
   builds ON the exporter, not folded INTO it.

---

## 1. Why This Exists (The Idea)

Daena's internal structure (10 departments x 6 capabilities, soul
vault, skills, DCPs) is more expressive than any single external
agent runtime. Exporting it lets a Daena tenant give one of their
operators a Cursor / Claude Code / OpenCode setup that "feels like
the same Engineering MIND we use inside Daena", without that operator
running Daena locally.

Use cases the founder has talked about:

* A new Daena tenant wants to seed their developers' Claude Code
  installs with the same Engineering MIND prompt + tool list +
  guardrails the tenant uses inside Daena.
* A consulting engagement wants to leave the customer with "your
  Daena Sales department, exported as a working Cursor rule pack and
  an OpenCode agent bundle" so the customer keeps a piece of the
  setup after Daena rolls off.
* OSS / fighter-brand: Daena OSS could publish a small "departments
  pack" derived from the commercial departments via the exporter,
  giving newcomers a taste without granting them the full commercial
  surface.

In all three cases the exporter writes a packaged pile of files that
the external runtime knows how to consume, and Daena keeps owning
the canonical definition.

---

## 2. Source Material (Inside Daena)

These are the inputs the exporter reads. The exact schema may shift
between now and when this work starts; verify before designing the
mapping table.

| Source | Where it lives today | What it contains |
|--------|----------------------|------------------|
| Department definitions | `backend/app/core/constants.py` `DEFAULT_DEPARTMENTS` | 10 departments, sunflower index, color, default agents |
| Sub-capability enum | `backend/app/core/constants.py` `SubCapability` | MIND, EYES, HANDS, VOICE, SHIELD, MEMORY |
| Soul vault | `backend/app/soul/` (inside codebase, gitignored) and `D:\Ideas\Daena-Mind\soul\` (outside codebase) | 6 files: foundation, reasoning, personality, loyalty, shield, evolution |
| Skills | `D:\Ideas\Daena\skills\<name>\SKILL.md` (canonical) and the per-runtime mirrors | YAML frontmatter + markdown body |
| Domain Context Packs (DCPs) | `backend/app/config/dcps.json` | 55 packs covering 3 domains x N experts |
| Per-department policy | TBD - currently in `DepartmentPolicy` model | Permission matrix, budget, approval thresholds |
| Tools / connectors registered to a department | Connections V2 registry (`connection_v2/`) | Per-department tool whitelist |

**Verify before designing:** the soul vault location may move when
the Execution Spine lands, and the DepartmentPolicy schema is still
in flux. Re-read `D:\Ideas\Daena\CLAUDE.md` AGENT MODEL section and
`docs/Ultraview/DAENA_EXECUTION_SPINE_PRD.md` (if present at trigger
time) before locking the source schema.

---

## 3. Target Formats (Outside Daena)

The exporter must produce six output families. Each has its own
on-disk layout, metadata format, and capability surface. Treat each
as a separate writer module so they can evolve independently.

### 3.1 Claude Code agents
* On-disk layout: `~/.claude/agents/<name>/agent.md`
* Format: markdown body + YAML frontmatter declaring `name`,
  `description`, `tools`, optional `model`
* Daena department -> Claude Code agent mapping: one Claude Code
  agent per (department, capability) pair, name like `daena-eng-mind`
* Tools: derived from the department's connection allowlist + the
  capability's intrinsic tool set
* Open question at park-time: how to represent SHIELD as a
  capability when Claude Code agents do not have a native "shield"
  primitive. Likely fold SHIELD into the agent's system prompt as
  hard rules.

### 3.2 OpenCode agents
* OSS Claude Code analogue.
* Format diverges in places (e.g. tool registration, model selection
  defaults). Verify against OpenCode docs at trigger time.
* Reuse the Claude Code writer's mapping where possible; fork a
  per-target adapter only where the format actually diverges.

### 3.3 Gemini CLI agents
* Gemini CLI added agent support in 2026 Q1; verify the current
  format at trigger time.
* The mapping is likely simpler than Claude Code (fewer tool
  primitives) so some Daena capabilities may not have a faithful
  Gemini representation. Document those gaps in the export report.

### 3.4 Cursor rules
* On-disk layout: `.cursor/rules/*.mdc` files (or `.cursorrules`
  legacy single file)
* Format: markdown with conditional triggers and per-file/path
  scoping
* Daena department -> Cursor rule mapping: one rule file per
  department, scoped to file globs that match the department's
  natural surface (e.g. Engineering MIND scopes to `**/*.{ts,py}`,
  Marketing scopes to `**/*.{md,html}`)
* Cursor has no "agent" model; rules are passive context injection.
  The exporter must downgrade department prompts into rule prose,
  losing the call/response shape. Document the loss.

### 3.5 OpenClaw workspaces
* On-disk layout: workspace YAML descriptors
* Format: declarative workspace spec with allowed tools, environment,
  startup commands
* Daena department -> OpenClaw workspace mapping: one workspace per
  department, with the capability surface as available toolsets
* OpenClaw is in the HOT PATH per CLAUDE.md - Daena is NOT. The
  exporter writes workspaces FOR users to consume in OpenClaw; Daena
  itself never executes from one.

### 3.6 MCP manifests
* On-disk layout: `mcp.json` (server descriptor)
* Format: JSON declaring tools, resources, prompts
* Daena department -> MCP server: each exported department becomes a
  thin MCP server that exposes the department's tool surface +
  prompts. The actual server code is a separate concern (likely a
  small wrapper around the exported manifest); the exporter only
  writes the manifest.
* MCP is the most "Daena-native" of the six formats since Daena
  already speaks MCP both as client and server. The mapping should be
  the cleanest.

---

## 4. Suggested Architecture (Sketch, NOT Locked)

```
backend/app/services/agent_pack_exporter/
  __init__.py
  source/
    department_loader.py    # reads DEFAULT_DEPARTMENTS + DepartmentPolicy
    soul_loader.py          # reads soul vault
    skill_loader.py         # reads skills/*/SKILL.md
    dcp_loader.py           # reads dcps.json
    schema.py               # canonical intermediate representation
  targets/
    claude_code_writer.py
    opencode_writer.py
    gemini_cli_writer.py
    cursor_writer.py
    openclaw_writer.py
    mcp_manifest_writer.py
  cli.py                    # daena export agents --target claude-code --out PATH
  report.py                 # post-export summary: what was exported, what was lost
```

CLI shape (sketch, not locked):

```
daena export agents --target claude-code --out ~/.claude/agents/daena/
daena export agents --target cursor --out ./my-project/.cursor/rules/
daena export agents --target all --out ./daena-pack/
```

The intermediate representation (`source/schema.py`) is the
de-coupling layer: source loaders fill it, target writers read it.
Adding a 7th target later means only writing one new writer.

---

## 5. Test Surface (Required Before Ship)

Whoever picks this up MUST add these tests before the first commit:

1. **Round-trip schema test** for the intermediate representation:
   build a representation from a known department, verify all six
   writers consume it without crashing.
2. **Format conformance test** per target: emitted file matches the
   target's documented schema (parse with the target's own validator
   if available, otherwise structural assertions).
3. **Lossy-mapping disclosure test**: the export report MUST list
   every Daena capability that could not be faithfully expressed in
   each target. A target writer that silently drops a capability is
   a bug. The report makes the loss visible.
4. **No-secret-leak test**: the soul vault must NOT be exported
   verbatim. The exporter strips the sensitive sections (T4
   founder-private, T5 EvilBob anything, internal IP comments) before
   writing any external file. Pin this with a test that fails if any
   exported file contains known secret markers.
5. **Idempotency test**: running the exporter twice with the same
   inputs produces byte-identical outputs.

---

## 6. Cross-References (For The Future Agent)

When this work starts, the following sources will likely matter:

* `D:\Ideas\Daena\CLAUDE.md` AGENT MODEL section - 10 dept x 6
  capability shape
* `D:\Ideas\Daena\backend\app\core\constants.py` `DEFAULT_DEPARTMENTS`
  + `SubCapability` + `PermissionLevel`
* `D:\Ideas\Daena\skills\` directory - canonical skill format
* `D:\Ideas\Daena-Mind\soul\` - soul vault (read-only at export time)
* `docs/Ultraview/DAENA_EXECUTION_SPINE_PRD.md` (if present) - the
  Spine schema this exporter follows
* CLAUDE.md SKILLS SYNC RULE - shows how skills already mirror across
  Claude Code and Daena; the exporter generalizes this pattern to 6
  targets.
* CLAUDE.md ORGANIZE-BY-UMBRELLA PROTOCOL - the exporter output
  directory should follow the umbrella pattern (one folder per target,
  not 6 sibling folders at top level).

---

## 7. Why This Is Parked, Not Cancelled

The founder explicitly stated this is **future packaging/reference
work, not a current sprint item**. The reasons it's deferred:

1. **The Execution Spine isn't live yet.** Until the Spine PRD lands
   and the source schemas (DepartmentPolicy, capability surface,
   soul vault layout) stabilize, designing an exporter against them
   is wasted effort - the mappings will need to be redone when the
   schemas shift.
2. **Canonicalization first.** The current sprint is collapsing
   duplicate surfaces inside Daena (PR-3 Connections, PR-GOV-01
   Founder guard, PR-4 Security Scan, PR-GOV-02..05 governance).
   Adding an outbound exporter while the inbound surface is still
   being unified would compound complexity.
3. **Better target studies later.** Each of the six target formats
   is a moving target itself. Picking up this work in 1-3 months will
   benefit from more mature documentation on Cursor MDC rules,
   OpenCode agent semantics, and Gemini CLI agent shape.

---

## 8. Trigger Conditions (When To Start)

Start this work when ALL of these are true:

- [ ] Daena Execution Spine PRD is approved
- [ ] Execution Spine implementation has shipped (department + soul
      + skill + capability schemas are stable)
- [ ] Current canonicalization sprint has finished (no open
      PR-CANON-* tickets)
- [ ] Founder has explicitly authorized starting this PR (it does
      not auto-trigger)

If any of those is false, this stays parked.

---

## 9. Out Of Scope For This Note

This document is a **research and design parking lot**, not a spec.
It deliberately does NOT:

* Examine agency-agents source code (the founder said "study after
  Spine is live", not "study now")
* Lock the intermediate representation schema (waits for Spine)
* Lock the CLI shape (sketch only)
* Estimate effort (depends on Spine schema)
* Pick a target order (depends on tenant demand at trigger time)
* Define a marketplace, hosting, or distribution model (separate
  effort, not part of the exporter)

The next agent who picks this up should treat the parked rules in
Section 0 as load-bearing constraints and the rest as informed
sketches to refine.
