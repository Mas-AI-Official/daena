---
name: edit-choreography
description: "Best-in-class editing choreography + scene-voice sync for viral short-form vertical 9:16 video in 2026. Converts a script + voice brief into a deterministic edit plan (shots, transitions, captions, grade) and FFmpeg/Remotion filter strings. Use when composing TikTok/Reels/Shorts edits or when contentops-director needs a beat map."
metadata:
  tags: editing, short-form, tiktok, reels, shorts, ffmpeg, remotion, captions, hormozi, mrbeast, beat-sync, contentops, daena
---

# Edit Choreography Skill

Deterministic rules for cutting, captioning, and grading 9:16 vertical video at 30fps. Every number below is a frame count at 30fps (divide by 1.25 for 24fps, multiply by 2 for 60fps). Pair with `contentops-director` for orchestration and `video-production` for the actual renderer.

## 1. Cut-to-beat patterns

**Cadence by section (30fps frames per shot):**

| Section | Frames/shot | Shots/sec | Purpose |
|---|---|---|---|
| Hook (0-3s) | 2-7 | 4.3-15 | Pattern interrupt montage |
| Payoff body (3-22s) | 15-45 | 0.66-2 | Cognitive load stays readable |
| CTA (22-30s) | 24-60 | 0.5-1.25 | Settle, one clear action |

**Cut triggers (in priority order):**
1. Vocal stress — cut on the downbeat of the stressed syllable, not 1-2 frames before (use word-level Whisper timestamps, subtract 1 frame for visual-audio lead).
2. Music kick — if music has a detectable kick, snap cut to nearest kick within +/- 3 frames of vocal stress.
3. Pattern interrupt — every 5-7s at minimum, force a cut even mid-phrase. Dead air for >2.5s on the same shot = scroll.
4. Breath pause — cut on a >200ms silence.

**J/L-cut rules:** J-cut (audio leads) 8-15 frames before B-roll; L-cut (audio lingers) 4-10 frames after cut. Never align both audio and video cuts to the exact same frame outside the hook — that reads as amateur.

## 2. B-roll insertion rules

- **Insert when:** the voiceover names a concrete noun (object, place, person, number). Don't insert on abstract words.
- **Length:** 18-45 frames (0.6-1.5s). Shorter reads as flash; longer steals from the talking head.
- **Type selection:**
  - Concrete noun + common → Pexels/Pixabay stock
  - Abstract concept / metaphor → AI-generated (LTX/Seedance)
  - Product / UI demo → screen capture, never stock
  - Emotion / reaction → creator reaction shot, never stock
- **Fade:** 2-frame crossfade in/out (never hard cut to B-roll unless synced to music kick).
- **Density cap:** max 40% of runtime as B-roll. Over 40% and the persona disappears.

## 3. Caption animation patterns

Three patterns, pick one per video (never mix):

**Hormozi word-pop** (default for high-energy):
- One word at a time, bottom-third, Montserrat Black 900, 72pt
- White default, gold `#FFD500` on stressed word
- Pop-in: 2 frames scale 0.85 -> 1.05 -> 1.00 (ease-out-back)
- Timing offset: caption in at word start -2 frames (lead the audio)
- Stress detection: dB peak > mean + 6dB, OR semantic keyword (hook words, numbers, names)

**MrBeast staggered** (faceless/narrative):
- 2-3 words per line, stacked; each line drops in 3 frames apart
- Chonky outlined font (Impact-style), shadow 4px
- Color by emotion: yellow = curiosity, red = shock, green = win

**Minimal corner** (cinematic/measured, 2026 "dynamic minimalism"):
- 4-6 words, lower-left, safe-margin 120px from edge
- Fade in 4 frames, fade out 6 frames
- No color changes, single family (Inter Medium 48pt)

All styles respect **TikTok safe zone** — 270px top, 340px bottom reserved for UI.

## 4. Zoom / push-in patterns

- **Emphasis zoom:** punch in 8-12% over 4 frames on a stressed keyword, hold 15-20 frames, release in 3 frames. Use only on the talking head shot.
- **Hold-and-release:** slow zoom 2% over 60 frames during a reveal sentence, then snap back in 1 frame at the punchline.
- **Dolly-in cinematic:** 1.0 -> 1.06 linear over full shot duration (for payoff section only).
- **Hard rule:** no more than 3 zooms per 30s. Zoom fatigue kills retention.

## 5. Transitions

