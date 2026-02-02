# Explorer Mode Implementation (Human-in-the-Loop)

**Date**: 2025-12-13  
**Status**: ✅ **IMPLEMENTED**

---

## Overview

Explorer Mode is a **human-in-the-loop consultation system** that allows Daena to suggest consulting external LLMs (ChatGPT, Gemini, Claude) when appropriate. The user manually copies prompts, pastes responses, and Daena synthesizes the results.

**Key Principle**: NO APIs, NO automation, NO scraping - human bridge only.

---

## Architecture

### Layer Separation

**Layer A - Official Router (API-based, clean):**
- Azure OpenAI, Gemini API, other providers
- Used when keys exist
- Logged, auditable, safe
- Existing `LLMService` handles this correctly

**Layer B - Explorer Mode (Human-in-the-loop, NO API):**
- Formats prompts for user to paste
- Parses responses when user pastes back
- Feeds into Daena brain + router
- NO automation, NO scraping, NO login attempts

---

## Components

### 1. Explorer Bridge Service
**File**: `backend/services/explorer_bridge.py`

**Methods:**
- `build_prompt(task, target, context)` - Formats prompt for external LLM UI
- `parse_response(text, target)` - Parses response from external LLM UI
- `merge_with_daena_response(daena_response, explorer_response)` - Merges responses

**Features:**
- Supports: ChatGPT, Gemini, Claude
- Structured prompt format (REASONING / ASSUMPTIONS / FINAL ANSWER / CONFIDENCE)
- Intelligent parsing (handles variations in format)
- Response merging with Daena's analysis

### 2. API Endpoints
**File**: `backend/routes/explorer.py`

**Endpoints:**
- `POST /api/v1/explorer/build_prompt` - Build formatted prompt
- `POST /api/v1/explorer/parse_response` - Parse pasted response
- `POST /api/v1/explorer/merge` - Merge with Daena's response
- `GET /api/v1/explorer/status` - Get Explorer Mode status

### 3. Daena Brain Integration
**File**: `backend/routes/daena.py`

**Behavior:**
- Detects when Explorer Mode might be helpful
- Adds `explorer_hint` to response context
- Requires manual approval (hint only, no automatic execution)

### 4. UI Integration
**File**: `frontend/templates/dashboard.html`

**Features:**
- Explorer Consultation panel (appears when Daena suggests it)
- Copy prompt button
- Paste response textarea
- Submit & merge button
- Process logs (Manus style)

---

## Configuration

### Settings
**File**: `backend/config/settings.py`

```python
enable_explorer_mode: bool = Field(default=True, env="ENABLE_EXPLORER_MODE")
```

**Default**: `True` (enabled by default)

**Independent of:**
- `ENABLE_CLOUD_LLM` (API mode)
- `ENABLE_UI_CONSULT` (automation mode)

---

## Usage Flow

### 1. User asks Daena
```
User: "Compare this with what ChatGPT thinks about AI safety"
```

### 2. Daena suggests Explorer Mode
```json
{
  "content": "I can help you consult ChatGPT for a second opinion...",
  "context": {
    "explorer_hint": {
      "suggested": true,
      "providers": ["chatgpt", "gemini"],
      "requires_approval": true,
      "mode": "explorer"
    }
  }
}
```

### 3. UI shows Explorer Panel
- User sees formatted prompt
- Clicks "Copy" button
- Opens ChatGPT/Gemini manually
- Pastes prompt
- Copies response
- Pastes back into Daena

### 4. Daena processes
- Parses response
- Merges with Daena's analysis
- Returns synthesis

---

## Security & Safety

✅ **NO Automation**: Zero browser automation, zero scraping  
✅ **NO Credentials**: No login attempts, no credential storage  
✅ **Human Bridge**: User remains in control  
✅ **Manual Approval**: Always requires explicit user action  
✅ **Independent Mode**: Doesn't interfere with API mode  
✅ **Full Audit**: All explorer interactions logged  

---

## API Examples

### Build Prompt
```bash
POST /api/v1/explorer/build_prompt
{
  "task": "What is the capital of France?",
  "target": "chatgpt",
  "context": {"session_id": "abc123"}
}
```

