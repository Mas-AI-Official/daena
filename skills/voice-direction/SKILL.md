---
name: voice-direction
description: "2026 voice-direction and TTS-prompting patterns for short-form video voice-overs. Covers ElevenLabs v3 audio tags and voice_settings, Edge-TTS SSML, Chatterbox emotion/exaggeration controls, F5-TTS reference-clip rules, cross-engine pacing/emphasis principles, persona-to-voice mapping, and a compose_voice_brief() helper. Invoke when generating any spoken script for TikTok/Reels/Shorts or matching a voice to a persona."
metadata:
  tags: voice, tts, elevenlabs, edge-tts, chatterbox, f5-tts, ssml, voice-over, short-form, daena, klyntar
---

# Voice Direction Skill (2026)

Practical settings. Ship the brief with the script.

## 1. ElevenLabs (v3 + Voice Design API)

**Model:** `eleven_v3` for expressive short-form. `eleven_v3_conversational` for agent dialogue. Audio tags only fire on v3.

**`voice_settings` cheat sheet (0.0-1.0):**

| Content type          | stability | similarity_boost | style | use_speaker_boost | speed |
|-----------------------|-----------|------------------|-------|-------------------|-------|
| Hook (first 3s)       | 0.30      | 0.75             | 0.65  | true              | 1.05  |
| Narration/explainer   | 0.50      | 0.80             | 0.35  | true              | 1.00  |
| Tutorial/voice-of-god | 0.65      | 0.80             | 0.20  | true              | 0.95  |
| Meme/comedy           | 0.20      | 0.70             | 0.80  | true              | 1.10  |
| Luxury/ASMR           | 0.75      | 0.85             | 0.15  | true              | 0.90  |
| CTA (last 2s)         | 0.40      | 0.80             | 0.55  | true              | 1.00  |

Lower stability = more emotional variance (better hooks). Higher style = more voice-unique color but less predictable. `speed` above 1.1 garbles consonants — cap at 1.15.

**Audio tags that actually retain attention:** `[whispers]`, `[excited]`, `[laughs]`, `[sighs]`, `[sarcastic]`, `[curious]`, `[shouting]`, `[pause]`, `[gasps]`, `[scoffs]`. Event tags: `[applause]`, `[leaves rustling]`. Inline them directly: `"[whispers] Nobody's talking about this. [pause] But they should."`

Rules: (1) tags only effective when the voice's training data supports them — test each combo once. (2) Never stack more than 2 emotional tags in one sentence. (3) Put `[pause]` before the payload word, not after. (4) Use `suggested_audio_tags` on agents (max 20) so the LLM picks consistent ones.

## 2. Edge-TTS (free, Azure Neural)

**Voice picks by persona type:**

| Persona              | Voice                          |
|----------------------|--------------------------------|
| Warm authoritative F | `en-US-AriaNeural` style=chat  |
| Deep authoritative M | `en-US-GuyNeural` / `en-GB-RyanNeural` |
| Raspy villain / menace | `en-US-DavisNeural` style=angry |
| Young energetic M    | `en-US-AndrewNeural`           |
| Calm philosophical M | `en-US-BrandonNeural` / `en-GB-ThomasNeural` |
| Friendly coach F     | `en-US-JennyNeural` style=cheerful |

**SSML prosody adjustments:**

```xml
<prosody rate="+8%" pitch="-3Hz" volume="+0%">Hook line.</prosody>
<break time="350ms"/>
<prosody rate="-5%" pitch="-8Hz">The punchline lands here.</prosody>
```

Rate: hooks `+5%`–`+12%`, body `0%` to `-5%`, CTA `+3%`. Pitch: authority `-5Hz` to `-10Hz`, excitement `+10Hz` to `+20Hz`, menace `-15Hz`. Use `<mstts:express-as style="...">` for `narration-professional`, `excited`, `angry`, `whispering`, `empathetic`, `cheerful`.

## 3. Chatterbox (Resemble, local)

Two knobs: `exaggeration` (0.0–1.0) and `cfg_weight` (0.0–1.0, emotion adherence).

| Use case             | exaggeration | cfg_weight |
|----------------------|--------------|------------|
| Calm narration       | 0.25         | 0.5        |
| Hook / high-energy   | 0.75         | 0.7        |
| Deadpan/dry humor    | 0.15         | 0.3        |
| Menacing villain     | 0.60         | 0.8        |
| Emotional story beat | 0.80         | 0.6        |

`exaggeration > 0.7` + `cfg_weight < 0.4` = chaos. Keep `cfg_weight` ≥ 0.5 when exaggerated. Chatterbox respects bracketed cues like `[laughs]` but less reliably than ElevenLabs — use SSML-style punctuation direction instead.