| Type | When | Duration | FFmpeg equivalent |
|---|---|---|---|
| Straight cut | Default. 90% of cuts. | 0 frames | concat demuxer |
| Whip pan | Hook only, high energy, direction change | 4 frames | `xfade=slideleft:duration=0.13:offset=T` + `zoompan` kick |
| Match cut | Object/shape continuity | 0 frames (just plan it) | concat demuxer, pre-align shots |
| Morph | Seedance-generated only, rare | 8-12 frames | `xfade=dissolve:duration=0.33:offset=T` or GL transition |
| Crossfade | B-roll in/out only | 2 frames | `xfade=fade:duration=0.066:offset=T` |
| Flash cut | Shock reveal | 1 frame white | `fade=t=in:st=T:d=0.033:color=white` |

**FFmpeg filter-chain library** (T = seconds into video, replace literally):

```bash
# Straight cut -> no filter, use concat
ffmpeg -f concat -i list.txt -c copy out.mp4

# Whip pan left (4 frames @ 30fps = 0.133s)
-filter_complex "[0][1]xfade=transition=slideleft:duration=0.133:offset=T[v]"

# 2-frame B-roll crossfade
-filter_complex "[0][1]xfade=transition=fade:duration=0.066:offset=T[v]"

# Dissolve morph
-filter_complex "[0][1]xfade=transition=dissolve:duration=0.33:offset=T[v]"

# Flash white (shock)
-vf "fade=t=in:st=T:d=0.033:color=white,fade=t=out:st=T+0.066:d=0.033:color=white"

# Emphasis zoom (1.0 -> 1.10 over 4 frames, hold, release)
-vf "zoompan=z='if(lte(on,4),1+0.025*on,if(lte(on,24),1.10,1.10-0.033*(on-24)))':d=27:s=1080x1920"
```

## 6. Color grade per emotion

| Beat | Look | LUT preset | FFmpeg tune |
|---|---|---|---|
| Menace / problem | Dark cinematic teal | Teal-Orange blockbuster @ 55% | `eq=contrast=1.15:saturation=0.85,colorbalance=bs=0.1:rm=-0.05` |
| Nostalgia / origin | Warm 2500K fade | Kodak 2383 @ 60% | `eq=gamma_r=1.05:gamma_b=0.95:saturation=0.92` |
| Shock / reveal | High-contrast punch | Punchy S-curve @ 70% | `eq=contrast=1.35:saturation=1.15:brightness=0.02` |
| Win / aspiration | Bright warm glow | Golden Hour @ 50% | `eq=gamma_r=1.08:saturation=1.1:brightness=0.04` |
| Technical / data | Clean neutral | None / Rec709 | `eq=saturation=0.95` |

Apply LUT at 40-70% mix (`lut3d=file=X.cube` then blend). Above 80% reads as filter-heavy.

## 7. Three-act mini-structure (30s vertical)

| Act | Time | Cuts/sec | B-roll density | Captions | Grade |
|---|---|---|---|---|---|
| Hook | 0-3s | 4-15 | 60-80% | Hormozi pop, 1 word/frame-cluster | Shock LUT |
| Payoff | 3-22s | 0.66-2 | 20-35% | Hormozi pop, keyword gold | Primary emotion LUT |
| CTA | 22-30s | 0.5-1.25 | 0-10% | Minimal corner, one CTA | Win LUT |

## 8. Voice-scene sync

1. Transcribe with faster-whisper `large-v3` at word level.
2. Compute dB envelope per word (RMS over 100ms window).
3. Mark stress = dB > mean+6dB OR word in keyword list (numbers, names, power verbs).
4. Mark phrase boundary = silence > 200ms OR punctuation in transcript.
5. Propose cut at every phrase boundary; propose B-roll on every concrete noun.
6. Energy match: scene motion (optical flow mean) must correlate with vocal dB envelope within 0.3s lag. Low-energy voice on high-motion scene = jarring.

## Edit-plan JSON schema

