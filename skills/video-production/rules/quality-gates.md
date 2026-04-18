# Quality Gates & Production Intelligence

Patterns for ensuring video quality, managing costs, and preventing common failures.
Inspired by production-grade video systems. Clean-room implementation for MAS-AI.

## 1. Provider Scoring Engine

When multiple AI video engines can serve a scene, score them across 7 dimensions to auto-select the best one.

### Scoring Dimensions

| Dimension | Weight | What it measures |
|---|---|---|
| Quality | 0.25 | Visual fidelity, coherence, artifact rate |
| Cost | 0.20 | Price per second of output |
| Speed | 0.15 | Generation time (seconds to deliver) |
| Reliability | 0.15 | Uptime, error rate, timeout rate |
| Capability match | 0.10 | Does engine support this scene type? (lip-sync, long-form, 4K) |
| Style fit | 0.10 | How well does engine match the target aesthetic? |
| Availability | 0.05 | Is API key configured? Is local GPU free? |

### Provider Score Card (current as of 2026-04)

```json
{
  "providers": {
    "seedance_2.0": {
      "quality": 0.95,
      "cost": 0.40,
      "speed": 0.50,
      "reliability": 0.85,
      "capabilities": ["lip_sync", "text_to_video", "image_to_video", "multi_reference", "audio_gen"],
      "max_duration_sec": 15,
      "max_resolution": "720p"
    },
    "ltx_2.3_local": {
      "quality": 0.80,
      "cost": 1.00,
      "speed": 0.30,
      "reliability": 0.95,
      "capabilities": ["text_to_video", "image_to_video", "video_extension", "lora"],
      "max_duration_sec": 60,
      "max_resolution": "4k"
    },
    "kling_3.0": {
      "quality": 0.85,
      "cost": 0.80,
      "speed": 0.60,
      "reliability": 0.80,
      "capabilities": ["text_to_video", "image_to_video", "long_form"],
      "max_duration_sec": 300,
      "max_resolution": "4k"
    },
    "higgsfield": {
      "quality": 0.88,
      "cost": 0.50,
      "speed": 0.55,
      "reliability": 0.82,
      "capabilities": ["multi_model", "character_consistency", "storyboard"],
      "max_duration_sec": 60,
      "max_resolution": "1080p"
    },
    "remotion": {
      "quality": 0.90,
      "cost": 1.00,
      "speed": 0.85,
      "reliability": 1.00,
      "capabilities": ["data_viz", "text_animation", "charts", "programmatic"],
      "max_duration_sec": 3600,
      "max_resolution": "4k"
    },
    "pexels": {
      "quality": 0.70,
      "cost": 1.00,
      "speed": 0.95,
      "reliability": 0.90,
      "capabilities": ["stock_broll", "establishing_shot"],
      "max_duration_sec": 60,
      "max_resolution": "4k"
    }
  }
}
```

### Selection Algorithm

```python
def select_provider(scene: dict, budget_remaining: float) -> str:
    """Score all providers for a scene and return the best one."""
    scores = {}
    for name, provider in PROVIDERS.items():
        # Skip if provider can't handle this scene type
        if scene["visual_type"] not in provider["capabilities"]:
            continue
        # Skip if scene is longer than provider max
        if scene["duration_sec"] > provider["max_duration_sec"]:
            continue
        # Skip if no budget left for paid providers
        if provider["cost"] < 1.0 and budget_remaining <= 0:
            continue

        score = (
            provider["quality"] * 0.25 +
            provider["cost"] * 0.20 +
            provider["speed"] * 0.15 +
            provider["reliability"] * 0.15 +
            (1.0 if scene["visual_type"] in provider["capabilities"] else 0.0) * 0.10 +
            style_match(scene["scene_mood"], name) * 0.10 +
            (1.0 if is_available(name) else 0.0) * 0.05
        )
        scores[name] = score

    return max(scores, key=scores.get) if scores else "pexels"  # Fallback to stock
```

## 2. Slideshow Risk Scoring

The #1 failure mode in AI video is producing an "animated PowerPoint" -- static images with Ken Burns that feel dead. Score every video before delivery.

