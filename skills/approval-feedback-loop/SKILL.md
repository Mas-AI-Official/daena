---
name: approval-feedback-loop
description: Human-in-the-loop approval workflow with a learning feedback cycle. When a rendered artifact (video, caption, DM draft) is REJECTED with a comment, the comment is stored in rejections.jsonl and periodically mined for patterns — so repeated complaints produce improvement tickets that fix the underlying generator. Use whenever the operator uses the dashboard's Approve/Reject buttons or when generating artifacts that the operator will review.
---

# Approval Feedback Loop

## The core insight

A rejection without a reason = wasted signal. A rejection WITH a reason and no follow-up = a complaint that keeps coming back next render.

This skill closes the loop:
```
render → operator reviews → [approve] → publish, done
                          → [reject + comment] → (1) delete artifact
                                                  (2) append comment to rejections.jsonl
                                                  (3) weekly/on-demand: scan log, find patterns,
                                                      auto-file a P2 ticket in inbox.md
                                                  (4) Claude picks up the ticket, fixes the
                                                      generator, marks resolved
```

## Data model — `data/rejections.jsonl`

Append-only JSON Lines file. One rejection per line:

```json
{
  "timestamp": "2026-04-22T21:05:13Z",
  "script_id": 15,
  "artifact_type": "video_render" | "caption_draft" | "dm_draft" | "post_draft",
  "platform": "x" | "instagram" | null,
  "rejector": "operator",
  "comment": "caption too small on mobile — increase font size",
  "artifact_refs": {
    "video_path": "data/renders/script_15/final.mp4",
    "thumbnail": "data/renders/script_15/_v9_frame0.png"
  },
  "tags": ["caption", "size", "mobile"]
}
```

The `tags` array is extracted by a local-LLM pass (cheap — uses Qwen3-8B) when the line is written. Patterns cluster on tag frequency.

## Dashboard wiring

The existing `/api/approve/{script_id}` is green-path. Add a companion:

```python
@app.post("/api/reject/{script_id}")
def api_reject(script_id: int, body: dict) -> dict:
    """Reject an artifact with a comment. Body: {comment: str, artifact_type: str}."""
    comment = (body.get("comment") or "").strip()
    if not comment:
        raise HTTPException(400, "comment required — rejections without comments waste signal")
    from contentops.feedback import record_rejection
    entry = record_rejection(
        script_id=script_id,
        artifact_type=body.get("artifact_type", "video_render"),
        comment=comment,
        artifact_refs=body.get("artifact_refs", {}),
    )
    # Delete the artifact per CLAUDE.md policy
    vp = RENDERS_DIR / f"script_{script_id}" / "final.mp4"
    if vp.exists(): vp.unlink()
    return {"recorded": True, "log_path": entry["log_path"]}
```

## Pattern-mining job (`contentops/feedback.py`)

Scan `rejections.jsonl` weekly (APScheduler cron trigger or manual CLI). For each tag cluster:

```python
def scan_for_patterns(min_cluster: int = 3) -> list[dict]:
    """Group rejections by normalized tag. Clusters with >=min_cluster entries
    become candidate improvement tickets."""
    from collections import Counter
    with open("data/rejections.jsonl") as f:
        entries = [json.loads(line) for line in f]
    tag_count = Counter(t for e in entries for t in e.get("tags", []))
    patterns = [
        {
            "tag": tag,
            "count": n,
            "examples": [e["comment"] for e in entries if tag in e.get("tags", [])][:5],
            "proposed_fix": _suggest_fix(tag, entries),
        }
        for tag, n in tag_count.items() if n >= min_cluster
    ]
    return patterns
```

The `_suggest_fix()` function asks Qwen3-8B: *"Given these 5 operator complaints all tagged [caption, size], propose one concrete code change in contentops/video_render.py that would fix the pattern."* — the LLM returns a specific file + diff suggestion that Claude acts on in the next session.

## The improvement ticket format

When a pattern fires, append to `D:\Claude-Coworker\inbox.md`:

```
## IMPROVEMENT TICKET — 2026-04-22 P2 — caption-size-on-mobile

**Signal:** 5 rejections in 14 days, all tagged [caption, size, mobile].

**Examples:**
- "caption too small on mobile — increase font size"
- "can barely read the text on my phone"
- "captions overlap with tiktok UI"

**Proposed fix:** CAPTION_STYLE FontSize=10 → FontSize=12 in contentops/video_render.py
(the 288-PlayRes space value, effective 80px on 1920px video — currently 67px).

**Affected file:** contentops/video_render.py line ~67 (CAPTION_STYLE constant)

**How Claude should act:** next session, verify the fix on script 15 render before
closing the ticket. If the fix works, move the ticket to `inbox-archived.md`.
```

## Rules of operation (enforce via CLAUDE.md)

1. **No silent rejections.** Every rejection MUST carry a `comment` string. The API 400s when missing.
2. **Delete the artifact.** Rejected videos/drafts come off disk so they can't be accidentally republished.
3. **Always tag before logging.** A rejection with no tags can't be clustered. The tag-extraction LLM call is cheap (~100ms on local Qwen3-8B) — do it inline.
4. **Weekly scan is automatic.** Schedule `contentops.feedback.scan_for_patterns()` via APScheduler every Sunday midnight. Improvement tickets auto-file.
5. **Never loop on rejected patterns.** Before generating a new artifact, Claude should grep `rejections.jsonl` for patterns touching the current component and adjust upfront.

## Why this architecture vs simple "approve/reject" binary

Three reasons a naive binary misses:

1. **Rejection is the highest-signal operator interaction.** Approval is mostly noise — it means "good enough," which doesn't teach the system anything. Rejection tells you EXACTLY what to fix.
2. **Rejection comments are training data.** At ~5/week, in 3 months you have ~60 concrete operator preferences. Fed to an LLM, this becomes a brand-voice + style profile better than anything you could write manually.
3. **Patterns beat individual fixes.** One rejection of "caption too small" might be an outlier; 5 is a defect. The clustering threshold (default 3) is the signal-to-noise filter.

## Integration with existing skills

- `brand-voice:brand-voice-enforcement` — run on every draft BEFORE it enters the approval queue. Rejections for brand-voice reasons get tagged `[brand-voice]` and automatically propose a brand-voice-guideline update.
- `universal-shortform-director` — hooks into this loop: rejections tagged `[hook, weak]` or `[hook, generic]` trigger the director's "regenerate hook with higher contrarian stakes" path.
- `news-to-video` — rejections tagged `[evidence, missing]` flag that the multi-source research step was insufficient; the next run must pull >5 sources instead of 3.

## Contract

- **Consumes:** operator approvals/rejections via dashboard; drafted artifacts from the pipeline
- **Produces:** `data/rejections.jsonl`, improvement tickets in `inbox.md`
- **Calls:** Qwen3-8B on :8080 for tag extraction + fix suggestion
- **Never:** allows a rejection without a comment; keeps a rejected artifact on disk; clusters below the min_cluster threshold (noisy ticketing is worse than no ticketing)