```json
{
  "meta": {"duration_s": 30, "fps": 30, "aspect": "9:16", "grade": "teal_orange", "music_mood": "tense_cinematic"},
  "shots": [
    {"id": 1, "start_s": 0.0, "end_s": 0.23, "type": "talking_head", "motion": {"zoom": [1.0,1.08], "pan": null}, "caption": {"style": "hormozi", "text": "STOP", "color": "#FFD500"}}
  ],
  "transitions": [
    {"after_shot": 1, "type": "whip_left", "duration_s": 0.133}
  ],
  "captions": {"style": "hormozi", "font": "Montserrat Black 900", "size": 72, "safe_top": 270, "safe_bottom": 340},
  "grade": {"lut": "teal_orange.cube", "mix": 0.55, "extra": "eq=contrast=1.15:saturation=0.85"},
  "music": {"mood": "tense_cinematic", "bpm": 128, "kick_frames": [12, 42, 72]}
}
```

## Few-shot: same 22-second script, three choreographies

Script: *"You're losing 3 hours a day to inbox chaos. I rebuilt mine with Daena. Now I spend 12 minutes. Here's how."*

**Energetic** — 11 shots, hook=5 micro-cuts, whip pans, Hormozi gold pops, shock grade.
```
0.00-0.23 TH "YOU'RE"   zoom 1.00->1.08, pop
0.23-0.46 BR stopwatch  whip_left
0.46-1.00 TH "LOSING"   static, pop gold
1.00-1.33 BR chaos_mail whip_right
1.33-2.00 TH "3 HOURS"  punch 1.10, flash
2.00-3.00 BR inbox_ui   2f crossfade in
3.00-8.50 TH rebuild     dolly 1.00->1.04, keyword pops
8.50-11.0 BR daena_demo 2f crossfade
11.0-18.0 TH "12 min"    emphasis zoom on "12"
18.0-20.0 BR clock_12m  match-cut from TH watch
20.0-22.0 TH "HERE'S HOW" minimal CTA, win LUT
```

**Measured** — 6 shots, longer holds, L-cuts, minimal-corner captions, neutral grade shifting to warm.
```
0.0-3.0   TH hook        slow zoom 1.00->1.03
3.0-8.0   TH explain     static, L-cut audio leads next
8.0-12.0  BR daena_demo  8f dissolve in, 30% opacity captions
12.0-18.0 TH reveal 12m  punch 1.06 on "12"
18.0-20.0 BR result_grid 2f crossfade
20.0-22.0 TH CTA         warm LUT, minimal corner caption
```

**Cinematic** — 4 shots, all dolly-ins, morph transitions, teal-orange grade, MrBeast staggered.
```
0.0-5.5   TH hook wide   dolly 1.00->1.06, teal grade
5.5-11.0  BR metaphor    8f morph dissolve
11.0-18.0 TH reveal       dolly 1.00->1.08, orange warm shift
18.0-22.0 BR logo_end    12f morph, staggered CTA lines
```

## Python helper