### 6 Risk Dimensions

| Dimension | Weight | What it detects |
|---|---|---|
| Motion variety | 0.25 | Are there real camera moves, or just zoom/pan on stills? |
| Visual type variety | 0.20 | How many different scene types (avatar, B-roll, data viz, text)? |
| Cut frequency | 0.15 | Cuts per minute (target: 3-8 for short, 2-5 for long) |
| Audio-visual sync | 0.15 | Do visuals change when speech topic changes? |
| Human presence | 0.15 | Is there enough avatar/human footage to feel personal? |
| Pacing dynamics | 0.10 | Does the energy vary (fast/slow), or is it monotone? |

### Risk Thresholds

```
Risk score < 0.3  -> GREEN: Ship it
Risk score 0.3-0.6 -> YELLOW: Review specific weak dimensions, consider regenerating weak beats
Risk score > 0.6  -> RED: Do not ship. Regenerate with different engine/approach
```

### Quick Check (before render)

Before committing to a full render, check the beat map:
- [ ] At least 3 different visual_type values across all beats
- [ ] No single visual_type used for > 40% of total duration
- [ ] Avatar lip-sync appears in at least 15% of total duration
- [ ] At least 1 data visualization or text animation per 2 minutes
- [ ] No sequence of 3+ consecutive beats with same visual_type

## 3. Pipeline Checkpointing

Every stage saves its output. If a stage fails, resume from the last checkpoint instead of starting over.

### Checkpoint Schema

```json
{
  "pipeline_id": "prod_20260415_ai_healthcare",
  "format": "short_form",
  "created_at": "2026-04-15T14:30:00Z",
  "current_stage": "scene_generation",
  "stages": {
    "research": {"status": "complete", "output": "data/research/ai_healthcare.json", "completed_at": "..."},
    "script": {"status": "complete", "output": "data/scripts/ai_healthcare_dual.json", "completed_at": "..."},
    "voice": {"status": "complete", "output": "data/audio/ai_healthcare/full.wav", "completed_at": "..."},
    "beat_map": {"status": "complete", "output": "data/beat_maps/ai_healthcare.json", "completed_at": "..."},
    "scene_generation": {
      "status": "in_progress",
      "beats_total": 12,
      "beats_complete": 8,
      "beats_failed": ["beat_09"],
      "output_dir": "data/scenes/ai_healthcare/"
    },
    "alignment": {"status": "pending"},
    "composite": {"status": "pending"},
    "review": {"status": "pending"},
    "export": {"status": "pending"}
  },
  "budget": {
    "allocated": 15.00,
    "spent": 8.40,
    "remaining": 6.60,
    "breakdown": {
      "seedance_2.0": 6.30,
      "elevenlabs": 2.10,
      "pexels": 0.00,
      "ltx_local": 0.00
    }
  }
}
```

### Resume Logic

```python
def resume_pipeline(checkpoint_path: str):
    """Resume a pipeline from its last checkpoint."""
    cp = load_checkpoint(checkpoint_path)

    for stage_name, stage in cp["stages"].items():
        if stage["status"] == "complete":
            continue  # Skip completed stages
        elif stage["status"] == "in_progress":
            # Resume partial stage (e.g., regenerate failed beats only)
            resume_stage(stage_name, stage)
            break
        elif stage["status"] == "pending":
            # Start this stage fresh
            run_stage(stage_name, cp)
            break
```

**Rule:** After each stage completes, save the checkpoint. If Claude Code crashes mid-session, the next session reads the checkpoint and picks up where it left off.

## 4. Budget Governance

Every production run has a budget. Track spending in real-time and enforce limits.

### Budget Tiers

| Content Type | Budget Cap | Breakdown |
|---|---|---|
| Short-form (60s) | $15 | TTS $2, AI video $10, stock $0, music $0, buffer $3 |
| Long-form (15min) | $50 | TTS $8, AI video $30, stock $0, music $5, buffer $7 |
| Long-form (30min) | $80 | TTS $15, AI video $45, stock $0, music $8, buffer $12 |
| Premium (hero video) | $150 | Full Seedance 2.0 for every scene |

