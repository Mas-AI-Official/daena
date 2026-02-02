# Frontend↔Backend Endpoint Mismatches

## Date: December 20, 2025

## Issues Found

### 1. Daena Chat Endpoints

**Frontend Calls:**
- `POST /api/v1/daena/chat/start` - Start new chat
- `POST /api/v1/daena/chat/{sessionId}/message` - Send message
- `GET /api/v1/daena/chat/{sessionId}` - Get chat history

**Backend Provides:**
- `POST /api/v1/daena/chat` - Send message (with session_id in body)
- `GET /api/v1/daena/chat/{session_id}` - Get chat session
- `GET /api/v1/daena/chat/sessions` - List all sessions
- `DELETE /api/v1/daena/chat/{session_id}` - Delete session

**Fix:** Update frontend to match backend endpoints.

### 2. Department Chat Endpoints

**Frontend Calls:**
- `POST /api/v1/office/{deptId}/chat` - Send message to department

**Backend Provides:**
- `POST /api/v1/departments/{department_id}/chat` - Department chat

**Fix:** Update frontend to use `/api/v1/departments/{id}/chat`.

### 3. Category Endpoints

**Frontend Calls:**
- `GET /api/v1/daena/categories/list` - List categories
- `POST /api/v1/daena/categories/{sessionId}/set` - Set category
- `POST /api/v1/daena/categories/{sessionId}/update_title` - Update title

**Backend Provides:**
- `GET /api/v1/chat-history/categories` - Get categories
- `GET /api/v1/chat-history/categories/{category}` - Get sessions by category
- `PUT /api/v1/chat-history/sessions/{session_id}` - Update session (includes category)

**Fix:** Update frontend to use chat-history endpoints.

### 4. Chat History Endpoints

**Frontend Calls:**
- `GET /api/v1/chat-history/departments/{id}/chats` - ✅ EXISTS
- `POST /api/v1/chat-history/departments/{id}/sessions` - ✅ EXISTS
- `POST /api/v1/chat-history/sessions/{id}/messages` - ✅ EXISTS

**Status:** These are correct!

## Fixes Needed

1. Update `api-client.js` to match backend endpoints
2. Update `department-chat.js` to use correct department endpoint
3. Add missing endpoints to backend if needed
4. Ensure all endpoints return consistent JSON format



