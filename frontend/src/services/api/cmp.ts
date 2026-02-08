/**
 * CMP Integrations API Service
 * Enhanced API for the Integration Hub with governance support.
 */

import api from './client';

// Types
export interface IntegrationCatalogItem {
    id: string;
    key: string;
    name: string;
    category: string;
    icon_url?: string;
    icon_svg?: string;
    color?: string;
    auth_type: 'oauth2' | 'api_key' | 'webhook';
    default_risk_level: 'low' | 'medium' | 'high';
    requires_approval: boolean;
    description: string;
    oauth_scopes?: string[];
    api_key_fields?: string[];
}

export interface IntegrationInstance {
    id: string;
    catalog_key: string;
    name: string;
    icon_url?: string;
    icon_svg?: string;
    color?: string;
    category: string;
    status: 'connected' | 'disconnected' | 'paused' | 'error';
    status_message?: string;
    connected_at?: string;
    last_used_at?: string;
    metadata?: Record<string, any>;
    policy?: {
        allow_founder: boolean;
        allow_daena: boolean;
        allow_agents: boolean;
        approval_mode: string;
    };
}

export interface IntegrationPolicy {
    instance_id: string;
    allow_founder: boolean;
    allow_daena: boolean;
    allow_agents: boolean;
    allowed_departments: string[];
    approval_mode: 'auto' | 'needs_approval' | 'always';
    max_daily_calls: number;
    max_daily_cost_usd: number;
    restricted_actions: string[];
}

export interface AuditLogEntry {
    id: string;
    timestamp: string;
    actor_type: string;
    actor_name: string;
    action: string;
    catalog_key: string;
    risk_level: string;
    approval_required: boolean;
    approval_status?: string;
    execution_time_ms?: number;
    error_message?: string;
}

// API Methods
export const cmpApi = {
    // ============================================================
    // Catalog
    // ============================================================

    getCatalog: async (params?: {
        category?: string;
        search?: string;
        featured_only?: boolean
    }): Promise<{ integrations: IntegrationCatalogItem[]; categories: string[] }> => {
        const response = await api.get('/integrations/catalog', { params });
        return response.data;
    },

    // ============================================================
    // Instances
    // ============================================================

    getInstances: async (params?: {
        status?: string
    }): Promise<{ instances: IntegrationInstance[] }> => {
        const response = await api.get('/integrations/instances', { params });
        return response.data;
    },

    connectIntegration: async (
        catalogKey: string,
        authType: string,
        credentials: Record<string, any>,
        metadata?: Record<string, any>
    ): Promise<{ id: string; status: string; message: string }> => {
        const response = await api.post(`/integrations/instances/${catalogKey}/connect`, {
            auth_type: authType,
            credentials,
            metadata: metadata || {}
        });
        return response.data;
    },

    disconnectIntegration: async (instanceId: string): Promise<{ status: string }> => {
        const response = await api.post(`/integrations/instances/${instanceId}/disconnect`);
        return response.data;
    },

    pauseIntegration: async (instanceId: string): Promise<{ status: string }> => {
        const response = await api.post(`/integrations/instances/${instanceId}/pause`);
        return response.data;
    },

    resumeIntegration: async (instanceId: string): Promise<{ status: string }> => {
        const response = await api.post(`/integrations/instances/${instanceId}/resume`);
        return response.data;
    },

    testIntegration: async (instanceId: string): Promise<{ connected: boolean; tested_at: string }> => {
        const response = await api.post(`/integrations/instances/${instanceId}/test`);
        return response.data;
    },

    // ============================================================
    // OAuth
    // ============================================================

    getOAuthUrl: async (
        catalogKey: string,
        redirectUri: string
    ): Promise<{ auth_url: string; state: string }> => {
        const response = await api.post(`/integrations/oauth/${catalogKey}/auth-url`, {
            redirect_uri: redirectUri
        });
        return response.data;
    },

    handleOAuthCallback: async (
        code: string,
        state: string,
        catalogKey: string
    ): Promise<{ status: string }> => {
        const response = await api.post('/integrations/oauth/callback', {
            code,
            state,
            catalog_key: catalogKey
        });
        return response.data;
    },

    // ============================================================
    // Policy
    // ============================================================

    getPolicy: async (instanceId: string): Promise<IntegrationPolicy> => {
        const response = await api.get(`/integrations/instances/${instanceId}/policy`);
        return response.data;
    },

    updatePolicy: async (
        instanceId: string,
        policy: Partial<IntegrationPolicy>
    ): Promise<{ message: string }> => {
        const response = await api.put(`/integrations/instances/${instanceId}/policy`, policy);
        return response.data;
    },

    // ============================================================
    // Execution
    // ============================================================

    executeAction: async (
        instanceId: string,
        action: string,
        params: Record<string, any>,
        actorContext?: Record<string, any>
    ): Promise<{
        status: 'success' | 'pending_approval';
        result?: any;
        approval_id?: string;
        execution_time_ms?: number;
        message?: string;
    }> => {
        const response = await api.post('/integrations/execute', {
            instance_id: instanceId,
            action,
            params,
            actor_context: actorContext || {}
        });
        return response.data;
    },

    // ============================================================
    // Audit
    // ============================================================

    getAuditLog: async (params?: {
        instance_id?: string;
        action?: string;
        actor_type?: string;
        risk_level?: string;
        limit?: number;
        offset?: number;
    }): Promise<{ logs: AuditLogEntry[]; total: number; limit: number; offset: number }> => {
        const response = await api.get('/integrations/audit-log', { params });
        return response.data;
    }
};

export default cmpApi;
