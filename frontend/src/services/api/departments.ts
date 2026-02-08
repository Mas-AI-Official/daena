import api from './client';

export interface Department {
    id: string;
    name: string;
    description: string;
    color: string;
    agents_count: number;
    sunflower_index: number;
    cell_id: number;
    coordinates: number[];
    agents?: Agent[];
}

export interface Agent {
    id: string;
    name: string;
    role: string;
    sunflower_index: number;
    cell_id: number;
    department_id?: string;
    department_name?: string;
    status?: 'active' | 'idle' | 'paused' | 'error';
}

export const departmentsApi = {
    getAll: async (includeAgents = false): Promise<{ departments: Department[], total_count: number }> => {
        const response = await api.get('/departments', { params: { include_agents: includeAgents } });
        return response.data;
    },

    getById: async (id: string, includeAgents = true): Promise<{ department: Department }> => {
        const response = await api.get(`/departments/${id}`, { params: { include_agents: includeAgents } });
        return response.data;
    },

    getAgents: async (departmentId: string): Promise<{ agents: Agent[] }> => {
        const response = await api.get(`/departments/${departmentId}/agents`);
        return response.data;
    },

    create: async (data: { name: string, description: string, color: string, sunflower_index?: number, is_hidden?: boolean }) => {
        const response = await api.post('/departments', data);
        return response.data;
    }
};