### Cost Estimation Before Generation

```python
def estimate_scene_cost(beat: dict) -> float:
    """Estimate cost before generating a scene."""
    engine = beat["engine"]
    duration = beat["duration_sec"]

    rates = {
        "seedance_2.0": 0.30,       # per second
        "seedance_2.0_fast": 0.14,
        "kling_3.0": 0.10,
        "ltx_2.3_local": 0.00,
        "remotion": 0.00,
        "pexels": 0.00,
        "higgsfield": 0.20,         # approximate per second
    }

    return rates.get(engine, 0.0) * duration

def check_budget(beat: dict, budget_remaining: float) -> bool:
    """Check if we can afford this scene. If not, downgrade engine."""
    estimated = estimate_scene_cost(beat)
    if estimated <= budget_remaining:
        return True

    # Try cheaper engine
    fallback_order = ["kling_3.0", "seedance_2.0_fast", "ltx_2.3_local", "pexels"]
    for fallback in fallback_order:
        beat["engine"] = fallback
        if estimate_scene_cost(beat) <= budget_remaining:
            return True

    return False  # Out of budget entirely
```

## 5. Deep Research Stage

Before writing any script, run comprehensive research to ground the video in real, current information.

### Research Protocol

```
1. BROAD SEARCH (5-8 queries)
   - "[topic] latest news 2026"
   - "[topic] statistics data"
   - "[topic] expert opinion"
   - "[topic] controversy debate"
   - "[topic] examples case study"

2. DEEP SEARCH (5-10 queries based on broad results)
   - Follow up on specific claims found
   - Verify statistics from multiple sources
   - Find contrarian viewpoints
   - Search for visual references

3. CORPUS BUILD (for long-form)
   - Search Pexels/Pixabay for relevant stock footage
   - Tag each clip with semantic keywords
   - Score relevance to topic (0-1)
   - Build a searchable index for the scene generation stage

4. SYNTHESIS
   - Extract 5-10 key facts with sources
   - Identify 3-5 visual metaphors
   - Find 2-3 compelling quotes
   - Draft a "hook fact" (the most surprising/engaging finding)
```

### Research Output Schema

```json
{
  "topic": "AI in Healthcare 2026",
  "research_date": "2026-04-15",
  "queries_run": 18,
  "sources_cited": 12,
  "hook_fact": {
    "text": "AI can now diagnose 94% of cancers that human radiologists miss in early stages",
    "source": "Nature Medicine, March 2026",
    "source_url": "https://...",
    "visual_suggestion": "Medical scan with AI overlay highlighting micro-tumors invisible to human eye"
  },
  "key_facts": [...],
  "visual_metaphors": [...],
  "quotes": [...],
  "contrarian_views": [...],
  "stock_corpus": {
    "clips_found": 45,
    "clips_relevant": 12,
    "index_path": "data/corpus/ai_healthcare_clips.json"
  }
}
```

**Rule:** Never produce a video without running the research stage first. Unresearched videos contain hallucinations and generic claims that damage credibility.

## 6. Delivery Promise

Before starting production, state what the video will deliver. After render, check against the promise.

```json
{
  "promise": {
    "content_type": "short_form_explainer",
    "duration_target_sec": 55,
    "duration_tolerance_sec": 5,
    "visual_types_minimum": 3,
    "avatar_percentage_minimum": 0.15,
    "facts_cited_minimum": 3,
    "hook_in_first_seconds": 3,
    "captions": true,
    "music": true,
    "brand_elements": true
  },
  "delivery": {
    "duration_actual_sec": 57,
    "visual_types_used": ["avatar_lipsync", "ai_generation", "data_visualization", "stock_broll"],
    "avatar_percentage": 0.22,
    "facts_cited": 4,
    "hook_at_second": 0.5,
    "captions": true,
    "music": true,
    "brand_elements": true,
    "all_promises_met": true
  }
}
```

**Rule:** If any promise is not met, the video goes back to the failed stage for regeneration. Do not ship a video that breaks its own delivery promise.