## 4. F5-TTS (zero-shot clone)

**Reference clip rules (make or break):**
- **Length: 10–15s.** Shorter = unstable. Longer = truncated to first 15s anyway.
- **Content:** natural-paced declarative sentences. No shouts, no whispers, no music underneath.
- **Quality:** 24kHz+ mono WAV. No room reverb. No compression artifacts. Phone-recorded voice memo from a quiet room > studio mic in a reverberant space.
- **Transcript:** provide exact `ref_text` — auto-ASR adds 2–5% error that compounds. End `ref_text` with a period (no trailing silence).
- **Match energy:** if you want excited output, use an excited reference clip. F5 clones prosody, not just timbre.
- **Leave ~0.5s silence at the end of ref_audio.** Prevents the first generated phoneme from being clipped.

## 5. Cross-Engine Principles

**WPM targets:**
- Hook (0–3s): **180–200 wpm** — fast, front-loaded, no filler.
- Body / explainer: **150–170 wpm**.
- Tutorial / how-to: **140–155 wpm** — room for viewer to process.
- CTA: **160–180 wpm** — confident, not rushed.

**Punctuation as direction** (works in every engine):
- `,` → 80–120ms micro-pause.
- `.` → 250–350ms full stop.
- `—` (em-dash) → 180ms beat + slight pitch drop. Use for dramatic reveals.
- `...` → 400–600ms cliffhanger pause. Use once per clip max.
- `?` → pitch rise on last word.
- `!` → higher energy, shorter pause than `.`.
- ALL CAPS → +15% energy (engine-dependent; reliable on v3/Chatterbox).

**Emphasis tagging for retention:** bold the *benefit noun* + the *urgency verb*. In ElevenLabs use `<emphasis level="strong">`, in Edge-TTS SSML `<emphasis level="strong">`, in Chatterbox use CAPS, in F5 use punctuation stress (comma before the emphasized word). Emphasize 1 word per 10 — more dilutes it.

**Energy curve:** start at 90%, dip to 65% around 40% of the clip (breathing room), climb back to 95% for CTA. Never flat. Never monotone climb.

## 6. JSON Voice-Direction Schema

```json
{
  "voice": "en-US-AriaNeural",
  "rate": "+5%",
  "pitch": "-3Hz",
  "ssml": "<speak>...</speak>",
  "emotion_tags": ["[whispers]", "[excited]"],
  "emphasis": ["finally", "never"],
  "engine": "elevenlabs",
  "voice_settings": {"stability": 0.35, "similarity_boost": 0.8, "style": 0.6, "use_speaker_boost": true, "speed": 1.05},
  "wpm_target": 180,
  "energy_curve": [0.9, 0.7, 0.65, 0.8, 0.95]
}
```

## 7. Few-Shot: Same Paragraph, 5 Emotions x 5 SSML Treatments

Base: *"You've been doing this wrong your whole life. The fix takes thirty seconds."*

| Emotion | ElevenLabs v3 rendering |
|--------|-------------------------|
| Conspiratorial | `[whispers] You've been doing this wrong... your whole life. [pause] The fix? Thirty seconds.` |
| Excited | `[excited] You've been doing this WRONG your whole life! The fix takes thirty seconds.` |
| Deadpan | `You've been doing this wrong your whole life. [sighs] The fix takes thirty seconds.` |
| Menacing | `[serious] You've been doing this wrong. Your whole life. [pause] The fix takes thirty seconds.` |
| Warm mentor | `[empathetic] You've been doing this wrong your whole life — and that's okay. The fix takes thirty seconds.` |

| Treatment | Edge-TTS SSML |
|-----------|---------------|
| Hook-punch | `<prosody rate="+12%" pitch="+8Hz">You've been doing this <emphasis level="strong">wrong</emphasis> your whole life.</prosody><break time="300ms"/><prosody rate="0%">The fix takes thirty seconds.</prosody>` |
| Authoritative | `<prosody rate="-3%" pitch="-8Hz">You've been doing this wrong your whole life.</prosody><break time="400ms"/><prosody pitch="-5Hz">The fix takes thirty seconds.</prosody>` |
| Suspense | `<prosody rate="-10%">You've been doing this wrong...</prosody><break time="600ms"/><prosody rate="+5%">your whole life.</prosody><break time="350ms"/>The fix takes thirty seconds.` |
| Frantic | `<prosody rate="+18%" pitch="+15Hz" volume="+10%">You've been doing this wrong your whole life!</prosody><break time="200ms"/>The fix takes thirty seconds.` |
| Philosophical | `<mstts:express-as style="narration-professional"><prosody rate="-8%" pitch="-5Hz">You've been doing this wrong your whole life. <break time="500ms"/>The fix takes thirty seconds.</prosody></mstts:express-as>` |

