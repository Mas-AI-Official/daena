# CODEMAP — DAENA
Generated: 2026-04-07 11:50
Purpose: Quick architecture reference for Claude Code sessions.
Update: Run `python D:\Ideas\codemap.py daena`

## Directory Structure
```
Daena/ (1 py)
  .archive/
    backend_logs_20260318/ (1 py)
    dead_approval_queue/ (3 py)
    phase3_dupes/
  .claude/
    worktrees/
      modest-pascal/ (3 py)
      upbeat-banzai/
  .github/
    workflows/
  .pytest_cache/
    v/
      cache/
  .ruff_cache/
    0.15.5/
  .secrets/
  .serena/
    cache/
      python/
    memories/
  BrowserMetrics/
  Default/
  DeferredBrowserMetrics/
  Doc/ (2 py)
    Daena-Mind/
      T0-ephemeral/
      T0-raw/
      T1-draft/
      T1-working/
      T2-refined/
      T2-verified/
      T3-core/
      T3-production/
      T4-compound/
      T4-constitutional/
      agents/
      edna-audit/
      experts/
      jobs/
      knowledge/
    Deep report/
      risks/
    Deep report v2/
    Phase1/
    Phase2/
    applications/
      screenshots/
    benchmarks/
    chatgt finall daena 3-25-2026/
    content-drafts/
    demo/
    lates update/
    marketing/
    misc/
    pitch-package/
      inputs/
      investor_package/ (1 py)
    prompts/
    shiping/
    v1-data/
      prompt_library/
      tool_playbooks/
    v1-docs/
      12-11-2025/
      12-12-2025/
      2025-12-13/
      6 TOP-LEVEL SYSTEM DESIGN SPEC AND REFACTOR MISSION/
      ARCHITECTURE/
      BUSINESS/
      DEPLOYMENT/
      GUIDES/
      IMPLEMENTATION/
      MIGRATION/
      REPORTS/
      TECHNICAL/
      TESTING/
      archive/
      encrypt/
      patents/ (5 py)
      upgrade/
  ShaderCache/
  agent-harness/ (1 py)
    .pytest_cache/
      v/
    cli_anything/
      daena/ (3 py)
    cli_anything_daena.egg-info/
  backend/ (1 py)
    .archive/
      general/
    .pytest_cache/
      v/
    .ruff_cache/
      0.15.5/
    app/ (2 py)
      api/ (2 py)
      config/ (2 py)
      core/ (12 py)
      middleware/ (4 py)
      models/ (15 py)
      schemas/ (11 py)
      services/ (50 py)
      skills/
      tasks/ (1 py)
    data/
      mind/
    migrations/ (1 py)
      versions/ (1 py)
    tests/ (70 py)
      test_benchmarks/ (2 py)
      test_daenabot/ (6 py)
      test_execution_layer/ (6 py)
      test_mobile_api/ (2 py)
      test_remote/ (2 py)
      test_session_sync/ (2 py)
      test_system/ (2 py)
      test_tool_lifecycle/ (11 py)
    uploads/
  component_crx_cache/
  data/
    mind/
      T0-ephemeral/
      T1-working/
      T2-refined/
      T3-core/
      T4-constitutional/
      reports/
      templates/
  docs/ (3 py)
    assets/
    laevateinn/
    pitch/
  frontend/ (2 ts)
    .claude/
    .pytest_cache/
      v/
    .ruff_cache/
      0.15.5/
    dist_old/
      assets/
    e2e/ (2 ts)
    extglob/
    public/
    src/ (2 ts)
      assets/
      components/
      hooks/ (1 ts)
      lib/ (1 ts)
      pages/ (24 ts)
      providers/ (1 ts)
      stores/ (6 ts)
      styles/ (1 ts)
      types/ (1 ts)
    test-results/
      screenshot-all-Screenshot-All-Pages-screenshot-chat-chromium/
  landing/
    screenshots/
  marketing/
  patent/
    final - NBMF-EDNA-TLM/
      figures/
  pitch-deck/ (1 py)
    audio/
  scripts/ (6 py)
  segmentation_platform/
  skills/
  test-results/
  tests/ (2 py)
    e2e/ (3 py)
  uploads/
  vault/
  venv_daena/
    Include/
      site/
    Lib/
      site-packages/ (10 py)
    Scripts/ (3 py)
    share/
      man/
  venv_daena_main_py310/
```

## Backend (252 Python files)

### Key Modules

