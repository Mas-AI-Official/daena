# UI Consult Mode (Manual Approval, Safe)

**Date**: 2025-12-13  
**Status**: ✅ Implemented  
**Feature Flag**: `ENABLE_UI_CONSULT=1`

---

## Overview

UI Consult Mode allows Daena to consult Gemini and ChatGPT via browser automation as a **fallback** when APIs are unavailable or too costly. This is a **manual approval mode** by default, ensuring transparency and safety.

---

## Architecture

### Components

1. **Backend Tool**: `backend/tools/executors/ui_consult_playwright.py`
   - Uses Playwright for reliable browser automation
   - Supports persistent browser profiles (preserves login sessions)
   - Fails gracefully on CAPTCHA or login required
   - Full audit logging

2. **API Endpoint**: `POST /api/v1/tools/consult_ui`
   - Requires `ENABLE_UI_CONSULT=1`
   - Manual approval by default
   - Returns: `{ status, provider, answer_text, trace_id, error }`

3. **Tool Registry**: Integrated into `backend/tools/registry.py`
   - Tool name: `consult_ui`
   - Optional dependency (Playwright)
   - Rate limited and audited

4. **Daena Brain Integration**: `backend/routes/daena.py`
   - Can suggest UI consult when appropriate
   - Always requires manual approval
   - Merges external answers with Daena's reasoning

---

## Security Model

### ✅ Safety Features

- **Manual Approval Required**: Default mode requires explicit user approval
- **Domain Allowlist**: Only `chat.openai.com` and `gemini.google.com` allowed
- **No Credential Storage**: Uses existing browser sessions (user must log in manually)
- **CAPTCHA Detection**: Fails gracefully if CAPTCHA detected (never attempts to solve)
- **Full Audit Logging**: Every consult is logged with trace_id, timestamp, provider, question
- **Feature Flag**: Disabled by default (`ENABLE_UI_CONSULT=0`)

### 🔒 Browser Profile Isolation

- Each provider uses a dedicated browser profile directory:
  - `~/.daena_browser_profiles/chatgpt/`
  - `~/.daena_browser_profiles/gemini/`
- Profiles persist login sessions (user logs in once manually)
- No credential harvesting or storage

---

## Usage

### 1. Enable Feature

```bash
set ENABLE_UI_CONSULT=1
```

### 2. Install Playwright (Optional Dependency)

```bash
pip install playwright
playwright install chromium
```

**Note**: Backend will still boot if Playwright is not installed. Tool will return an error when called.

### 3. Manual Login (One-Time Setup)

1. Enable UI Consult Mode: `ENABLE_UI_CONSULT=1`
2. Start Daena
3. First consult will open browser - log in to ChatGPT/Gemini manually
4. Browser profile saves session for future consults

### 4. API Usage

**Endpoint**: `POST /api/v1/tools/consult_ui`

**Request:**
```json
{
  "provider": "chatgpt",  // or "gemini"
  "question": "What is the capital of France?",
  "timeout_sec": 60,
  "manual_approval": true  // default: true
}
```

**Response:**
```json
{
  "success": true,
  "status": "ok",
  "provider": "chatgpt",
  "answer_text": "The capital of France is Paris.",
  "timestamp": "2025-12-13T10:00:00Z",
  "trace_id": "abc123...",
  "audit_id": "xyz789..."
}
```

**Error Responses:**
- `status: "error"` - Playwright not installed or feature disabled
- `status: "captcha"` - CAPTCHA detected (user must solve manually)
- `status: "not_logged_in"` - User not logged in (must log in manually first)
- `status: "timeout"` - Request timed out

---

## Integration with Daena Brain

### When Daena Suggests UI Consult

Daena may suggest UI consult when:
- User asks for "second opinion" or "compare with ChatGPT/Gemini"
- User explicitly mentions consulting external LLMs
- APIs are unavailable (fallback mode)

### Response Format

When UI consult is suggested, Daena's response includes:

