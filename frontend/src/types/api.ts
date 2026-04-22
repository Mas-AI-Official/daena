/** Daena API type definitions — mirrors backend schemas exactly */

// ── Enums ──

export type UserRole = 'AUDITOR' | 'VIEWER' | 'OPERATOR' | 'MANAGER' | 'ADMIN' | 'FOUNDER'
export type ChatMode = 'CMD' | 'EXE'
export type RoutingMode = 'STANDARD' | 'COUNCIL' | 'QUINTESSENCE'
export type ModelProvider = 'OLLAMA' | 'PERPLEXITY' | 'ANTHROPIC' | 'OPENAI' | 'GEMINI' | 'OPENROUTER' | 'TOGETHER' | 'GROQ'
export type HealthStatus = 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE'
export type GovernanceMode = 'UNLEASHED' | 'BALANCED' | 'GOVERNED'
export type RiskLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type GovernanceTier = 0 | 1 | 2 | 3 | 4
export type SubCapability = 'MIND' | 'EYES' | 'HANDS' | 'VOICE' | 'SHIELD' | 'MEMORY'
export type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'BLOCKED'
export type TaskStatus = 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'AUTO_APPROVED' | 'EXPIRED'
export type ConnectorAuthType = 'OAUTH2' | 'API_KEY' | 'NONE'
export type ConnectionStatus = 'CONNECTED' | 'DISCONNECTED' | 'ERROR' | 'NEEDS_REAUTH'
export type PermissionLevel = 'ALWAYS_ALLOW' | 'ASK_EACH_TIME' | 'BLOCK'
export type MemoryTier = 0 | 1 | 2 | 3 | 4
export type ContentType = 'FACT' | 'PREFERENCE' | 'LEARNING' | 'POLICY' | 'DIRECTIVE'

// ── Common ──

export interface Pagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  pagination?: Pagination
}

export interface ApiError {
  success: false
  error: {
    code: string
    message: string
  }
}

// ── Auth ──

export interface UserResponse {
  user_id: string
  email: string
  display_name: string
  role: UserRole
  tenant_id: string
  created_at: string
  // Optional fields populated by /auth/me + /settings/profile endpoints.
  // Kept optional so the type stays compatible with anywhere a minimal
  // user response is returned (register, list endpoints that only need
  // identity).
  tenant_name?: string
  email_verified?: boolean
  oauth_provider?: string | null
  id?: string  // alias for user_id returned by some endpoints
}

export interface TokenData {
  access_token: string
  token_type: string
  expires_in: number
  user: UserResponse
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  confirm_password: string
  display_name: string
  tenant_name: string
}

// ── Chat ──

export interface SessionResponse {
  id: string
  user_id: string
  tenant_id: string
  title: string
  mode: ChatMode
  routing_mode: RoutingMode

  autopilot: boolean
  think_mode: boolean
  category_id: string | null
  department_id: string | null
  department_name: string | null
  is_archived: boolean
  created_at: string
  updated_at: string
  message_count: number
}

export interface MessageResponse {
  id: string
  session_id: string
  role: 'USER' | 'ASSISTANT' | 'SYSTEM' | 'TOOL'
  content: string
  model_used: string | null
  provider_used: string | null
  governance_tier: GovernanceTier | null
  cost_usd: number | null
  latency_ms: number | null
  token_count_input: number | null
  token_count_output: number | null
  created_at: string
}

export interface CreateSessionRequest {
  title?: string
  mode: ChatMode
  routing_mode?: RoutingMode

  category_id?: string
  department_id?: string
  autopilot?: boolean
  think_mode?: boolean
}

export interface UpdateSessionRequest {
  title?: string
  mode?: ChatMode
  routing_mode?: RoutingMode

  is_archived?: boolean
  autopilot?: boolean
  think_mode?: boolean
}

export interface SendMessageRequest {
  content: string
  role?: 'USER'
  preferred_model?: string | null

}

export interface ModelRegistryProviderResponse {
  provider: ModelProvider
  display_name: string
  kind: 'local' | 'cloud'
  configured: boolean
  registered: boolean
  reachable: boolean
  selectable: boolean
  health: HealthStatus
  model_count: number
  reason: string
}

