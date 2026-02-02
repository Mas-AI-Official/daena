# Human Relay Explorer Mode

**Date**: 2025-12-13  
**Status**: ✅ Implemented

---

## Overview

Human Relay Explorer is a **manual copy/paste bridge** for consulting external LLMs (ChatGPT, Gemini) when no API is available. It provides a cost-saving fallback without any automation, scraping, or login attempts.

**Key Principle**: NO browser automation, NO scraping, NO login automation - human bridge only.

---

## What It Is

### Purpose
- Cost-saving fallback when APIs are unavailable or too costly
- Manual consultation with external LLMs (ChatGPT, Gemini)
- Daena synthesizes external insights with her own analysis

### What It Does
1. **Generate Prompt**: Creates a copy/paste-ready prompt for external LLM UI
2. **Ingest Response**: Parses and stores pasted response from external LLM
3. **Synthesize**: Daena brain merges external insights with her own analysis

---

## What It Is NOT

- ❌ **NOT browser automation** - No Playwright, Selenium, or browser control
- ❌ **NOT scraping** - No web scraping or data extraction
- ❌ **NOT login automation** - No session stealing or credential use
- ❌ **NOT mixed with router** - Separate tool, doesn't affect normal chat
- ❌ **NOT automatic** - Requires explicit user action at each step

---

## Architecture

### Backend Service
**File**: `backend/services/human_relay_explorer.py`

**Methods**:
- `generate_prompt(provider, task, context)` - Creates formatted prompt
- `ingest_response(relay_id, provider, pasted_answer)` - Parses and stores response
- `synthesize(task, insight_ids, mode)` - Calls canonical Daena brain with insights

**Storage**: Simple JSON file (`data/human_relay_insights.json`)

### API Endpoints
**File**: `backend/routes/human_relay.py`

**Endpoints**:
- `POST /api/v1/human-relay/prompt` - Generate prompt
- `POST /api/v1/human-relay/ingest` - Ingest pasted response
- `POST /api/v1/human-relay/synthesize` - Synthesize with Daena brain
- `GET /api/v1/human-relay/status` - Get status

### UI Panel
**File**: `frontend/templates/dashboard.html`

**Location**: Accessible via "Human Relay" button in header

**Features**:
- Provider dropdown (ChatGPT/Gemini)
- Task input
- Generate prompt button
- Copy prompt button
- Paste response textarea
- Ingest button
- Synthesize button
- Final answer display

---

## Usage Flow

### Step 1: Generate Prompt
1. Select provider (ChatGPT or Gemini)
2. Enter task/question
3. Click "Generate Prompt"
4. Prompt appears in textarea

### Step 2: Copy & Paste
1. Click "Copy" button
2. Open ChatGPT/Gemini in browser manually
3. Paste prompt into chat
4. Copy response from external LLM
5. Paste response back into Daena panel

### Step 3: Ingest Response
1. Click "Ingest Response"
2. Response is parsed and stored
3. Insight ID is displayed

### Step 4: Synthesize
1. Click "Synthesize with Daena"
2. Daena brain processes task with external insights as reference
3. Final synthesis is displayed

---

## API Examples

### Generate Prompt
```bash
POST /api/v1/human-relay/prompt
{
  "provider": "chatgpt",
  "task": "What is the capital of France?",
  "context": {"session_id": "abc123"}
}
```

**Response**:
```json
{
  "success": true,
  "provider": "chatgpt",
  "prompt_text": "TASK:\nWhat is the capital of France?\n\nPlease provide your response in the following format:\n\nREASONING:\n[...]\n\nFINAL ANSWER:\n[...]",
  "relay_id": "uuid-here",
  "trace_id": "trace-here",
  "timestamp": "2025-12-13T10:00:00Z"
}
```

### Ingest Response
```bash
POST /api/v1/human-relay/ingest
{
  "relay_id": "uuid-here",
  "provider": "chatgpt",
  "pasted_answer": "REASONING:\nI need to find...\n\nFINAL ANSWER:\nThe capital of France is Paris."
}
```

**Response**:
```json
{
  "success": true,
  "stored_id": "insight-uuid",
  "parsed": {
    "summary": "...",
    "key_points": [...],
    "reasoning": "...",
    "answer": "The capital of France is Paris.",
    "confidence": "High"
  },
  "trace_id": "trace-here",
  "timestamp": "2025-12-13T10:00:00Z"
}
```

### Synthesize
```bash
POST /api/v1/human-relay/synthesize
{
  "task": "What is the capital of France?",
  "insight_ids": ["insight-uuid"],
  "mode": "assist_only"
}
```

