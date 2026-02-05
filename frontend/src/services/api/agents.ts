import api from './client';

export interface Agent {
    id: string;
    name: string;
    role: string;
    type: string;
    department_id: string;
    status: 'active' | 'idle' | 'offline' | 'error';
    is_active: boolean;
    efficiency: string;
    tasks: number;
    uptime: string;
    created_at: string;
}

export const agentsApi = {
    getAll: async (limit = 100, offset = 0, departmentId?: string): Promise<{ agents: Agent[], total_count: number }> => {
        const response = await api.get('/agents', {
            params: { limit, offset, department_id: departmentId }
        });
        return response.data;
    },

    getById: async (id: string): Promise<{ agent: Agent }> => {
        const response = await api.get(`/agents/${id}`);
        return response.data;
    },

    chat: async (id: string, message: string, context?: any): Promise<any> => {
        const response = await api.post(`/agents/${id}/chat`, { message, context });
        return response.data;
    },

    getTasks: async (id: string): Promise<any> => {
        const response = await api.get(`/agents/${id}/tasks`);
        return response.data;
    }
};