```python
# edit_choreography.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Any

FPS = 30
ENERGY_PROFILES = {
    "energetic": {"hook_fps_shot": 4,  "body_fps_shot": 18, "cta_fps_shot": 30,
                  "broll_density": 0.40, "caption_style": "hormozi",
                  "grade": "shock_punch",      "transitions": ["whip_left","whip_right","flash","cut"]},
    "measured":  {"hook_fps_shot": 30, "body_fps_shot": 45, "cta_fps_shot": 60,
                  "broll_density": 0.20, "caption_style": "minimal_corner",
                  "grade": "neutral_to_warm", "transitions": ["cut","crossfade","l_cut"]},
    "cinematic": {"hook_fps_shot": 60, "body_fps_shot": 90, "cta_fps_shot": 120,
                  "broll_density": 0.25, "caption_style": "mrbeast_stagger",
                  "grade": "teal_orange",    "transitions": ["morph","dissolve","match_cut"]},
}
GRADE_FILTERS = {
    "shock_punch":     {"lut":"punchy_scurve.cube","mix":0.70,"extra":"eq=contrast=1.35:saturation=1.15:brightness=0.02"},
    "teal_orange":     {"lut":"teal_orange.cube",  "mix":0.55,"extra":"eq=contrast=1.15:saturation=0.85"},
    "neutral_to_warm": {"lut":"kodak_2383.cube",   "mix":0.50,"extra":"eq=gamma_r=1.05:saturation=0.95"},
    "golden_hour":     {"lut":"golden_hour.cube",  "mix":0.50,"extra":"eq=gamma_r=1.08:saturation=1.1"},
}

@dataclass
class Shot:
    id: int; start_s: float; end_s: float
    type: Literal["talking_head","broll","graphic"]
    motion: dict; caption: dict

def _nouns(words): return [w for w in words if w.get("pos") in ("NOUN","PROPN") or w.get("is_number")]
def _stress(words): return [w for w in words if w.get("db_peak",0) > w.get("db_mean",0)+6 or w.get("is_keyword")]

def compose_edit_plan(script_json: dict, voice_brief: dict, persona: dict,
                      target_energy: Literal["energetic","measured","cinematic"]="energetic") -> dict:
    prof = ENERGY_PROFILES[target_energy]
    words = voice_brief["words"]                       # list of {text,start,end,db_peak,db_mean,pos,is_number,is_keyword}
    dur   = voice_brief["duration_s"]
    hook_end = min(3.0, dur*0.10); cta_start = max(dur-8.0, dur*0.75)

    shots: list[Shot] = []; sid = 0; t = 0.0
    stress_set = {round(w["start"],2) for w in _stress(words)}
    noun_set   = {round(w["start"],2): w["text"] for w in _nouns(words)}

    def seg_len(now):
        if now < hook_end:   return prof["hook_fps_shot"]/FPS
        if now < cta_start:  return prof["body_fps_shot"]/FPS
        return prof["cta_fps_shot"]/FPS

    while t < dur:
        length = seg_len(t)
        # snap end to nearest stress within +/- 3 frames if present
        snap = next((s for s in stress_set if abs(s-(t+length)) < 3/FPS), None)
        end  = snap if snap else min(t+length, dur)
        # decide shot type: B-roll iff concrete noun spoken in window AND density budget not blown
        noun_hit = any(ns for ns in noun_set if t <= ns < end)
        density  = sum(1 for sh in shots if sh.type=="broll")*max(length,0.5)/max(dur,1)
        typ = "broll" if (noun_hit and density < prof["broll_density"]) else "talking_head"
        cap_word = next((w["text"] for w in words if t <= w["start"] < end), "")
        is_stress = any(s for s in stress_set if t <= s < end)
        motion = {"zoom":[1.00, 1.08 if is_stress else 1.02], "pan": None}
        caption = {"style": prof["caption_style"], "text": cap_word.upper() if prof["caption_style"]=="hormozi" else cap_word,
                   "color": "#FFD500" if is_stress and prof["caption_style"]=="hormozi" else "#FFFFFF"}
        sid += 1
        shots.append(Shot(sid, round(t,3), round(end,3), typ, motion, caption))
        t = end

    transitions = []
    for i, sh in enumerate(shots[:-1]):
        if sh.end_s < hook_end:
            kind = prof["transitions"][i % len(prof["transitions"])]
            dur_s = {"whip_left":0.133,"whip_right":0.133,"flash":0.033,"cut":0.0,
                     "crossfade":0.066,"dissolve":0.33,"morph":0.4,"match_cut":0.0,"l_cut":0.0}[kind]
        elif sh.type != shots[i+1].type:
            kind, dur_s = "crossfade", 0.066
        else:
            kind, dur_s = "cut", 0.0
        transitions.append({"after_shot": sh.id, "type": kind, "duration_s": dur_s})

    return {
        "meta": {"duration_s": dur, "fps": FPS, "aspect":"9:16",
                 "grade": prof["grade"], "music_mood": voice_brief.get("mood","tense_cinematic"),
                 "persona": persona.get("name","default"), "energy": target_energy},
        "shots": [asdict(s) for s in shots],
        "transitions": transitions,
        "captions": {"style": prof["caption_style"], "font":"Montserrat Black 900" if prof["caption_style"]=="hormozi" else "Inter Medium",
                     "size": 72 if prof["caption_style"]=="hormozi" else 48, "safe_top": 270, "safe_bottom": 340},
        "grade": GRADE_FILTERS[prof["grade"]],
        "music": {"mood": voice_brief.get("mood","tense_cinematic"),
                  "bpm": voice_brief.get("bpm",128),
                  "kick_frames": voice_brief.get("kick_frames",[])},
    }
```

## Contract with contentops-director

- **Input:** `script_json` (dual-script), `voice_brief` (faster-whisper word timings + dB + BPM), `persona` (brand voice config), `target_energy` in `{energetic,measured,cinematic}`.
- **Output:** `edit_plan` dict matching the schema above — fed to Remotion template or FFmpeg filter-graph builder.
- **Never:** mix caption styles; exceed 40% B-roll; place a zoom in the CTA; apply LUT at >80% mix.
- **Always:** respect 270/340 safe zones; snap cuts to stress within 3 frames; cap shot length in hook at 7 frames.
