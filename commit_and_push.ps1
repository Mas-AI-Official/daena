
# Run this from an elevated PowerShell or regular terminal (not Claude Code sandbox)
Set-Location D:\Ideas\Daena

Write-Host "=== Staging all changes ===" -ForegroundColor Cyan
git add -A

Write-Host "`n=== Changes to commit ===" -ForegroundColor Cyan
git status --short

Write-Host "`n=== Committing ===" -ForegroundColor Cyan
git commit -m @"
Phase G + G+ + H: Agentic loop, integrations, full agent autonomy

Phase G: MCP Connections + Department Execution
- 3 API clients (Gmail, Calendar, Notion) with REST APIs
- IntegrationRouter with governance permission checks
- 10 department workflows across 7 departments
- Persistent DepartmentTask model with cron scheduling
- Heartbeat daemon wiring for automated workflow execution

Phase G+: The Agentic Tool-Use Loop
- ToolSchemaBuilder: Dynamic LLM function definitions
- Stage 8.5 in orchestrator: generate -> parse -> execute -> inject -> continue
- ToolUseLoop: Standalone executor dispatching to all tool categories

Phase H: Full Agent Autonomy + Desktop Control
- Tool schema expanded from 19 to 35+ tools
- Desktop control via pyautogui (mouse, keyboard, screen capture)
- MCP auto-discovery: registered MCP tools auto-appear in LLM schema
- Working web search via DuckDuckGo
- File delete respects Hard Law 6 (archive only)
- New tools: run_python, install_package, http_get/post, copy/move/delete files
- Browser: extract_text, fill_form, click_element
- Fixed routing source label bug (user_override vs primary_mind)
- MCPRegistry singleton wired to app events

Frontend:
- Fixed 7 broken connector icons (Slack, Canva, OpenAI/Codex, Monday, Salesforce, Teams, Amplitude)
- CDN icon fallback shows letter badge instead of blank space
- Tool call/result SSE events wired to chat store + rendered in MessageList
- AGI Mode toggle added to Settings > Session Defaults
- Pipeline stages show tool execution progress

Tests: 1410 passing, 0 failing (+23 new tests)
Frontend: 0 TypeScript errors

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
"@

Write-Host "`n=== Pushing to GitHub ===" -ForegroundColor Cyan
git push

Write-Host "`n=== Done! ===" -ForegroundColor Green
Read-Host "Press Enter to close"