**Response**:
```json
{
  "success": true,
  "final_answer": "Based on my analysis and the external consultation, the capital of France is Paris...",
  "used_insights": [
    {
      "provider": "chatgpt",
      "summary": "...",
      "key_points": [...],
      "answer": "The capital of France is Paris."
    }
  ],
  "trace_id": "trace-here",
  "timestamp": "2025-12-13T10:00:00Z"
}
```

---

## Integration with Daena Brain

### Synthesis Mode: "assist_only"

When synthesizing, Human Relay Explorer calls the **canonical Daena brain** with:
- Original task
- External insights as context (reference only, not definitive truth)
- Mode: "assist_only" (Daena uses insights as reference, not as truth)

**Canonical Path**:
```
POST /api/v1/human-relay/synthesize
  → human_relay_explorer.synthesize()
  → daena_brain.process_message()  ← CANONICAL BRAIN
  → LLMService.generate_response()
  → Response (synthesis)
```

**Router NOT Modified**: Normal chat endpoint (`/api/v1/daena/chat`) remains unchanged.

---

## Security & Safety

✅ **NO Automation**: Zero browser automation, zero scraping  
✅ **NO Credentials**: No login attempts, no credential storage  
✅ **Human Bridge**: User remains in control at every step  
✅ **Manual Only**: Requires explicit user action  
✅ **Separate Tool**: Doesn't mix with router logic  
✅ **Full Audit**: All operations logged (via trace_id)  

---

## Configuration

### Settings
**File**: `backend/config/settings.py`

```python
enable_human_relay_explorer: bool = Field(default=True, env="ENABLE_HUMAN_RELAY_EXPLORER")
```

**Default**: `True` (enabled for local dev)

**Disable**:
```bash
set ENABLE_HUMAN_RELAY_EXPLORER=0
```

---

## UI Access

### Dashboard Button
- Click "Human Relay" button in header
- Panel opens with 4-step workflow

### Warning Display
- Panel shows warning: "Do NOT paste secrets/passwords"
- Clearly labeled: "Manual Copy/Paste Mode (No API, No Automation)"

---

## Tests

**File**: `tests/test_human_relay_explorer.py`

**Test Coverage**:
- ✅ Status endpoint
- ✅ Generate prompt
- ✅ Ingest response
- ✅ Synthesize with Daena brain
- ✅ No router mixing
- ✅ Uses canonical brain

**Run Tests**:
```bash
pytest tests/test_human_relay_explorer.py -v
```

---

## Files Created/Modified

### New Files
- `backend/services/human_relay_explorer.py` - Human Relay service
- `backend/routes/human_relay.py` - Human Relay API endpoints
- `tests/test_human_relay_explorer.py` - Tests
- `docs/upgrade/2025-12-13/HUMAN_RELAY_EXPLORER.md` - This file

### Modified Files
- `backend/config/settings.py` - Added `enable_human_relay_explorer` flag
- `backend/main.py` - Registered human_relay router
- `frontend/templates/dashboard.html` - Added Human Relay panel and functions

---

## Differences from Explorer Mode

| Feature | Human Relay Explorer | Explorer Mode |
|---------|---------------------|---------------|
| **Purpose** | Manual copy/paste bridge | Human-in-the-loop consultation |
| **Endpoints** | `/api/v1/human-relay/*` | `/api/v1/explorer/*` |
| **Storage** | JSON file (insights) | No storage |
| **Synthesis** | Calls Daena brain with insights | Merges responses |
| **Use Case** | Cost-saving fallback | General consultation |

**Both modes are independent and can coexist.**

---

## Troubleshooting

### "Feature disabled"
- Set `ENABLE_HUMAN_RELAY_EXPLORER=1` in environment
- Restart Daena

### "Failed to ingest"
- Check that relay_id matches the generated prompt
- Verify pasted answer is not empty

### "Synthesis failed"
- Check that insight_id exists
- Verify Daena brain is working (test normal chat)

---

## Best Practices

1. **Use for Cost Savings**: When APIs are unavailable or too costly
2. **Manual Only**: Always require explicit user action
3. **No Secrets**: Never paste passwords or secrets
4. **Synthesis Mode**: Use "assist_only" mode (insights as reference, not truth)
5. **Separate from Router**: Don't auto-trigger from normal chat

---

**STATUS: ✅ HUMAN RELAY EXPLORER IMPLEMENTED**

**Human Relay Explorer is ready for use. It provides a safe, legal, manual copy/paste bridge for consulting external LLMs without any automation or API costs.**









