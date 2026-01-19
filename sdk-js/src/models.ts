/**
 * Data models for Daena SDK.
 */

export interface Agent {
  agent_id: string;
  name: string;
  department: string;
  role: string;
  status: string;
  capabilities: string[];
  performance_metrics: Record<string, any>;
  is_active: boolean;
}

export interface Department {
  department_id: string;
  name: string;
  description: string;
  agent_count: number;
  active_agents: number;
  status: string;
}

export interface MemoryRecord {
  record_id: string;
  key: string;
  class_name: string;
  payload: any;
  metadata: Record<string, any>;
  compression_ratio: number;
  size_bytes: number;
  created_at: string;
  tenant_id?: string;
}

export interface CouncilDecision {
  decision_id: string;
  department: string;
  topic: string;
  decision: string;
  confidence: number;
  agents_involved: string[];
  created_at: string;
  status: string;
  impact_level?: string;
}

export interface ExperienceVector {
  vector_id: string;
  pattern_type: string;
  features: Record<string, number>;
  confidence: number;
  source_count: number;
  metadata: Record<string, any>;
  created_at: string;
}

export interface SystemMetrics {
  total_agents: number;
  active_agents: number;
  departments: number;
  memory_usage: Record<string, any>;
  api_calls_per_minute: number;
  average_latency_ms: number;
  error_rate: number;
  timestamp: string;
}

