# Call Center Automation Pattern

How Daena handles inbound + outbound phone calls as a capability of
the Customer Service department (and any other department with a
voice capability), using the local voice LLM already running on the
host. No standalone "Voice Console" UI; voice is infrastructure.

This aligns the voice stack with the department model documented in
`AGENT-OPS-PLAYBOOK.md`. The voice pipeline (`backend/app/services/
voice/`) stays. The frontend page that surfaced it as a user feature
was removed 2026-04-17.

---

## The Canonical Call Center Pattern

Modern automated call centers (Five9, Genesys, NICE, plus the newer
AI-native ones like Retell, Bland, Vapi, Cresta) all share the same
6-stage pattern. Daena maps each stage to existing primitives.

```
1. Call arrives on a DID (inbound) / dialed (outbound)
       |
       v
2. Identify intent
   (IVR menu OR AI intent classifier OR called-number-to-dept map)
       |
       v
3. Route to the right department + agent
   (skill-based routing: which department owns this intent)
       |
       v
4. Conversational turn loop
   (STT -> LLM turn -> TTS, per-turn risk classification)
       |
       v
5. Pause for high-tier utterance approval (governance gate)
   (pricing, commitments, PII, retention offers)
       |
       v
6. Wrap-up + audit chain
   (transcript persisted, call metadata linked to ChatSession,
    SHA-256-chained audit entry)
```

## Stage-by-Stage Mapping to Daena

### 1. Arrival -- DID assignment per department

Each customer-facing department that answers phones gets a dedicated
DID (phone number) from the telephony provider. VAPI supports number
buckets; Twilio gives you full numbers.

Mapping:

| Department | DID purpose |
|---|---|
| Customer Service | main support line |
| Sales | inbound demo / quote requests |
| Security Operations | incident response hotline (regulated customers) |
| Founder (overflow) | VIP / escalation |

Calls to the support DID land in Customer Service's queue. Never
mixed. Departments do not cross-pollinate calls unless transferred.

### 2. Identify intent

Two paths, not mutually exclusive:

