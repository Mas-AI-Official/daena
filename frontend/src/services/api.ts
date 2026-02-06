
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Interceptor to add auth token if needed
client.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const api = {
    quintessence: {
        deliberate: async (data: { problem: string; domain: string; risk_level: string }) => {
            const response = await client.post('/quintessence/deliberate', data);
            return response.data;
        },
    },
    shadow: {
        getStats: async () => {
            const response = await client.get('/shadow/stats');
            return response.data;
        },
        deployHoneypot: async (data: { target: string }) => {
            const response = await client.post('/shadow/honeypots', data);
            return response.data;
        },
        runRedTeam: async (data: { target: string; attack_vector: string }) => {
            const response = await client.post('/shadow/red-team', data);
            return response.data;
        }
    },
    founder: {
        getControlPanel: async () => {
            const response = await client.get('/founder/control-panel');
            return response.data;
        },
        setBrainMode: async (mode: 'local' | 'hybrid' | 'cloud') => {
            const response = await client.post('/founder/brain/mode', { mode });
            return response.data;
        },
        toggleAutopilot: async (enabled: boolean) => {
            const response = await client.post('/founder/governance/autopilot', { enabled });
            return response.data;
        },
        decideApproval: async (approvalId: string, decision: any) => {
            const response = await client.post(`/founder/approvals/${approvalId}/decide`, decision);
            return response.data;
        }
    },
    dashboard: {
        getSunflowerData: async () => {
            const response = await client.get('/dashboard/sunflower');
            return response.data;
        }
    },
    chat: {
        getHistory: async (params: { limit: number; cursor?: string; search?: string }) => {
            // Updated to correct API prefix
            const response = await client.get('/api/v1/chat/history', { params });
            return response.data;
        },
        getSession: async (sessionId: string) => {
            const response = await client.get(`/api/v1/chat/sessions/${sessionId}`);
            return response.data;
        },
        deleteSession: async (sessionId: string) => {
            const response = await client.delete(`/api/v1/chat/sessions/${sessionId}`);
            return response.data;
        },
        batchDeleteHistory: async (ids: string[]) => {
            const response = await client.delete('/api/v1/chat/history', { data: ids });
            return response.data;
        }
    }
};