export interface ModelRegistryModelResponse {
  model_id: string
  display_name: string
  provider: ModelProvider
  provider_display_name: string
  kind: 'local' | 'cloud'
  installed: boolean
  configured: boolean
  reachable: boolean
  selectable: boolean
  availability_reason: string
  context_window: number
  supports_streaming: boolean
  supports_vision: boolean
  supports_tools: boolean
  cost_per_1m_input: number
  cost_per_1m_output: number
  tags: string[]
  is_default: boolean
  source: 'ollama_api' | 'provider_catalog'
}

export interface RoutingModeTruthResponse {
  truthful: boolean
  reason: string
}

export interface ModelRegistryResponse {
  providers: ModelRegistryProviderResponse[]
  models: ModelRegistryModelResponse[]
  default_model: string
  ollama_base_url: string
  summary: {
    configured_provider_count: number
    registered_provider_count: number
    healthy_provider_count: number
    selectable_model_count: number
    installed_model_count: number
  }
  routing_modes: {
    STANDARD: RoutingModeTruthResponse
    COUNCIL: RoutingModeTruthResponse
    QUINTESSENCE: RoutingModeTruthResponse
  }
}

// ── Agents ──

export interface DepartmentResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  sunflower_index: number
  cell_id: string | null
  config: Record<string, unknown> | null
  is_active: boolean
  agent_count: number
  created_at: string
  updated_at: string
}