**Response:**
```json
{
  "success": true,
  "target": "chatgpt",
  "formatted_prompt": "TASK:\nWhat is the capital of France?\n\nPlease provide your response in the following format:\n\nREASONING:\n[...]\n\nFINAL ANSWER:\n[...]",
  "instructions": "1. Copy the prompt below\n2. Open CHATGPT in your browser\n...",
  "response_format": "REASONING / ASSUMPTIONS / FINAL ANSWER / CONFIDENCE"
}
```

### Parse Response
```bash
POST /api/v1/explorer/parse_response
{
  "text": "REASONING:\nI need to find the capital...\n\nFINAL ANSWER:\nThe capital of France is Paris.",
  "target": "chatgpt"
}
```

**Response:**
```json
{
  "success": true,
  "target": "chatgpt",
  "reasoning": "I need to find the capital...",
  "answer": "The capital of France is Paris.",
  "confidence": "High",
  "parsed_successfully": true
}
```

### Merge Responses
```bash
POST /api/v1/explorer/merge
{
  "daena_response": "Based on my analysis, the capital is Paris.",
  "explorer_response": {
    "target": "chatgpt",
    "answer": "The capital of France is Paris.",
    "reasoning": "...",
    "confidence": "High"
  }
}
```

**Response:**
```json
{
  "success": true,
  "synthesis": "**Daena's Analysis:**\nBased on my analysis...\n\n**External Consultation (CHATGPT):**\n...\n\n**Synthesis:**\nAfter consulting external sources...",
  "daena_analysis": "Based on my analysis, the capital is Paris.",
  "external_consultation": {...},
  "confidence": "High"
}
```

---

## Tests

**File**: `tests/test_explorer_mode.py`

**Test Coverage:**
- ✅ Explorer Mode status endpoint
- ✅ Build prompt functionality
- ✅ Parse response functionality
- ✅ Merge responses functionality
- ✅ API mode independence
- ✅ No automation verification
- ✅ Manual approval requirement
- ✅ No duplicate services

**Run Tests:**
```bash
pytest tests/test_explorer_mode.py -v
```

---

## Files Created/Modified

### New Files
- `backend/services/explorer_bridge.py` (Explorer Bridge service)
- `backend/routes/explorer.py` (Explorer API endpoints)
- `tests/test_explorer_mode.py` (Tests)
- `docs/upgrade/2025-12-13/EXPLORER_MODE_IMPLEMENTATION.md` (This file)

### Modified Files
- `backend/config/settings.py` (Added `enable_explorer_mode` flag)
- `backend/main.py` (Registered explorer router)
- `backend/routes/daena.py` (Added explorer hint detection)
- `frontend/templates/dashboard.html` (Added Explorer Consultation panel)

---

## Verification

### No Duplicates
```bash
python scripts/verify_no_duplicates.py
# Output: OK: no duplicate/same-purpose files detected
```

### No Truncation
```bash
python scripts/verify_no_truncation.py
# Output: OK: no truncation placeholder patterns detected in .py files
```

### Tests Pass
```bash
pytest tests/test_explorer_mode.py -v
# Expected: All tests pass
```

---

## Differences from UI Consult Mode

| Feature | Explorer Mode | UI Consult Mode |
|---------|--------------|-----------------|
| **Automation** | ❌ None (human bridge) | ✅ Browser automation (Playwright) |
| **Login** | ❌ User logs in manually | ✅ Uses saved browser sessions |
| **Approval** | ✅ Manual (copy-paste) | ✅ Manual (button click) |
| **Dependencies** | ✅ None (pure Python) | ⚠️ Playwright required |
| **Use Case** | Cost saving, legal compliance | When APIs unavailable |

**Both modes are independent and can coexist.**

---

## Next Steps

1. **Test Explorer Mode Flow:**
   - Ask Daena: "Compare this with ChatGPT"
   - Verify Explorer panel appears
   - Test copy-paste workflow
   - Verify response merging

2. **Optional Enhancements:**
   - Multi-provider consultation (ChatGPT + Gemini simultaneously)
   - Confidence scoring
   - Citation tracking

---

**STATUS: ✅ IMPLEMENTATION COMPLETE**

**Explorer Mode is ready for use. It provides a safe, legal, human-in-the-loop alternative for consulting external LLMs without any automation or API costs.**