```json
{
  "content": "I can consult ChatGPT and Gemini for a second opinion. Would you like me to?",
  "type": "general",
  "context": {
    "brain_used": true,
    "ui_consult_hint": {
      "suggested": true,
      "providers": ["chatgpt", "gemini"],
      "requires_approval": true
    }
  }
}
```

### Merging Responses

When UI consult is executed:
1. Daena generates her own response via `daena_brain`
2. External LLM responses are fetched (ChatGPT + Gemini)
3. Daena synthesizes all responses with reasoning
4. Final answer includes:
   - Daena's analysis
   - External LLM answers (with citations)
   - Confidence scores
   - Synthesis reasoning

---

## UI Integration (Dashboard)

### Approval Button

When Daena suggests UI consult, the dashboard shows:

```html
<div class="ui-consult-approval">
  <p>Daena suggests consulting external LLMs:</p>
  <button onclick="approveConsult('chatgpt')">Approve: ChatGPT</button>
  <button onclick="approveConsult('gemini')">Approve: Gemini</button>
  <button onclick="approveConsult('both')">Approve: Both</button>
</div>
```

### Process Logs (Manus Style)

During execution, show process tabs:
- **Status**: "Waiting for approval" → "Executing" → "Complete"
- **Logs**: Real-time browser automation logs
- **Results**: External LLM answers + Daena synthesis

---

## Limitations & Best Practices

### ⚠️ Limitations

1. **Not Fully Autonomous**: Always requires manual approval (by design)
2. **Browser Dependent**: Requires user to be logged in manually first
3. **CAPTCHA Blocks**: Cannot solve CAPTCHAs (fails gracefully)
4. **Rate Limits**: Subject to provider rate limits (not bypassed)
5. **Cost**: Still uses provider's free tier (if available)

### ✅ Best Practices

1. **Use as Fallback**: Prefer API when available
2. **Manual Approval**: Always require explicit approval
3. **Audit Everything**: All consults are logged
4. **Synthesize Responses**: Never rely only on external UI output
5. **Transparency**: Show user what Daena is doing

---

## Future Enhancements

### Potential Additions

1. **Gmail Integration**: Use OAuth APIs (not UI scraping) for email management
2. **Multi-Provider Synthesis**: Automatically consult both ChatGPT and Gemini
3. **Confidence Scoring**: Rate external answers for reliability
4. **Citation Tracking**: Link external answers to sources

### Not Planned

- ❌ Fully autonomous UI scraping
- ❌ CAPTCHA solving
- ❌ Credential storage
- ❌ Bypassing provider rate limits

---

## Troubleshooting

### "Playwright not installed"

```bash
pip install playwright
playwright install chromium
```

### "Not logged in"

1. Enable UI Consult: `ENABLE_UI_CONSULT=1`
2. Make a consult request
3. Browser will open - log in manually
4. Future consults will use saved session

### "CAPTCHA detected"

- Provider detected automated access
- Solve CAPTCHA manually in browser
- Retry consult

### "Feature disabled"

- Set `ENABLE_UI_CONSULT=1` in environment
- Restart Daena

---

## Audit Logging

All UI consults are logged to:
- `backend/tools/audit_log.py` (JSONL format)
- Includes: `tool_name`, `args` (redacted), `status`, `result`, `trace_id`, `timestamp`

**Example Audit Entry:**
```json
{
  "tool_name": "consult_ui",
  "args": {"provider": "chatgpt", "question": "[REDACTED]"},
  "status": "ok",
  "result": {"answer_text": "[REDACTED]", "provider": "chatgpt"},
  "trace_id": "abc123...",
  "timestamp": "2025-12-13T10:00:00Z",
  "audit_id": "xyz789..."
}
```

---

**STATUS: ✅ IMPLEMENTED AND READY FOR USE**

**Next Steps:**
1. Enable feature: `ENABLE_UI_CONSULT=1`
2. Install Playwright: `pip install playwright && playwright install chromium`
3. Test with manual approval flow
4. Integrate UI approval buttons in dashboard









