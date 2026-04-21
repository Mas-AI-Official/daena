---
name: music-direction
description: "Music selection + mixing rules for short-form vertical video. Per-persona vibe maps (klyntar=dark/tense, daena_boardroom=analytical electronic, daena_casual=lofi), volume mixing under voice (-16 to -20 dB), entrance/exit fade behavior, beat-sync to caption pops. Pairs with edit-choreography (consumes the beat map for music kicks). Use when adding background music or sound design to ANY video."
metadata:
  tags: music, sound-design, audio-mixing, ducking, sidechain, lofi, dark-cinematic, cyberpunk, persona-vibe, contentops, daena, klyntar
---

# Music Direction Skill

Vibe-matched background music + mixing rules so the music supports the voice
instead of competing with it. Skill consumes the persona + emotion arc from
the script and returns a music brief: which track, what volume, what fade
behavior, optional sidechain ducking, and beat-to-caption alignment.

## When to invoke

- Any video where voice + visuals alone feel "naked"
- After voice-direction has produced the SSML and edit-choreography has the beat map
- BEFORE the final mux step

## Per-persona vibe map

| Persona | Vibe | Genre seed terms (for Pixabay/free-music search) | Tempo (BPM) | Mood tags |
|---|---|---|---|---|
| `daena_boardroom` | Analytical, confident, slight tension | "ambient electronic", "tech corporate", "thinking music", "modern documentary" | 90-110 | thoughtful, focused, urgent-but-controlled |
| `daena_casual` | Warm, inviting, productive | "lofi hip hop", "chillhop", "morning routine", "cafe ambient" | 70-85 | warm, dewy, sun-through-window |
| `klyntar` | Dark, menacing, cybersecurity threat | "dark cinematic", "cyberpunk pulse", "hacker", "ominous synth", "phonk drift" | 100-130 | tense, menacing, distant warning siren |

## Mixing volume map (in dBFS relative to voice peak)

| Section | BGM volume | Voice ducking |
|---|---|---|
| Intro / hook (0-3s) | -16 dB | none -- voice + music both present |
| Body / explainer (3-22s) | -20 dB | sidechain compress -3 dB when voice present |
| CTA (22-end) | -14 dB | none -- music returns to "felt" level |
| Pause / silence between sentences | -16 dB | bring music up briefly during voice gaps |

Cap absolute peak at -3 dBFS true-peak after sum so the final video
loudnorms cleanly to -16 LUFS without clipping.

## Fade behavior

- **Intro fade-in**: 600ms exponential from -infty to target volume
- **Outro fade-out**: 800ms exponential, completing 100ms BEFORE video end
- **Mid-video volume changes**: 200ms ease (not hard cut)
- **Section transitions** (when caption pops or B-roll cuts): no volume change unless
  edit-choreography flags a "kick" pattern_break in the beat map

## Sidechain ducking (optional, recommended)

When voice is present, duck BGM by -3 dB with:
- Attack: 30ms
- Release: 250ms
- Threshold: -28 dBFS on voice channel
- Ratio: 4:1

ffmpeg one-liner (combine BGM + voice with sidechain duck):

```bash
ffmpeg -i voice.mp3 -i bgm.mp3 -filter_complex \
  "[1:a]volume=-16dB[bgm]; \
   [bgm][0:a]sidechaincompress=threshold=0.04:ratio=4:attack=30:release=250[ducked]; \
   [0:a][ducked]amix=inputs=2:duration=longest[out]" \
  -map "[out]" -c:a aac -b:a 192k mixed.aac
```

## Beat-sync to caption pops

If `edit_plan.shots[i].pattern_break == "caption_flash"`, attempt to align the
caption pop to the nearest music beat (BPM-derived). Only do this when:
- Track has detectable BPM (bpm_detect.py available locally)
- Caption pop falls within +/- 4 frames (~133ms at 30fps) of a beat
- Audio crosspad is enabled in the renderer