## 8. Persona to Voice Map

| Persona | Primary (ElevenLabs) | Fallback (Edge-TTS) | F5 ref-clip note | voice_settings |
|---------|----------------------|---------------------|------------------|----------------|
| **Daena** (warm authoritative F) | Rachel / custom clone | `en-US-AriaNeural` chat | 12s clip, warm register, smile in voice | stab 0.45, sim 0.85, style 0.4, spd 1.0 |
| **Klyntar** (deep menacing M) | Custom dark-timbre clone / Clyde | `en-US-DavisNeural` angry | 14s clip, low register, slow breath | stab 0.55, sim 0.9, style 0.55, spd 0.92 |
| **Naval-style** (calm philosophical M) | Adam / Daniel | `en-GB-ThomasNeural` | 15s clip, measured, no smile | stab 0.7, sim 0.8, style 0.15, spd 0.95 |
| **Hormozi-style** (intense M) | Josh / custom high-energy clone | `en-US-AndrewNeural` cheerful+rate+10% | 10s clip, shouted intro, gym room | stab 0.25, sim 0.75, style 0.75, spd 1.08 |

## 9. Python Helper

```python
def compose_voice_brief(script: str, persona: str, emotion_target: str) -> dict:
    """Return a full voice-direction brief. Drops into any TTS pipeline."""
    personas = {
        "daena":    {"voice": "Rachel", "edge": "en-US-AriaNeural", "pitch": "-2Hz", "rate": "+2%",
                     "vs": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.4, "use_speaker_boost": True, "speed": 1.0}},
        "klyntar":  {"voice": "Clyde", "edge": "en-US-DavisNeural", "pitch": "-12Hz", "rate": "-5%",
                     "vs": {"stability": 0.55, "similarity_boost": 0.9, "style": 0.55, "use_speaker_boost": True, "speed": 0.92}},
        "naval":    {"voice": "Daniel", "edge": "en-GB-ThomasNeural", "pitch": "-5Hz", "rate": "-3%",
                     "vs": {"stability": 0.7, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True, "speed": 0.95}},
        "hormozi":  {"voice": "Josh", "edge": "en-US-AndrewNeural", "pitch": "+5Hz", "rate": "+10%",
                     "vs": {"stability": 0.25, "similarity_boost": 0.75, "style": 0.75, "use_speaker_boost": True, "speed": 1.08}},
    }
    emotion_map = {
        "hook":         {"tags": ["[excited]"], "wpm": 190, "curve": [0.95, 0.9, 0.8, 0.85, 0.95]},
        "conspiratorial": {"tags": ["[whispers]", "[pause]"], "wpm": 155, "curve": [0.7, 0.6, 0.55, 0.7, 0.85]},
        "authoritative":{"tags": ["[serious]"], "wpm": 150, "curve": [0.85, 0.75, 0.7, 0.8, 0.9]},
        "menacing":     {"tags": ["[serious]", "[pause]"], "wpm": 140, "curve": [0.8, 0.7, 0.65, 0.75, 0.9]},
        "warm":         {"tags": ["[empathetic]"], "wpm": 160, "curve": [0.85, 0.7, 0.65, 0.8, 0.9]},
        "deadpan":      {"tags": ["[sighs]"], "wpm": 150, "curve": [0.7, 0.65, 0.6, 0.65, 0.7]},
        "frantic":      {"tags": ["[excited]", "[gasps]"], "wpm": 200, "curve": [1.0, 0.95, 0.85, 0.9, 1.0]},
    }
    p = personas.get(persona.lower(), personas["daena"])
    e = emotion_map.get(emotion_target.lower(), emotion_map["authoritative"])
    ssml = (f'<speak><voice name="{p["edge"]}">'
            f'<prosody rate="{p["rate"]}" pitch="{p["pitch"]}">{script}</prosody>'
            f'</voice></speak>')
    words = [w for w in script.split() if len(w) > 4]
    emphasis = [words[i] for i in (0, len(words)//2, len(words)-1) if words] if words else []
    return {
        "voice": p["voice"], "edge_voice": p["edge"],
        "rate": p["rate"], "pitch": p["pitch"],
        "ssml": ssml,
        "emotion_tags": e["tags"],
        "emphasis": emphasis,
        "engine": "elevenlabs",
        "voice_settings": p["vs"],
        "wpm_target": e["wpm"],
        "energy_curve": e["curve"],
        "tagged_script": f'{"".join(e["tags"])} {script}',
    }
```

**Usage:** produce this brief alongside every script. Downstream ContentOps/video-production skills consume it directly.
