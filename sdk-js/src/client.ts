/**
 * Daena AI VP JavaScript/TypeScript SDK Client
 * 
 * Production-ready SDK for Daena AI VP System.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import {
  DaenaAPIError,
  DaenaAuthenticationError,
  DaenaRateLimitError,
  DaenaNotFoundError,
  DaenaValidationError,
  DaenaTimeoutError
} from './exceptions';
import {
  Agent,
  Department,
  MemoryRecord,
  CouncilDecision,
  ExperienceVector,
  SystemMetrics
} from './models';

export interface DaenaClientConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  retryBackoff?: number;
}

/**
 * Official JavaScript/TypeScript SDK client for Daena AI VP System.
 * 
 * @example
 * ```typescript
 * import { DaenaClient } from '@daena/sdk';
 * 
 * const client = new DaenaClient({
 *   apiKey: 'your-api-key',
 *   baseUrl: 'https://api.daena.ai'
 * });
 * 
 * // Get system health
 * const health = await client.getHealth();
 * 
 * // Get all agents
 * const agents = await client.getAgents();
 * 
 * // Send a message to Daena
 * const response = await client.chat('What\'s the status of our marketing campaigns?');
 * ```
 */
export class DaenaClient {
  private axiosInstance: AxiosInstance;
  private config: Required<DaenaClientConfig>;