export interface AgentResponse {
  id: string
  tenant_id: string
  department_id: string
  name: string
  sub_capability: SubCapability
  description: string | null
  model_preference: string | null
  config: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

// ── Governance ──

export interface GovernanceDecisionResponse {
  allowed: boolean
  governance_tier: GovernanceTier
  risk_level: RiskLevel
  action_type: string
  requires_approval: boolean
  request_id: string | null
  hard_law_violations: string[]
  message: string
}

export interface ApprovalResponse {
  id: string
  tenant_id: string
  user_id: string
  action_type: string
  action_params: Record<string, unknown> | null
  risk_level: RiskLevel
  governance_tier: GovernanceTier
  status: ApprovalStatus
  decided_by: string | null
  decided_at: string | null
  decision_reason: string | null
  expires_at: string | null
  session_id: string | null
  context: { project_name?: string; [key: string]: unknown } | null
  created_at: string
  updated_at: string
}

export interface AuditEntryResponse {
  id: string
  tenant_id: string
  actor_id: string
  actor_type: string
  action_type: string
  action_params: Record<string, unknown> | null
  result: 'ALLOWED' | 'BLOCKED' | 'APPROVAL_REQUIRED'
  risk_level: RiskLevel
  governance_tier: GovernanceTier
  prev_hash: string | null
  entry_hash: string
  session_id: string | null
  created_at: string
}

export interface FounderRoutingTrace {
  id: string
  created_at: string
  result: string
  risk_level: RiskLevel
  governance_tier: GovernanceTier
  session_id: string | null
  intent: string | null
  model: string | null
  provider: string | null
  requested_mode: RoutingMode
  applied_mode: RoutingMode
  routing_source: string | null
  selection_reason: string | null
  mode_reason: string | null
  provider_strategy: string | null
  providers_considered: string[]
  latency_ms: number | null
  user_message: string | null
  top_candidates: Array<Record<string, unknown>>
}

export interface FounderRoutingTelemetry {
  runtime: Record<string, unknown>
  registry: ModelRegistryResponse
  recent_routes: FounderRoutingTrace[]
  trace_summary: {
    total_routes: number
    fallback_count: number
    fallback_rate: number
    downgraded_mode_count: number
    by_requested_mode: Record<string, number>
    by_applied_mode: Record<string, number>
    by_provider: Record<string, number>
    by_source: Record<string, number>
    by_intent: Record<string, number>
  }
  audit_pagination: Pagination
}

export interface FounderRoutingPreview {
  preview_source: string
  query_understanding: {
    intent: string
    confidence: number
    complexity_score: number
    complexity_label: string
    risk_level: RiskLevel
    governance_tier: GovernanceTier
    suggested_mode: RoutingMode
    suggested_providers: ModelProvider[]
    ambiguity_signals: string[]
    clarifying_question: string | null
    processing_time_ms: number
  }
  routing: {
    requested_mode: RoutingMode
    applied_mode: RoutingMode
    primary: Record<string, unknown>
    fallback_chain: Array<Record<string, unknown>>
    council_models: Array<Record<string, unknown>>
    selection_reason: string | null
    mode_reason: string | null
    provider_strategy: string | null
    providers_considered: string[]
    top_candidates: Array<Record<string, unknown>>
    routing_time_ms: number
  }
}

// ── Founder Routing Policy ──

export interface FounderRoutingPolicy {
  id?: string
  preferred_models: Record<string, string>
  provider_priority: string[]
  cost_ceiling: number | null
  blocked_models: string[]
  blocked_providers: string[]
  default_model: string | null
  enforce_local_only: boolean
  updated_by?: string | null
  updated_at?: string | null
}

// ── Execution ──

export interface ToolExecutionResponse {
  id: string
  task_id: string | null
  session_id: string | null
  tool_name: string
  tool_params: Record<string, unknown>
  tool_result: unknown
  status: ExecutionStatus
  governance_tier: GovernanceTier
  latency_ms: number | null
  error: string | null
  created_at: string
}

export interface TaskResponse {
  id: string
  user_id: string
  tenant_id: string
  session_id: string | null
  name: string
  description: string | null
  status: TaskStatus
  progress: number
  result: unknown
  error: string | null
  checkpoint_data: Record<string, unknown> | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

// ── Skills ──

export interface SkillResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  category: string | null
  schema_def: Record<string, unknown>
  implementation: string | null
  governance_tier: GovernanceTier
  is_active: boolean
  version: string
  usage_count: number
  created_at: string
  updated_at: string
}

// ── Connections ──

export interface ConnectorResponse {
  id: string
  name: string
  description: string | null
  auth_type: ConnectorAuthType
  config_schema: Record<string, unknown>
  tools: string[]
  icon_url: string | null
  category: string | null
  created_at: string
}

export interface ConnectorInstanceResponse {
  id: string
  connector_id: string
  user_id: string
  tenant_id: string
  status: ConnectionStatus
  last_used: string | null
  connector_name: string | null
  created_at: string
  updated_at: string
}

export interface ConnectorPermissionResponse {
  id: string
  instance_id: string
  tool_name: string
  permission_level: PermissionLevel
}

// ── Memory ──

export interface MemoryResponse {
  id: string
  tenant_id: string
  user_id: string | null
  tier: MemoryTier
  content_type: ContentType
  content: string
  summary: string | null
  tags: string[]
  source: string | null
  confidence: number
  access_count: number
  last_accessed: string | null
  expires_at: string | null
  verification_status: 'UNVERIFIED' | 'VERIFIED' | 'REJECTED'
  verified_by: string | null
  metadata: Record<string, unknown> | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

// ── DaenaBot Activity ──

export interface DaenaBotActivityEvent {
  type: 'daenabot_activity'
  agent: string        // e.g. "FileAgent", "TerminalAgent", "BrowserAgent"
  operation: string    // e.g. "list_directory", "execute_command"
  status: 'executing' | 'completed' | 'failed'
  description: string  // Human-readable: "List files in /home/user/project"
}

// ── V2 Runtime Status ──

export type RuntimeStatus = 'online' | 'offline' | 'rate_limited' | 'error' | 'not_installed'
export type SubTaskStatus = 'pending' | 'running' | 'complete' | 'failed' | 'rejected' | 'cancelled'

export interface RuntimeInfo {
  id: string
  name: string
  status: RuntimeStatus
  capabilities: Record<string, number>
  cost_per_1k_tokens: number
  is_free: boolean
}

// ── V2 Execution View (Phase 5) ──

export interface SubTaskResponse {
  id: string
  description: string
  task_type: string
  assigned_runtime: string
  fallback_runtime: string | null
  depends_on: string[]
  estimated_tokens: number
  estimated_cost_usd: number
  status: SubTaskStatus
  result_data: unknown
  duration_ms: number | null
  actual_cost_usd: number | null
}

export interface ExecutionPlanResponse {
  session_id: string
  task_description: string
  subtasks: SubTaskResponse[]
  total_estimated_cost: number
  total_actual_cost: number
  runtimes_used: string[]
  start_time: string | null
  end_time: string | null
  status: 'planning' | 'executing' | 'complete' | 'failed' | 'cancelled'
}

// ── V2 Projects (Phase 6) ──

export interface ProjectResponse {
  id: string
  name: string
  description: string
  owner_id: string
  created_at: string
  updated_at: string
  working_directory: string | null
  connected_runtimes: string[]
  memory_scope: string
  task_count: number
  file_count: number
  department_count: number
  settings: Record<string, unknown>
}

export interface ProjectListResponse {
  projects: ProjectResponse[]
  count: number
}

// ── V2 Approval Dashboard ──

export interface ApprovalItemResponse {
  id: string
  timestamp: string
  session_id: string
  action_description: string
  action_type: string
  rejection_source: string
  rejection_reason: string
  rejection_confidence: number
  governance_tier: number
  user_decision: string | null
  decided_by: string | null
  user_decision_time: string | null
  override_logged: boolean
  is_pending: boolean
}

export interface ApprovalSummaryResponse {
  pending: number
  approved: number
  rejected: number
  escalated: number
  total: number
}

// ── WebSocket ──

export interface WsMessage {
  type: 'message' | 'chunk' | 'done' | 'ack' | 'error' | 'ping' | 'pong'
  content?: string
  message_id?: string
  session_id?: string
  message?: string
}

// ── Department Minds (Souls) ──
// Mirrors backend/app/api/v1/souls.py response_models.

export interface SoulSummary {
  slug: string
  name?: string | null
  department?: string | null
  runtime_preference?: string | null
  voice?: string | null
  accent_color?: string | null
  temperature?: number | null
}

export interface SoulDetail extends SoulSummary {
  body: string
  fallback_runtimes: string[]
  tools_enabled: string[]
  version?: string | null
}

export interface SoulRefineVerdict {
  slug: string
  verdict: string
  confidence: number
  error?: string | null
  gap_count?: number
  evidence_sources?: number
  improvement_notes?: string[]
}

export interface SoulProposal {
  proposal_id: string
  department_slug: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_at?: string | null
  decided_by?: string | null
  notes?: string | null
  verdict?: string
  confidence?: number
  current_body?: string
  proposed_body?: string
  improvement_notes?: string[]
  gap_report?: Record<string, unknown>
  evidence_sources?: string[]
}

// ── Company Mode (GTM activation) ──
// Mirrors backend/app/api/v1/company_mode.py ActivateRequest + ActivationResult.

export type MissionChannel = 'linkedin' | 'email' | 'twitter_dm' | 'sms' | 'web_form' | 'phone'

export interface ActivateRequest {
  company_name: string
  company_one_liner: string
  target_customer: string
  customer_pain: string
  our_promise: string
  proof_points: string[]
  channels: MissionChannel[]
  prospect_limit_per_mission: number
  tone: string
  auto_send: boolean
  require_founder_approval: boolean
  notes?: string | null
}

export type MissionStatus = 'drafting' | 'awaiting_approval' | 'sending' | 'sent' | 'failed'

export interface ActivationMission {
  id: string
  department: string
  mind: string
  channel: MissionChannel
  objective: string
  status: MissionStatus | string
  prospects_found: number
  drafts_generated: number
  drafts_awaiting_approval: number
  errors: string[]
}

export interface ActivationBriefEcho {
  company_name: string
  target_customer: string
  channels: MissionChannel[]
  auto_send: boolean
}

export interface ActivationResult {
  activation_id: string
  created_at: string
  brief: ActivationBriefEcho
  missions: ActivationMission[]
  summary: string
  prospects_count: number
  drafts_preview: Record<string, unknown>[]
  next_steps: string[]
  governance_warning?: string | null
}

export interface ActivationHistoryEntry {
  activation_id: string
  created_at: string
  company_name: string
  prospects: number
  drafts: number
  summary: string
}
