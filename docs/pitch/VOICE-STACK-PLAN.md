# Daena Voice Stack — Plan and Audit

Current state as of April 2026 + the Phase-2 build-out for outbound voice agents. Keyed to Roadmap V2 Phase I.

---

## What Exists Today (Phase 1)

- `backend/app/services/voice_service.py` - settings-only service, no actual audio processing. Designed as a thin server layer over browser-native Web Speech API.
- `frontend/src/providers/VoiceProvider.tsx` - React context for voice state.
- `frontend/src/components/chat/VoiceControls.tsx` - mic button, push-to-talk, conversational mode toggle.
- `frontend/src/pages/settings/SettingsVoice.tsx` - user preferences tab (rate, voice, provider hint).

**How it works today**: the browser runs SpeechRecognition and SpeechSynthesis natively. Transcribed text is sent as a normal chat message. Response text is read aloud by SpeechSynthesis. Zero server audio handling, zero cost.

**What it cannot do today**:
- Outbound phone calls
- Inbound phone calls
- Server-side transcription for audit
- Conversation-level interruption handling (barge-in)
- Voice interactions outside a browser session
- Speaker diarization
- Call recording with governance-approved storage

The upgrade path in `voice_service.py` already documents the direction: WebSocket audio streams to Whisper for STT, and ElevenLabs or XTTS for TTS.

---

## Phase 2 Architecture

### Providers (pluggable, governance-gated)

**STT (speech to text)**

| Provider | Mode | Use case | Cost |
|---|---|---|---|
| Browser SpeechRecognition | Phase 1 | Casual in-browser chat | Free |
| faster-whisper local | Phase 2 default | Most chat and all SOVEREIGN deployments | Free (local compute) |
| OpenAI Whisper API | Phase 2 fallback | When local GPU unavailable | $0.006/min |
| Deepgram Nova-3 | Phase 2 premium | Real-time call streaming | ~$0.0043/min |

**TTS (text to speech)**

| Provider | Mode | Use case | Cost |
|---|---|---|---|
| Browser SpeechSynthesis | Phase 1 | Casual in-browser chat | Free |
| Piper TTS local | Phase 2 default | Most outbound. Sub-second latency on CPU. Free. | Free |
| Coqui XTTS v2 local | Phase 2 | Higher quality, voice cloning | Free (local compute) |
| Voicebox (Meta research) | Evaluation | Research-grade quality | Non-commercial license, evaluation only |
| ElevenLabs Conversational | Phase 2 premium | Enterprise outbound that must sound human | ~$0.07/min |

**Telephony (inbound/outbound call fabric)**

| Provider | Use case | Cost |
|---|---|---|
| VAPI | Dev-friendly call orchestration + built-in agents | ~$0.05/min platform fee + carrier |
| Retell AI | Latency-optimized, similar feature set | ~$0.07/min |
| Vocode | Open-source, self-host option | Free self-host, infra cost |
| Twilio Programmable Voice | Baseline carrier | ~$0.013/min US termination |
| Daily.co | WebRTC + telephony | ~$0.002/participant-min |

**Decision**: default to VAPI for Phase I demo (fastest to ship), add Vocode self-host adapter for SOVEREIGN deployments where outbound traffic must stay on-prem.

---

## Architecture (Backend)

Four new modules under `backend/app/services/voice/`:

### `stt_pipeline.py`
Unified STT interface with provider selection. Signature:

```python
class STTPipeline:
    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes],
        *, language: str = "en", model_hint: str | None = None,
    ) -> AsyncIterator[TranscriptChunk]: ...

    async def transcribe_file(
        self, audio_bytes: bytes, *, language: str = "en",
    ) -> Transcript: ...
```

Provider plugins implement `_STTProvider`: `FasterWhisperProvider`, `OpenAIWhisperProvider`, `DeepgramProvider`, `BrowserBridgeProvider` (Phase 1 compatibility).

### `tts_pipeline.py`
Mirror of STT. Yields audio chunks as they synthesize (for streaming to the caller without buffering a full response).

```python
class TTSPipeline:
    async def synthesize_stream(
        self, text: str, *, voice: str, rate: float = 1.0,
    ) -> AsyncIterator[bytes]: ...
```

Providers: `PiperProvider`, `XTTSProvider`, `ElevenLabsConvProvider`, `BrowserBridgeProvider`.

### `conversation_session.py`
The brain that stitches STT + LLM + TTS into a real-time conversation. Reuses the 10-stage governance pipeline for every turn. For high-stakes utterances (pricing, commitments, data handling), emits a `governance_approval_pending` event to the frontend and pauses the call until the operator approves.

Key methods:
- `start(channel: 'webrtc' | 'phone', direction: 'inbound' | 'outbound')`
- `speak(text, tier: RiskTier)` - synthesizes and emits. Tier 3+ waits for approval.
- `listen()` - streams STT chunks, hands final transcripts to chat_orchestrator.
- `handoff_to_human(reason)` - warm transfer to a human operator on the same channel.
- `end(reason, transcript_store=True)` - audit chain entry, transcript persistence.

### `outbound.py`
Provider-agnostic call placement. Today: VAPI. Later: Retell, Vocode self-host for SOVEREIGN.

```python
class OutboundClient:
    async def place_call(
        self, *, to_number: str, from_number: str,
        agent_id: str, conversation_id: UUID, metadata: dict,
    ) -> CallHandle: ...

    async def cancel(self, handle: CallHandle) -> None: ...
    async def transfer(self, handle: CallHandle, to_number: str) -> None: ...
```