  constructor(config: DaenaClientConfig) {
    this.config = {
      baseUrl: config.baseUrl || 'http://localhost:8000',
      timeout: config.timeout || 30000,
      maxRetries: config.maxRetries || 3,
      retryBackoff: config.retryBackoff || 1.0,
      ...config
    };

    this.axiosInstance = axios.create({
      baseURL: this.config.baseUrl.replace(/\/$/, ''),
      timeout: this.config.timeout,
      headers: {
        'X-API-Key': this.config.apiKey,
        'Content-Type': 'application/json',
        'User-Agent': `Daena-JS-SDK/1.0.0`
      }
    });

    // Add retry interceptor
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        return this.handleError(error);
      }
    );
  }

  private async handleError(error: AxiosError): Promise<never> {
    if (error.response) {
      const { status, data, headers } = error.response;

      switch (status) {
        case 401:
          throw new DaenaAuthenticationError(
            'Authentication failed. Please check your API key.',
            status,
            data
          );
        case 404:
          throw new DaenaNotFoundError(
            `Resource not found: ${error.config?.url}`,
            status,
            data
          );
        case 429:
          const retryAfter = parseInt(headers['retry-after'] || '60', 10);
          throw new DaenaRateLimitError(
            'Rate limit exceeded. Please try again later.',
            retryAfter,
            status,
            data
          );
        case 422:
          throw new DaenaValidationError(
            'Request validation failed.',
            status,
            data
          );
        default:
          throw new DaenaAPIError(
            (data as any)?.detail || `API request failed: ${status}`,
            status,
            data
          );
      }
    } else if (error.code === 'ECONNABORTED') {
      throw new DaenaTimeoutError(
        `Request timed out after ${this.config.timeout}ms`,
        undefined
      );
    } else {
      throw new DaenaAPIError(
        `Request failed: ${error.message}`,
        undefined
      );
    }
  }

  private async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    endpoint: string,
    config?: AxiosRequestConfig
  ): Promise<T> {
    try {
      const response = await this.axiosInstance.request<T>({
        method,
        url: endpoint,
        ...config
      });
      return response.data;
    } catch (error) {
      // Error already handled by interceptor
      throw error;
    }
  }

  // ===================================================================
  // System Operations
  // ===================================================================

  /**
   * Get system health status.
   */
  async getHealth(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/api/v1/system/health');
  }

  /**
   * Get comprehensive system summary.
   */
  async getSystemSummary(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/api/v1/system/summary');
  }

  /**
   * Get system metrics.
   */
  async getSystemMetrics(): Promise<SystemMetrics> {
    const data = await this.request<SystemMetrics>('GET', '/api/v1/monitoring/metrics');
    return data;
  }

  /**
   * Test connection to Daena API.
   */
  async testConnection(): Promise<boolean> {
    try {
      await this.getHealth();
      return true;
    } catch {
      return false;
    }
  }

  // ===================================================================
  // Agent Management
  // ===================================================================

  /**
   * Get list of agents.
   */
  async getAgents(params?: {
    department_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<Agent[]> {
    const data = await this.request<{ agents: Agent[] }>('GET', '/api/v1/agents', {
      params
    });
    return data.agents || [];
  }

  /**
   * Get agent by ID.
   */
  async getAgent(agentId: string): Promise<Agent> {
    return this.request<Agent>('GET', `/api/v1/agents/${agentId}`);
  }

  /**
   * Get agent metrics.
   */
  async getAgentMetrics(agentId?: string): Promise<Record<string, any>> {
    const params = agentId ? { agent_id: agentId } : undefined;
    return this.request<Record<string, any>>('GET', '/api/v1/monitoring/agent-metrics', {
      params
    });
  }

  // ===================================================================
  // Daena Chat
  // ===================================================================

  /**
   * Send a message to Daena chat.
   */
  async chat(
    message: string,
    options?: {
      session_id?: string;
      context?: Record<string, any>;
    }
  ): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('POST', '/api/v1/daena/chat', {
      data: {
        message,
        ...options
      }
    });
  }

  /**
   * Get chat session status.
   */
  async getChatStatus(sessionId: string): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', `/api/v1/daena/chat/${sessionId}/status`);
  }

  // ===================================================================
  // Memory & NBMF
  // ===================================================================

  /**
   * Store a memory record using NBMF.
   */
  async storeMemory(params: {
    key: string;
    payload: any;
    class_name?: string;
    metadata?: Record<string, any>;
    tenant_id?: string;
  }): Promise<MemoryRecord> {
    return this.request<MemoryRecord>('POST', '/api/v1/memory/store', {
      data: {
        class_name: 'default',
        ...params
      }
    });
  }

  /**
   * Retrieve a memory record.
   */
  async retrieveMemory(key: string, tenantId?: string): Promise<MemoryRecord | null> {
    try {
      const params = tenantId ? { tenant_id: tenantId } : undefined;
      return await this.request<MemoryRecord>('GET', `/api/v1/memory/retrieve/${key}`, {
        params
      });
    } catch (error) {
      if (error instanceof DaenaNotFoundError) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Search memory records.
   */
  async searchMemory(
    query: string,
    options?: {
      limit?: number;
      tenant_id?: string;
    }
  ): Promise<MemoryRecord[]> {
    const data = await this.request<{ results: MemoryRecord[] }>('GET', '/api/v1/memory/search', {
      params: {
        query,
        limit: options?.limit || 10,
        tenant_id: options?.tenant_id
      }
    });
    return data.results || [];
  }

  /**
   * Get memory system metrics.
   */
  async getMemoryMetrics(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/api/v1/memory/metrics');
  }

  // ===================================================================
  // Council System
  // ===================================================================

  /**
   * Run a council debate on a topic.
   */
  async runCouncilDebate(params: {
    department: string;
    topic: string;
    context?: Record<string, any>;
    tenant_id?: string;
  }): Promise<CouncilDecision> {
    return this.request<CouncilDecision>('POST', '/api/v1/council/debate', {
      data: params
    });
  }

  /**
   * Get recent council conclusions.
   */
  async getCouncilConclusions(params?: {
    department?: string;
    limit?: number;
  }): Promise<CouncilDecision[]> {
    const data = await this.request<{ decisions: CouncilDecision[] }>('GET', '/api/v1/council/conclusions', {
      params
    });
    return data.decisions || [];
  }

  /**
   * Get pending approval requests.
   */
  async getPendingApprovals(params?: {
    department?: string;
    impact?: string;
    limit?: number;
  }): Promise<Record<string, any>[]> {
    const data = await this.request<{ approvals: Record<string, any>[] }>('GET', '/api/v1/council/approvals/pending', {
      params
    });
    return data.approvals || [];
  }

  /**
   * Approve a council decision.
   */
  async approveDecision(decisionId: string, approverId: string): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('POST', `/api/v1/council/approvals/${decisionId}/approve`, {
      data: { approver_id: approverId }
    });
  }

  // ===================================================================
  // Knowledge Distillation
  // ===================================================================

  /**
   * Distill experience vectors from data items.
   */
  async distillExperience(params: {
    data_items: Record<string, any>[];
    tenant_id?: string;
  }): Promise<ExperienceVector[]> {
    const data = await this.request<{ vectors: ExperienceVector[] }>('POST', '/api/v1/knowledge/distill', {
      data: params
    });
    return data.vectors || [];
  }

  /**
   * Search for similar knowledge patterns.
   */
  async searchSimilarPatterns(params: {
    query_features: Record<string, number>;
    pattern_type?: string;
    top_k?: number;
    similarity_threshold?: number;
  }): Promise<Record<string, any>[]> {
    const data = await this.request<{ patterns: Record<string, any>[] }>('POST', '/api/v1/knowledge/search', {
      data: {
        top_k: 5,
        similarity_threshold: 0.7,
        ...params
      }
    });
    return data.patterns || [];
  }

  /**
   * Get pattern recommendations based on context.
   */
  async getPatternRecommendations(params: {
    context: Record<string, any>;
    pattern_type?: string;
    top_k?: number;
  }): Promise<Record<string, any>[]> {
    const data = await this.request<{ recommendations: Record<string, any>[] }>('POST', '/api/v1/knowledge/recommend', {
      data: {
        top_k: 3,
        ...params
      }
    });
    return data.recommendations || [];
  }

  // ===================================================================
  // Analytics
  // ===================================================================

  /**
   * Get analytics summary.
   */
  async getAnalyticsSummary(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/api/v1/analytics/summary');
  }

  /**
   * Get advanced analytics insights.
   */
  async getAdvancedInsights(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/api/v1/analytics/insights');
  }
}

