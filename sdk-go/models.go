package daena

// HealthResponse represents the health status response
type HealthResponse struct {
	Status   string `json:"status"`
	Version  string `json:"version,omitempty"`
	Uptime   int64  `json:"uptime,omitempty"`
	Database string `json:"database,omitempty"`
}

// SystemSummary represents the system summary response
type SystemSummary struct {
	TotalAgents     int    `json:"total_agents"`
	ActiveAgents    int    `json:"active_agents"`
	Departments     int    `json:"departments"`
	TotalProjects   int    `json:"total_projects"`
	ActiveProjects  int    `json:"active_projects"`
	MemoryRecords   int64  `json:"memory_records"`
	Status          string `json:"status"`
}

// ChatRequest represents a chat request
type ChatRequest struct {
	Message string `json:"message"`
}

// ChatResponse represents a chat response
type ChatResponse struct {
	Response string `json:"response"`
	AgentID  string `json:"agent_id,omitempty"`
}

// Agent represents an AI agent
type Agent struct {
	AgentID    string   `json:"agent_id"`
	Name       string   `json:"name"`
	Department string   `json:"department"`
	Role       string   `json:"role"`
	Status     string   `json:"status"`
	Capabilities []string `json:"capabilities,omitempty"`
}

// MemoryRecord represents a memory record in NBMF
type MemoryRecord struct {
	RecordID        string                 `json:"record_id"`
	Key             string                 `json:"key"`
	Payload         map[string]interface{} `json:"payload"`
	ClassName       string                 `json:"class_name"`
	CompressionRatio float64               `json:"compression_ratio,omitempty"`
	SizeBytes       int64                  `json:"size_bytes,omitempty"`
	CreatedAt       string                 `json:"created_at"`
}

// StoreMemoryRequest represents a request to store memory
type StoreMemoryRequest struct {
	Key       string                 `json:"key"`
	Payload   map[string]interface{} `json:"payload"`
	ClassName string                 `json:"class_name"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// CouncilDebateRequest represents a request for council debate
type CouncilDebateRequest struct {
	Department string                 `json:"department"`
	Topic      string                 `json:"topic"`
	Context    map[string]interface{} `json:"context,omitempty"`
}

// CouncilDecision represents a council decision
type CouncilDecision struct {
	DecisionID   string                 `json:"decision_id"`
	Decision     string                 `json:"decision"`
	Department   string                 `json:"department"`
	Topic        string                 `json:"topic"`
	Confidence   float64                `json:"confidence"`
	ImpactLevel  string                 `json:"impact_level,omitempty"`
	RequiresApproval bool               `json:"requires_approval,omitempty"`
}

// APIError represents an API error response
type APIError struct {
	Message    string `json:"message"`
	StatusCode int    `json:"status_code"`
	ErrorType  string `json:"error_type,omitempty"`
}

