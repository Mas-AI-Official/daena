import api from './client';

export interface Council {
    id: string;
    name: string;
    agent_count: number;
    status: string;
}

export const councilsApi = {
    list: async (): Promise<Council[]> => {
        const response = await api.get('/councils');
        return response.data;
    },
    create: async (name: string, description: string = "", member_agent_ids: string[] = []) => {
        const response = await api.post('/councils', { name, description, member_agent_ids });
        return response.data;
    },
    getDetails: async (id: string) => {
        const response = await api.get(`/councils/${id}`);
        return response.data;
    }
};