If alignment shifts a caption by more than 4 frames, prefer the natural cut
(do NOT force align — viewer notices the jarring miss more than the missed beat).

## Where music files live (canonical paths)

```
data/music/
  daena_boardroom_<id>.mp3   -- analytical bed
  daena_casual_<id>.mp3      -- lofi bed
  klyntar_<id>.mp3           -- dark cinematic bed
  README.md                  -- requirements + sourcing notes
```

A `manifest.json` in `data/music/` maps each file to:
```json
{
  "filename": "klyntar_threat_pulse_001.mp3",
  "persona": "klyntar",
  "duration_s": 45.0,
  "bpm": 110,
  "tags": ["dark","cyberpunk","menacing"],
  "source": "Pixabay",
  "license": "CC0",
  "credit_required": false
}
```

Pipeline reads the manifest and randomly picks a track matching the video's
persona, with duration >= video duration.

## Sourcing free music (no API key required)

| Source | Method | License | Notes |
|---|---|---|---|
| Pixabay | https://pixabay.com/music/search/<query>/ + scrape, OR API key (free) | CC0, no attribution | Best for vibe-matched search; tag-rich |
| Free Music Archive | API key (free) | mostly CC-BY | Larger catalog, attribution sometimes |
| Incompetech (Kevin MacLeod) | Direct download | CC-BY | Cinematic bed standards |
| YouTube Audio Library | Manual download | YT TOS only | No external use without rights |
| Fesliyan Studios | Direct mp3 download | Personal use free | Commercial requires license |

Recommended pipeline default: Pixabay scraper (free, CC0, no attribution).

## Sound effects (optional accents)

Per edit-choreography pattern_break tags, layer SFX at -22 dB:

| pattern_break | SFX | Free source |
|---|---|---|
| `caption_flash` | sharp tick | freesound.org "ui_tick" |
| `whoosh` | air whoosh | freesound.org "whoosh_swipe" |
| `flash` | impact + reverb | Pixabay SFX "impact_dramatic" |
| `sfx` (generic accent) | soft chime | freesound.org "ui_confirm" |
| `freeze` | record-scratch / pause | Pixabay SFX "scratch" |
| `ding` | revelation bell | freesound.org "ui_success" |

## Music brief JSON output

```json
{
  "video_slug": "string",
  "persona": "daena_boardroom|daena_casual|klyntar",
  "vibe": "string",
  "track": {
    "filename": "data/music/klyntar_threat_pulse_001.mp3",
    "duration_s": 45.0,
    "bpm": 110,
    "tags": ["dark","cyberpunk"]
  },
  "mixing": {
    "intro_db": -16,
    "body_db": -20,
    "cta_db": -14,
    "fade_in_ms": 600,
    "fade_out_ms": 800,
    "sidechain_duck": true,
    "sidechain_db": -3
  },
  "sfx": [
    {"t_sec": 0.0, "type": "whoosh", "db": -22},
    {"t_sec": 3.0, "type": "caption_flash_tick", "db": -22}
  ]
}
```

## Anti-patterns

- BGM at -8 dB or louder under voice (drowns the analyst tone, sounds amateur)
- Same track for daena_boardroom AND klyntar (vibe mismatch — one is analytical, other is menacing)
- Music starts AT the same instant as voice (let it pre-roll 200-400ms so listener establishes mood)
- Hard cut-out at video end (always fade)
- BPM-locking captions when the natural cut is more than 4 frames off the beat (forced alignment is more jarring than no alignment)
- BGM with vocals (voice-on-voice = listener confused)
- Track shorter than video (causes silent tail OR loop with audible seam) -- always pick track_dur >= video_dur

## Contract with contentops-director

- Input: persona, video_slug, edit_plan (for beat map), voice_brief (for ducking config)
- Output: music_brief.json (per-video) + bgm path threaded into Remotion props as `bgmUrl` + `bgmVolumeDb`
- Renderer uses the music brief to mix the final audio track via ffmpeg sidechain compress
