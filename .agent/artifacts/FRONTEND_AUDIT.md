# Frontend Audit Report
## Generated 2026-02-01

### STUB TEMPLATES (< 1KB - placeholders with no real functionality)
These are tiny files that just display a heading and redirect to other pages:

| File | Size | Action |
|------|------|--------|
| cmp_voting.html | 506b | Replace with cmp_canvas.html link |
| council_dashboard.html | 754b | Replace with councils.html link |
| council_synthesis.html | 610b | Merge into councils.html |
| daena_command_center.html | 713b | Replace with dashboard.html |
| enhanced_dashboard.html | 689b | Remove - dashboard.html is the main |
| honey_tracker.html | 503b | Merge into control_plane_v2.html |
| strategic_meetings.html | 506b | Merge into strategic_room.html |
| system_monitor.html | 987b | Merge into control_plane_v2.html |
| task_timeline.html | 490b | Merge into tasks.html |

### DUPLICATE/VERSIONED TEMPLATES
| File | Preferred Version | Action |
|------|-------------------|--------|
| control_plane.html | control_plane_v2.html | Delete old |
| DAENA_NEW_BLUEPRINT.html | Reference only | Keep as docs |

### DUPLICATE BACKEND ROUTES
These files have multiple versions that should be consolidated:

| Pattern | Files | Keep |
|---------|-------|------|
| agent_builder_*.py | 5 files | agent_builder.py |
| council_*.py | 4 files | council.py |
| workspace_*.py | 2 files | workspace.py |

### CORE PAGES TO KEEP
1. **dashboard.html** - Main executive dashboard
2. **daena_office.html** - VP office with chat
3. **founder_panel.html** - Founder controls
4. **control_plane_v2.html** - New unified control plane
5. **councils.html** - Council management
6. **departments.html** - Department overview
7. **agents.html** - Agent management
8. **skills.html** - Skill registry
9. **tasks.html** - Task management
10. **projects.html** - Project management
11. **mcp_hub.html** - MCP connections
12. **cmp_canvas.html** - CMP graph editor
13. **approval_workflow.html** - Approval system
14. **qa_guardian_dashboard.html** - QA system
15. **brain_settings.html** - LLM configuration
16. **voice_diagnostics.html** - Voice system

### RECOMMENDED DELETIONS
Files that should be deleted as they're superseded:

1. `cmp_voting.html` - Stub
2. `council_dashboard.html` - Stub
3. `council_synthesis.html` - Stub
4. `daena_command_center.html` - Stub
5. `enhanced_dashboard.html` - Stub
6. `honey_tracker.html` - Stub
7. `strategic_meetings.html` - Stub
8. `system_monitor.html` - Stub
9. `task_timeline.html` - Stub
10. `control_plane.html` - Replaced by v2

### BACKEND ROUTE CONSOLIDATION
Delete these duplicate route files:
1. `agent_builder_api.py`
2. `agent_builder_api_simple.py`
3. `agent_builder_complete.py`
4. `agent_builder_platform.py`
5. `agent_builder_simple.py`
6. `change_control_v2.py`
7. `council_v2.py`
8. `workspace_v2.py`
9. `founder_api.py` (merge into founder_panel.py)

Keep: `agent_builder.py`, `council.py`, `workspace.py`
