
# Phase I commit and push script
# Run from an elevated PowerShell (not Claude Code sandbox)
Set-Location D:\Ideas\Daena

Write-Host "=== Staging Phase I changes ===" -ForegroundColor Cyan
git add backend/app/api/v1/connector_oauth.py
git add backend/app/api/v1/__init__.py
git add backend/app/services/integrations/integration_router.py
git add backend/app/services/department_router.py
git add backend/app/services/integrations/oauth_service.py
git add backend/app/services/chat_orchestrator.py
git add backend/tests/test_department_router.py
git add frontend/src/components/chat/MessageList.tsx
git add frontend/src/components/icons/BrandIcons.tsx
git add frontend/src/pages/ChatPage.tsx
git add frontend/src/pages/settings/SettingsGeneral.tsx
git add frontend/src/stores/chatStore.ts

Write-Host "`n=== Changes ===" -ForegroundColor Cyan
git status --short

Write-Host "`n=== Committing ===" -ForegroundColor Cyan
git commit -m @"
Phase I: Department routing + OAuth connector flow + frontend wiring

Backend:
- DepartmentRouter: maps task types to 60 department agents (MIND/EYES/HANDS/VOICE/SHIELD/MEMORY)
- SwarmPlanner + SwarmExecutor wired into Stage 7.5 (was dead code, now active for multi-step tasks)
- ConnectorOAuthService: Google OAuth 2.0 for Gmail/Calendar (authorize, callback, token refresh)
- Connector OAuth API endpoints: /connectors/{id}/oauth/authorize + callback
- IntegrationRouter: auto-refresh expired tokens before every API call
- MCPRegistry singleton in app events

Frontend:
- 7 broken connector icons fixed (Slack, Canva, OpenAI/Codex, Monday, Salesforce, Teams, Amplitude)
- Tool call/result SSE rendering in chat (spinner, checkmark, params + result preview)
- AGI Mode toggle in Settings > Session Defaults
- CdnIcon fallback shows letter badge instead of blank

Tests: 1550 passing, 0 failing
Frontend: 0 TypeScript errors

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
"@

Write-Host "`n=== Pushing to GitHub ===" -ForegroundColor Cyan
git push

Write-Host "`n=== Done! ===" -ForegroundColor Green