- `backend/app/api/deps.py`: **CurrentUser** (0m) | `get_current_user`, `require_role`
- `backend/app/api/v1/agents.py`: `get_agent_service`, `list_departments`, `get_department`, `create_department`, `list_agents`
- `backend/app/api/v1/auth.py`: **OAuthExchangeRequest** (0m), **CompleteProfileRequest** (0m) | `_check_login_rate_limit`, `_record_login_attempt`, `_cleanup_expired`, `get_auth_service`, `register`
- `backend/app/api/v1/autopilot.py`: **AutopilotStartRequest** (0m), **AutopilotApproveRequest** (0m), **AutopilotRejectRequest** (0m), **AutopilotStopRequest** (0m), **AutopilotResponse** (0m) | `get_autopilot_controller`, `start_autopilot`, `stop_autopilot`, `approve_step`, `reject_step`
- `backend/app/api/v1/benchmark.py`: `cost_comparison`, `quick_summary`
- `backend/app/api/v1/billing.py`: **QuotaUpdateRequest** (0m) | `_tracker`, `get_overview`, `get_cost_by_provider`, `get_cost_by_task_type`, `get_usage_history`
- `backend/app/api/v1/chat.py`: `_run_memory_writeback`, `get_chat_service`, `get_model_registry`, `_resolve_stream_session`, `_stream_message_response`
- `backend/app/api/v1/connections.py`: `get_connection_service`, `create_connector`, `list_connectors`, `get_connector`, `connect`
- `backend/app/api/v1/connector_oauth.py`: `authorize`, `oauth_callback`, `refresh_tokens`
- `backend/app/api/v1/daenabot.py`: **DaenaBotCommandRequest** (0m), **DaenaBotCommandResponse** (0m) | `execute_command`, `list_agents`
- `backend/app/api/v1/dynamic_models.py`: **ProvisionRequest** (0m), **ProvisionResponse** (0m), **RemoveRequest** (0m) | `get_dynamic_model_service`, `provision_provider`, `remove_provider`, `list_provisionable`, `refresh_provider`
- `backend/app/api/v1/execution.py`: `get_execution_service`, `execute_tool`, `list_executions`, `get_execution`, `create_task`
- `backend/app/api/v1/files.py`: `_type_allowed`, `upload_file`, `get_file_meta`
- `backend/app/api/v1/founder.py`: `get_audit_service`, `get_model_registry`, `_serialize_candidate`, `_normalize_route_event`, `_summarize_routes`
- `backend/app/api/v1/governance.py`: `get_governance_engine`, `get_approval_service`, `get_audit_service`, `evaluate_action`, `list_pending_approvals`
- `backend/app/api/v1/health.py`: `_get_ollama_status`, `health_check`, `readiness_check`, `version_info`, `detailed_health_check`
- `backend/app/api/v1/heartbeat.py`: `_get_daemon`, `_get_scheduler`, `heartbeat_status`, `heartbeat_start`, `heartbeat_pause`
- `backend/app/api/v1/integrations.py`: **ToolExecuteRequest** (0m), **QualifiedToolRequest** (0m), **WorkflowRunRequest** (0m) | `list_available_tools`, `execute_tool`, `execute_qualified_tool`, `list_providers`, `list_workflows`
- `backend/app/api/v1/laevateinn.py`: **LaevateinnQueryRequest** (0m), **LaevateinnQuickRequest** (0m), **ComprehensionRequest** (0m), **ComprehensionResponse** (0m), **LaevateinnTraceResponse** (0m), **LaevateinnStatusResponse** (0m) | `process_query`, `quick_answer`, `comprehend_query`, `get_apex_status`
- `backend/app/api/v1/mcp_server.py`: `_get_mcp_server`, `list_tools`, `call_tool`, `jsonrpc_endpoint`
- `backend/app/api/v1/memory.py`: `get_memory_service`, `store_memory`, `list_memories`, `get_memory`, `promote_memory`
- `backend/app/api/v1/mobile.py`: **MobileCommandRequest** (0m), **QuickActionRequest** (0m), **MobileApprovalRequest** (0m), **MobileResponse** (0m) | `send_command`, `get_status`, `get_tasks`, `approve_gate`, `get_notifications`
- `backend/app/api/v1/pipeline.py`: **CreateProjectRequest** (0m), **AdvanceStageRequest** (0m), **UpdateScoringRequest** (0m), **UpdateFinancialsRequest** (0m), **SetDocumentRequest** (0m) | `get_pipeline_service`, `pipeline_summary`, `list_projects`, `create_project`, `get_project`
- `backend/app/api/v1/projects.py`: **CreateProjectBody** (2m), **UpdateProjectBody** (2m) | `_sanitize_text`, `list_projects`, `create_project`, `get_project`, `update_project`
- `backend/app/api/v1/prompts.py`: **PromptResponse** (0m) | `_get_manager`, `list_pending_prompts`, `respond_to_prompt`, `prompt_history`
- `backend/app/api/v1/runtimes.py`: **PrimaryRuntimeRequest** (0m) | `list_runtimes`, `rediscover_runtimes`, `get_runtime`, `refresh_runtime_auth`, `test_runtime_connection`
- `backend/app/api/v1/self_improvement.py`: **FeedbackRequest** (0m) | `_get_auditor`, `_get_learning_service`, `run_audit`, `last_audit`, `list_suggestions`
- `backend/app/api/v1/settings.py`: **DeveloperModeResponse** (0m), **DeveloperModeUpdate** (0m), **SettingsOverview** (0m), **UserPreferencesResponse** (0m), **UserPreferencesUpdate** (0m) | `get_settings_overview`, `get_developer_mode`, `toggle_developer_mode`, `get_user_preferences`, `update_user_preferences`
- `backend/app/api/v1/skill_refinery.py`: **ExtractSkillRequest** (0m), **PromoteRequest** (0m), **TrackUsageRequest** (0m) | `get_skill_store`, `search_skills_endpoint`, `list_skills`, `refinery_health`, `emergency_stop`
- `backend/app/api/v1/skills.py`: **CreateFileSkillRequest** (0m), **FileSkillCreate** (0m) | `get_skill_service`, `create_skill`, `list_skills`, `list_installed_skills`, `get_skill`
- `backend/app/api/v1/waitlist.py`: **WaitlistSignup** (0m), **WaitlistResponse** (0m) | `join_waitlist`, `waitlist_count`
- `backend/app/api/v1/ws.py`: `_get_manager`, `websocket_chat`
- `backend/app/config/founder_accounts.py`: **FounderAccount** (0m), **DaenaIdentity** (4m) | `get_service_account`
- `backend/app/config/stop_slop.py`: **SlopMatch** (0m), **SlopScore** (3m) | `scan_slop`, `strip_slop`, `score_content`
- `backend/app/core/config.py`: **Settings** (14m) | `_env_file_path`, `_env_file_values`, `_default_env_precedence`, `_env_precedence_mode`, `get_settings`
- `backend/app/core/constants.py`: **PlanType** (0m), **UserRole** (2m), **SubCapability** (0m), **ModelProvider** (0m), **HealthStatus** (0m), **ChatMode** (0m), **RoutingMode** (0m), **GovernanceSlider** (0m), **MessageRole** (0m), **RiskLevel** (0m), **ApprovalStatus** (0m), **ActorType** (0m), **NBMFTier** (0m), **ContentType** (0m), **VerificationStatus** (0m), **LearningAction** (0m), **TaskStatus** (0m), **ExecutionStatus** (0m), **AuthType** (0m), **ConnectorStatus** (0m), **PermissionLevel** (0m), **SecretType** (0m), **SubscriptionStatus** (0m)
- `backend/app/core/database.py`: `get_db`
- `backend/app/core/events.py`: **EventBus** (4m) | `get_runtime_registry`, `get_mcp_registry`, `initialize_runtime_registry`
- `backend/app/core/exceptions.py`: **DaenaError** (1m), **AuthenticationError** (0m), **TokenExpiredError** (0m), **InsufficientRoleError** (0m), **GovernanceBlockedError** (0m), **HardLawViolationError** (0m), **ApprovalRequiredError** (0m), **TenantNotFoundError** (0m), **TenantIsolationError** (0m), **NotFoundError** (0m), **ConflictError** (0m), **ValidationError** (0m), **ProviderError** (0m), **ProviderUnavailableError** (0m), **BudgetExceededError** (0m), **UserQuotaExhaustedError** (0m), **ExecutionTimeoutError** (0m), **SandboxError** (0m), **RateLimitError** (0m)
- `backend/app/core/hard_laws.py`: **HardLaw** (1m) | `check_hard_laws`
- `backend/app/core/logging.py`: `setup_logging`, `get_logger`
- `backend/app/core/redis.py`: `get_redis_client`, `check_redis_health`
- `backend/app/core/security.py`: `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `generate_refresh_token`
- `backend/app/core/vault.py`: `_derive_key`, `_get_aesgcm`, `encrypt_dict`, `decrypt_dict`, `is_encrypted`
- `backend/app/core/websocket.py`: **ConnectionManager** (9m)
- `backend/app/main.py`: `_seed_departments_for_all_tenants`, `lifespan`, `create_app`
- `backend/app/middleware/rate_limit.py`: **RateLimitMiddleware** (2m)
- `backend/app/middleware/request_id.py`: **RequestIDMiddleware** (1m)
- `backend/app/middleware/tenant.py`: **TenantMiddleware** (1m)
- `backend/app/models/base.py`: **GUID** (3m), **JSONBCompat** (1m), **Base** (0m), **TimestampMixin** (0m), **TenantMixin** (0m), **SoftDeleteMixin** (0m)
- `backend/app/models/chat.py`: **ChatCategory** (0m), **ChatSession** (0m), **ChatMessage** (0m)
- `backend/app/models/connections.py`: **Connector** (0m), **ConnectorInstance** (0m), **ConnectorPermission** (0m)
- `backend/app/models/department_task.py`: **DepartmentTask** (0m)
- `backend/app/models/execution.py`: **Task** (0m), **ToolExecution** (0m), **Skill** (0m)
- `backend/app/models/financial.py`: **UsageLedger** (0m), **VaultSecret** (0m), **Subscription** (0m), **UserQuota** (0m)
- `backend/app/models/governance.py`: **GoaRequest** (0m), **GoaPolicyState** (0m), **GoaAuditEvent** (0m), **PendingApproval** (0m), **RoutingPolicy** (0m)
- `backend/app/models/identity.py`: **Tenant** (0m), **User** (0m), **RefreshToken** (0m), **PasswordResetToken** (0m)
- `backend/app/models/memory.py`: **MemoryEntry** (0m), **LearningLog** (0m)
- `backend/app/models/organization.py`: **Department** (0m), **Agent** (0m), **BrainModel** (0m)
- `backend/app/models/pipeline.py`: **PipelineStage** (2m), **ProjectPipeline** (1m)
- `backend/app/models/project.py`: **Project** (1m)
- `backend/app/models/skill.py`: **RefinedSkill** (0m)
- `backend/app/models/waitlist.py`: **WaitlistEntry** (1m)
- `backend/app/schemas/_base.py`: **DaenaSchema** (0m), **ErrorDetail** (0m), **StandardResponse** (0m), **ErrorResponse** (0m), **PaginationParams** (1m), **PaginatedMeta** (0m), **PaginatedResponse** (0m), **TenantScoped** (0m), **TimestampedResponse** (0m)
- `backend/app/schemas/agents.py`: **CreateDepartmentRequest** (0m), **CreateAgentRequest** (0m), **DepartmentResponse** (0m), **AgentResponse** (0m)
- `backend/app/schemas/auth.py`: **RegisterRequest** (2m), **LoginRequest** (0m), **ForgotPasswordRequest** (0m), **ResetPasswordRequest** (2m), **UserResponse** (0m), **TokenData** (0m), **RegisterResponse** (0m)
- `backend/app/schemas/chat.py`: **CreateSessionRequest** (0m), **UpdateSessionRequest** (0m), **SendMessageRequest** (0m), **StreamMessageRequest** (0m), **TruncateMessagesRequest** (0m), **SessionResponse** (0m), **MessageResponse** (0m)
- `backend/app/schemas/connections.py`: **CreateConnectorRequest** (0m), **ConnectRequest** (0m), **SetPermissionRequest** (0m), **ConnectorResponse** (0m), **ConnectorInstanceResponse** (0m), **ConnectorPermissionResponse** (0m)
- `backend/app/schemas/execution.py`: **ExecuteToolRequest** (0m), **CreateTaskRequest** (0m), **UpdateTaskRequest** (0m), **ToolExecutionResponse** (0m), **TaskResponse** (0m), **GovernanceCheckResponse** (0m)
- `backend/app/schemas/founder.py`: **RoutingPreviewRequest** (0m), **RoutingPolicyUpdate** (0m)
- `backend/app/schemas/governance.py`: **EvaluateRequest** (0m), **GovernanceDecisionResponse** (0m), **CreateApprovalRequest** (0m), **ApprovalDecisionRequest** (0m), **ApprovalResponse** (0m), **AuditEntryResponse** (0m)
- `backend/app/schemas/memory.py`: **StoreMemoryRequest** (0m), **StoreExperienceRequest** (0m), **PromoteRequest** (0m), **DemoteRequest** (0m), **MemoryResponse** (0m), **LearningLogResponse** (0m), **MemoryStatsResponse** (0m)
- `backend/app/schemas/skills.py`: **CreateSkillRequest** (0m), **UpdateSkillRequest** (0m), **SkillResponse** (0m), **SkillSummaryResponse** (0m)
- `backend/app/services/_base.py`: **BaseService** (4m)
- `backend/app/services/agent_core/agent_loop.py`: **AgentStep** (0m), **StepResult** (1m), **ExecutionReceipt** (1m), **AgentLoop** (9m)
- `backend/app/services/agent_core/browser_agent.py`: **BrowserAgent** (15m)
- `backend/app/services/agent_core/daemon.py`: **DaenaDaemon** (6m)
- `backend/app/services/agent_core/interactive_prompts.py`: **PromptType** (0m), **PromptOption** (0m), **InteractivePrompt** (1m), **InteractivePromptManager** (18m)
- `backend/app/services/agent_core/prompt_governance.py`: **GovernedPromptManager** (12m)
- `backend/app/services/agent_core/smart_resolver.py`: **SmartResolver** (6m) | `_run_sync`, `_search_files`
- `backend/app/services/agent_core/system_access.py`: **CriticalityClassifier** (1m), **SystemAccess** (15m) | `_run_sync`
- `backend/app/services/agents.py`: **AgentService** (9m)
- `backend/app/services/approval.py`: **ApprovalService** (9m)
- `backend/app/services/archive.py`: **ArchiveService** (5m) | `_is_developer_mode`
- `backend/app/services/audit.py`: **AuditService** (6m)
- `backend/app/services/auth.py`: **AuthService** (9m)
- `backend/app/services/autopilot/background_queue.py`: **BackgroundTask** (1m), **BackgroundQueue** (11m)
- `backend/app/services/autopilot/continuation.py`: **AutopilotState** (1m), **AutopilotController** (10m)
- `backend/app/services/autopilot/criticality_classifier.py`: **CriticalityLevel** (0m), **CriticalityRule** (0m), **CriticalityClassifier** (6m)
- `backend/app/services/benchmarks/cost_benchmark.py`: **QueryScenario** (0m), **RegularCostResult** (0m), **DaenaCostResult** (0m), **BenchmarkComparison** (0m), **BenchmarkReport** (0m), **CostBenchmark** (7m)
- `backend/app/services/benchmarks/hallucination_benchmark.py`: **QuestionCategory** (0m), **BenchmarkQuestion** (0m), **AnswerEvaluation** (0m), **CategoryResult** (7m), **BenchmarkReport** (3m), **HallucinationBenchmark** (4m) | `evaluate_answer`, `_question_to_intent`, `run_governance_logic_benchmark`
- `backend/app/services/benchmarks/suite.py`: **BenchmarkResult** (1m), **DaenaBenchmarkSuite** (7m)
- `backend/app/services/billing/budget_manager.py`: **BudgetConfig** (1m), **BudgetManager** (6m)
- `backend/app/services/billing/cost_tracker.py`: **UsageEntry** (0m), **UnifiedCostTracker** (11m)
- `backend/app/services/chat.py`: **ChatService** (16m)
- `backend/app/services/chat_orchestrator.py`: **_AgentLoopHandled** (0m), **ChatOrchestrator** (6m)
- `backend/app/services/connection_service.py`: **ConnectionService** (15m)
- `backend/app/services/cost_guard.py`: **CostEstimate** (1m), **BudgetStatus** (0m), **UserBudgetStatus** (0m), **CostGuard** (7m)
- `backend/app/services/cost_router.py`: **CostAwareRouter** (3m)
- `backend/app/services/council_engine.py`: **MemberResponse** (0m), **CouncilResult** (0m), **CouncilEngine** (5m)
- `backend/app/services/daenabot/_base_agent.py`: **BaseAgent** (3m)
- `backend/app/services/daenabot/browser_agent.py`: **BrowserAgent** (11m)
- `backend/app/services/daenabot/file_agent.py`: **FileAgent** (10m)
- `backend/app/services/daenabot/intent_parser.py`: **ToolCall** (1m), **IntentParser** (6m)
- `backend/app/services/daenabot/mcp_agent.py`: **MCPAgent** (2m)
- `backend/app/services/daenabot/planner.py`: **Action** (0m), **ActionPlanner** (3m)
- `backend/app/services/daenabot/router.py`: **ToolCall** (0m), **DaenaBotRouter** (1m)
- `backend/app/services/daenabot/terminal_agent.py`: **TerminalAgent** (5m)
- `backend/app/services/daenabot/vision_browser_agent.py`: **VisionBrowserAgent** (14m)
- `backend/app/services/daenabot/web_crawler_agent.py`: **WebCrawlerAgent** (7m)
- `backend/app/services/daenabot/workspace.py`: **ActionResult** (0m), **Workspace** (6m)
- `backend/app/services/dcp_loader.py`: **DCPExpert** (0m), **DCPDomain** (0m), **DCPLoader** (9m) | `get_dcp_loader`
- `backend/app/services/demo_mode.py`: `is_demo_mode`, `mock_llm_response`, `seed_demo_data`
- `backend/app/services/department_prompts.py`: `get_agent_prompt`, `get_all_agent_prompts`, `register_dynamic_department`
- `backend/app/services/department_router.py`: **AgentAssignment** (0m), **DepartmentRouter** (6m)
- `backend/app/services/department_workflows.py`: **WorkflowStep** (0m), **WorkflowDef** (0m), **WorkflowResult** (1m), **DepartmentWorkflowEngine** (10m) | `_register`
- `backend/app/services/dream_engine.py`: **DreamAction** (0m), **DreamReport** (1m), **DreamEngine** (13m) | `is_sensitive`, `simple_token_similarity`, `get_dream_engine`
- `backend/app/services/drift_detector.py`: **DriftSeverity** (0m), **DriftAction** (0m), **ExecutionState** (0m), **ResourceBudget** (0m), **DriftCheckpoint** (0m), **DriftResponse** (0m), **DriftDetector** (11m)
- `backend/app/services/dynamic_departments.py`: `should_create_department`, `create_department`, `auto_detect_and_create`
- `backend/app/services/dynamic_model_service.py`: **ProvisionResult** (0m), **DynamicModelService** (7m)
- `backend/app/services/execution_service.py`: **ExecutionService** (14m)
- `backend/app/services/extension_scanner.py`: **ExtensionInfo** (1m) | `_categorize_plugin`, `_human_name`, `scan_extensions`
- `backend/app/services/governance.py`: **GovernanceEngine** (8m)
- `backend/app/services/heartbeat/cron_scheduler.py`: **CronFrequency** (0m), **CronJob** (2m), **CronScheduler** (9m)
- `backend/app/services/heartbeat/heartbeat_checks.py`: **ActionPriority** (0m), **SuggestedAction** (0m), **HeartbeatCheckResult** (0m) | `_run_sync`, `check_runtime_health`, `check_file`, `check_git_status`, `_attempt_auto_fix`
- `backend/app/services/heartbeat/heartbeat_config.py`: **HeartbeatState** (0m), **AutopilotLevel** (0m), **CheckType** (0m), **HeartbeatCheck** (0m), **HeartbeatConfig** (3m)
- `backend/app/services/heartbeat/heartbeat_daemon.py`: **HeartbeatCycleLog** (1m), **HeartbeatDaemon** (15m)
- `backend/app/services/heartbeat/work_queue.py`: **QueueTaskStatus** (0m), **QueueTaskPriority** (0m), **QueueTask** (1m), **WorkQueue** (11m)
- `backend/app/services/integrations/calendar_client.py`: **CalendarClient** (8m)
- `backend/app/services/integrations/gmail_client.py`: **GmailClient** (10m)
- `backend/app/services/integrations/integration_router.py`: **IntegrationError** (0m), **PermissionDeniedError** (0m), **NotConnectedError** (0m), **IntegrationRouter** (7m)
- `backend/app/services/integrations/notion_client.py`: **NotionClient** (11m)
- `backend/app/services/integrations/oauth_service.py`: **ConnectorOAuthService** (6m)
- `backend/app/services/intent_amplifier.py`: **VaguePattern** (0m), **Expansion** (0m), **AmplifiedIntent** (0m) | `amplify_intent`
- `backend/app/services/laevateinn/code_verifier.py`: **CodeBlock** (0m), **CodeExecutionResult** (0m), **CodeVerifier** (8m)
- `backend/app/services/laevateinn/comprehension.py`: **DeepComprehensionEngine** (10m)
- `backend/app/services/laevateinn/compute_scaler.py`: **DynamicComputeScaler** (4m)
- `backend/app/services/laevateinn/debate.py`: **AdversarialModelDebate** (11m)
- `backend/app/services/laevateinn/deep_think.py`: **DeepThinkResult** (0m), **DeepThinkEngine** (9m) | `_now_ms`
- `backend/app/services/laevateinn/delivery.py`: **JobsDeliveryEngine** (7m)
- `backend/app/services/laevateinn/depth_engine.py`: **RecursiveDepthEngine** (9m)
- `backend/app/services/laevateinn/episodic_memory.py`: **Episode** (0m), **EpisodeSearchResult** (0m), **EpisodicMemory** (11m) | `_row_to_episode`, `_tokenize`
- `backend/app/services/laevateinn/interaction_logger.py`: **Interaction** (0m), **InteractionStats** (0m), **InteractionLogger** (12m)
- `backend/app/services/laevateinn/knowledge_graph.py`: **Entity** (0m), **Relationship** (0m), **Pattern** (0m), **KnowledgeEnrichment** (0m), **PersistentKnowledgeGraph** (26m)
- `backend/app/services/laevateinn/meta_monitor.py`: **StageMetric** (0m), **ModelMetric** (0m), **DifficultyCalibration** (0m), **MetaReport** (0m), **MetaMonitor** (12m)
- `backend/app/services/laevateinn/pipeline.py`: **LaevateinnPipeline** (3m)
- `backend/app/services/laevateinn/speculative.py`: **CachedAnswer** (0m), **SpeculationResult** (0m), **SpeculativePrecomputer** (12m)
- `backend/app/services/laevateinn/tool_augmented.py`: **ToolCall** (0m), **AugmentedVerification** (0m), **ToolAugmentedReasoner** (13m)
- `backend/app/services/laevateinn/types.py`: **Difficulty** (0m), **BloomLevel** (0m), **CognitiveSystem** (0m), **ComprehensionResult** (0m), **Interpretation** (0m), **ComputeProfile** (0m), **DebateRound** (0m), **DebateResult** (0m), **VerificationQuestion** (0m), **DepthResult** (0m), **ValidationResult** (0m), **DeliveryResult** (0m), **LaevateinnTrace** (0m)
- `backend/app/services/laevateinn/validation.py`: **ValidationGauntlet** (9m)
- `backend/app/services/learning_service.py`: **ActionOutcome** (0m), **LearnedPattern** (1m), **LearningService** (11m)
- `backend/app/services/llm_service.py`: **OrchestratedResponse** (0m), **LLMService** (11m)
- `backend/app/services/mcp/server.py`: **MCPTool** (0m), **MCPToolResult** (1m), **DaenaMCPServer** (10m)
- `backend/app/services/mcp_registry.py`: **MCPTool** (0m), **MCPRegistry** (8m)
- `backend/app/services/memory.py`: **MemoryService** (26m) | `_tokenize`, `_content_hash`
- `backend/app/services/memory_import.py`: `get_import_prompt`, `parse_import_response`, `convert_to_memories`
- `backend/app/services/model_management/auto_updater.py`: **ModelInfo** (0m), **UpdateResult** (1m), **OllamaAutoUpdater** (8m) | `_run_ollama`
- `backend/app/services/model_registry.py`: **ModelRegistry** (16m)
- `backend/app/services/model_router.py`: **ModelCandidate** (0m), **RoutingDecision** (0m), **RuntimeRoutingDecision** (0m), **ModelRouter** (18m)
- `backend/app/services/nbmf_archive.py`: `_ensure_tier_dir`, `archive_chat_session`, `archive_audit_entries`, `export_vault_as_zip`
- `backend/app/services/oauth.py`: **OAuthUserInfo** (0m), **OAuthService** (4m)
- `backend/app/services/pipeline_service.py`: **PipelineService** (11m)
- `backend/app/services/project_service.py`: **ProjectService** (7m)
- `backend/app/services/providers/anthropic.py`: **AnthropicProvider** (8m)
- `backend/app/services/providers/base.py`: **LLMMessage** (0m), **ModelInfo** (0m), **LLMResponse** (0m), **LLMChunk** (0m), **GenerateRequest** (0m), **BaseProvider** (10m)
- `backend/app/services/providers/claude_cli.py`: **CliRuntimeSpec** (0m), **CliProvider** (8m) | `_run_cli`
- `backend/app/services/providers/gemini.py`: **GeminiProvider** (8m)
- `backend/app/services/providers/groq.py`: **GroqProvider** (8m)
- `backend/app/services/providers/ollama.py`: **OllamaProvider** (9m) | `_get_default_model`, `_pick_best_model`, `_model_preference_score`, `_estimate_param_size`
- `backend/app/services/providers/openai.py`: **OpenAIProvider** (8m)
- `backend/app/services/providers/openrouter.py`: **OpenRouterProvider** (7m)
- `backend/app/services/providers/perplexity.py`: **PerplexityProvider** (8m)
- `backend/app/services/providers/together.py`: **TogetherProvider** (8m)
- `backend/app/services/query_understanding.py`: **IntentType** (0m), **ComplexityLabel** (0m), **QueryInput** (0m), **QueryUnderstanding** (0m), **QueryUnderstandingService** (16m)
- `backend/app/services/quintessence_engine.py`: **ExpertSynthesis** (0m), **QuintessenceResult** (0m), **QuintessenceEngine** (10m)
- `backend/app/services/remote/gateway.py`: **CommandStatus** (0m), **RemoteCommand** (0m), **CommandResult** (0m), **RemoteGateway** (15m)
- `backend/app/services/runtimes/adapters/claude_code.py`: **ClaudeCodeAdapter** (8m) | `_run_cmd`
- `backend/app/services/runtimes/adapters/claude_session.py`: **ClaudeSessionResult** (0m), **ClaudeSession** (3m), **ClaudeSessionManager** (7m) | `_run_claude`
- `backend/app/services/runtimes/adapters/codex.py`: **CodexAdapter** (8m) | `_run_cmd`
- `backend/app/services/runtimes/adapters/gemini_cli.py`: **GeminiCLIAdapter** (8m) | `_run_cmd`
- `backend/app/services/runtimes/adapters/grok_cli.py`: **GrokCLIAdapter** (8m)
- `backend/app/services/runtimes/adapters/mcp_bridge.py`: **MCPBridgeAdapter** (9m)
- `backend/app/services/runtimes/adapters/ollama_adapter.py`: **OllamaRuntimeAdapter** (9m)
- `backend/app/services/runtimes/base_adapter.py`: **RuntimeStatus** (0m), **RuntimeCapability** (2m), **ExecutionReceipt** (1m), **BaseRuntimeAdapter** (9m)
- `backend/app/services/runtimes/capability_matrix.py`: `task_type_for_intent`, `composite_score`, `rank_runtimes`
- `backend/app/services/runtimes/cost_estimator.py`: **CostEstimate** (0m), **CostEstimator** (5m)
- `backend/app/services/runtimes/registry.py`: **NoRuntimeAvailableError** (0m), **RuntimeRegistry** (19m)
- `backend/app/services/runtimes/session_manager.py`: **RuntimeSession** (2m), **SessionManager** (10m)
- `backend/app/services/runtimes/subscription_auth.py`: **AuthMethod** (0m), **SubscriptionStatus** (0m), **SubscriptionAuth** (3m)
- `backend/app/services/security/install_scanner.py`: **ScanResult** (4m), **InstallScanner** (4m)
- `backend/app/services/security_gate.py`: **ScanResult** (0m), **SecurityGate** (1m)
- `backend/app/services/self_fix.py`: **SelfImprovementResult** (1m) | `_run_sync`, `run_audit`, `run_fix`, `run_improve`
- `backend/app/services/self_improvement/self_audit.py`: **AuditResult** (1m), **SelfAudit** (7m) | `_run_sync`
- `backend/app/services/self_repair.py`: **RepairResult** (0m) | `extract_error_location`, `attempt_self_repair`
- `backend/app/services/session/session_sync.py`: **DeviceRecord** (0m), **PersistentSession** (0m), **SessionSyncService** (11m)
- `backend/app/services/skill_refinery/_nbmf_hook.py`: `record_skill_outcome`
- `backend/app/services/skill_refinery/extraction_service.py`: `build_extraction_prompt`, `parse_extraction_response`, `generate_skill_id`, `build_embedding_text`, `_empty_skill`
- `backend/app/services/skill_refinery/news_monitor.py`: `scan_for_updates`
- `backend/app/services/skill_refinery/refinement_service.py`: `_track_cost`, `get_daily_cost`, `trigger_emergency_stop`, `clear_emergency_stop`, `is_emergency_stopped`
- `backend/app/services/skill_refinery/retrieval_service.py`: `_tokenize`, `_score_skill`, `search_skills`, `format_evidence_block`
- `backend/app/services/skill_refinery/skill_store.py`: **SkillStore** (14m)
- `backend/app/services/skill_scanner.py`: **SkillInfo** (1m) | `_parse_skill_frontmatter`, `scan_skills`, `create_skill`
- `backend/app/services/skill_service.py`: **SkillService** (9m)
- `backend/app/services/skills/claude_code_orchestration.py`: **OrchestratedTask** (0m) | `select_best_runtime`, `decompose_for_parallel_execution`, `get_orchestration_system_prompt`
- `backend/app/services/subscription_service.py`: **SubscriptionTier** (0m), **AuthMethod** (0m), **RuntimeSubscription** (3m), **SubscriptionService** (10m)
- `backend/app/services/swarm/executor.py`: **SwarmExecutor** (9m)
- `backend/app/services/swarm/planner.py`: **SubTask** (1m), **SwarmPlanner** (5m)
- `backend/app/services/system/stay_awake.py`: **AwakeMode** (0m), **StayAwakeConfig** (0m), **AwakeStatus** (0m), **StayAwakeService** (18m)
- `backend/app/services/tool_lifecycle/__init__.py`: `__getattr__`
- `backend/app/services/tool_lifecycle/activation_proxy.py`: **ToolCall** (0m), **ToolCallResult** (0m), **BlockedCall** (0m), **CostSavings** (0m), **ProxyResult** (1m), **ActivationProxy** (4m)
- `backend/app/services/tool_lifecycle/auto_scanner.py`: **ScanConfig** (0m), **ScanResult** (0m), **AutoScanner** (13m)
- `backend/app/services/tool_lifecycle/health_monitor.py`: **HealthState** (0m), **HealthCheck** (0m), **FallbackEvent** (0m), **HealthMonitor** (19m)
- `backend/app/services/tool_lifecycle/nbmf_bridge.py`: **PredictedTool** (0m), **MemoryEntry** (0m), **NBMFBridge** (9m)
- `backend/app/services/tool_lifecycle/orchestra_integration.py`: `get_tlm_registry`, `get_tlm_session_manager`, `get_tlm_proxy`, `get_tlm_tracker`, `get_tlm_bridge`
- `backend/app/services/tool_lifecycle/phase_detector.py`: **PhaseDetection** (0m), **ConversationPhaseDetector** (5m), **AdaptiveToolSelector** (4m)
- `backend/app/services/tool_lifecycle/session_manager.py`: **ToolStatus** (0m), **ToolSession** (0m), **DeactivationReport** (0m), **SessionManager** (12m)
- `backend/app/services/tool_lifecycle/tool_discovery.py`: **ToolCandidate** (0m), **ToolDiscovery** (6m)
- `backend/app/services/tool_lifecycle/tool_registry.py`: **GovernanceRules** (0m), **ToolDefinition** (0m), **LightweightCatalogEntry** (0m), **ToolRegistry** (15m)
- `backend/app/services/tool_lifecycle/usage_tracker.py`: **UsageRecord** (0m), **ToolCooccurrence** (0m), **SessionCostReport** (0m), **UsageTracker** (13m)
- `backend/app/services/tool_use_loop.py`: **ToolUseLoop** (16m)
- `backend/app/services/user_config.py`: `get_daena_md_path`, `ensure_daena_md`, `read_daena_md`, `get_config_value`, `merge_with_settings`
- `backend/app/services/vision_loop.py`: **VisionAction** (0m), **VisionStep** (0m), **VisionLoop** (11m)
- `backend/app/services/voice_service.py`: **VoiceSettings** (1m), **VoiceUsageMetrics** (1m), **VoiceService** (6m)

### Dependency Metrics
- Files: 252
- Import edges: 938

### Hub Files (most imported)
- 140x  `backend/app/core/logging.py`
-  59x  `backend/app/api/v1/runtimes.py`
-  40x  `backend/app/core/config.py`
-  39x  `backend/app/services/providers/base.py`
-  37x  `backend/app/api/v1/skill_refinery.py`
-  33x  `backend/app/core/database.py`
-  31x  `backend/app/core/constants.py`
-  30x  `backend/app/api/deps.py`
-  24x  `backend/app/services/benchmarks/cost_benchmark.py`
-  22x  `backend/app/core/events.py`
-  16x  `backend/app/core/exceptions.py`
-  15x  `backend/app/services/runtimes/base_adapter.py`
-  14x  `backend/app/models/identity.py`
-  14x  `backend/app/models/base.py`
-  13x  `backend/app/services/llm_service.py`
-  12x  `backend/app/services/agent_core/system_access.py`
-  11x  `backend/app/services/_base.py`
-  10x  `backend/app/services/laevateinn/types.py`
-   9x  `backend/app/schemas/_base.py`
-   8x  `backend/app/services/query_understanding.py`

### Orphan Files (not imported by any other module)
- `backend/app/api/v1/agents.py`
- `backend/app/api/v1/autopilot.py`
- `backend/app/api/v1/benchmark.py`
- `backend/app/api/v1/billing.py`
- `backend/app/api/v1/chat.py`
- `backend/app/api/v1/connector_oauth.py`
- `backend/app/api/v1/daenabot.py`
- `backend/app/api/v1/dynamic_models.py`
- `backend/app/api/v1/execution.py`
- `backend/app/api/v1/files.py`
- `backend/app/api/v1/founder.py`
- `backend/app/api/v1/governance.py`
- `backend/app/api/v1/health.py`
- `backend/app/api/v1/heartbeat.py`
- `backend/app/api/v1/integrations.py`
- `backend/app/api/v1/laevateinn.py`
- `backend/app/api/v1/mcp_server.py`
- `backend/app/api/v1/memory.py`
- `backend/app/api/v1/mobile.py`
- `backend/app/api/v1/pipeline.py`

## Frontend (87 TypeScript files)

- **components/auth/**: OAuthButtons.tsx, PasswordStrengthMeter.tsx, ProtectedRoute.tsx
- **components/chat/**: ChatInput.tsx, DaenaAvatar.tsx, InteractivePrompt.tsx, MessageBubble.tsx, MessageList.tsx, NeuralOrb.tsx, RuntimeSwapper.tsx, SessionList.tsx, SlashCommands.tsx, ThinkingProcess.tsx, VoiceControls.tsx, index.ts
- **components/common/**: Badge.tsx, Button.tsx, Card.tsx, CommandPalette.tsx, EmptyState.tsx, ErrorBoundary.tsx, GovernanceSlider.tsx, Input.tsx, Modal.tsx, Shimmer.tsx, Switch.tsx, ToastContainer.tsx, index.ts
- **components/execution/**: ExecutionPanel.tsx
- **components/icons/**: BrandIcons.tsx
- **components/layout/**: Header.tsx, PageLayout.tsx, Sidebar.tsx
- **components/visualizations/**: SunflowerGrid.tsx, SunflowerHive.tsx
- **hooks/**: usePageTitle.ts
- **lib/**: api.ts
- **pages/**: AuthCallbackPage.tsx, ChatPage.tsx, CompleteProfilePage.tsx, ConnectionsPage.tsx, DaenaBotPage.tsx, DashboardPage.tsx, DepartmentChatPage.tsx, DepartmentsPage.tsx, ForgotPasswordPage.tsx, FounderPage.tsx, GovernanceApprovalsPage.tsx, GovernanceAuditPage.tsx, LoginPage.tsx, PipelinePage.tsx, PrivacyPage.tsx, ProjectDetailPage.tsx, ProjectsPage.tsx, RegisterPage.tsx, ResetPasswordPage.tsx, SettingsPage.tsx, SkillsPage.tsx, StubPage.tsx, TasksPage.tsx, TermsPage.tsx
- **pages/settings/**: SettingsAbout.tsx, SettingsAppearance.tsx, SettingsBilling.tsx, SettingsConnections.tsx, SettingsDeveloper.tsx, SettingsGeneral.tsx, SettingsGovernance.tsx, SettingsHeartbeat.tsx, SettingsLLM.tsx, SettingsMemory.tsx, SettingsModelsRuntimes.tsx, SettingsNotifications.tsx, SettingsPrivacy.tsx, SettingsShortcuts.tsx, SettingsVoice.tsx
- **providers/**: VoiceProvider.tsx
- **root/**: App.tsx, main.tsx
- **stores/**: authStore.ts, chatStore.ts, daenabotStore.ts, modelRegistryStore.ts, toastStore.ts, uiStore.ts
- **styles/**: designTokens.ts
- **types/**: api.ts

## Tests (103 test files)

- `backend/tests/conftest.py` (3 tests)
- `backend/tests/test_agent_core.py` (23 tests)
- `backend/tests/test_agents.py` (17 tests)
- `backend/tests/test_archive.py` (13 tests)
- `backend/tests/test_auth.py` (6 tests)
- `backend/tests/test_auth_oauth.py` (8 tests)
- `backend/tests/test_auth_password_reset.py` (10 tests)
- `backend/tests/test_auth_service.py` (9 tests)
- `backend/tests/test_autonomous_features.py` (12 tests)
- `backend/tests/test_autopilot.py` (37 tests)
- `backend/tests/test_benchmarks/test_cost_benchmark.py` (19 tests)
- `backend/tests/test_chat.py` (11 tests)
- `backend/tests/test_claude_session.py` (16 tests)
- `backend/tests/test_config_runtime.py` (5 tests)
- `backend/tests/test_connections.py` (10 tests)
- `backend/tests/test_control_combinations.py` (46 tests)
- `backend/tests/test_council_engine.py` (10 tests)
- `backend/tests/test_daenabot/test_browser_agent.py` (12 tests)
- `backend/tests/test_daenabot/test_dispatch.py` (15 tests)
- `backend/tests/test_daenabot/test_file_agent.py` (15 tests)
- `backend/tests/test_daenabot/test_router.py` (20 tests)
- `backend/tests/test_daenabot/test_terminal_agent.py` (12 tests)
- `backend/tests/test_daenabot_api.py` (12 tests)
- `backend/tests/test_daenabot_planner.py` (28 tests)
- `backend/tests/test_dcp_loader.py` (28 tests)
- `backend/tests/test_demo_mode.py` (21 tests)
- `backend/tests/test_department_router.py` (19 tests)
- `backend/tests/test_drift_detector.py` (28 tests)
- `backend/tests/test_dynamic_model_service.py` (19 tests)
- `backend/tests/test_execution.py` (6 tests)
- `backend/tests/test_execution_layer/test_browser_roundtrip.py` (5 tests)
- `backend/tests/test_execution_layer/test_edge_cases.py` (9 tests)
- `backend/tests/test_execution_layer/test_memory.py` (7 tests)
- `backend/tests/test_execution_layer/test_pipeline.py` (22 tests)
- `backend/tests/test_execution_layer/test_smoke.py` (4 tests)
- `backend/tests/test_founder_policy.py` (9 tests)
- `backend/tests/test_founder_routing.py` (2 tests)
- `backend/tests/test_governance.py` (14 tests)
- `backend/tests/test_governance_v2.py` (31 tests)
- `backend/tests/test_hallucination_benchmark.py` (17 tests)
- `backend/tests/test_health.py` (3 tests)
- `backend/tests/test_heartbeat.py` (34 tests)
- `backend/tests/test_integration_critical_flows.py` (18 tests)
- `backend/tests/test_integrations.py` (61 tests)
- `backend/tests/test_interactive_prompts.py` (30 tests)
- `backend/tests/test_laevateinn.py` (46 tests)
- `backend/tests/test_laevateinn_gaps.py` (34 tests)
- `backend/tests/test_learning_service.py` (16 tests)
- `backend/tests/test_llm_service.py` (11 tests)
- `backend/tests/test_mcp_registry.py` (9 tests)
- `backend/tests/test_mcp_server.py` (18 tests)
- `backend/tests/test_memory.py` (32 tests)
- `backend/tests/test_middleware.py` (16 tests)
- `backend/tests/test_mobile_api/test_mobile_api.py` (13 tests)
- `backend/tests/test_model_registry.py` (34 tests)
- `backend/tests/test_new_endpoints.py` (7 tests)
- `backend/tests/test_orchestration_skill.py` (19 tests)
- `backend/tests/test_orchestrator_pipeline.py` (8 tests)
- `backend/tests/test_project_service.py` (21 tests)
- `backend/tests/test_quintessence_engine.py` (13 tests)
- `backend/tests/test_refinement_circuit_breaker.py` (18 tests)
- `backend/tests/test_remote/test_gateway.py` (18 tests)
- `backend/tests/test_router_phase2.py` (19 tests)
- `backend/tests/test_runtime_adapters.py` (54 tests)
- `backend/tests/test_self_repair.py` (8 tests)
- `backend/tests/test_session_sync/test_session_sync.py` (15 tests)
- `backend/tests/test_skill_refinery.py` (21 tests)
- `backend/tests/test_skill_refinery_phase2.py` (16 tests)
- `backend/tests/test_skill_refinery_phase3.py` (15 tests)
- `backend/tests/test_skills.py` (7 tests)
- `backend/tests/test_stop_slop.py` (27 tests)
- `backend/tests/test_subscription_auth.py` (18 tests)
- `backend/tests/test_subscription_service.py` (28 tests)
- `backend/tests/test_swarm.py` (21 tests)
- `backend/tests/test_system/test_stay_awake.py` (13 tests)
- `backend/tests/test_tool_lifecycle/test_activation_proxy.py` (21 tests)
- `backend/tests/test_tool_lifecycle/test_health_monitor.py` (22 tests)
- `backend/tests/test_tool_lifecycle/test_integration.py` (12 tests)
- `backend/tests/test_tool_lifecycle/test_nbmf_bridge.py` (17 tests)
- `backend/tests/test_tool_lifecycle/test_orchestra_integration.py` (20 tests)
- `backend/tests/test_tool_lifecycle/test_phase_detector.py` (24 tests)
- `backend/tests/test_tool_lifecycle/test_session_manager.py` (32 tests)
- `backend/tests/test_tool_lifecycle/test_tool_discovery.py` (31 tests)
- `backend/tests/test_tool_lifecycle/test_tool_registry.py` (33 tests)
- `backend/tests/test_tool_lifecycle/test_usage_tracker.py` (19 tests)
- `backend/tests/test_tool_use_loop.py` (52 tests)
- `backend/tests/test_vault.py` (12 tests)
- `backend/tests/test_vision_and_prompts.py` (17 tests)
- `backend/tests/test_vision_browser_agent.py` (15 tests)
- `backend/tests/test_voice_service.py` (15 tests)
- `backend/tests/test_waitlist.py` (11 tests)
- `backend/tests/test_web_crawler_agent.py` (14 tests)
- `backend/tests/test_websocket.py` (16 tests)
- `backend/tests/test_work_queue.py` (17 tests)