Calls always get a `conversation_id` that ties back to a `ChatSession` record, so the call appears in the session history alongside chat messages. Unified timeline.

---

## Architecture (Frontend)

### `VoiceConsolePage.tsx` (new)
Live call monitor. Left pane: active calls with live waveforms. Center pane: streaming transcript of the selected call. Right pane: governance approvals queued for this call, barge-in button, transfer-to-human button.

### `VoiceProvider.tsx` (extend)
Adds call-level state beyond the current in-browser chat state. Wires to a new WebSocket endpoint `/api/v1/voice/ws/<session_id>` that multiplexes STT chunks out, governance events out, and control events in.

### `SettingsVoice.tsx` (extend)
Provider selector: Browser / Whisper+Piper / VAPI / Retell / ElevenLabs. Per-tenant default plus per-user override.

---

## Governance Mapping for Voice Actions

| Spoken action | Risk | Tier (GOVERNED mode) | What happens |
|---|---|---|---|
| Small talk, introductions | NONE | 0 | Silent pass |
| Discovery questions, scope confirmation | LOW | 1 | Logged |
| Scheduling followups | MEDIUM | 2 | User notified |
| Pricing commitments, T&Cs | HIGH | 3 | Call pauses, operator approves, then Daena speaks |
| PII request, data export offer, classified reference | CRITICAL | 4 | Call pauses, founder approves |

The call UI shows the operator exactly what Daena is about to say, with Approve / Edit / Reject controls, when a tier 3 or 4 utterance is queued. This matches how the current approval queue works for tool execution.

---

## Evidence and Audit Chain

Every call produces:
- Full audio, AES-256 encrypted at rest (reuses `EvidenceVault` from security subsystem)
- Streaming transcript with per-chunk SHA-256 hash
- Governance trace id linking each audited utterance to an audit log entry
- Optional diarized speaker-tagged transcript
- Call metadata (duration, carrier, caller ID, recording consent disclosure version)

Retention policy: 18 months for enterprise tier, 36 months for regulated enterprise, configurable for SOVEREIGN.

---

## Cost Model at Scale

Assumed mix at 1,000 minutes/day split across calls:
- 60% in-browser chat via Piper+Whisper local: $0
- 30% outbound sales calls via VAPI + Piper: ~$0.05/min platform + negligible TTS = $15
- 10% enterprise premium via ElevenLabs Conversational: ~$0.07/min = $7

Total: ~$22/day at 1,000 minutes = $660/month. Billable to customers at voice-tier pricing recovers this 5-10x depending on mix.

## What Ships in Phase I (6 weeks)

- `stt_pipeline.py` with FasterWhisper + Browser providers
- `tts_pipeline.py` with Piper + Browser providers
- `conversation_session.py` with WebRTC channel only (no phone yet)
- `voice_service.py` extended with provider selection
- `VoiceConsolePage.tsx` minimal viewer with live transcript
- 12 integration tests
- Demo: Masoud types "call the test number and ask whether they received the brief," Daena dials via VAPI test mode, completes the call, transcript and audit chain land in the session

What explicitly does not ship in Phase I:
- Inbound DID handling (Phase I+)
- Speaker diarization (Phase I+)
- ElevenLabs fallback wiring (Phase I+)
- Voicebox evaluation (Phase J, SOVEREIGN)

---

## Risk Notes

- **PSTN originator verification** (STIR/SHAKEN): must be configured with the chosen carrier before outbound scaling, otherwise calls land as "Spam Likely."
- **State-by-state consent laws**: two-party consent states (CA, FL, IL, PA, WA, and others) require explicit recording disclosure. Mandatory intro TTS handled by `conversation_session.py` opening the call with a consent statement that the caller can decline.
- **TCPA compliance**: outbound dialing rules for cold outreach. Agents never cold-dial without a prior business relationship or opt-in unless explicitly cleared by Legal.
- **Latency cliff**: Piper sub-second on a modern CPU, but XTTS can exceed 2s without a GPU. Production default Piper; XTTS only when voice cloning is explicitly requested.

## Integration Points With Existing Code

- `voice_service.py` gets extended, not replaced. Existing `VoiceSettings` dataclass grows a `provider` field and a `call_allowed` boolean.
- `chat_orchestrator.py` gets a new entrypoint `stream_voice_turn()` that the conversation session calls. Internally it is the same 10-stage pipeline.
- `execution_service.py` (post-2026-04-17 permission resolver fix) already persists approval rows. Voice tier 3+ utterances create approval rows just like tool calls. Frontend Sidebar badge increments.
- `models/chat.py::ChatSession` gains optional `call_handle_id` when the session is attached to a live call.

## Open Decisions for Founder

- Select primary telephony provider: VAPI (ship fastest) vs Retell (latency) vs Vocode self-host (sovereignty). Current recommendation: **VAPI for Phase I, add Vocode adapter in Phase J for SOVEREIGN**.
- Select default local TTS: Piper (fast, smaller variety) vs XTTS (cloning, heavier). Current recommendation: **Piper default, XTTS opt-in**.
- Default recording disclosure: short-form legal-safe line. Current recommendation: "Hi, this is Daena, an AI assistant calling on behalf of MAS-AI Technologies. This call will be recorded for quality and auditing purposes. Continue?" Callee must respond affirmatively before the call proceeds past discovery.