**(a) Zero-IVR intent classifier (default)**. On connect, Daena
speaks a 10-second opener + recording-consent line (legal must-have
in two-party-consent states), asks an open question ("What brought
you to us today?"), runs the transcript through a lightweight
intent classifier backed by DCP lenses. Routes to the right
department based on the classification.

**(b) Legacy IVR fallback**. For enterprise customers that insist on
menu-tree dialing ("Press 1 for Sales..."), VAPI's DTMF capture
drives the same routing.

The classifier lives in the Voice department's skill pack:
`skill:support.intent-classify-on-arrival` (to be authored in Phase N).

### 3. Route to department + agent

Uses the existing SwarmPlanner + DepartmentStateService (Session A):

- SwarmPlanner inspects the classified intent, picks the department.
- DepartmentStateService returns the next IDLE agent in that
  department. If none, queues with hold-music + periodic status.
- The Daena VP meta-agent (Session B) applies cross-department
  policies (e.g., if pricing appears in Customer Service intent,
  loop in Sales automatically).

Skill routing to agents uses the same scoring the text chat router
already uses (tag_match, locality, cost, context_window). One agent
can be flagged as the **voice lead** for a department -- that agent
gets a consistent voice identity across calls so returning customers
hear the same "Amy" or "Jordan" voice.

### 4. Conversational turn loop

Already built: `backend/app/services/voice/conversation_session.py`
+ `stt_pipeline.py` + `tts_pipeline.py`.

Provider stack for the local-LLM setup Masoud has on his laptop:

- **STT**: `FasterWhisperProvider` (local, free; base or small model).
- **LLM turn**: routes through the existing 10-stage orchestrator
  (chat_orchestrator.py) so every spoken turn gets the same
  governance + audit as a text chat turn. The voice WebSocket's
  current `_echo_chat_turn` is a Phase-I-scaffold placeholder; the
  next focused session wires it to `stream` through the orchestrator.
- **TTS**: `PiperProvider` (local, free; per-department voice model
  chosen from the Piper voice catalog).

Per-agent voice assignment pattern:

```python
# app/services/departments/voice_config.py (future)
DEPARTMENT_VOICES = {
    "Customer Service": "en_US-amy-medium",   # warm, mid-pitch
    "Sales":            "en_US-ryan-high",    # direct, confident
    "Security Ops":     "en_GB-alan-medium",  # calm, technical
    "Legal":            "en_US-kathleen-low", # measured, formal
    "Finance":          "en_US-joe-medium",
    ...
}
```

Assignment is per-department, not per-call, so a customer who calls
Customer Service twice in a week hears the same voice both times.

### 5. Governance gate (already wired)

`ConversationSession` already classifies each reply via
`default_tier_classifier`. HIGH (pricing, commitments) and CRITICAL
(PII, credentials, data export) utterances emit
`status=awaiting_approval` with an approval_id. The InlineApproval
Banner shipped in ChatPage picks up any pending approval within 5
seconds, so a founder or supervisor can grant/deny without leaving
the chat view.

Call-center-specific extension needed (Phase I.2):

- **Hold pattern while awaiting approval**: play a short "one moment
  please" TTS utterance and hold-music loop until the approval
  resolves. `ConversationSession` needs a `pause_with_hold()`
  method.
- **Warm transfer**: when approval rejects or the agent hits its
  skill boundary, transfer the call to a human supervisor or a
  different department's voice lead. VAPI's transfer API handles
  the carrier leg; Daena sends a full context payload ahead of the
  transfer so the human does not start cold.

### 6. Wrap-up + audit chain

After call-end (hangup, timeout, or transfer):

- Full audio persisted to AES-256 `EvidenceVault` (reuses the
  pre-existing `security/evidence_capture.py`).
- Streaming transcript stored with per-chunk SHA-256 hash.
- Call metadata (carrier, caller ID, duration, recording-consent
  version) linked to the originating `ChatSession`.
- Every governance tier event during the call landed an audit row
  already; the final wrap writes a summary row with the tier
  distribution.
- Skill Governance ingests the transcript into the Skill Refinery
  via the existing `/skills/refinery/extract` endpoint so successful
  call patterns compound into T3 skills.

Retention policy: 18 months for enterprise tier, 36 months for
regulated enterprise, configurable for Sovereign deployments.

## What Changes in the UI

**Before** (the mistake I shipped):
- New top-level `/voice` Voice Console page with mic, transcript,
  connection toggle. Treated voice as a user feature.

**After** (aligned with department model):
- No top-level voice page.
- Each department's room at `/departments/{id}` gains a "live calls"
  pane that shows any active call that routed to this department.
  Operators monitor by navigating to their department, not to a
  generic voice page.
- The Customer Service department room has the richest voice UI
  because it owns the main support DID. Sales has a lighter
  version for demo-request calls. Security Ops has an incident-
  response-specific panel.
- Founders see a roll-up across all departments on `/company` (the
  existing Company Dashboard).

## Local Voice LLM

Masoud confirmed a local voice LLM runs on his laptop. The voice
pipeline's provider plugin model already supports this:

- `FasterWhisperProvider` for STT: local, CPU-only (int8), sub-
  second latency on modern laptops.
- `PiperProvider` for TTS: local, CPU-only, sub-second latency.
- Both lazy-import their dependencies, so `pip install
  faster-whisper piper-tts` enables them without further wiring.

If Masoud's laptop already runs a different local LLM stack
(Whisper.cpp, Ollama-whisper, VoiceBox, etc.) add a new provider
class implementing `STTProvider` or `TTSProvider` and register it.
10 lines per provider, no call-site changes anywhere else.

## Outbound Calls (Sales)

Same pipeline, reverse direction. VAPI or Twilio places the call;
on answer, the conversation_session takes over. The Sales agent's
voice speaks the opener, classifies the callee's response, and runs
the scripted discovery-call skill pack (authored in `CONTENT-OPS-
PLAYBOOK.md` Seed Skill 7).

Governance guardrails specific to outbound (already documented in
the playbook):

- Max 100 outbound dial attempts per tenant per day for first 90 days.
- Pre-recorded intro disclosing AI assistant + recording consent.
- Mandatory stop-rule on inbound "please stop" / "unsubscribe".
- Tier 3 approval on pricing, demo scheduling, contract discussion.

## Phase I.2 Delivery Scope (next focused session)

Small, tight:

- Wire `ConversationSession._echo_chat_turn` replacement that calls
  the 10-stage orchestrator's `stream` method. ~30 lines in
  `voice_ws.py`.
- Add `pause_with_hold()` method to `ConversationSession`. ~15 lines.
- Add `DEPARTMENT_VOICES` config map + per-call voice resolution in
  the TTS stage. ~20 lines.
- Add the "live calls" pane to `DepartmentChatPage.tsx` (a small
  component that polls active `ChatSession` rows tagged with a
  `call_handle_id`). ~80 lines of TSX.
- DID-to-department routing: a static map in `voice/outbound.py`
  resolving inbound phone numbers to departments. ~10 lines.

No new user-facing pages. No standalone voice UI. Every capability
lives inside the department that owns it.

## Why This Is Better Than the Page I Built

- **Consistent mental model**: everything is a department. No
  exceptions. A user never has to learn "voice is over here, CRM
  is over there, engagements are in a third place."
- **Persistence**: a call that lands in Customer Service shows up
  in Customer Service's history forever. The Voice Console page I
  built had no department affiliation, so a call was orphaned.
- **Governance consistency**: the same approval queue the department
  already uses for text actions catches voice actions too. No dual
  approval surfaces.
- **Brand coherence**: per-department voice identity means customers
  recognize who they're talking to. A generic voice console has no
  identity.
- **No ghost features**: the page I built was a demo harness, not a
  product. Removing it removes a distraction for real customers.
