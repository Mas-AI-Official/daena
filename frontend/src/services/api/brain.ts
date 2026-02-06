import api from './client';

export interface BrainStatusData {
    connected: boolean;
    provider: string;
    models: ModelInfo[];
    active_model: string | null;
    routing_mode: string;
    gpu_info: any;
    error: string | null;
    // Backwards compat shim
    brain_operational?: boolean;
    ollama_available?: boolean;
    connection_details?: any;
}

export interface ModelInfo {
    name: string;
    size: number;
    family: string;
    parameter_size?: string;
    quantization?: string;
    tier?: string;
    capabilities?: string[];
    is_reasoning?: boolean;
    is_coding?: boolean;
    size_formatted?: string;
}

export interface ModelRegistrationPayload {
    model_id: string;
    provider: 'azure_openai' | 'azure_ai_inference' | 'ollama';
    endpoint_base?: string;
    deployment_name?: string;
    model_name?: string;
    api_version?: string;
    cost_per_1k_input?: number;
    cost_per_1k_output?: number;
    capabilities?: string[];
}

export const brainApi = {
    getStatus: async (): Promise<BrainStatusData> => {
        // Use the richer Brain route that includes Ollama health checks
        const response = await api.get('/api/v1/brain/status');
        return response.data;
    },

    listModels: async (): Promise<{ models: ModelInfo[]; active_model: string }> => {
        // Use the unified registry list for the fleet view
        const response = await api.get('/api/v1/models/registry');
        return {
            models: response.data.registry.models,
            active_model: response.data.primary
        };
    },

    registerModel: async (payload: ModelRegistrationPayload) => {
        const response = await api.post('/api/v1/models/register', payload);
        return response.data;
    },

    getUsage: async (period: 'day' | 'month' = 'day') => {
        const response = await api.get(`/api/v1/models/usage?period=${period}`);
        return response.data;
    },

    pingOllama: async () => {
        // Use the real backend diagnostic tool
        const response = await api.get('/api/v1/brain/ping-ollama');
        return response.data;
    },

    testModel: async (modelId: string) => {
        const response = await api.post(`/api/v1/models/evaluate?model_name=${encodeURIComponent(modelId)}`);
        return response.data;
    },

    setActiveModel: async (modelId: string) => {
        const response = await api.post('/api/v1/models/active', { model_id: modelId });
        return response.data;
    },

    toggleModel: async (modelId: string, enabled: boolean) => {
        const response = await api.post('/api/v1/models/toggle', { model_id: modelId, enabled });
        return response.data;
    }
};

