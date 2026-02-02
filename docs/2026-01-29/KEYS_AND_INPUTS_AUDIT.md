# Keys and message inputs – audit

Quick reference for which pages have chat/message inputs and how Enter + Send work.

## Pages with message input (chat/send)

| Page | Input ID | Enter key | Send button | Voice widget |
|------|----------|-----------|-------------|--------------|
| **Daena Office** | `message-input` | ✅ keydown (Enter sends, Shift+Enter newline) | ✅ form submit | ✅ |
| **Department Office** | `messageInput` | ✅ onkeypress + addEventListener | ✅ `sendMessage()` | ✅ (messageInput fallback) |
| **Conference Room** | `message-input` | ✅ `handleEnter(event)` | ✅ `sendMessage()` | ✅ |
| **Council Debate** | `message-input` | ✅ addEventListener keypress | ✅ `sendMessage()` | ✅ |

## Fixes applied

- **voice-widget.js**: Voice-to-input now looks for both `message-input` and `messageInput` so Department Office is supported; auto-send calls `window.sendMessage()` when no `chat-form` exists.
- **conference_room.html**: `sendMessage()` null-checks input and `chat-messages` before use.
- **council_debate.html**: Enter handler and `sendMessage()` null-check `message-input`.
- **daena_office.html**: Enter handler null-checks `message-input` and `chat-form` before attaching/submitting.

## Pages without message input

Dashboard, Incident Room, QA Guardian, Founder, Connections, App Setup, Brain & API, Agents, etc. have no chat input; keyboard/voice “send” does not apply. Buttons and other controls on those pages are unchanged.
